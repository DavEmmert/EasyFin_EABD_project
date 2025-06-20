import logging
from quixstreams import Application

def main():
    logging.info("START...")
    app = Application(
        broker_address="127.0.0.1:9092",
        consumer_group="chart",
        auto_offset_reset="latest",
    )
    input_topic = app.topic("live_stock_price", value_deserializer="json")
    sdf = app.dataframe(input_topic).print()
    app.run(sdf)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
