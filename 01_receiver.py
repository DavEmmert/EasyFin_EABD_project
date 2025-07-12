import time
import logging
import json
from datetime import datetime
from kafka import KafkaProducer
from yfinance import WebSocket
import ssl, certifi, os
import websockets.exceptions
import redis
import json
import requests
# Zertifikate korrekt setzen
os.environ['SSL_CERT_FILE'] = certifi.where()
logging.basicConfig(level=logging.INFO)

# Kafka Producer mit IPv4-Adresse
producer = KafkaProducer(
   bootstrap_servers="srv-captain--kafka:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: k.encode("utf-8")
)

# Nachrichten-Handler
from datetime import datetime
import logging
from datetime import datetime, timedelta
# Dictionary zum Speichern von open_price je Aktie und Datum
daily_open_prices = {}
daily_price_extrema = {}  # {(stock, date): {"low": ..., "high": ...}}


def handle_message(msg):
    if "id" in msg and "price" in msg:
        stock = msg["id"]
        price = round(msg["price"], 4)
        now = datetime.now()
        now = datetime.now()
        today = now.date()
        yesterday = today - timedelta(days=1)

        # Nur Einträge löschen, die älter als gestern sind
        keys_to_delete = [k for k in daily_open_prices if k[0] == stock and k[1] < yesterday]
        for k in keys_to_delete:
            logging.info(f"Removing outdated open_price for {stock} from {k[1]}")
            del daily_open_prices[k]
        keys_to_delete = [k for k in daily_price_extrema if k[0] == stock and k[1] < yesterday]
        for k in keys_to_delete:
            logging.info(f"Removing outdated open_price for {stock} from {k[1]}")
            del daily_price_extrema[k]

        # open_price setzen, falls noch nicht vorhanden
        key = (stock, today)
        if "open_price" in msg:
            open_price = round(msg["open_price"], 4)
            daily_open_prices[key] = open_price  # ggf. überschreiben
        else:
            # Wenn kein offener Preis vorhanden und noch nicht gesetzt → selbst setzen
            if key not in daily_open_prices:
                daily_open_prices[key] = price
                logging.info(f"Set open_price for {stock} on {today}: {price}")
            open_price = daily_open_prices[key]

        # Key für tägliche Extremwerte
        extrema_key = (stock, today)
        if not ("day_low" in msg and "day_high" in msg):
            if extrema_key not in daily_price_extrema:
                daily_price_extrema[extrema_key] = {"low": price, "high": price}
            else:
                daily_price_extrema[extrema_key]["low"] = min(daily_price_extrema[extrema_key]["low"], price)
                daily_price_extrema[extrema_key]["high"] = max(daily_price_extrema[extrema_key]["high"], price)

        # day_low & day_high: aus msg, oder selbst berechnet
        day_low = round(msg["day_low"], 4) if "day_low" in msg else round(daily_price_extrema[extrema_key]["low"], 4)
        day_high = round(msg["day_high"], 4) if "day_high" in msg else round(daily_price_extrema[extrema_key]["high"], 4)

        exchange_to_currency = {
            "NMS": "USD",
            "NYQ": "USD",
            "XETRA": "EUR",
            "LSE": "GBP",
            "TSE": "JPY"
        }

        exchange = msg.get("exchange")
        currency = msg.get("currency")

        if not currency:
            currency = exchange_to_currency.get(exchange, "N/A")  # Fallback wenn unbekannt

        currency

        measurement = {
            "timestamp": now.isoformat(),
            "stock": stock,
            "price": price,
            "cur": currency,
            "open_price": open_price,
            "day_low": day_low,
            "day_high": day_high
        }

        logging.info("Received message: %s", measurement)

        try:
            future = producer.send("live_stock_price", key=stock, value=measurement)
            future.get(timeout=10)
            logging.info(f"✅ Nachricht an Kafka gesendet: {measurement}")
        except Exception as e:
            logging.error("Kafka send error: %s", e)



def print_message(msg):
    print(msg)

# WebSocket-Verbindung starten

topics = ["AAPL", "MSFT", "TSLA", "BABA", "SAP",  "AMZN", "TM", "RDSA", "NFLX", "ASML",  "NVO","SHOP"]

    # symbol = s  # z. B. Apple
    # url = f"https://easyfin-api.fdfdf.demo.nilstaglieber.com/stocks/{symbol}"

    # try:
    #     response = requests.get(url, timeout=3)
    #     headers = {
    #     "x-api-token": "supersecrettoken123"
    #     }
    #     response = requests.get(url, headers=headers, timeout=3)    

    #     data = response.json()
    #     print(f"{data}")

    # except requests.exceptions.RequestException as e:
    #     print(f"Error  stock: {e}")
    # topics.append(data.get("symbol") ) #
    # print(topics)


    
# Verbindung zu Redis herstellen
redis_host = os.getenv("REDIS_HOST", "srv-captain--redis")  # fallback für dev
REDIS_PASSWORD="Kurt"
time.sleep(10)
r = redis.Redis(host=redis_host, port=6379, password=REDIS_PASSWORD)

# Liste als JSON-String speichern
r.set("topics_to_listen", json.dumps(topics))

def start_listening():
    ws = WebSocket()
    ws.subscribe(topics)
    ws.listen(handle_message)


while True:
    try:
        print("🔌 Verbinde mit WebSocket...")
        producer.send("live_stock_price", key="TEST", value={"test": "message", "timestamp": datetime.now().isoformat()})
        start_listening()
    except websockets.exceptions.ConnectionClosedOK:
        print("🔁 Verbindung wurde sauber getrennt (1005). Versuche erneut in 3s...")
        time.sleep(3)
    except Exception as e:
        print(f"❌ WebSocket-Fehler: {e}. Neustart in 5s...")
        time.sleep(5)