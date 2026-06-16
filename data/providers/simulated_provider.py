import time
import random
import pandas as pd
from datetime import datetime, timedelta
from typing import Callable, List
from core.interfaces.data_provider import MarketDataProvider
from core.events import TickEvent

class SimulatedRealtimeProvider(MarketDataProvider):
    def __init__(self, df: pd.DataFrame, speed: float = 100.0, symbol: str = "BTC/USDT"):
        self.df = df
        self.speed = speed
        self.symbol = symbol
        self._callbacks: List[Callable[[TickEvent], None]] = []
        self._stop_requested = False
        self._current_time: int = None
        self._drop_until = None
        self._is_paused = False
        
        # Torture Mode Config
        self.torture_mode = False
        self.torture_keep_ticks = 50
        self.torture_drop_ticks = 10
        self.torture_random_prob = 0.01
        self.torture_duration_range = (5, 100)
        self.tick_counter = 0
        
        # Time Drift Config
        self.time_drift_mode = False
        self.buffer = []
        
    def start(self):
        self._stop_requested = False
        if self.df.empty:
            return
            
        last_timestamp = None
        
        for timestamp, candle in self.df.iterrows():
            if self._stop_requested:
                break
                
            while self._is_paused and not self._stop_requested:
                time.sleep(0.1)
                
            self._current_time = timestamp
            
            if last_timestamp is not None:
                dt = (timestamp - last_timestamp).total_seconds()
                sleep_time = dt / self.speed
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            last_timestamp = timestamp
            
            # Check fake disconnect
            if self._drop_until and timestamp < self._drop_until:
                continue # Drop data (simulate packet loss/disconnect)
            else:
                self._drop_until = None
                
            if self.torture_mode:
                self.tick_counter += 1
                cycle = self.torture_keep_ticks + self.torture_drop_ticks
                if cycle > 0 and self.tick_counter % cycle >= self.torture_keep_ticks:
                    continue
                
                if random.random() < self.torture_random_prob:
                    drop_duration_ticks = random.randint(self.torture_duration_range[0], self.torture_duration_range[1])
                    # Giả định timeframe 1m = 60s
                    self.drop_data_for(drop_duration_ticks * 60)
                    continue
            
            if self.time_drift_mode:
                self.buffer.append((timestamp, candle))
                if len(self.buffer) == 3:
                    # Hoán đổi thứ tự tick: (0, 1, 2) -> (2, 0, 1) Out of order!
                    out_of_order = [self.buffer[2], self.buffer[0], self.buffer[1]]
                    for t_stamp, c in out_of_order:
                        tick = TickEvent(
                            timestamp=int(t_stamp.timestamp() * 1000) if isinstance(t_stamp, datetime) else t_stamp,
                            symbol=self.symbol,
                            open=c['open'], high=c['high'], low=c['low'], close=c['close'], volume=c.get('volume', 0.0),
                            is_closed=True, source="synthetic"
                        )
                        for cb in self._callbacks:
                            cb(tick)
                    self.buffer.clear()
            else:
                tick = TickEvent(
                    timestamp=int(timestamp.timestamp() * 1000) if isinstance(timestamp, datetime) else timestamp,
                    symbol=self.symbol,
                    open=candle['open'], high=candle['high'], low=candle['low'], close=candle['close'], volume=candle.get('volume', 0.0),
                    is_closed=True, source="synthetic"
                )
                for cb in self._callbacks:
                    cb(tick)
                
    def stop(self):
        self._stop_requested = True
        
    def pause(self):
        self._is_paused = True
        
    def resume(self):
        self._is_paused = False
        
    def subscribe(self, callback: Callable[[TickEvent], None]):
        self._callbacks.append(callback)
        
    def get_current_time(self) -> int:
        if self._current_time is None:
            return 0
        if isinstance(self._current_time, datetime):
            return int(self._current_time.timestamp() * 1000)
        return self._current_time
        
    def drop_data_for(self, simulated_seconds: int):
        """Simulate WebSocket disconnection for N simulated seconds"""
        if self._current_time:
            self._drop_until = self._current_time + timedelta(seconds=simulated_seconds)
            
    def enable_torture_mode(self, keep_ticks=50, drop_ticks=10, random_prob=0.01, duration_range=(5, 100)):
        self.torture_mode = True
        self.torture_keep_ticks = keep_ticks
        self.torture_drop_ticks = drop_ticks
        self.torture_random_prob = random_prob
        self.torture_duration_range = duration_range
        self.tick_counter = 0
        
    def disable_torture_mode(self):
        self.torture_mode = False
        
    def enable_time_drift(self):
        self.time_drift_mode = True
        self.buffer.clear()
        
    def disable_time_drift(self):
        self.time_drift_mode = False
        self.buffer.clear()
