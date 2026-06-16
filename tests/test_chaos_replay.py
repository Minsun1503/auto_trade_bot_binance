import unittest
import os
import json
from datetime import datetime, timedelta
import pandas as pd

from backtest.engine import TradingEngine, ReconciliationMode
from backtest.adapters.backtest_execution import BacktestExecutionAdapter
from core.events import EventBus
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

class TestChaosReplay(unittest.TestCase):
    def test_replay_under_chaos(self):
        # Thiết lập 2 engine: 1 engine gốc (crash ngang), 1 engine replay
        strategy = DummyStrategy()
        adapter = BacktestExecutionAdapter(fee_rate=0.0)
        
        engine = TradingEngine(
            initial_capital=10000.0,
            strategy=strategy,
            execution_adapter=adapter,
            symbol="BTC/USDT"
        )
        engine.reconciliation_mode = ReconciliationMode.STRICT
        # Window cực lớn để cố tình giam các fills trong Buffer
        engine.event_buffer.window = 10000
        
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        
        # 1. Đặt 2 orders
        o1 = engine.place_limit_order("BUY", 40000.0, 1.0)
        o2 = engine.place_limit_order("BUY", 39000.0, 1.0)
        strategy.tracked_orders.add(o1)
        strategy.tracked_orders.add(o2)
        
        # Thay vì chờ Simulator khớp (vì TICK bị buffer giữ), ta giả lập Live Exchange
        # Live Exchange khớp o1, xoá khỏi Adapter, thêm vào trade_history, và bắn FillEvent.
        del adapter.active_orders[o1]
        
        trade_id_o1 = "trd_live_123"
        adapter.trade_history.append({
            "trade_id": trade_id_o1,
            "order_id": o1,
            "symbol": "BTC/USDT",
            "side": "BUY",
            "price": 40000.0,
            "quantity": 1.0,
            "fee_amount": 0.0,
            "fee_asset": "USDT",
            "timestamp": int(base_time.timestamp() * 1000)
        })
        
        # Bắn FillEvent vào Buffer
        fill = FillEvent(
            trade_id=trade_id_o1,
            order_id=o1,
            symbol="BTC/USDT",
            side="BUY",
            price=40000.0,
            quantity=1.0,
            fee_amount=0.0,
            fee_asset="USDT",
            timestamp=int(base_time.timestamp() * 1000)
        )
        engine._route_fill_to_buffer(fill)
        
        # Lúc này Adapter ĐÃ mất o1, Buffer ĐANG GIỮ o1 fill, Strategy VẪN GIỮ o1, Ledger = 0.
        self.assertEqual(len(engine.get_active_orders()), 1) # Chỉ còn o2
        self.assertEqual(len(strategy.get_tracked_orders()), 2) # o1, o2
        self.assertEqual(engine.ledger.rebuild_position("BTC/USDT").quantity, 0.0)
        
        # 3. Chụp SNAPSHOT ngay lúc này! (Không lưu Buffer)
        import hashlib
        data_core = {
            "schema_version": 1,
            "cash": engine.ledger.cash,
            "positions": {},
            "orders": engine.get_active_orders(),
            "trades": adapter.get_trade_history("BTC/USDT"),
            "equity": engine.initial_capital
        }
        checksum_str = json.dumps(data_core, sort_keys=True)
        data_core["checksum"] = hashlib.sha256(checksum_str.encode()).hexdigest()
        
        # 4. KHỞI ĐỘNG LẠI (Replay) bằng Engine mới
        strategy_new = DummyStrategy()
        strategy_new.tracked_orders.add(o1)
        strategy_new.tracked_orders.add(o2) # Ta coi như Strategy lưu persistent state riêng
        
        adapter_new = BacktestExecutionAdapter(fee_rate=0.0)
        engine_new = TradingEngine(
            initial_capital=10000.0,
            strategy=strategy_new,
            execution_adapter=adapter_new,
            symbol="BTC/USDT"
        )
        engine_new.reconciliation_mode = ReconciliationMode.STRICT
        engine_new.event_buffer.window = 1000 # Trở về bth
        
        # Load snapshot
        engine_new.load_snapshot(data_core)
        
        # Verify trạng thái khôi phục
        # Vì o1 đã khớp ở engine cũ, nhưng FillEvent chưa kịp xử lý do nằm trong Buffer.
        # Khi restore, _sync_with_exchange sẽ phát hiện trade của o1 trong trade_history nhưng chưa có ở Ledger!
        # Nên nó sẽ phục hồi o1, gọi on_order_filled, cập nhật Ledger.
        # Vậy: 
        # 1. Adapter active orders: 1 (chỉ còn o2)
        self.assertEqual(len(engine_new.get_active_orders()), 1)
        self.assertIn(o2, [o['id'] for o in engine_new.get_active_orders()])
        
        # 2. Strategy: Đã xử lý o1, nên chỉ còn theo dõi o2
        self.assertEqual(len(strategy_new.get_tracked_orders()), 1)
        self.assertIn(o2, strategy_new.get_tracked_orders())
        
        # 3. Ledger: Đã ghi nhận 1.0 BTC của o1!
        pos = engine_new.ledger.rebuild_position("BTC/USDT")
        self.assertAlmostEqual(pos.quantity, 1.0)
        self.assertEqual(len(engine_new.ledger.trades), 1)
        
        # 4. Idempotency: Nếu ta đẩy lại y chang 1 event cũ từ Buffer cũ bị kẹt vào Engine mới (Duplicate)
        trade_id = engine_new.ledger.trades[0].trade_id
        old_fill = FillEvent(
            trade_id=trade_id, # Cố tình trùng ID
            order_id=o1,
            symbol="BTC/USDT",
            side="BUY",
            price=40000.0,
            quantity=1.0,
            fee_amount=0.0,
            fee_asset="USDT",
            timestamp=int(base_time.timestamp() * 1000)
        )
        engine_new._route_fill_to_buffer(old_fill)
        
        # Chạy 1 tick để flush
        from core.events import TickEvent
        tick2 = TickEvent(
            timestamp=int((base_time + timedelta(seconds=20)).timestamp() * 1000),
            symbol="BTC/USDT",
            open=39500, high=39500, low=39500, close=39500, volume=0.0,
            is_closed=True, source="synthetic"
        )
        engine_new.step(tick2)
        
        # Verify KHÔNG BỊ DOUBLE FILL
        pos_after = engine_new.ledger.rebuild_position("BTC/USDT")
        self.assertAlmostEqual(pos_after.quantity, 1.0) # Vẫn 1.0
        self.assertEqual(len(engine_new.ledger.trades), 1) # Vẫn 1 trade

if __name__ == '__main__':
    unittest.main()
