import unittest
import os
import json
import pandas as pd
from datetime import datetime, timedelta
from backtest.validation import calculate_manifest_checksum, run_single_period_backtest, DummyAdapter
from backtest.engine import StrategyBase
from config.settings import DCAConfig

class DummyTestStrategy(StrategyBase):
    def __init__(self, config):
        self.config = config
        self.trade_done = False
    def on_tick(self, tick, engine):
        # Mua ngay nến đầu tiên, bán nến thứ hai
        if not self.trade_done:
            engine.execute_market_order("BUY", 1.0, tick.close, datetime.fromtimestamp(tick.timestamp / 1000.0))
            self.trade_done = True
        elif self.trade_done and len(engine.ledger.trades) == 1:
            engine.execute_market_order("SELL", 1.0, tick.close, datetime.fromtimestamp(tick.timestamp / 1000.0))
    def get_tracked_orders(self):
        return []

class TestValidation(unittest.TestCase):
    def setUp(self):
        self.manifest_path = "test_manifest.json"
        self.dummy_strategy_path = "test_dummy_strat.py"
        
        # Tạo file test giả lập
        with open(self.dummy_strategy_path, "w", encoding="utf-8") as f:
            f.write("# Dummy strategy content\nprint('hello')\n")
            
        manifest_data = {
            "files": [self.dummy_strategy_path],
            "dependencies_lockfile_hash": "dummy_lockfile_hash_123"
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

    def tearDown(self):
        if os.path.exists(self.manifest_path):
            os.remove(self.manifest_path)
        if os.path.exists(self.dummy_strategy_path):
            os.remove(self.dummy_strategy_path)

    def test_calculate_manifest_checksum(self):
        checksum1 = calculate_manifest_checksum(self.manifest_path)
        checksum2 = calculate_manifest_checksum(self.manifest_path)
        self.assertEqual(checksum1, checksum2)
        self.assertGreater(len(checksum1), 0)

    def test_run_single_period_backtest(self):
        # Tạo dữ liệu 10 nến
        start_time = datetime(2023, 1, 1, 0, 0)
        times = [start_time + timedelta(minutes=i) for i in range(10)]
        index = pd.DatetimeIndex(times)
        
        # Giá tăng từ 100 lên 109
        close_prices = [100.0 + i for i in range(10)]
        data = pd.DataFrame({"close": close_prices}, index=index)
        
        # Thiết lập config giả lập
        config = DCAConfig(
            interval_candles=60,
            base_order_size=100.0,
            drawdown_trigger=0.02,
            drawdown_multiplier=2.0
        )
        
        # Chạy thử
        result = run_single_period_backtest(
            strategy_class=DummyTestStrategy,
            strategy_config=config,
            data=data,
            start_date=start_time,
            end_date=times[-1],
            initial_capital=1000.0,
            warmup_candles=0
        )
        
        # Xác thực kết quả
        self.assertIn("roi", result)
        self.assertIn("sharpe", result)
        self.assertIn("trade_count", result)
        # 1 buy và 1 sell -> 1 consolidated roundtrip trade
        self.assertEqual(result["trade_count"], 1)
        self.assertEqual(len(result["roundtrip_pnls"]), 1)
        # Buy 1 BTC @ 100.0, Sell 1 BTC @ 101.0 -> PnL thô = 1.0 (trừ phí)
        self.assertGreater(result["roundtrip_pnls"][0], 0.0)

if __name__ == "__main__":
    unittest.main()
