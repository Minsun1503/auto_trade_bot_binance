import unittest
from datetime import datetime, timedelta
import pandas as pd
import random
import uuid

from backtest.engine import TradingEngine, ReconciliationMode
from backtest.adapters.backtest_execution import BacktestExecutionAdapter
from core.interfaces.execution_adapter import FillEvent

class DummyStrategy:
    def __init__(self):
        self.tracked_orders = set()
        
    def on_tick(self, tick, engine: TradingEngine):
        pass
        
    def on_order_fill(self, order_id: str, side: str, fill_price: float, quantity: float, engine: TradingEngine):
        if order_id in self.tracked_orders:
            self.tracked_orders.remove(order_id)
            
    def get_tracked_orders(self) -> list[str]:
        return list(self.tracked_orders)

class TestChaosExecution(unittest.TestCase):
    def setUp(self):
        self.strategy = DummyStrategy()
        self.adapter = BacktestExecutionAdapter(fee_rate=0.0)
        # Tắt simulation tự động của adapter vì ta sẽ tự bơm FillEvent
        self.adapter.simulator.simulate_limit_buy = lambda p, c: False
        self.adapter.simulator.simulate_limit_sell = lambda p, c: False
        
        self.engine = TradingEngine(
            initial_capital=100000.0,
            strategy=self.strategy,
            execution_adapter=self.adapter,
            symbol="BTC/USDT"
        )
        self.engine.reconciliation_mode = ReconciliationMode.STRICT
        self.engine.event_buffer.window = 500
        self.engine.event_buffer.epsilon = 5000

    def test_chaos_split_fills_and_teleport(self):
        # Tạo 500 order xen kẽ
        orders = []
        for i in range(500):
            side = "BUY" if i % 2 == 0 else "SELL"
            # Limit order
            order_id = self.engine.place_limit_order(side, price=40000.0, quantity=1.0)
            self.strategy.tracked_orders.add(order_id)
            orders.append({"id": order_id, "side": side})

        # Giờ ta sẽ tạo một loạt các FillEvent và TickEvent hỗn loạn
        # Tick base:
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        
        # Sát thủ 1: Time Teleport Bug (Tick nhảy cóc)
        # Ta sẽ bơm các Tick lộn xộn, nhưng EngineBuffer sẽ sắp xếp lại.
        ticks = [
            (base_time + timedelta(seconds=0), 40000),
            (base_time + timedelta(seconds=2), 40001),
            (base_time + timedelta(seconds=1), 40002), # Nhảy ngược
            (base_time + timedelta(seconds=4), 40003),
            (base_time + timedelta(seconds=3), 40004), # Nhảy ngược
        ]
        
        # Sát thủ 2: Split fill (partial fill) và Out-of-order fill
        # Lấy order đầu tiên (BUY)
        split_order = orders[0]
        # Bơm 3 mảnh (0.2, 0.5, 0.3) với timestamp lộn xộn
        # Mảnh 3 (0.3)
        self.engine._route_fill_to_buffer(FillEvent(
            trade_id="split_3", order_id=split_order["id"], symbol="BTC/USDT", side="BUY",
            price=40000.0, quantity=0.3, fee_amount=0.0, fee_asset="USDT",
            timestamp=int((base_time + timedelta(milliseconds=150)).timestamp() * 1000)
        ))
        # Mảnh 1 (0.2)
        self.engine._route_fill_to_buffer(FillEvent(
            trade_id="split_1", order_id=split_order["id"], symbol="BTC/USDT", side="BUY",
            price=40000.0, quantity=0.2, fee_amount=0.0, fee_asset="USDT",
            timestamp=int((base_time + timedelta(milliseconds=50)).timestamp() * 1000)
        ))
        # Mảnh 2 (0.5)
        self.engine._route_fill_to_buffer(FillEvent(
            trade_id="split_2", order_id=split_order["id"], symbol="BTC/USDT", side="BUY",
            price=40000.0, quantity=0.5, fee_amount=0.0, fee_asset="USDT",
            timestamp=int((base_time + timedelta(milliseconds=100)).timestamp() * 1000)
        ))
        # Sát thủ 3: Duplicate fill (Mảnh 1 bị duplicate 3 lần)
        for _ in range(3):
            self.engine._route_fill_to_buffer(FillEvent(
                trade_id="split_1", order_id=split_order["id"], symbol="BTC/USDT", side="BUY",
                price=40000.0, quantity=0.2, fee_amount=0.0, fee_asset="USDT",
                timestamp=int((base_time + timedelta(milliseconds=50)).timestamp() * 1000)
            ))
            
        # Sát thủ 4: Negative Event Injection (Cancel rồi Fill)
        # Order 2 (SELL) bị cancel
        neg_order = orders[1]
        print(f"SPLIT ORDER: {split_order['id']}")
        print(f"NEG ORDER: {neg_order['id']}")
        self.engine.cancel_order(neg_order["id"]) # Adapter xoá order
        self.strategy.tracked_orders.remove(neg_order["id"]) # Cập nhật strategy
        
        # Xóa split_order khỏi adapter vì nó sẽ được fill đầy
        if split_order["id"] in self.adapter.active_orders:
            del self.adapter.active_orders[split_order["id"]]
        
        # ... nhưng Fill trễ lại chui vào buffer!
        self.engine._route_fill_to_buffer(FillEvent(
            trade_id="neg_fill_1", order_id=neg_order["id"], symbol="BTC/USDT", side="SELL",
            price=40000.0, quantity=1.0, fee_amount=0.0, fee_asset="USDT",
            timestamp=int((base_time + timedelta(milliseconds=300)).timestamp() * 1000)
        ))
        
        from core.events import TickEvent
        # Process Ticks để đẩy flush_buffer
        for ts, price in ticks:
            tick = TickEvent(
                timestamp=int(ts.timestamp() * 1000),
                symbol="BTC/USDT", open=price, high=price, low=price, close=price, volume=0.0,
                is_closed=True, source="synthetic"
            )
            self.engine.step(tick)
            
        # Chạy một tick cuối cách xa để flush toàn bộ buffer
        final_ts = base_time + timedelta(seconds=10)
        final_tick = TickEvent(
            timestamp=int(final_ts.timestamp() * 1000),
            symbol="BTC/USDT", open=40000, high=40000, low=40000, close=40000, volume=0.0,
            is_closed=True, source="synthetic"
        )
        self.engine.step(final_tick)
        
        # Verify:
        # Order 0: Buy 1.0 (từ 3 split_1, split_2, split_3)
        # Order 1: Sell 1.0 (từ negative event - cancel nhưng fill tới)
        # Kết quả Ledger: Quantity = 0 (1 mua - 1 bán)
        # Các order còn lại chưa khớp
        
        pos = self.engine.ledger.rebuild_position("BTC/USDT")
        
        # Mua 1.0, Bán 1.0 => quantity = 0.0
        self.assertAlmostEqual(pos.quantity, 0.0)
        
        # Kiểm tra trades
        trades = self.engine.ledger.trades
        self.assertEqual(len(trades), 4) # split_1, split_2, split_3, neg_fill_1
        
        # Đảm bảo Double Fill bị chặn (split_1 xuất hiện 4 lần nhưng trade ghi nhận 1 lần)
        split_1_count = sum(1 for t in trades if t.trade_id == "split_1")
        self.assertEqual(split_1_count, 1)

if __name__ == '__main__':
    unittest.main()
