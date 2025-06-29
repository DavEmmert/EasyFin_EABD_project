import logging
from collections import defaultdict, deque
from quixstreams import Application
from threading import Event
from datetime import datetime

import redis
import json

r = redis.Redis(host="redis", port=6379, decode_responses=True)

# Versuche, gespeicherte Topics zu laden
raw = r.get("topics_to_listen")

if raw:
    topics_to_listen = json.loads(raw)
else:
    # Fallback: Default-Liste setzen und verwenden
    topics_to_listen = ["AAPL"]
    r.set("topics_to_listen", json.dumps(topics_to_listen))


def buffer_to_redis(topic, data):
    topic_name = topic.name if hasattr(topic, "name") else str(topic)
    key = f"buffer:{topic_name}"
    r.rpush(key, json.dumps(data))
    r.ltrim(key, -86400*30, -1)

def open_min_max_to_redis(topic, data):
    topic_name = topic.name if hasattr(topic, "name") else str(topic)
    key = f"settings:{topic_name}"
    r.rpush(key, json.dumps(data))
    r.ltrim(key, -1, -1)

def main():
    logging.info("Consumer START...")

    app = Application(
        broker_address="kafka:9092",
        consumer_group="price_buffer",
        auto_offset_reset="latest",
        consumer_extra_config={
        "session.timeout.ms": 150000,          # Zeit bis Kafka den Consumer als "tot" erklärt (Default: 10000)
        "max.poll.interval.ms": 300000,       # Zeit die der Consumer maximal pro Nachricht blockieren darf (Default: 300000)
        "heartbeat.interval.ms": 15000        # Zeitabstand zwischen Heartbeats (Default: 3000)
    }
    )

    dataframes = []

    for topic_name in topics_to_listen:
        topic = app.topic(topic_name, value_deserializer="json")
        sdf = app.dataframe(topic)
        logging.info("Listening to topic: %s", topic_name)


        def make_processor(label):
            def process(msg):
                stock = msg.get("stock")
                price = msg.get("price")
                ts = msg.get("processing_timestamp") or datetime.now().isoformat()
                open = msg.get("open_price")
                min = msg.get("day_low")
                max = msg.get("day_high")
                cur = msg.get("cur")

                if price is not None and stock:
                    datapoint = {"stock": stock, "price": price, "timestamp": ts, "cur": cur}
                    buffer_to_redis(stock, datapoint)
                    logging.info("Buffered [%s] → %s", label, datapoint)
                    datapoint = {"open": open, "min": min, "max": max}
                    open_min_max_to_redis(f'{stock}_settings', datapoint)
                    logging.info("updated settings[%s] → %s", label, datapoint)
            return process

        sdf = sdf.apply(make_processor(topic_name))  # 👈 KEIN with_context()
        dataframes.append(sdf)

    try:
        app.run(dataframes)
    except KeyboardInterrupt:
        stop_event.set()
        logging.info("Consumer stopped.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
