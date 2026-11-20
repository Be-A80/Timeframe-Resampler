import streamlit as st
import pandas as pd
from datetime import datetime, date, time as dt_time, timezone
import plotly.graph_objects as go
from data_loader import fetch_crypto_ccxt, fetch_stock_yfinance
from resampler import resample_calendar, resample_by_bar_count

st.set_page_config(page_title="Custom Timeframe Charting", layout="wide")
st.title("📈 Custom Timeframe Charting Engine")

# --- 1. Markt & Datenquelle ---
st.sidebar.header("1. Markt & Datenquelle")
market_type = st.sidebar.radio("Markt", ["Krypto (CCXT)", "Aktien / ETFs (Yahoo Finance)"])

if market_type == "Krypto (CCXT)":
    exchange = st.sidebar.selectbox("Börse", ["kraken", "binance", "bybit", "coinbase", "okx"], index=0)
    symbol = st.sidebar.text_input("Handelspaar", value="BTC/USDT")
    base_tf = st.sidebar.selectbox("Basis-Kerzen", ["15m", "1h", "4h", "1d"], index=1)
    candle_history = st.sidebar.slider("Max. Anzahl Basis-Kerzen", 500, 10000, 3000, step=500)
else:
    symbol = st.sidebar.text_input("Ticker-Symbol", value="AAPL")
    base_tf = st.sidebar.selectbox("Basis-Kerzen", ["15m", "30m", "1h", "1d"], index=2)

# --- 1b. Zeitraum / Historischer Sprung ---
st.sidebar.header("2. Zeitraum & Startpunkt")
time_mode = st.sidebar.radio("Zeitraum", ["Aktuell (Rückblick bis heute)", "Ab historischem Datum"])

start_dt_utc = None
if time_mode == "Ab historischem Datum":
    col_d, col_t = st.sidebar.columns(2)
    selected_date = col_d.date_input("Startdatum", value=date(2022, 12, 19))
    selected_time = col_t.time_input("Startzeit (UTC)", value=dt_time(22, 0))
    start_dt_utc = datetime.combine(selected_date, selected_time, tzinfo=timezone.utc)

# --- 3. Custom Timeframe ---
st.sidebar.header("3. Custom Timeframe")
if market_type == "Aktien / ETFs (Yahoo Finance)":
    agg_mode = st.sidebar.radio(
        "Berechnungs-Modus",
        ["Echte Handels-Bars (ohne Nacht/Wochenende)", "Kalenderzeit"]
    )
else:
    agg_mode = "Kalenderzeit"

if agg_mode == "Kalenderzeit":
    col1, col2 = st.sidebar.columns(2)
    tf_val = col1.number_input("Dauer", min_value=1, value=64, step=1)
    tf_unit = col2.selectbox("Einheit", ["min", "h", "D", "W"], index=1)
    custom_tf_label = f"{tf_val}{tf_unit}"
    offset_val = st.sidebar.number_input("Zusätzlicher Offset (Stunden)", min_value=0, max_value=23, value=0)
else:
    bar_multiplier = st.sidebar.number_input(f"Multiplikator (x {base_tf})", min_value=1, value=64, step=1)
    bar_offset = st.sidebar.number_input("Start-Versatz (in Basis-Kerzen)", min_value=0, max_value=100, value=0)
    custom_tf_label = f"{bar_multiplier}x {base_tf} (Handelszeit)"

# --- 4. Darstellung ---
st.sidebar.header("4. Darstellung")
show_volume = st.sidebar.checkbox("Volumen anzeigen", value=True)
hide_gaps = st.sidebar.checkbox("Handelspausen ausblenden", value=(market_type != "Krypto (CCXT)"))

# --- Daten abrufen ---
@st.cache_data(ttl=300)
def get_raw_data(m_type, sym, b_tf, exch=None, hist=3000, s_dt=None):
    if m_type == "Krypto (CCXT)":
        return fetch_crypto_ccxt(exch, sym, b_tf, hist, s_dt)
    else:
        return fetch_stock_yfinance(sym, b_tf, s_dt)

with st.spinner(f"Lade Daten für {symbol}..."):
    try:
        if market_type == "Krypto (CCXT)":
            raw_df = get_raw_data(market_type, symbol, base_tf, exchange, candle_history, start_dt_utc)
        else:
            raw_df = get_raw_data(market_type, symbol, base_tf, start_dt=start_dt_utc)
    except Exception as e:
        st.error(f"Fehler beim Datenabruf: {e}")
        st.stop()

if raw_df.empty:
    st.warning("Keine Daten für diesen Zeitraum gefunden. (Tipp: Bei Aktien max. 730 Tage für 1h-Daten beachten.)")
    st.stop()

# --- Resampling anwenden ---
try:
    origin_ts = pd.Timestamp(start_dt_utc) if start_dt_utc else None
    if agg_mode == "Kalenderzeit":
        chart_df = resample_calendar(raw_df, timeframe=custom_tf_label, offset=f"{offset_val}h", origin_ts=origin_ts)
    else:
        if origin_ts is not None:
            raw_df = raw_df[raw_df.index >= origin_ts]
        chart_df = resample_by_bar_count(raw_df, bars_per_candle=bar_multiplier, bar_offset=bar_offset)
except Exception as e:
    st.error(f"Fehler beim Resampling: {e}")
    st.stop()

# --- Plotly Chart ---
start_info = f"ab {start_dt_utc.strftime('%d.%m.%Y %H:%M UTC')}" if start_dt_utc else "aktuell"
st.subheader(f"{symbol} — {custom_tf_label} ({start_info} | {len(chart_df)} Kerzen)")

x_axis = chart_df.index.strftime("%Y-%m-%d %H:%M") if hide_gaps else chart_df.index

fig = go.Figure()
fig.add_trace(go.Candlestick(
    x=x_axis,
    open=chart_df['Open'],
    high=chart_df['High'],
    low=chart_df['Low'],
    close=chart_df['Close'],
    name="Preis"
))

if show_volume:
    colors = ['#26a69a' if c >= o else '#ef5350' for o, c in zip(chart_df['Open'], chart_df['Close'])]
    fig.add_trace(go.Bar(
        x=x_axis,
        y=chart_df['Volume'],
        name="Volumen",
        marker_color=colors,
        opacity=0.35,
        yaxis="y2"
    ))

layout_args = dict(
    template="plotly_dark",
    height=700,
    xaxis_rangeslider_visible=False,
    margin=dict(l=20, r=20, t=30, b=20),
    yaxis=dict(title="Preis", domain=[0.22, 1.0] if show_volume else [0, 1]),
    xaxis=dict(type="category" if hide_gaps else "date", nticks=15)
)

if show_volume:
    layout_args["yaxis2"] = dict(title="Volumen", domain=[0, 0.18], showgrid=False)

fig.update_layout(**layout_args)
st.plotly_chart(fig, use_container_width=True)

with st.expander("Berechnete OHLCV-Tabelle & CSV-Export"):
    st.dataframe(chart_df.head(100), use_container_width=True)
    csv = chart_df.to_csv().encode('utf-8')
    st.download_button("Als CSV herunterladen", data=csv, file_name=f"{symbol.replace('/', '_')}_{custom_tf_label}.csv", mime="text/csv")

if market_type == "Krypto (CCXT)":
    exchange = st.sidebar.selectbox(
        "Börse", 
        ["okx", "kucoin", "bybit", "coinbase", "binance", "kraken"], 
        index=0,
        help="Hinweis: 'kraken' liefert nur die letzten 720 Kerzen. Für historische Daten ab 2022 'okx' oder 'kucoin' nutzen."
    )
