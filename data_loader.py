import ccxt
import yfinance as yf
import pandas as pd
import time
from datetime import datetime, timezone

def fetch_crypto_ccxt(
    exchange_id: str, 
    symbol: str, 
    timeframe: str = "1h", 
    limit_total: int = 3000,
    start_dt: datetime | None = None
) -> pd.DataFrame:
    """
    Lädt historische OHLCV-Daten über CCXT ab einem optionalen Startzeitpunkt (UTC).
    """
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({'enableRateLimit': True})
    
    tf_ms = exchange.parse_timeframe(timeframe) * 1000
    now = exchange.milliseconds()
    
    if start_dt is not None:
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        since = int(start_dt.timestamp() * 1000)
    else:
        since = now - (limit_total * tf_ms)
    
    all_ohlcv = []
    candles_fetched = 0
    
    while since < now and candles_fetched < limit_total:
        # Manche Börsen (z.B. OKX) erlauben max. 100-300 Kerzen pro Call
        batch_limit = min(500, limit_total - candles_fetched)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=batch_limit)
        
        if not ohlcv:
            break
            
        # Schutz vor Börsen wie Kraken, die 'since' ignorieren und nur aktuelle Daten liefern:
        if start_dt is not None and candles_fetched == 0:
            first_ts = ohlcv[0][0]
            # Wenn die älteste gelieferte Kerze mehr als 7 Tage nach dem Wunschdatum liegt:
            if first_ts - since > (7 * 24 * 3600 * 1000):
                raise ValueError(
                    f"Die Börse '{exchange_id}' liefert für diesen Zeitraum keine historischen Daten zurück "
                    f"(älteste gelieferte Kerze: {pd.to_datetime(first_ts, unit='ms', utc=True)}). "
                    f"Bitte wechsle in der Sidebar auf 'okx', 'bybit' oder 'kucoin'."
                )

        all_ohlcv.extend(ohlcv)
        candles_fetched += len(ohlcv)
        
        last_ts = ohlcv[-1][0]
        if last_ts + tf_ms <= since:
            break
        since = last_ts + tf_ms
        
        time.sleep(exchange.rateLimit / 1000.0)

    if not all_ohlcv:
        return pd.DataFrame()

    df = pd.DataFrame(all_ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms', utc=True)
    df.set_index('Timestamp', inplace=True)
    df = df[~df.index.duplicated(keep='last')]
    return df
