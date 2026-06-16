import unittest
import pandas as pd
from datetime import datetime, timedelta
from backtest.benchmarks.buy_hold import run_buy_and_hold
from backtest.benchmarks.daily_dca import run_daily_dca

class TestBenchmarks(unittest.TestCase):
    def setUp(self):
        # Tạo dữ liệu test dạng OHLCV trong 5 ngày
        start_time = datetime(2023, 1, 1, 0, 0)
        times = [start_time + timedelta(hours=i) for i in range(120)] # 5 ngày, mỗi giờ 1 nến
        self.index = pd.DatetimeIndex(times)
        
        # Giá đóng cửa tăng dần từ 100 đến 220
        close_prices = [100.0 + i for i in range(120)]
        self.data = pd.DataFrame({"close": close_prices}, index=self.index)
        self.initial_capital = 1000.0

    def test_buy_and_hold(self):
        result = run_buy_and_hold(self.data, self.initial_capital)
        self.assertEqual(result["label"], "Buy & Hold")
        self.assertEqual(result["entry_price"], 100.0)
        self.assertEqual(result["exit_price"], 219.0)
        self.assertEqual(result["quantity"], 10.0) # 1000 / 100 = 10
        self.assertEqual(result["final_equity"], 2190.0) # 10 * 219 = 2190
        self.assertAlmostEqual(result["roi"], 1.19) # (2190 - 1000) / 1000 = 1.19
        self.assertEqual(len(result["equity_curve"]), 120)

    def test_daily_dca(self):
        result = run_daily_dca(self.data, self.initial_capital)
        self.assertEqual(result["label"], "Daily DCA")
        # 5 ngày, mỗi ngày mua 1000 / 5 = 200 USDT
        # Nến đầu tiên ngày 1: giá 100 -> mua 2 BTC
        # Nến đầu tiên ngày 2 (giờ thứ 24): giá 124 -> mua 200/124 BTC
        # Nến đầu tiên ngày 3 (giờ thứ 48): giá 148 -> mua 200/148 BTC
        # Nến đầu tiên ngày 4 (giờ thứ 72): giá 172 -> mua 200/172 BTC
        # Nến đầu tiên ngày 5 (giờ thứ 96): giá 196 -> mua 200/196 BTC
        expected_qty = (200/100) + (200/124) + (200/148) + (200/172) + (200/196)
        self.assertAlmostEqual(result["final_quantity"], expected_qty, places=6)
        self.assertAlmostEqual(result["remaining_cash"], 0.0)
        self.assertEqual(len(result["equity_curve"]), 120)

    def test_empty_data(self):
        empty_df = pd.DataFrame()
        bh_result = run_buy_and_hold(empty_df, self.initial_capital)
        dca_result = run_daily_dca(empty_df, self.initial_capital)
        
        self.assertEqual(bh_result["final_equity"], self.initial_capital)
        self.assertEqual(dca_result["final_equity"], self.initial_capital)

if __name__ == "__main__":
    unittest.main()
