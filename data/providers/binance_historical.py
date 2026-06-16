import os
import requests
import pandas as pd
import logging
from typing import List, Optional, Callable
from datetime import datetime, timedelta
import time
from core.interfaces.data_provider import MarketDataProvider
from core.events import TickEvent

logger = logging.getLogger(__name__)

class BinanceDataFetcher:
    """Fetcher to pull historical klines from Binance API and save as Parquet."""
    
    BASE_URL = "https://api.binance.com/api/v3/klines"
    
    @staticmethod
    def fetch_klines(symbol: str, interval: str, start_time: datetime, end_time: datetime, save_path: str):
        """
        Fetch klines from start_time to end_time in chunks of 1000 and save to parquet.
        """
        logger.info(f"Downloading {symbol} {interval} from {start_time} to {end_time}...")
        
        start_ts = int(start_time.timestamp() * 1000)
        end_ts = int(end_time.timestamp() * 1000)
        
        all_klines = []
        current_start = start_ts
        
        while current_start < end_ts:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": current_start,
                "endTime": end_ts,
                "limit": 1000
            }
            
            response = requests.get(BinanceDataFetcher.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                break
                
            all_klines.extend(data)
            
            # The last fetched kline's open time + 1ms will be our new start
            last_open_time = data[-1][0]
            current_start = last_open_time + 1
            
            logger.info(f"  Fetched {len(data)} candles, up to {datetime.fromtimestamp(last_open_time / 1000)}")
            
            # Sleep slightly to respect rate limits
            time.sleep(0.5)
            
        if not all_klines:
            logger.warning("No data fetched.")
            return
            
        df = pd.DataFrame(all_klines, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        
        # Format according to standard TICK schema
        # Binance REST klines are ALWAYS closed
        df["is_closed"] = True
        df["source"] = "rest"
        df["symbol"] = symbol
        
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
            
        # Select only needed columns
        df = df[["timestamp", "symbol", "open", "high", "low", "close", "volume", "is_closed", "source"]]
        
        df.sort_values("timestamp", inplace=True)
        
        # Ensure dir exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # Define pyarrow schema
        import pyarrow as pa
        schema = pa.schema([
            ('timestamp', pa.int64()),
            ('symbol', pa.string()),
            ('open', pa.float64()),
            ('high', pa.float64()),
            ('low', pa.float64()),
            ('close', pa.float64()),
            ('volume', pa.float64()),
            ('is_closed', pa.bool_()),
            ('source', pa.string())
        ])
        
        df.to_parquet(save_path, engine="pyarrow", index=False, schema=schema)
        logger.info(f"Saved {len(df)} candles to {save_path}")

class BinanceHistoricalProvider(MarketDataProvider):
    """
    Market Data Provider that reads from a local Parquet file.
    Supports Deterministic Replay and Realtime Simulation modes.
    """
    def __init__(self, parquet_path: str, realtime_sim: bool = False, speed_multiplier: float = 1.0):
        self.parquet_path = parquet_path
        self.realtime_sim = realtime_sim
        self.speed_multiplier = speed_multiplier
        
        self._df: Optional[pd.DataFrame] = None
        self._running = False
        self._callback: Optional[Callable[[TickEvent], None]] = None
        self._current_time: Optional[int] = None
        
    def subscribe(self, callback: Callable[[TickEvent], None]):
        self._callback = callback
        
    def start(self):
        if not os.path.exists(self.parquet_path):
            raise FileNotFoundError(f"Parquet file not found: {self.parquet_path}")
            
        logger.info(f"Loading data from {self.parquet_path}")
        self._df = pd.read_parquet(self.parquet_path)
        logger.info(f"Loaded {len(self._df)} rows.")
        
        self._running = True
        self._run_loop()
        
    def stop(self):
        self._running = False
        
    def get_current_time(self) -> int:
        return self._current_time or int(datetime.now().timestamp() * 1000)
        
    def _run_loop(self):
        for idx, row in self._df.iterrows():
            if not self._running:
                break
                
            self._current_time = row['timestamp']
            
            if self._callback:
                tick = TickEvent(
                    timestamp=row['timestamp'],
                    symbol=row['symbol'],
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row['volume'],
                    is_closed=row['is_closed'],
                    source=row['source']
                )
                self._callback(tick)
                
            if self.realtime_sim:
                # Simulate the delay between candles. For 1m interval, 60 seconds / speed_multiplier
                time.sleep(60.0 / self.speed_multiplier)
                
        logger.info("BinanceHistoricalProvider reached end of data.")
        self._running = False
