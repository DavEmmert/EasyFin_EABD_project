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
import numpy as np
from datetime import timedelta
import os 


# Redis-Verbindung
redis_host = os.getenv("REDIS_HOST", "srv-captain--redis")  # fallback für dev
REDIS_PASSWORD="Kurt"

r = redis.Redis(host=redis_host, port=6379, password=REDIS_PASSWORD)


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
    "price_delta_to_open": 0,
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
    "show_in_eur": False,
    "show_cur": "cur",
    "rate":1,
    "stock_name": "Kurt ohne Helm und Ohne Gurt"

}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def get_buffer_from_redis(stock: str, max_items: int = 12*60*24):
    key = f"buffer:{stock}"
    raw_entries = r.lrange(key, -max_items, -1)
    return deque(json.loads(item) for item in raw_entries)

def get_settings_from_redis(stock: str, max_items: int = 2):
    key = f"settings:{stock}_settings"
    raw_entries = r.lrange(key, -max_items, -1)
    return deque(json.loads(item) for item in raw_entries)

def get_q_and_a_from_redis(stock: str):
    key = f"q_and_a:{stock}"
    try:
        raw_entry = r.get(key)  # Nur den letzten Eintrag holen
        return json.loads(raw_entry) if raw_entry else {}
    except Exception as e:
        st.error(f"Redis read error: {e}")
        return {}
    
def update_price_chart(prices, timestamps, open_price, price_delta):
    fig = go.Figure()

    # Farben je nach Kursentwicklung
    line_color = "#D50000" if price_delta < 0 else "#00C853"

    # Preislinie
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=prices,
        mode='lines',
        line=dict(color=line_color, width=2),
        name='Price',
        showlegend=False
    ))

    # Aktueller Preis als Marker
    fig.add_trace(go.Scatter(
        x=[timestamps[-1]],
        y=[prices[-1]],
        mode="markers+text",
        marker=dict(color=line_color, size=10),
        text=[f"{prices[-1]:,.2f}"],
        textposition="top center",
        showlegend=False
    ))

    # Berechnung: Mittelwert und ±2x Standardabweichung
    mean_price = np.mean(prices)
    std_price = np.std(prices)
    upper_bound = mean_price + 2 * std_price
    lower_bound = mean_price - 2 * std_price
    out_of_bounds_times_h = []
    out_of_bounds_prices_h = []
    out_of_bounds_times_l = []
    out_of_bounds_prices_l = []

    for t, p in zip(timestamps, prices):
        if p > upper_bound:
            out_of_bounds_times_h.append(t)
            out_of_bounds_prices_h.append(p)

    for t, p in zip(timestamps, prices):
        if p < lower_bound:
            out_of_bounds_times_l.append(t)
            out_of_bounds_prices_l.append(p)


    # Horizontale Linien: +2σ / -2σ / Open
    fig.add_shape(type="line", x0=min(timestamps), x1=max(timestamps), y0=upper_bound, y1=upper_bound,
                  line=dict(color="orange", width=1, dash="dot"))
    fig.add_shape(type="line", x0=min(timestamps), x1=max(timestamps), y0=lower_bound, y1=lower_bound,
                  line=dict(color="orange", width=1, dash="dot"))
    fig.add_shape(type="line", x0=min(timestamps), x1=max(timestamps), y0=open_price, y1=open_price,
                  line=dict(color="gray", width=2, dash="dash"))
    
    fig.add_trace(go.Scatter(
    x=[timestamps[-1] + timedelta(minutes=3)],
    y=[upper_bound],
    mode="text",
    text=[f"↑ 2σ: {upper_bound:,.2f}"],
    textposition="top right",
    showlegend=False,
    textfont=dict(color="orange", size=10)
    ))

    fig.add_trace(go.Scatter(
        x=[timestamps[-1] + timedelta(minutes=3)],
        y=[lower_bound],
        mode="text",
        text=[f"↓ 2σ: {lower_bound:,.2f}"],
        textposition="bottom right",
        showlegend=False,
        textfont=dict(color="orange", size=10)
    ))

    fig.add_trace(go.Scatter(
        x=[timestamps[-1] + timedelta(minutes=3)],
        y=[open_price],
        mode="text",
        text=[f"Open: {open_price:,.2f}"],
        textposition="middle right",
        showlegend=False,
        textfont=dict(color="gray", size=10)
    ))

    fig.add_trace(go.Scatter(
        x=out_of_bounds_times_l,
        y=out_of_bounds_prices_l,
        mode="markers",
        marker=dict(color="red", size=8, symbol="x"),
        name="Outlier",
        showlegend=True
    ))

    fig.add_trace(go.Scatter(
        x=out_of_bounds_times_h,
        y=out_of_bounds_prices_h,
        mode="markers",
        marker=dict(color="green", size=8, symbol="x"),
        name="Outlier",
        showlegend=True
    ))



    # Formatierte Titel-Zeitspanne
    start_str = timestamps[0].strftime('%d.%m.%Y %H:%M')
    end_str = timestamps[-1].strftime('%H:%M')

    # Layout
    fig.update_layout(
        title={
            "text": f"last 24h<br><sup>{start_str} → {end_str}</sup>",
            "x": 0.5,
            "xanchor": "center"
        },
        xaxis_title='Time',
        yaxis_title=st.session_state.cur ,
        template='plotly_dark',
        plot_bgcolor="#111111",
        paper_bgcolor="#111111",
        font=dict(color="white"),
        xaxis=dict(
            showgrid=True,
            gridcolor="#333333",
            tickformat="%H:%M\n%d.%m"
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#333333",
            tickformat=",.2f"  # Format: xx,xxx.xx
        )
    )

    # Hover-Format
    fig.update_traces(
        hovertemplate="<b>%{y:,.2f}</b><br>%{x|%d.%m %H:%M}<extra></extra>"
    )

    return fig



def show_overview():
    
    st.set_page_config(layout="wide")   
    st.text("")

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
    df = df[df["Name"] != "Keine Daten"],

    # Layout mit 2 Spalten: links Filter, rechts Tabelle
    col1, col2 = st.columns([1, 3])  # Breitenverhältnis 1:3

    with col1:
       # st.subheader("🔍 Filter")
        st.image("easyfin_logo.png")
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

            for stock in stock_data:
                if stock["Symbol"] == symbol:
                    st.session_state.stock_name = stock["Name"]
                    break

            st.rerun()

        # Dropdown für Symbol-Auswahl
        selected = st.selectbox("📈 Choose stock:", filtered_df["Symbol"].tolist(), key="stock_selector")
        st.session_state.selected_topic = selected
        # Button zum Anzeigen
        if st.button("🔍 Show Details"):
            select_stock(selected)




def show_detail_for_selected_stock():



    col1, colempty, col2, col3, col4 = st.columns([8,0.5,3,0.5,1])
    
    q_and_a = get_q_and_a_from_redis(st.session_state.selected_topic)
    
    with colempty:
       "" 
    with col1:
        # Dropdown: Nur Fragen anzeigen
        question_options = {f"q{i}": q_and_a.get(f"q{i}") for i in range(1, 6) if q_and_a.get(f"q{i}")}

        if question_options:
            st.subheader("What do you want to know?")
            selected_q_key = st.selectbox("", options=question_options.keys(), format_func=lambda k: question_options[k])
            selected_answer = q_and_a.get(f"a{selected_q_key[1:]}", "Keine Antwort verfügbar.")

            st.markdown(f"**Answer:** {selected_answer}")
        else:
            st.info("Keine Fragen verfügbar.")
    
    with col3: 
        blinker_placeholder = st.empty()
        #st.image("easyfin_logo.png", width = 300)


    with col4:
        st.image("easyfin_logo.png", width = 300)
        def test(): 
            st.session_state.current_view = "overview"
        st.button("Back", on_click=test)    # --- Daten aktualisieren alle 5 Sekunden ---
        
        
    #while True:
    st.session_state["last_update"] = time.time()

    buffer = get_buffer_from_redis(st.session_state.selected_topic )
    settings = get_settings_from_redis(st.session_state.selected_topic )

    


    if buffer and settings:
        last_entry = buffer[-1]
        setting = settings[-1]

        st.session_state.rate = last_entry["eur_rate"] if st.session_state.show_cur == "EUR" else 1

        st.session_state.value = last_entry['price'] * st.session_state.rate
        st.session_state.cur = last_entry['cur'] if st.session_state.show_cur == "cur" else "€"
        if st.session_state.value != st.session_state.last_value:
            st.session_state.label = st.session_state.selected_topic 
            converted_open = setting["open"] * st.session_state.rate
            st.session_state.price_delta_to_open = ((st.session_state.value - converted_open) / converted_open) * 100
            st.session_state.min = setting["min"] * st.session_state.rate
            st.session_state.max = setting["max"] * st.session_state.rate
            st.session_state.open = setting["open"] * st.session_state.rate
            st.session_state.blinker_c = "🔴" if st.session_state.value < st.session_state.last_value else "🟢"
            st.session_state.max_delta = max(st.session_state.price_delta *0.02, abs(st.session_state.max_delta)) * st.session_state.rate
            prices = [entry["price"] * st.session_state.rate for entry in buffer]
            timestamps = [datetime.fromisoformat(entry["timestamp"]).astimezone(ZoneInfo("Europe/Berlin")) for entry in buffer]
            st.session_state.price_delta = round(
                                                (st.session_state.value - st.session_state.last_value) / st.session_state.last_value,
                                                2
                                            ) if st.session_state.last_value != 0 else 0.01
            
           

            # Update Chart
            fig = update_price_chart(prices, timestamps, st.session_state.open, st.session_state.price_delta_to_open)
            st.session_state.fig = fig

        
        
        
            blinker_placeholder.markdown(st.session_state.blinker_c)
            #time.sleep(1)
            st.session_state.blinker = ""
            blinker_placeholder.markdown(st.session_state.blinker)
            st.session_state.last_value = st.session_state.value

            #st_autorefresh(interval=1000, key="data_refresh")  # s

            # --- Anzeige ---
        with col2:
            st.subheader(st.session_state.stock_name)
            st.metric(label="",
                                    value = f"{float(st.session_state.value):,.2f} {st.session_state.cur}",
                                    delta=f"{st.session_state.price_delta:+.2f} %")
            if st.button("EUR" if st.session_state.show_cur =="cur" else  last_entry['cur'] ):
                st.session_state.show_cur = "EUR" if st.session_state.show_cur == "cur" else "cur"
                st.rerun() 
            
        st.plotly_chart(st.session_state.fig, use_container_width=True)
    

    st.session_state.live = st.session_state.live+1
    if st.session_state.live == 2:
        blinker_placeholder.markdown(st.session_state.blinker_c)
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
