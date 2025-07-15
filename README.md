
# 📈 EasyFin Live Stock Monitor

A real-time stock monitoring and dashboard system built with Kafka, Redis, Streamlit, and custom microservices.

---

## 📦 Project Overview

This project consists of four main services:

1. **`01_receiver.py`**  
   - Connects to a WebSocket for selected stock tickers.
   - Processes incoming messages to extract price data and enriches it with daily stats.
   - Publishes the data to a Kafka topic `live_stock_price`.

2. **`02_exchange_and_clock.py`**  
   - Consumes from `live_stock_price`.
   - Converts all stock prices into EUR using real-time exchange rates.
   - Enriches messages with metadata (e.g., currency symbol).
   - Publishes stock-specific messages to individual Kafka topics.

3. **`03_buffer_to_redis.py`**  
   - Buffers price data and stores it in Redis.
   - Fetches additional stock metadata and Q&A info from an external API.
   - Maintains daily open, high, and low values.

4. **`04_dashboard.py`**  
   - Web-based dashboard built with Streamlit.
   - Visualizes stock price trends, stats, and outliers.
   - Displays questions & answers per stock from external sources.

---

## 🚀 Getting Started

### Prerequisites

- Docker & Docker Compose
- Access to a Kafka broker and Redis instance (already configured in `docker-compose.yml`)

---

## ⚙️ Installation

1. **Clone the repository**

```bash
git clone https://your-repo-url
cd easyfin-stock-dashboard
```

2. **Configure environment (optional)**  
   Check `docker-compose.yml` for Kafka, Redis, and service settings.

3. **Start services**

```bash
docker-compose up --build
```

---

## 📊 Dashboard Access

Once running, access the Streamlit dashboard at:

```
http://localhost:8501
```

You can:

- View current prices and deltas.
- Toggle between native currency and EUR.
- Explore metadata and Q&A.
- Use filters for sector, industry, and country.

---

## 🧪 API Dependencies

- WebSocket Stock Feed (via `yfinance.WebSocket`)
- Metadata & Q&A API:
  - `https://easyfin-api.fdfdf.demo.nilstaglieber.com/stocks/{symbol}`
  - `https://easyfin-api.fdfdf.demo.nilstaglieber.com/answers/{symbol}`

Authorization token: `supersecrettoken123`  
(Replace with a secure token for production.)

---

## 🛠️ Kafka Topics Used

- `live_stock_price`: Raw price updates
- `{symbol}`: Stock-specific processed data streams

---

## 🔐 Environment Variables

Set in Docker:

- `REDIS_HOST`: Defaults to `srv-captain--redis`
- `REDIS_PASSWORD`: Currently set to `Kurt` (consider securing this)

---

## 📁 File Summary

| File | Role |
|------|------|
| `01_receiver.py` | Data collector & Kafka producer |
| `02_exchange_and_clock.py` | Enricher & broadcaster |
| `03_buffer_to_redis.py` | Redis buffer and metadata/Q&A fetcher |
| `04_dashboard.py` | Streamlit UI |

---

## 🧼 Notes

- Logs are printed to console.
- Daily and hourly metadata fetching is optimized with Redis caching.
- Currency conversion rates are cached (USD: daily, others: weekly).

---

## 🧩 To Do

- Add authentication to the dashboard.
- Implement unit tests.
- Improve WebSocket reconnection handling.
- Secure API token and Redis credentials.
