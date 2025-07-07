import streamlit as st
from collections import deque
from datetime import datetime
import redis
import json
import plotly.graph_objects as go
import time
from datetime import datetime
from zoneinfo import ZoneInfo


st.set_page_config(page_title="Live Price Viewer", layout="centered")

# --- Init session state ---
defaults = {
    "currency_label": "EUR",
    "label":"",
    "cur": "USD",
    "eur_rate": 1.0,
    "value": 0,
    "price_delta": 0,
    "blinker": "",
    "max_running_time": 0,
    "refresh_time": 5,
    "last_update": time.time(),
    "max_delta":0.01,
    "last_value":0,
    "update": True,
    "live":0
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

if "fig" not in st.session_state:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
    x=[],
    y=[],
    mode='lines',
    line=dict(color="#00C853", width=2),
        name='Price'))
    st.session_state.fig = fig
else:
    fig = st.session_state.fig

# --- Redis connection ---
r = redis.Redis(host="redis", port=6379, decode_responses=True)

def get_buffer_from_redis(stock: str, max_items: int = 60*60*24):
    key = f"buffer:{stock}"
    raw_entries = r.lrange(key, -max_items, -1)
    return deque(json.loads(item) for item in raw_entries)

def get_settings_from_redis(stock: str, max_items: int = 2):
    key = f"settings:{stock}_settings"
    raw_entries = r.lrange(key, -max_items, -1)
    return deque(json.loads(item) for item in raw_entries)

def toggle_currency():
    if st.session_state.currency_label == "EUR":
        st.session_state.currency_label = st.session_state.cur
    else:
        st.session_state.currency_label = "EUR"

# --- UI Setup ---
r = redis.Redis(host="redis", port=6379, decode_responses=True)

# Versuche, gespeicherte Topics zu laden
raw = r.get("topics_to_listen")

if raw:
    topics_to_listen = json.loads(raw)
else:
    # Fallback: Default-Liste setzen und verwenden
    topics_to_listen = ["AAPL"]
    r.set("topics_to_listen", json.dumps(topics_to_listen))

print("Aktive Topics:", topics_to_listen)
cleaned_topics = [topic.replace("_live", "") for topic in topics_to_listen]
st.session_state.selected_topic = st.selectbox("Wähle ein Topic:", cleaned_topics)

col1, col2 = st.columns([10,2])


# st.title("📈 Live Stock Price Monitor")
# st.button(label=st.session_state.currency_label, key="currency_toggle_button", on_click=toggle_currency)

with col2: 
    blinker_placeholder = st.empty()

# --- Daten aktualisieren alle 5 Sekunden ---
#while True:
st.session_state["last_update"] = time.time()

buffer = get_buffer_from_redis(st.session_state.selected_topic )
settings = get_settings_from_redis(st.session_state.selected_topic )



if buffer and settings:
    last_entry = buffer[-1]
    setting = settings[-1]

    st.session_state.value = last_entry['price']
    st.session_state.cur = last_entry['cur']
    if st.session_state.value != st.session_state.last_value:
        st.session_state.label = st.session_state.selected_topic 
        st.session_state.price_delta = ((st.session_state.value - setting["open"]) / setting["open"])*100
        st.session_state.min = setting["min"]
        st.session_state.max = setting["max"]
        st.session_state.open = setting["open"]
        st.session_state.blinker = "🔴" if st.session_state.value < st.session_state.last_value else "🟢"
        st.session_state.max_delta = max(st.session_state.price_delta *0.02, abs(st.session_state.max_delta))
        prices = [entry["price"] for entry in buffer]
        timestamps = [datetime.fromisoformat(entry["timestamp"]).astimezone(ZoneInfo("Europe/Berlin")) for entry in buffer]

        print(st.session_state.price_delta)

        if len(fig.data) == 0:
            fig.add_trace(go.Scatter(
                x=timestamps,
                y=prices,
                mode='lines',
                line=dict(color="#D50000" if st.session_state.price_delta < 0 else "#00C853"  , width=2),
                name='Price'
            ))
        else:
            trace = fig.data[0]  # Zugriff auf erste Trace
            trace.x = timestamps
            trace.y = prices
            trace.line.color = "#D50000" if st.session_state.price_delta < 0 else "#00C853"


        fig.update_layout(
            title='last 24h',
            xaxis_title='Time',
            yaxis_title='Price',
            yaxis=dict(range=[
                st.session_state.min - st.session_state.min * st.session_state.max_delta,
                st.session_state.max + st.session_state.max * st.session_state.max_delta
            ]),
            template='plotly_dark',
            shapes=[
                dict(
                    type="line",
                    x0=min(timestamps),
                    x1=max(timestamps),
                    y0=st.session_state.open,
                    y1=st.session_state.open,
                    line=dict(color="gray", width=2, dash="dash"),
                )
            ]
        )
        st.session_state.fig = fig
       
       
       
        blinker_placeholder.markdown(st.session_state.blinker)
        time.sleep(1)
        st.session_state.blinker = ""
        blinker_placeholder.markdown(st.session_state.blinker)
        st.session_state.last_value = st.session_state.value

        #st_autorefresh(interval=1000, key="data_refresh")  # s

        # --- Anzeige ---
    with col1:
        st.metric(label=st.session_state.label,
                                value = f"{float(st.session_state.value):,.2f} {st.session_state.cur}",
                                delta=f"{st.session_state.price_delta:+.2f} %")
        
    st.plotly_chart(st.session_state.fig, use_container_width=True)

st.session_state.live = st.session_state.live+1
if st.session_state.live == 2:
    blinker_placeholder.markdown("live")
    st.session_state.live = 0

time.sleep(0.5)
blinker_placeholder.markdown("")


time.sleep(0.5)
st.rerun()

