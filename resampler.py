import pandas as pd
import numpy as np

def resample_calendar(df: pd.DataFrame, timeframe: str, offset: str = "0h") -> pd.DataFrame:
    """
    Standard-Resampling basierend auf echter Kalenderzeit (ideal für 24/7 Krypto).
    """
    agg_dict = {
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }
    return df.resample(timeframe, offset=offset).agg(agg_dict).dropna()


def resample_by_bar_count(df: pd.DataFrame, bars_per_candle: int, bar_offset: int = 0) -> pd.DataFrame:
    """
    Fasst eine exakte Anzahl aufeinanderfolgender Basis-Kerzen zusammen.
    Perfekt für Aktien, um z.B. 64 echte Handelsstunden ohne Wochenend-/Nachtlücken zu bündeln.
    """
    if bar_offset > 0:
        df = df.iloc[bar_offset:]
        
    # Jede Gruppe erhält eine fortlaufende ID (0, 0, ..., 1, 1, ...)
    group_ids = np.arange(len(df)) // bars_per_candle
    
    resampled = df.groupby(group_ids).agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    })
    
    # Zeitstempel der jeweils ersten Basis-Kerze der Gruppe als Index verwenden
    first_timestamps = df.groupby(group_ids).apply(lambda g: g.index[0])
    resampled.index = pd.DatetimeIndex(first_timestamps)
    
    return resampled.dropna()
