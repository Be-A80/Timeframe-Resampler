import pandas as pd
import numpy as np

def resample_calendar(
    df: pd.DataFrame, 
    timeframe: str, 
    offset: str = "0h",
    origin_ts: pd.Timestamp | None = None
) -> pd.DataFrame:
    """
    Aggregiert nach Kalenderzeit. Wenn origin_ts gesetzt ist, beginnt 
    die erste Kerze exakt an diesem Zeitstempel.
    """
    agg_dict = {
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }
    
    if origin_ts is not None:
        df = df[df.index >= origin_ts]
        return df.resample(timeframe, origin=origin_ts, offset=offset).agg(agg_dict).dropna()
    
    return df.resample(timeframe, offset=offset).agg(agg_dict).dropna()


def resample_by_bar_count(df: pd.DataFrame, bars_per_candle: int, bar_offset: int = 0) -> pd.DataFrame:
    """
    Fasst eine exakte Anzahl aufeinanderfolgender Basis-Kerzen zusammen.
    Perfekt für Aktien, um z.B. 64 echte Handelsstunden ohne Wochenend-/Nachtlücken zu bündeln.
    """
    if bar_offset > 0:
        df = df.iloc[bar_offset:]
        
    group_ids = np.arange(len(df)) // bars_per_candle
    
    resampled = df.groupby(group_ids).agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    })
    
    first_timestamps = df.groupby(group_ids).apply(lambda g: g.index[0])
    resampled.index = pd.DatetimeIndex(first_timestamps)
    
    return resampled.dropna()
