import time
from datetime import datetime
from quixstreams import Application
import streamlit as st
from collections import deque
import plotly.graph_objects as go

# Nur beim ersten Run initialisieren
if "stock_buffers" not in st.session_state:
    st.session_state.stock_buffers = {}


st.title("Stock Charts")

# Initialisiere Buffer, falls leer
if "selected_stock" not in st.session_state:
    st.session_state.selected_stock = "AAPL" # Default
if "timings" not in st.session_state:
    st.session_state.timings = deque(maxlen=10000)
if "ref" not in st.session_state:
    st.session_state.ref = 1000




# # Selectbox für verfügbare Aktien (initial leer, wird später gefüllt)
# available_stocks = list(st.session_state.stock_buffers.keys())
# if available_stocks:
#     selected = st.selectbox(
#         "Aktie wählen",
#         options=available_stocks,
#         index=available_stocks.index(st.session_state.selected_stock),
#         key="stock_selectbox"
#     )
#     st.session_state.selected_stock = selected


# Init Session State
if "currency_label" not in st.session_state:
    st.session_state.currency_label = "EUR"
if "cur" not in st.session_state:
    st.session_state.cur = "USD"  # fallback
if "eur_rate" not in st.session_state:
    st.session_state.eur_rate = 1.0
if "fig" not in st.session_state:
    st.session_state.fig = go.Figure()

if "label" not in st.session_state:
    st.session_state.label = st.session_state.selected_stock
if "value" not in st.session_state:
    st.session_state.value = "Sekunde bitte"
if "price_delta" not in st.session_state:
    st.session_state.price_delta = 0
if "blinker" not in st.session_state:
    st.session_state.blinker = ""
        

# Umschalt-Callback
def toggle_currency():
    if st.session_state.currency_label == "EUR":
        st.session_state.currency_label = st.session_state.cur
    else:
        st.session_state.currency_label = "EUR"


@st.cache_resource
def kafka_connection():
    return Application(
        broker_address="localhost:9092",
        consumer_group="dashboard",
        auto_offset_reset="latest",
    )

def set_to_apple(): 
    st.session_state.selected_stock = "AAPL"



from streamlit_autorefresh import st_autorefresh

# Alle 2000ms neu laden (nur UI, nicht Kafka!)
st_autorefresh(interval=10000, key="auto_refresh")

start = time.perf_counter()





# Kafka initialisieren
if "consumer" not in st.session_state:
    app = kafka_connection()
    price = app.topic("live_stock_1_sec")
    consumer = app.get_consumer()
    consumer.subscribe(["live_stock_1_sec"])
    st.session_state.consumer = consumer
    st.session_state.topic = price
else:
    consumer = st.session_state.consumer
    price = st.session_state.topic
# Alle Nachrichten seit letztem Refresh verarbeiten
has_new_data = False
for _ in range(50):  # Maximal 50 Nachrichten pro Tick verarbeiten
    msg = consumer.poll(timeout=0)
    print(msg)
    if msg is None:
        break
    if msg.topic() != price.name:
        continue

    has_new_data = True  # Flag setzen

    # Ab hier wie gehabt:
    price_msg = price.deserialize(msg)
    price_val = price_msg.value.get('price')
    open_price = price_msg.value.get('open_price')
    cur_symb = price_msg.value.get("cur_symb")
    day_low = price_msg.value.get("day_low")
    day_high = price_msg.value.get("day_high")
    cur = price_msg.value.get("cur")
    eur_rate = price_msg.value.get("eur_rate")
    timestamp_str = str(price_msg.value.get("processing_timestamp"))
    stock_id = str(price_msg.value.get('stock'))
    
    st.session_state.cur = cur
    st.session_state.eur_rate = eur_rate

    timestamp = datetime.fromisoformat(price_msg.value.get('timestamp'))

    if stock_id not in st.session_state.stock_buffers:
        st.session_state.stock_buffers[stock_id] = {
            "price": deque(maxlen=86400),
            "timestamp": deque(maxlen=86400),
            "day_low": deque(maxlen=86400),
            "day_high": deque(maxlen=86400),
            "open_price": deque(maxlen=1),
        }

    buffers = st.session_state.stock_buffers[stock_id]
    buffers["price"].append(price_val)
    buffers["timestamp"].append(timestamp_str)
    buffers["day_low"].append(day_low)
    buffers["day_high"].append(day_high)
    buffers["open_price"].append(open_price)

    if stock_id == st.session_state.selected_stock:
        price_delta = round((price_val - open_price) / open_price * 100, 2)
        st.session_state.label = stock_id
        if st.session_state.currency_label == "EUR":
            price_out = price_val
            cur_out = cur_symb
        else:
            price_out = round(price_val * eur_rate, 2)
            cur_out = "€"
        st.session_state.value = f"{price_out:,.2f} {cur_out}"
        st.session_state.price_delta = f"{price_delta:+.2f}"

        # Blinker-Logik
        if len(buffers["price"]) > 1 and buffers["price"][-1] != buffers["price"][-2]:
            if buffers["price"][-1] < buffers["open_price"][0]:
                st.session_state.blinker = "🔴"
            else:
                st.session_state.blinker = "🟢"
        else:
            st.session_state.blinker = ""

        # Chart aktualisieren
        selected_buffers = buffers
        if st.session_state.currency_label == "EUR":
            y_out = list(selected_buffers["price"])
            x_out = list(selected_buffers["timestamp"])
            min_day_low = min(selected_buffers["day_low"])
            max_day_high = max(selected_buffers["day_high"])
            min_price = min_day_low - (min_day_low * 0.01)
            max_price = max_day_high + (max_day_high * 0.01)
            open_price_out = open_price
        else:
            y_out = [p * eur_rate for p in selected_buffers["price"]]
            x_out = list(selected_buffers["timestamp"])
            min_day_low = min(selected_buffers["day_low"]) * eur_rate
            max_day_high = max(selected_buffers["day_high"]) * eur_rate
            min_price = min_day_low - (min_day_low * 0.05)
            max_price = max_day_high + (max_day_high * 0.05)
            open_price_out = open_price * eur_rate

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x_out,
            y=y_out,
            mode='lines',
            line=dict(color="#00C853" if st.session_state.blinker == "🟢" else "#D50000", width=2),
            name='Price'
        ))
        fig.update_layout(
            title='last 24h',
            xaxis_title='Time',
            yaxis_title='Price',
            yaxis=dict(range=[min_price, max_price]),
            template='plotly_dark',
            shapes=[
                dict(
                    type="line",
                    x0=min(x_out),
                    x1=max(x_out),
                    y0=open_price_out,
                    y1=open_price_out,
                    line=dict(color="gray", width=2, dash="dash"),
                )
            ]
        )
        st.session_state.fig = fig

print(st.session_state.label)
# Button außerhalb der Schleife
st.button(
    label=st.session_state.currency_label,
    key="currency_toggle_button",
    on_click=toggle_currency
)

st.button(
    label= "APPL",
    key="AAPL",
    on_click=set_to_apple
)


metric_placeholder = st.empty()
blinker_placeholder = st.empty()
chart_placeholder = st.empty()


metric_placeholder.metric(label=st.session_state.label,
                            value=st.session_state.value,
                            delta=st.session_state.price_delta)
blinker_placeholder.markdown(st.session_state.blinker)
chart_placeholder.plotly_chart(st.session_state.fig, key=f"plot")

end = time.perf_counter()
elapsed = end - start

# 3. Zeit hinzufügen
st.session_state.timings.append(elapsed)
import numpy as np
st.session_state.ref = np.quantile(st.session_state.timings,.95)

            

        
            

