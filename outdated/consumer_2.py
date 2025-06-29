import logging
from quixstreams import Application

def main():
    logging.info("START...")
    app = Application(
        broker_address="localhost:9092",
        consumer_group="check",
        auto_offset_reset="latest",
    )
    input_topic = app.topic("AAPL_live", value_deserializer="json")

    sdf = app.dataframe(input_topic)
    sdf = sdf.print()
    app.run(sdf)

if __name__ == "__main__":
    logging.basicConfig(level="DEBUG")
    main()