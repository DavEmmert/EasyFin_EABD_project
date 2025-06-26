import streamlit as st
from collections import deque
from datetime import datetime
import redis
import json
import plotly.graph_objects as go
import time
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Live Price Viewer", layout="centered")

# --- Init session state ---
defaults = {
    "currency_label": "EUR",
    "label":"",
    "cur": "USD",
    "eur_rate": 1.0,
    "fig": go.Figure(),
    "value": "Sekunde bitte",
    "price_delta": 0,
    "blinker": "",
    "max_running_time": 0,
    "refresh_time": 5,
    "last_update": time.time()
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- Redis connection ---
r = redis.Redis(decode_responses=True)

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
from test_2 import topics_to_listen  # Achtung: doppelt?
cleaned_topics = [topic.replace("_live", "") for topic in topics_to_listen]
selected_topic = st.selectbox("Wähle ein Topic:", cleaned_topics)
st.session_state.selected_topic = selected_topic

# st.title("📈 Live Stock Price Monitor")
# st.button(label=st.session_state.currency_label, key="currency_toggle_button", on_click=toggle_currency)

metric_placeholder = st.empty()
blinker_placeholder = st.empty()
chart_placeholder = st.empty()

# --- Daten aktualisieren alle 5 Sekunden ---
if True:
    st.session_state["last_update"] = time.time()

    buffer = get_buffer_from_redis(selected_topic)
    settings = get_settings_from_redis(selected_topic)

    if buffer and settings:
        last_entry = buffer[-1]
        setting = settings[-1]

        st.session_state.value = last_entry['price']
        st.session_state.cur = last_entry['cur']
        st.session_state.label = selected_topic
        st.session_state.price_delta = (last_entry['price'] - setting["open"]) / setting["open"]
        st.session_state.min = setting["min"]
        st.session_state.max = setting["max"]
        st.session_state.open = setting["open"]
        st.session_state.blinker = "🔴" if st.session_state.price_delta < 0 else "🟢"

        prices = [entry["price"] for entry in buffer]
        timestamps = [entry["timestamp"] for entry in buffer]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=prices,
            mode='lines',
            line=dict(color="#D50000" if st.session_state.price_delta < 0 else "#00C853"  , width=2),
            name='Price'
        ))
        fig.update_layout(
            title='last 24h',
            xaxis_title='Time',
            yaxis_title='Price',
            yaxis=dict(range=[
                st.session_state.min - st.session_state.min * 0.05,
                st.session_state.max + st.session_state.max * 0.05
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
        st.markdown("""
                <script>
                    const scrollPos = sessionStorage.getItem("scrollTop");
                    if (scrollPos) window.scrollTo(0, scrollPos);
                    window.addEventListener("beforeunload", () => {
                        sessionStorage.setItem("scrollTop", window.scrollY);
                    });
                </script>
            """, unsafe_allow_html=True)

        st_autorefresh(interval=1000, key="data_refresh")  # s

# --- Anzeige ---
metric_placeholder.metric(label=st.session_state.label,
                          value=st.session_state.value,
                          delta=st.session_state.price_delta)
blinker_placeholder.markdown(st.session_state.blinker)
chart_placeholder.plotly_chart(st.session_state.fig, use_container_width=True)
