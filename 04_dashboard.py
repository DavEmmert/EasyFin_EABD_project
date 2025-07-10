import streamlit as st
import redis
import json
import pandas as pd
import plotly.graph_objects as go
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo
import time
from streamlit_autorefresh import st_autorefresh



# Redis-Verbindung
r = redis.Redis(host="redis", port=6379, decode_responses=True)

# Session-State initialisieren
if "current_view" not in st.session_state:
    st.session_state.current_view = "overview"
if "selected_stock" not in st.session_state:
    st.session_state.selected_stock = None

defaults = {
    "currency_label": "EUR",
    "label": "",
    "cur": "USD",
    "eur_rate": 1.0,
    "value": 0,
    "price_delta": 0,
    "blinker": "",
    "max_running_time": 0,
    "refresh_time": 5,
    "last_update": time.time(),
    "max_delta": 0.01,
    "last_value": 0,
    "update": True,
    "live": 0,
    "freeze": 0,
    "fig": go.Figure(),
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def get_buffer_from_redis(stock: str, max_items: int = 60*60*24):
    key = f"buffer:{stock}"
    raw_entries = r.lrange(key, -max_items, -1)
    return deque(json.loads(item) for item in raw_entries)

def get_settings_from_redis(stock: str, max_items: int = 2):
    key = f"settings:{stock}_settings"
    raw_entries = r.lrange(key, -max_items, -1)
    return deque(json.loads(item) for item in raw_entries)

def show_overview():
    
    st.set_page_config(layout="wide")   
    st.title("📊 Easyfin")

    raw = r.get("topics_to_listen")
    topics = json.loads(raw) #if raw else ["AAPL"]
    cleaned_topics = [t.replace("_live", "") for t in topics]

    stock_data = []

    for stock in cleaned_topics:
        data_key = f"metadata:{stock}"
        raw_data = r.get(data_key)
        if raw_data:
            try:
                data = json.loads(raw_data)
                stock_data.append({
                    "Symbol": data.get("symbol", "–"),
                    "Name": data.get("name", "–"),
                    "Branch": data.get("industry", "–"),
                    "Sector": data.get("sector", "–"),
                    "Country": data.get("country", "–"),
                    "Exchange": data.get("exchange", "–"),
                    "Currency": data.get("currency", "–"),
                    "IPO": data.get("ipo_year", "–")
                })
            except Exception as e:
                st.warning(f"⚠️ Parsing Error {stock}: {e}")
        else:
            stock_data.append({
                "Symbol": stock,
                "Name": "Keine Daten",
                "Branch": "-",
                "Sector": "-",
                "Country": "-",
                "Exchange": "-",
                "Currency": "-",
                "IPO": "-"
            })

    df = pd.DataFrame(stock_data)

    # Layout mit 2 Spalten: links Filter, rechts Tabelle
    col1, col2 = st.columns([1, 3])  # Breitenverhältnis 1:3

    with col1:
        st.subheader("🔍 Filter")
        selected_country = st.selectbox("Country", ["All"] + sorted(df["Country"].unique()))
        selected_sector = st.selectbox("Sector", ["All"] + sorted(df["Sector"].unique()))
        selected_industry = st.selectbox("Branch", ["All"] + sorted(df["Branch"].unique()))

    # Filter anwenden
    filtered_df = df.copy()
    if selected_country != "All":
        filtered_df = filtered_df[filtered_df["Country"] == selected_country]
    if selected_sector != "All":
        filtered_df = filtered_df[filtered_df["Sector"] == selected_sector]
    if selected_industry != "All":
        filtered_df = filtered_df[filtered_df["Branch"] == selected_industry]

    with col2:
        st.subheader("📋 Stocks")
        if not filtered_df.empty:
            st.dataframe(filtered_df)
        else:
            st.info("No stocks available for these Filters.")
    with col1:
        st.subheader("📌 Details")
        def select_stock(symbol):
            st.session_state.selected_stock = symbol
            st.session_state.current_view = "detail"
            st.rerun()

        # Dropdown für Symbol-Auswahl
        selected = st.selectbox("📈 Aktie auswählen:", filtered_df["Symbol"].tolist(), key="stock_selector")
        st.session_state.selected_topic = selected
        # Button zum Anzeigen
        if st.button("🔍 Show Details"):
            select_stock(selected)




def show_detail_for_selected_stock():
    col1, col2 = st.columns([10,2])
    st.title(f"📈 {st.session_state.selected_stock} Details")
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
            fig = st.session_state.fig

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


    # --- Seitensteuerung ---
if st.session_state.current_view == "overview":
    show_overview()
elif st.session_state.current_view == "detail":
    if st.session_state.selected_stock:
        show_detail_for_selected_stock()
    else:
        st.warning("Kein Stock ausgewählt.")
