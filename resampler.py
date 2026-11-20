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
        # Daten exakt ab dem gewünschten Startzeitpunkt abschneiden
        df = df[df.index >= origin_ts]
        return df.resample(timeframe, origin=origin_ts, offset=offset).agg(agg_dict).dropna()
    
    return df.resample(timeframe, offset=offset).agg(agg_dict).dropna()
