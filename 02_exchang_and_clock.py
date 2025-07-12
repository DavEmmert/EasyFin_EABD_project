import logging
import time
import json
from quixstreams import Application
from threading import Thread, Event
from kafka import KafkaProducer
from datetime import datetime
import requests
from datetime import datetime, timedelta

currency_symbols = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥", "CHF": "CHF",
    "CAD": "C$", "AUD": "A$", "NZD": "NZ$", "SEK": "kr", "NOK": "kr", "DKK": "kr",
    "INR": "₹", "RUB": "₽", "BRL": "R$", "ZAR": "R", "SGD": "S$", "HKD": "HK$",
    "KRW": "₩", "TRY": "₺", "MXN": "MX$", "PLN": "zł", "CZK": "Kč", "HUF": "Ft",
    "ILS": "₪", "AED": "د.إ", "SAR": "﷼", "THB": "฿", "IDR": "Rp", "MYR": "RM", "PHP": "₱"
}



# Globaler Cache
exchange_rate_cache = {}
exchange_rate_cache_timestamp = {}
latest_values = {}  # stock → message


from datetime import datetime, timedelta

# Globaler Cache
exchange_rate_cache = {}
exchange_rate_cache_timestamp = {}

def get_exchange_rate_to_eur(currency_code):
    global exchange_rate_cache, exchange_rate_cache_timestamp

    now = datetime.now()

    if currency_code == "EUR":
        return 1.0

    # Cache-Strategie
    is_usd = currency_code == "USD"
    cache_duration = timedelta(days=1) if is_usd else timedelta(days=7)

    # Prüfung auf gültigen Cache
    cached_rate = exchange_rate_cache.get(currency_code)
    cached_time = exchange_rate_cache_timestamp.get(currency_code)

    if cached_rate is not None and cached_time is not None:
        if now - cached_time < cache_duration:
            return cached_rate

    # Abruf via Frankfurter API
    try:
        response = requests.get(
            f"https://api.frankfurter.app/latest?from={currency_code}&to=EUR",
            timeout=3
        )
        if response.status_code == 200:
            data = response.json()
            rate = data["rates"]["EUR"]

            # Cache aktualisieren
            exchange_rate_cache[currency_code] = rate
            exchange_rate_cache_timestamp[currency_code] = now

            logging.info(f"Fetched new rate for {currency_code} → EUR: {rate}")
            return rate
        #else:
            #logging.warning(f"Frankfurter API returned {response.status_code} for {currency_code}")
    except Exception as e:
        logging.error(f"Error fetching exchange rate for {currency_code}: {e}")

    return None


latest_value = None
stop_event = Event()

producer_2 = KafkaProducer(
    bootstrap_servers="srv-captain--kafka:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: k.encode("utf-8")
)

def throttled_publisher(mode="latest", interval=5):
    while not stop_event.is_set():
        time.sleep(interval)

        for stock, data in list(latest_values.items()):
            if mode == "latest" and not data.get("updated"):
                continue  # Nur senden, wenn aktualisiert

            val = data["value"]
            val["processing_timestamp"] = datetime.now().isoformat()

            try:
                logging.info("SENDING %s: %s", stock, val)
                future = producer_2.send(
                    f"{stock}",
                    key=stock,
                    value=val
                )
                future.get(timeout=10)
                if mode == "latest":
                    latest_values[stock]["updated"] = False  # Flag nur im "latest"-Modus zurücksetzen
            except Exception as e:
                logging.error("Kafka send error (%s): %s", stock, e)



def main():
    logging.info("START...")

    app = Application(
        broker_address="srv-captain--kafka:9092",
        consumer_group="alert",
        auto_offset_reset="latest",
    )

    input_topic = app.topic("live_stock_price", value_deserializer="json")
    sdf = app.dataframe(input_topic)

    def process(value):
        stock = value.get("stock")
        if not stock:
            return

        # Currency bearbeiten
        currency_code = value.get("cur", None)
        symbol = currency_symbols.get(currency_code, "")
        rate = get_exchange_rate_to_eur(currency_code)
        price = value.get("price")

        if value.get("price") is not None and rate is not None:
            value["eur_rate"] = rate
        else:
            value["price_eur"] = None

        value["cur_symb"] = symbol
        value["pirce"] = price

        # Speichern der aktualisierten Version für spätere Sendung
        latest_values[stock] = {"value": value, "updated": True}

        

    sdf = sdf.apply(process)

    # Starte Sende-Thread
    publisher_thread = Thread(target=throttled_publisher, kwargs={"mode": "latest", "interval": 1})
    publisher_thread.start()

    try:
        app.run(sdf)
    finally:
       # stop_event.set()
        publisher_thread.join()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
