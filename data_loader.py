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
    start_dt: datetime | None = None,
) -> pd.DataFrame:
    """
    Lädt historische OHLCV-Daten über CCXT ab einem optionalen Startzeitpunkt (UTC).
    """
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({"enableRateLimit": True})

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
        batch_limit = min(500, limit_total - candles_fetched)
        ohlcv = exchange.fetch_ohlcv(
            symbol, timeframe=timeframe, since=since, limit=batch_limit
        )

        if not ohlcv:
            break

        # Schutz vor Börsen wie Kraken, die 'since' ignorieren und nur aktuelle Daten liefern
        if start_dt is not None and candles_fetched == 0:
            first_ts = ohlcv[0][0]
            if first_ts - since > (7 * 24 * 3600 * 1000):
                raise ValueError(
                    f"Die Börse '{exchange_id}' liefert für diesen Zeitraum keine historischen Daten zurück "
                    f"(älteste gelieferte Kerze: {pd.to_datetime(first_ts, unit='ms', utc=True)}). "
                    f"Bitte wechsle in der Sidebar auf 'okx', 'kucoin' oder 'bybit'."
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

    df = pd.DataFrame(
        all_ohlcv, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"]
    )
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="ms", utc=True)
    df.set_index("Timestamp", inplace=True)
    df = df[~df.index.duplicated(keep="last")]
    return df


def fetch_stock_yfinance(
    ticker: str,
    interval: str = "1h",
    start_dt: datetime | None = None,
) -> pd.DataFrame:
    """
    Lädt Aktien-Daten über Yahoo Finance (optional ab start_dt).
    Hinweis: Yahoo erlaubt 1h-Daten nur für die letzten 730 Tage.
    """
    if start_dt is not None:
        df = yf.download(
            ticker,
            start=start_dt.strftime("%Y-%m-%d"),
            interval=interval,
            progress=False,
        )
    else:
        period_map = {
            "5m": "60d",
            "15m": "60d",
            "30m": "60d",
            "1h": "730d",
            "1d": "max",
        }
        df = yf.download(
            ticker,
            period=period_map.get(interval, "730d"),
            interval=interval,
            progress=False,
        )

    if df.empty:
        return df

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    return df[["Open", "High", "Low", "Close", "Volume"]]
