import sys
import os
import logging
from datetime import datetime, timedelta

# Thêm root path để import được
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.providers.binance_historical import BinanceDataFetcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    symbol = "BTCUSDT"
    interval = "1m"
    
    # Kéo 7 ngày gần nhất để làm Tầng 1 (Dev correctness)
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)
    
    save_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "storage", f"{symbol}_{interval}_7d.parquet")
    
    BinanceDataFetcher.fetch_klines(symbol, interval, start_time, end_time, save_path)
