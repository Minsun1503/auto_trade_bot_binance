import unittest
from datetime import datetime, timedelta
import uuid

from portfolio.ledger import Ledger
from portfolio.position import Trade
from core.interfaces.execution_adapter import FillEvent
from backtest.engine import TradingEngine, ReconciliationMode, StrategyBase
from backtest.adapters.backtest_execution import BacktestExecutionAdapter
from backtest.execution import ExecutionMode

class MockStrategy(StrategyBase):
    def __init__(self):
        self.tracked_orders = set()
    def get_tracked_orders(self):
        return list(self.tracked_orders)
    def on_tick(self, tick, engine):
        pass
    def on_order_fill(self, order_id, side, price, quantity, engine):
        if order_id in self.tracked_orders:
            self.tracked_orders.remove(order_id)

class TestExecutionLifecycle(unittest.TestCase):
    def setUp(self):
        self.adapter = BacktestExecutionAdapter(mode=ExecutionMode.CONSERVATIVE)
        self.strategy = MockStrategy()
        self.engine = TradingEngine(
            initial_capital=1000.0,
            strategy=self.strategy,
            execution_adapter=self.adapter,
            symbol="BTC/USDT"
        )
        self.engine.reconciliation_mode = ReconciliationMode.STRICT

    def test_double_fill_prevention(self):
        """Bơm 2 FillEvent trùng trade_id -> Ignore/Lọc trùng."""
        order_id = self.engine.place_limit_order("BUY", 100.0, 1.0)
        self.strategy.tracked_orders.add(order_id)
        
        trade_id = "trd_123"
        fill1 = FillEvent(
            trade_id=trade_id, order_id=order_id, symbol="BTC/USDT", 
            side="BUY", price=100.0, quantity=1.0, 
            fee_amount=0.0, fee_asset="USDT", timestamp=int(datetime.now().timestamp() * 1000)
        )
        # Duplicate
        fill2 = FillEvent(
            trade_id=trade_id, order_id=order_id, symbol="BTC/USDT", 
            side="BUY", price=100.0, quantity=1.0, 
            fee_amount=0.0, fee_asset="USDT", timestamp=int(datetime.now().timestamp() * 1000)
        )
        
        self.engine.on_order_filled(fill1)
        self.engine.on_order_filled(fill2)
        
        # Sổ cái chỉ ghi nhận 1 trade
        self.assertEqual(len(self.engine.ledger.trades), 1)
        self.assertEqual(self.engine.ledger.rebuild_position("BTC/USDT").quantity, 1.0)

    def test_partial_fill(self):
        """Fill 0.3 BTC trước, 0.7 BTC sau -> Engine merge state, không xé lẻ order."""
        order_id = self.engine.place_limit_order("BUY", 100.0, 1.0)
        self.strategy.tracked_orders.add(order_id)
        
        # Giả lập adapter trả về 2 phần của cùng một lệnh
        fill1 = FillEvent(
            trade_id="trd_p1", order_id=order_id, symbol="BTC/USDT", 
            side="BUY", price=100.0, quantity=0.3, 
            fee_amount=0.0, fee_asset="USDT", timestamp=int(datetime.now().timestamp() * 1000)
        )
        fill2 = FillEvent(
            trade_id="trd_p2", order_id=order_id, symbol="BTC/USDT", 
            side="BUY", price=100.0, quantity=0.7, 
            fee_amount=0.0, fee_asset="USDT", timestamp=int(datetime.now().timestamp() * 1000)
        )
        
        self.engine.on_order_filled(fill1)
        # Strategy có thể xóa track sau partial fill tùy thiết kế, ta test Ledger
        self.assertEqual(self.engine.ledger.rebuild_position("BTC/USDT").quantity, 0.3)
        
        self.engine.on_order_filled(fill2)
        self.assertEqual(self.engine.ledger.rebuild_position("BTC/USDT").quantity, 1.0)
        self.assertEqual(len(self.engine.ledger.trades), 2)

    def test_fill_after_cancel(self):
        """Lệnh bị huỷ nhưng sàn vẫn trả Fill trễ -> Vẫn phải record Trade vào Ledger."""
        order_id = self.engine.place_limit_order("BUY", 100.0, 1.0)
        self.strategy.tracked_orders.add(order_id)
        
        self.engine.cancel_order(order_id)
        self.strategy.tracked_orders.remove(order_id)
        
        # Đột nhiên có fill tới
        fill = FillEvent(
            trade_id="trd_late", order_id=order_id, symbol="BTC/USDT", 
            side="BUY", price=100.0, quantity=1.0, 
            fee_amount=0.0, fee_asset="USDT", timestamp=int(datetime.now().timestamp() * 1000)
        )
        self.engine.on_order_filled(fill)
        
        # Position vẫn phải tăng vì lệnh thực sự đã khớp trên sàn
        self.assertEqual(self.engine.ledger.rebuild_position("BTC/USDT").quantity, 1.0)

    def test_reorder_fill(self):
        """Fill 2 về trước Fill 1 -> Ledger xử lý tuần tự không fail."""
        order_id = self.engine.place_limit_order("BUY", 100.0, 1.0)
        self.strategy.tracked_orders.add(order_id)
        
        # Giả sử 2 phần được khớp ở sàn
        t1 = datetime.now()
        t2 = t1 + timedelta(seconds=1)
        
        fill1 = FillEvent(
            trade_id="trd_1", order_id=order_id, symbol="BTC/USDT", 
            side="BUY", price=100.0, quantity=0.4, 
            fee_amount=0.0, fee_asset="USDT", timestamp=int(t1.timestamp() * 1000)
        )
        fill2 = FillEvent(
            trade_id="trd_2", order_id=order_id, symbol="BTC/USDT", 
            side="BUY", price=100.0, quantity=0.6, 
            fee_amount=0.0, fee_asset="USDT", timestamp=int(t2.timestamp() * 1000)
        )
        
        # Nhưng mạng làm packet tới ngược thứ tự
        self.engine.on_order_filled(fill2)
        self.engine.on_order_filled(fill1)
        
        self.assertEqual(self.engine.ledger.rebuild_position("BTC/USDT").quantity, 1.0)
        # Sổ cái sẽ có 2 trades
        self.assertEqual(len(self.engine.ledger.trades), 2)
        
        # Optional: We could sort Ledger by timestamp before calculating, but currently append-only works fine 
        # since position is built iteratively.
        # Ensure that no shorting exception happens if we process out of order (though this is a BUY so it's fine).

if __name__ == "__main__":
    unittest.main()
