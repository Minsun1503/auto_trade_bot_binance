import unittest
from backtest.monte_carlo import calculate_avg_losing_streak, run_monte_carlo_simulation

class TestMonteCarlo(unittest.TestCase):
    def test_calculate_avg_losing_streak(self):
        # 1 win, 2 loss, 1 win, 3 loss -> losing streaks: [2, 3] -> mean = 2.5
        trades = [10.0, -5.0, -10.0, 15.0, -2.0, -3.0, -5.0]
        self.assertEqual(calculate_avg_losing_streak(trades), 2.5)
        
        # All wins
        self.assertEqual(calculate_avg_losing_streak([10.0, 20.0]), 1.0)
        
        # Empty
        self.assertEqual(calculate_avg_losing_streak([]), 1.0)

    def test_run_monte_carlo_simulation(self):
        trades = [10.0, -50.0, 20.0, -100.0, 50.0, -20.0]
        initial_capital = 200.0
        
        result1 = run_monte_carlo_simulation(trades, initial_capital, num_simulations=100, random_seed=42)
        result2 = run_monte_carlo_simulation(trades, initial_capital, num_simulations=100, random_seed=42)
        
        # Check reproducibility
        self.assertEqual(result1["p50_dd"], result2["p50_dd"])
        self.assertEqual(result1["p95_dd"], result2["p95_dd"])
        self.assertEqual(result1["worst_dd"], result2["worst_dd"])
        self.assertEqual(result1["prob_dd_25"], result2["prob_dd_25"])
        self.assertEqual(result1["prob_dd_50"], result2["prob_dd_50"])
        
        # Sanity check values
        self.assertGreaterEqual(result1["p95_dd"], 0.0)
        self.assertLessEqual(result1["p95_dd"], 1.0)
        self.assertGreaterEqual(result1["prob_dd_25"], 0.0)
        self.assertLessEqual(result1["prob_dd_25"], 1.0)

if __name__ == "__main__":
    unittest.main()
