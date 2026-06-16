import pandas as pd
from datetime import datetime
from typing import Callable, List
from core.interfaces.data_provider import MarketDataProvider

class HistoricalProvider(MarketDataProvider):
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self._callbacks: List[Callable[[datetime, pd.Series], None]] = []
        self._stop_requested = False
        self._current_time = None
        
    def start(self):
        self._stop_requested = False
        if self.df.empty:
            return
            
        for timestamp, candle in self.df.iterrows():
            if self._stop_requested:
                break
            self._current_time = timestamp
            for cb in self._callbacks:
                cb(timestamp, candle)
                
    def stop(self):
        self._stop_requested = True
        
    def subscribe(self, callback: Callable[[datetime, pd.Series], None]):
        self._callbacks.append(callback)
        
    def get_current_time(self) -> datetime:
        return self._current_time
