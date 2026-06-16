import unittest
from datetime import datetime
from backtest.metrics import (
    calculate_roi,
    calculate_cagr,
    calculate_max_drawdown,
    calculate_annualized_sharpe,
    calculate_annualized_sortino,
    calculate_calmar_ratio,
    calculate_recovery_factor,
    calculate_profit_factor,
    calculate_expectancy,
    calculate_exposure_ratio,
    calculate_trade_frequency
)

class TestMetrics(unittest.TestCase):
    def test_calculate_roi(self):
        self.assertEqual(calculate_roi(100, 150), 0.5)
        self.assertEqual(calculate_roi(100, 50), -0.5)
        self.assertEqual(calculate_roi(0, 50), 0.0)

    def test_calculate_cagr(self):
        start = datetime(2023, 1, 1)
        end = datetime(2024, 1, 1) # exactly 365 days
        self.assertAlmostEqual(calculate_cagr(100, 110, start, end), 0.1, places=3)
        self.assertEqual(calculate_cagr(100, 50, start, start), 0.0)

    def test_calculate_max_drawdown(self):
        equity = [100, 120, 90, 110, 80, 130]
        # Peak 120, trough 90 -> dd = 30/120 = 25%
        # Peak 120, trough 80 -> dd = 40/120 = 33.33%
        self.assertAlmostEqual(calculate_max_drawdown(equity), 40/120, places=4)
        self.assertEqual(calculate_max_drawdown([]), 0.0)

    def test_calculate_annualized_sharpe(self):
        # 10% daily return, zero variance -> returns 0
        returns = [0.01, 0.01, 0.01]
        self.assertEqual(calculate_annualized_sharpe(returns), 0.0)
        
        # simple non-zero variance
        returns = [0.01, -0.01, 0.02, -0.005]
        sharpe = calculate_annualized_sharpe(returns)
        self.assertGreater(sharpe, -100) # basic sanity

    def test_calculate_annualized_sortino(self):
        returns = [0.01, 0.02, 0.03]
        self.assertEqual(calculate_annualized_sortino(returns), 999.0) # no downside
        
        returns = [0.01, -0.01, 0.02, -0.005]
        sortino = calculate_annualized_sortino(returns)
        self.assertGreater(sortino, -100)

    def test_calculate_calmar_ratio(self):
        self.assertEqual(calculate_calmar_ratio(0.2, 0.1), 2.0)
        self.assertEqual(calculate_calmar_ratio(0.2, 0.0), 999.0)

    def test_calculate_recovery_factor(self):
        self.assertEqual(calculate_recovery_factor(500, 250), 2.0)
        self.assertEqual(calculate_recovery_factor(500, 0.0), 999.0)

    def test_calculate_profit_factor(self):
        trades = [100, -50, 200, -100]
        # profit sum = 300, loss sum = 150 -> PF = 2.0
        self.assertEqual(calculate_profit_factor(trades), 2.0)
        self.assertEqual(calculate_profit_factor([100, 200]), 999.0)
        self.assertEqual(calculate_profit_factor([-10, -20]), 0.0)

    def test_calculate_expectancy(self):
        trades = [100, -50, 100, -50]
        # winrate = 0.5, avgwin = 100, loserate = 0.5, avgloss = 50
        # expectancy = 0.5 * 100 - 0.5 * 50 = 25
        self.assertEqual(calculate_expectancy(trades), 25.0)
        self.assertEqual(calculate_expectancy([]), 0.0)

    def test_calculate_exposure_ratio(self):
        positions = [0.0, 1.5, 1.5, 0.0, 0.0, 2.0]
        # 3 out of 6 are active
        self.assertEqual(calculate_exposure_ratio(positions), 0.5)
        self.assertEqual(calculate_exposure_ratio([]), 0.0)

    def test_calculate_trade_frequency(self):
        start = datetime(2023, 1, 1)
        end = datetime(2023, 1, 11) # 10 days
        freq = calculate_trade_frequency(20, start, end)
        self.assertEqual(freq["trades_per_day"], 2.0)
        self.assertAlmostEqual(freq["trades_per_month"], 60.875, places=2)

if __name__ == "__main__":
    unittest.main()
