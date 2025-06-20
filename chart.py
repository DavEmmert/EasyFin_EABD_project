import streamlit as st
from datetime import datetime
from quixstreams import Application
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import altair as alt

# Auto-refresh every 2 seconds
st_autorefresh(interval=3000, key="refresh")
st.set_page_config(page_title="Live Stock Dashboard")
st.title("📈 Live Stock Metric")

# Initialize session_state buffers
if "price_buffer" not in st.session_state:
    st.session_state.price_buffer = []
if "timestamp_buffer" not in st.session_state:
    st.session_state.timestamp_buffer = []

# Kafka connection (cached)
@st.cache_resource
def kafka_connection():
    return Application(
        broker_address="127.0.0.1:9092",
        consumer_group="chart",
        auto_offset_reset="latest",
        auto_create_topics=True
    )

@st.cache_resource

def kafka_connection_and_topic():
    app = Application(
        broker_address="127.0.0.1:9092",
        consumer_group="chart",
        auto_offset_reset="latest",
        auto_create_topics=True
    )
    return app, app.topic("live_stock_price")

app, price_topic = kafka_connection_and_topic()

st_metric = st.empty()
st_chart = st.empty()

with app.get_consumer() as consumer:
    consumer.subscribe([price_topic.name])
    msg = consumer.poll(timeout=1.0)

    if msg and msg.topic() == price_topic.name:
        price_msg = price_topic.deserialize(msg)
        price = price_msg.value.get("price", 0.0)
        stock_id = price_msg.value.get("stock", "UNKNOWN")
        timestamp = datetime.fromisoformat(price_msg.value.get("timestamp"))

        st.session_state.price_buffer.append(price)
        st.session_state.timestamp_buffer.append(timestamp)

        # Limit to last 100 points
        st.session_state.price_buffer = st.session_state.price_buffer[-100:]
        st.session_state.timestamp_buffer = st.session_state.timestamp_buffer[-100:]

        st_metric.metric(label=f"{stock_id}", value=f"{price:.2f} $")

    else:
        st.warning("Warte auf neue Daten von Kafka...")

# Build DataFrame and chart outside Kafka polling
if st.session_state.price_buffer:
    df = pd.DataFrame({
        "time": st.session_state.timestamp_buffer,
        "price": st.session_state.price_buffer
    })

    y_min = df["price"].min()
    chart = alt.Chart(df).mark_line().encode(
        x=alt.X("time:T", title="Zeit"),
        y=alt.Y("price:Q", scale=alt.Scale(domain=[y_min, None]), title="Preis ($)")
    ).properties(
        width='container',
        height=300
    )

    st_chart.altair_chart(chart, use_container_width=True)
