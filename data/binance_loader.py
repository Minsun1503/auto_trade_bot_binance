import os
import ccxt
import pandas as pd
from typing import Optional, List
import logging
from datetime import datetime, timezone
import calendar
from tqdm import tqdm

logger = logging.getLogger(__name__)

class BinanceDataLoader:
    """
    Tải dữ liệu OHLCV lịch sử từ Binance và lưu cache theo từng tháng (Parquet).
    Ưu tiên dữ liệu 1m để backtest Grid được chính xác nhất.
    """
    
    def __init__(self, data_dir: str = "data_cache"):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
        })
        
    def _get_cache_filepath(self, symbol: str, timeframe: str, year: int, month: int) -> str:
        safe_symbol = symbol.replace("/", "")
        # e.g., data_cache/BTCUSDT
        symbol_dir = os.path.join(self.data_dir, safe_symbol)
        if not os.path.exists(symbol_dir):
            os.makedirs(symbol_dir)
            
        # e.g., data_cache/BTCUSDT/1m_2025_01.parquet
        filename = f"{timeframe}_{year}_{month:02d}.parquet"
        return os.path.join(symbol_dir, filename)

    def _fetch_month_data(self, symbol: str, timeframe: str, year: int, month: int) -> pd.DataFrame:
        """Tải toàn bộ dữ liệu của 1 tháng từ Binance (hoặc load cache)"""
        cache_file = self._get_cache_filepath(symbol, timeframe, year, month)
        if os.path.exists(cache_file):
            return pd.read_parquet(cache_file)
            
        # Tính toán start_time và end_time cho tháng
        start_dt = datetime(year, month, 1, tzinfo=timezone.utc)
        _, last_day = calendar.monthrange(year, month)
        end_dt = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        
        # Kiểm tra nếu tháng này nằm trong tương lai thì không fetch
        now = datetime.now(timezone.utc)
        if start_dt > now:
            return pd.DataFrame()
            
        # Nếu tháng hiện tại chưa kết thúc, chỉ fetch đến thời điểm hiện tại và KHÔNG CACHE để lần sau chạy vẫn fetch lại
        is_current_month = (year == now.year and month == now.month)
        if is_current_month:
            end_dt = now
            
        since_ms = int(start_dt.timestamp() * 1000)
        until_ms = int(end_dt.timestamp() * 1000)
        
        all_ohlcv = []
        current_since = since_ms
        
        # Estimate number of requests (1000 limit per request)
        # For 1m timeframe, 1 month ~ 43200 / 1000 = 44 requests
        est_requests = int((until_ms - since_ms) / (60000 * 1000)) + 1
        
        logger.info(f"Downloading {symbol} {timeframe} for {year}-{month:02d}...")
        pbar = tqdm(total=est_requests, desc=f"{year}-{month:02d}", leave=False)
        
        while current_since < until_ms:
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=1000)
                if not ohlcv:
                    break
                    
                all_ohlcv.extend(ohlcv)
                
                last_ts = ohlcv[-1][0]
                current_since = last_ts + 1
                
                pbar.update(1)
                
                if current_since >= until_ms:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching data: {e}")
                break
                
        pbar.close()
        
        if not all_ohlcv:
            return pd.DataFrame()
            
        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('datetime', inplace=True)
        df.index = df.index.tz_localize('UTC')
        df = df[~df.index.duplicated(keep='first')] # Remove duplicates just in case
        
        # Filter strictly within the month
        df = df[(df.index >= start_dt) & (df.index <= end_dt)]
        
        # Chỉ cache nếu không phải tháng hiện tại (do tháng hiện tại chưa đóng nến hết)
        if not is_current_month and len(df) > 0:
            df.to_parquet(cache_file)
            
        return df

    def fetch_historical_data(
        self, 
        symbol: str, 
        timeframe: str = "1m", 
        since_str: str = "2024-01-01 00:00:00",
        until_str: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Tải dữ liệu OHLCV. Tự động gộp các chunk tháng.
        since_str/until_str format: "YYYY-MM-DD HH:MM:SS"
        """
        since_dt = datetime.strptime(since_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        
        if until_str:
            until_dt = datetime.strptime(until_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        else:
            until_dt = datetime.now(timezone.utc)
            
        dfs = []
        
        start_year, start_month = since_dt.year, since_dt.month
        end_year, end_month = until_dt.year, until_dt.month
        
        current_year, current_month = start_year, start_month
        
        while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
            df_month = self._fetch_month_data(symbol, timeframe, current_year, current_month)
            if not df_month.empty:
                dfs.append(df_month)
                
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1
                
        if not dfs:
            return pd.DataFrame()
            
        final_df = pd.concat(dfs)
        final_df = final_df[~final_df.index.duplicated(keep='first')]
        
        # Filter the precise requested time window
        final_df = final_df[(final_df.index >= since_dt) & (final_df.index <= until_dt)]
        
        return final_df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loader = BinanceDataLoader(data_dir="C:/trade_bot/data_cache")
    # Tải test 2 tháng
    df = loader.fetch_historical_data(
        symbol="BTC/USDT",
        timeframe="1m", 
        since_str="2024-01-01 00:00:00",
        until_str="2024-02-28 23:59:59"
    )
    print(df.head())
    print(df.tail())
    print(f"Total shape: {df.shape}")
