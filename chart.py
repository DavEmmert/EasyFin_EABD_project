import time
from threading import Thread, Lock
from collections import deque, defaultdict
import copy
import streamlit as st
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from quixstreams import Application

# ---------- Thread-sicherer Lock ----------
buffer_lock = Lock()

# ---------- SessionState Init ----------
if "global_buffers" not in st.session_state:
    st.session_state.global_buffers = defaultdict(lambda: {
        "price": deque(maxlen=86400),
        "timestamp": deque(maxlen=86400),
        "day_low": deque(maxlen=86400),
        "day_high": deque(maxlen=86400),
        "open_price": None,
        "eur_rate": None,
        "cur_symb": None,
        "cur": None
    })

if "stock_buffers" not in st.session_state:
    st.session_state.stock_buffers = {}

# ---------- Kafka Setup ----------
app = Application(
    broker_address="localhost:9092",
    consumer_group="dashboard",
    auto_offset_reset="latest",
)
price_topic = app.topic("live_stock_1_sec", value_deserializer="json")

# ---------- Kafka Consumer Thread ----------
def consume_messages():
    consumer = app.get_consumer()
    consumer.subscribe(["live_stock_1_sec"])
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg and msg.topic() == price_topic.name:
            price_msg = price_topic.deserialize(msg)
            stock_id = price_msg.value.get("stock")
            if not stock_id:
                continue

            with buffer_lock:
                buf = st.session_state.global_buffers[stock_id]
                buf["price"].append(price_msg.value.get("price"))
                buf["timestamp"].append(price_msg.value.get("processing_timestamp"))
                buf["day_low"].append(price_msg.value.get("day_low"))
                buf["day_high"].append(price_msg.value.get("day_high"))
                buf["open_price"] = price_msg.value.get("open_price")
                buf["eur_rate"] = price_msg.value.get("eur_rate")
                buf["cur_symb"] = price_msg.value.get("cur_symb")
                buf["cur"] = price_msg.value.get("cur")
        time.sleep(0.1)

# ---------- Thread starten ----------
if "consumer_started" not in st.session_state:
    Thread(target=consume_messages, daemon=True).start()
    st.session_state.consumer_started = True

# ---------- UI Autorefresh ----------
st_autorefresh(interval=1000, limit=None, key="auto_refresh")

# ---------- Buffer Synchronisation ----------
with buffer_lock:
    for stock_id, buf in st.session_state.global_buffers.items():
        if stock_id not in st.session_state.stock_buffers:
            st.session_state.stock_buffers[stock_id] = copy.deepcopy(buf)
        else:
            for k in buf:
                if isinstance(buf[k], deque):
                    st.session_state.stock_buffers[stock_id][k] = deque(buf[k], maxlen=86400)
                else:
                    st.session_state.stock_buffers[stock_id][k] = buf[k]

# ---------- UI Start ----------
st.title("Stock Charts")

# ---------- UI Session Init ----------
if "selected_stock" not in st.session_state:
    st.session_state.selected_stock = "AAPL"
if "currency_label" not in st.session_state:
    st.session_state.currency_label = "EUR"

# ---------- Currency Umschalter ----------
def toggle_currency():
    st.session_state.currency_label = "USD" if st.session_state.currency_label == "EUR" else "EUR"

st.button(
    label=st.session_state.currency_label,
    key="currency_toggle_button",
    on_click=toggle_currency
)

# ---------- Stock Auswahl ----------
available_stocks = list(st.session_state.stock_buffers.keys())
if available_stocks:
    st.session_state.selected_stock = st.selectbox(
        "Aktie wählen",
        options=available_stocks,
        index=available_stocks.index(st.session_state.selected_stock)
        if st.session_state.selected_stock in available_stocks else 0,
        key="stock_selectbox"
    )

    selected = st.session_state.selected_stock
    selected_buf = st.session_state.stock_buffers.get(selected)

    if selected_buf and selected_buf["price"]:
        price_val = selected_buf["price"][-1]
        open_price = selected_buf["open_price"] or 1
        price_delta = round((price_val - open_price) / open_price * 100, 2)
        eur_rate = selected_buf["eur_rate"] or 1.0
        cur_symb = selected_buf["cur_symb"] or "$"

        if st.session_state.currency_label == "EUR":
            price_out = price_val
            cur_out = cur_symb
        else:
            price_out = round(price_val * eur_rate, 2)
            cur_out = "€"

        st.metric(
            label=selected,
            value=f"{price_out:,.2f} {cur_out}",
            delta=f"{price_delta:+.2f} %"
        )

        blink_placeholder = st.empty()
        if price_val < open_price:
            blink_placeholder.markdown("🔴")
            col = "#D50000"
        else:
            blink_placeholder.markdown("🟢")
            col = "#00C853"

        x_out = list(selected_buf["timestamp"])
        if st.session_state.currency_label == "EUR":
            y_out = list(selected_buf["price"])
            min_price = min(selected_buf["day_low"]) * 0.99
            max_price = max(selected_buf["day_high"]) * 1.01
            open_out = open_price
        else:
            y_out = [p * eur_rate for p in selected_buf["price"]]
            min_price = min(selected_buf["day_low"]) * eur_rate * 0.95
            max_price = max(selected_buf["day_high"]) * eur_rate * 1.05
            open_out = open_price * eur_rate

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_out, y=y_out, mode='lines', line=dict(color=col, width=2)))
        fig.update_layout(
            title='last 24h',
            xaxis_title='Time',
            yaxis_title='Price',
            yaxis=dict(range=[min_price, max_price]),
            template='plotly_dark',
            shapes=[
                dict(
                    type="line",
                    x0=min(x_out), x1=max(x_out),
                    y0=open_out, y1=open_out,
                    line=dict(color="gray", width=2, dash="dash")
                )
            ]
        )
        st.plotly_chart(fig, key=f"chart_{selected}")
else:
    st.info("Warte auf erste Aktien-Daten...")
