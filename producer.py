import time
import logging
import json
from datetime import datetime
from kafka import KafkaProducer
from yfinance import WebSocket
import ssl, certifi, os

os.environ['SSL_CERT_FILE'] = certifi.where()
logging.basicConfig(level=logging.INFO)

producer = KafkaProducer(
    bootstrap_servers="127.0.0.1:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: k.encode("utf-8")
)

def handle_message(msg):
    if "id" in msg and "price" in msg:
        measurement = {
            "timestamp": datetime.now().isoformat(),
            "stock": msg["id"],
            "price": round(msg["price"], 4)
        }
        producer.send("live_stock_price", key=measurement["stock"], value=measurement)

ws = WebSocket(verbose=True)
ws.subscribe(["AAPL"])
ws.listen(handle_message)
