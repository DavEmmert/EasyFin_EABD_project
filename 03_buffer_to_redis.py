import logging
from collections import defaultdict, deque
from quixstreams import Application
from threading import Event
from datetime import datetime
import requests

import redis
import json
import os
redis_host = os.getenv("REDIS_HOST", "srv-captain--redis")  
REDIS_PASSWORD="Kurt"

r = redis.Redis(host=redis_host, port=6379, password=REDIS_PASSWORD)

def buffer_to_redis(topic, data):
    topic_name = topic.name if hasattr(topic, "name") else str(topic)
    key = f"buffer:{topic_name}"
    r.rpush(key, json.dumps(data))
    r.ltrim(key, -17280, -1)

def open_min_max_to_redis(topic, data):
    topic_name = topic.name if hasattr(topic, "name") else str(topic)
    key = f"settings:{topic_name}"
    r.rpush(key, json.dumps(data))
    r.ltrim(key, -1, -1)

def update_daily_stock_data(symbol):
    today = datetime.now().date().isoformat()
    marker_key = f"daily:{symbol}:fetched_on"

    # Prüfen, ob bereits für heute abgerufen
    last_fetched = r.get(marker_key)
    if last_fetched == today:
        return  # ✅ Heute schon aktualisiert → überspringen

    url = f"https://easyfin-api.fdfdf.demo.nilstaglieber.com/stocks/{symbol}"
    headers = {
        "x-api-token": "supersecrettoken123"
    }

    try:
        response = requests.get(url, headers=headers, timeout=3)
        response.raise_for_status()
        data = response.json()

        # Tagesdaten speichern
        data_key = f"metadata:{symbol}"
        r.set(data_key, json.dumps(data))
        r.expire(data_key, 12*60*24*5)  # optional: 24h Gültigkeit

        # Marker speichern
        r.set(marker_key, today)
        r.expire(marker_key, 12*60*24*5))

        logging.info("✅ Updated daily stock info for %s: %s", symbol, data)
    except Exception as e:
        logging.warning("⚠️ Couldn't update daily data for %s: %s", symbol, e)


def update_q_and_a(symbol):
    current_hour = datetime.now().strftime("%Y-%m-%d-%H")
    marker_key = f"hourly:{symbol}:fetched_at"

    # Prüfen, ob bereits für diese Stunde abgerufen
    last_fetched = r.get(marker_key)
    if last_fetched == current_hour:
        return  # ✅ Diese Stunde schon aktualisiert → überspringen
    

    url = f"https://easyfin-api.fdfdf.demo.nilstaglieber.com/answers/{symbol}"
    headers = {
        "x-api-token": "supersecrettoken123"
    }

    try:
        response = requests.get(url, headers=headers, timeout=3)
        response.raise_for_status()
        data = response.json()
        print(data)
        # Tagesdaten speichern
        data_key = f"q_and_a:{symbol}"

        result = {}
        for item in data:
            q_id = item["question_id"]
            result[f"q{q_id}"] = item["question_text"]
            result[f"a{q_id}"] = item["answer_text"]

        # Optional: als JSON-String speichern
        result = json.dumps(result, indent=2)

        r.set(data_key, result)
        r.expire(data_key, 12*60*24*5)  # optional: 24h Gültigkeit

        # Marker speichern
        r.set(marker_key, current_hour)
        r.expire(marker_key,12*60*24*5)

        logging.info("❓🚬 Updated q_and_a info for %s: %s", symbol, result)
    except Exception as e:
        logging.warning("⚠️ Couldn't update daily data for %s: %s", symbol, e)



def main():
    raw = r.get("topics_to_listen")
    if raw:
        topics_to_listen = json.loads(raw)
    else:
        # Fallback: Default-Liste setzen und verwenden
        topics_to_listen = ["AAPL"]
        r.set("topics_to_listen", json.dumps(topics_to_listen))
    logging.info("Consumer START...")

    app = Application(
        broker_address="srv-captain--kafka:9092",
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
                eur_rate = msg.get("eur_rate")

                if price is not None and stock:
                    datapoint = {"stock": stock, "price": price, "timestamp": ts, "cur": cur, "eur_rate": eur_rate}
                    buffer_to_redis(stock, datapoint)
                    # Tagesdaten aktualisieren
                    update_daily_stock_data(stock)
                    update_q_and_a(stock)

                    logging.info("Buffered [%s] → %s", label, datapoint)
                    datapoint = {"open": open, "min": min, "max": max}
                    open_min_max_to_redis(f'{stock}_settings', datapoint)
                    logging.info("updated settings[%s] → %s", label, datapoint)
            return process

        sdf = sdf.apply(make_processor(topic_name))  
        dataframes.append(sdf)

    try:
        app.run(dataframes)
    except KeyboardInterrupt:
        stop_event.set()
        logging.info("Consumer stopped.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
