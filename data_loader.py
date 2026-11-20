import ccxt
import yfinance as yf
import pandas as pd
import time

def fetch_crypto_ccxt(exchange_id: str, symbol: str, timeframe: str = "1h", limit_total: int = 3000) -> pd.DataFrame:
    """
    Lädt historische OHLCV-Daten über CCXT mit Paginierung (ohne API-Key für Public Data).
    """
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({'enableRateLimit': True})
    
    # Millisekunden pro Kerze berechnen, um rückwärts zu paginieren
    tf_ms = exchange.parse_timeframe(timeframe) * 1000
    now = exchange.milliseconds()
    since = now - (limit_total * tf_ms)
    
    all_ohlcv = []
    while since < now:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
        if not ohlcv:
            break
        all_ohlcv.extend(ohlcv)
        # Nächster Startpunkt ist direkt nach der letzten geladenen Kerze
        since = ohlcv[-1][0] + tf_ms
        if len(ohlcv) < 100: # Ende der verfügbaren Daten erreicht
            break
        time.sleep(exchange.rateLimit / 1000.0)

    if not all_ohlcv:
        return pd.DataFrame()

    df = pd.DataFrame(all_ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms', utc=True)
    df.set_index('Timestamp', inplace=True)
    
    # Duplikate entfernen, falls Überlappungen auftreten
    df = df[~df.index.duplicated(keep='last')]
    return df


def fetch_stock_yfinance(ticker: str, interval: str = "1h") -> pd.DataFrame:
    """
    Lädt Aktien-/ETF-/Index-Daten über Yahoo Finance.
    """
    period_map = {
        "5m": "60d",
        "15m": "60d",
        "30m": "60d",
        "1h": "730d",
        "1d": "max"
    }
    period = period_map.get(interval, "730d")
    
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df.empty:
        return df

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    # Zeitzone einheitlich auf UTC normalisieren, falls vorhanden
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    else:
        df.index = df.index.tz_convert('UTC')
        
    return df[['Open', 'High', 'Low', 'Close', 'Volume']]
