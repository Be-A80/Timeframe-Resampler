import streamlit as st
import plotly.graph_objects as go
from data_loader import fetch_crypto_ccxt, fetch_stock_yfinance
from resampler import resample_calendar, resample_by_bar_count

st.set_page_config(page_title="Custom Timeframe Charting", layout="wide")
st.title("📈 Custom Timeframe Charting Engine")

# --- 1. Datenquelle wählen ---
st.sidebar.header("1. Markt & Datenquelle")
market_type = st.sidebar.radio("Markt", ["Krypto (CCXT)", "Aktien / ETFs (Yahoo Finance)"])

if market_type == "Krypto (CCXT)":
    exchange = st.sidebar.selectbox("Börse", ["kraken", "binance", "bybit", "coinbase", "okx"], index=0)
    symbol = st.sidebar.text_input("Handelspaar", value="BTC/USDT", help="Format: BTC/USDT, ETH/EUR, SOL/USDT")
    base_tf = st.sidebar.selectbox("Basis-Kerzen", ["15m", "1h", "4h"], index=1)
    candle_history = st.sidebar.slider("Anzahl Basis-Kerzen laden", 500, 10000, 3000, step=500)
else:
    symbol = st.sidebar.text_input("Ticker-Symbol", value="AAPL", help="z.B. AAPL, NVDA, SAP.DE, ^GDAXI")
    base_tf = st.sidebar.selectbox("Basis-Kerzen", ["15m", "30m", "1h", "1d"], index=2)

# --- 2. Custom Timeframe konfigurieren ---
st.sidebar.header("2. Custom Timeframe")

if market_type == "Aktien / ETFs (Yahoo Finance)":
    agg_mode = st.sidebar.radio(
        "Berechnungs-Modus",
        ["Echte Handels-Bars (ohne Nacht/Wochenende)", "Kalenderzeit"],
        help="Bei 'Echte Handels-Bars' bedeutet Faktor 64 auf 1h-Basis = exakt 64 Börsen-Handelsstunden."
    )
else:
    agg_mode = "Kalenderzeit"

if agg_mode == "Kalenderzeit":
    col1, col2 = st.sidebar.columns(2)
    tf_val = col1.number_input("Dauer", min_value=1, value=64, step=1)
    tf_unit = col2.selectbox("Einheit", ["min", "h", "D", "W"], index=1)
    custom_tf_label = f"{tf_val}{tf_unit}"
    offset_val = st.sidebar.number_input("Zeit-Offset (Stunden)", min_value=0, max_value=23, value=0)
else:
    bar_multiplier = st.sidebar.number_input(
        f"Multiplikator (x {base_tf})", 
        min_value=1, 
        value=64, 
        step=1,
        help="Fasst exakt N Basis-Kerzen zu einer neuen Kerze zusammen."
    )
    bar_offset = st.sidebar.number_input("Start-Versatz (in Basis-Kerzen)", min_value=0, max_value=100, value=0)
    custom_tf_label = f"{bar_multiplier}x {base_tf} (Handelszeit)"

# --- 3. Chart-Darstellung ---
st.sidebar.header("3. Darstellung")
show_volume = st.sidebar.checkbox("Volumen anzeigen", value=True)
hide_gaps = st.sidebar.checkbox(
    "Handelspausen ausblenden (kompakter Chart)", 
    value=(market_type != "Krypto (CCXT)")
)

# --- Daten abrufen ---
@st.cache_data(ttl=300)
def get_raw_data(m_type, sym, b_tf, exch=None, hist=3000):
    if m_type == "Krypto (CCXT)":
        return fetch_crypto_ccxt(exch, sym, b_tf, hist)
    else:
        return fetch_stock_yfinance(sym, b_tf)

with st.spinner(f"Lade Daten für {symbol}..."):
    try:
        if market_type == "Krypto (CCXT)":
            raw_df = get_raw_data(market_type, symbol, base_tf, exchange, candle_history)
        else:
            raw_df = get_raw_data(market_type, symbol, base_tf)
    except Exception as e:
        st.error(f"Fehler beim Datenabruf: {e}")
        st.stop()

if raw_df.empty:
    st.warning("Keine Daten erhalten. Prüfe Symbol, Börse oder Internetverbindung.")
    st.stop()

# --- Resampling anwenden ---
try:
    if agg_mode == "Kalenderzeit":
        chart_df = resample_calendar(raw_df, timeframe=custom_tf_label, offset=f"{offset_val}h")
    else:
        chart_df = resample_by_bar_count(raw_df, bars_per_candle=bar_multiplier, bar_offset=bar_offset)
except Exception as e:
    st.error(f"Fehler beim Resampling: {e}")
    st.stop()

# --- Plotly Chart aufbauen ---
st.subheader(f"{symbol} — {custom_tf_label} ({len(chart_df)} Kerzen)")

# Wenn Handelspausen ausgeblendet werden sollen, Zeitstempel als formatierten String übergeben
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
    st.dataframe(chart_df.tail(100), use_container_width=True)
    csv = chart_df.to_csv().encode('utf-8')
    st.download_button("Als CSV herunterladen", data=csv, file_name=f"{symbol.replace('/', '_')}_{custom_tf_label}.csv", mime="text/csv")
