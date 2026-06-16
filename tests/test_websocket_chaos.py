"""
test_websocket_chaos.py
=======================
Bộ test cho kiến trúc WebSocket Provider với 4 kịch bản:

1. WS mock vs backtest replay   → candle sequence phải khớp
2. Reconnect simulation          → 10s gap, không drift state
3. Lag injection                 → 1-3s delay, EventBuffer reorder đúng
4. Out-of-order fill + late candle close → không double PnL, không repaint
"""
import unittest
import time
import json
from datetime import datetime, timedelta

from backtest.engine import TradingEngine, ReconciliationMode
from backtest.adapters.backtest_execution import BacktestExecutionAdapter
from core.events import TickEvent
from core.interfaces.execution_adapter import FillEvent
from core.event_buffer import EventBuffer


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)

def make_tick(ts_ms: int, price: float = 40000.0, symbol: str = "BTCUSDT",
              is_closed: bool = True, source: str = "test") -> TickEvent:
    return TickEvent(
        timestamp=ts_ms, symbol=symbol,
        open=price, high=price + 10, low=price - 10, close=price,
        volume=1.0, is_closed=is_closed, source=source
    )

def make_kline_msg(open_time_ms: int, close_time_ms: int, close: float,
                   is_closed: bool = True, symbol: str = "BTCUSDT") -> dict:
    """Mô phỏng cấu trúc JSON message từ Binance WebSocket kline stream."""
    return {
        "e": "kline",
        "E": close_time_ms,
        "s": symbol,
        "k": {
            "t": open_time_ms,
            "T": close_time_ms,
            "s": symbol,
            "i": "1m",
            "o": str(close - 5),
            "h": str(close + 10),
            "l": str(close - 10),
            "c": str(close),
            "v": "1.5",
            "x": is_closed,
        }
    }

class DummyStrategy:
    def __init__(self):
        self.ticks_received = []
        self.tracked_orders = set()

    def on_tick(self, tick: TickEvent, engine: TradingEngine):
        self.ticks_received.append(tick.timestamp)

    def on_order_fill(self, order_id, side, fill_price, quantity, engine):
        self.tracked_orders.discard(order_id)

    def get_tracked_orders(self):
        return list(self.tracked_orders)


def _build_engine():
    strategy = DummyStrategy()
    adapter = BacktestExecutionAdapter(fee_rate=0.001)
    engine = TradingEngine(
        initial_capital=10000.0,
        strategy=strategy,
        execution_adapter=adapter,
        symbol="BTC/USDT"
    )
    engine.reconciliation_mode = ReconciliationMode.STRICT
    return engine, strategy, adapter


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: WS mock vs backtest replay (candle sequence phải khớp)
# ─────────────────────────────────────────────────────────────────────────────

class TestWSMockVsReplay(unittest.TestCase):
    def test_same_candle_sequence(self):
        """
        Cùng danh sách TickEvent được đưa vào theo 2 con đường:
          A) Bơm trực tiếp (historical replay)
          B) Đi qua WS mock parser (on_message)
        Kết quả: strategy nhận cùng 1 chuỗi timestamp.
        """
        base = _ms(datetime(2024, 1, 1, 12, 0, 0))
        prices = [40000.0, 40100.0, 39900.0, 40200.0, 40050.0]

        # ── Path A: Historical replay ──
        engine_a2, _, _ = _build_engine()
        engine_a2.event_buffer.window = 0  # Flush ngay lập tức
        closes_a2 = []
        engine_a2.strategy.on_tick = lambda tick, eng: closes_a2.append(tick.close)
        for i, p in enumerate(prices):
            ts = base + i * 60_000
            engine_a2.step(make_tick(ts, p, source="historical"))
        # Flush tick cuối cùng (nó nằm trong buffer vì window > 0 nếu không set)
        engine_a2._flush_buffer(base + len(prices) * 60_000 + 1)

        # ── Path B: WS mock parser ──
        from data.providers.binance_websocket import BinanceWebSocketProvider
        ws_prov = BinanceWebSocketProvider(symbol="BTCUSDT", interval="1m")
        closes_b = []
        ws_prov._callback = lambda tick: closes_b.append(tick.close)
        for i, p in enumerate(prices):
            open_ts = base + i * 60_000
            close_ts = open_ts + 59_999
            msg = make_kline_msg(open_ts, close_ts, p, is_closed=True)
            ws_prov._on_message(None, json.dumps(msg))

        self.assertEqual(closes_a2, closes_b,
                         "Historical và WS mock phải cho ra cùng chuỗi giá close")
        self.assertEqual(len(closes_a2), len(prices))

    def test_ws_drops_open_candles(self):
        """WS provider phải bỏ qua nến chưa đóng (is_closed=False)."""
        base = _ms(datetime(2024, 1, 1, 12, 0, 0))
        emitted = []

        from data.providers.binance_websocket import BinanceWebSocketProvider
        ws = BinanceWebSocketProvider(symbol="BTCUSDT", interval="1m")
        ws._callback = lambda t: emitted.append(t)

        # Gửi 5 update liên tục với is_closed=False
        for i in range(5):
            msg = make_kline_msg(base, base + 59_999, 40000.0 + i, is_closed=False)
            ws._on_message(None, json.dumps(msg))
        # Chỉ gửi 1 lần is_closed=True
        ws._on_message(None, json.dumps(make_kline_msg(base, base + 59_999, 40005.0, is_closed=True)))

        self.assertEqual(len(emitted), 1, "Chỉ nến đóng mới được emit vào Engine")
        self.assertTrue(emitted[0].is_closed)


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: EventBuffer Watermark — reject tick cũ (mô phỏng reconnect overlap)
# ─────────────────────────────────────────────────────────────────────────────

class TestReconnectNoStateDrift(unittest.TestCase):
    def test_watermark_rejects_old_ticks(self):
        """
        Sau khi engine đã xử lý tick đến T=base+5m,
        mọi tick cũ hơn đó phải bị EventBuffer reject.
        Ledger không được thay đổi sau reconnect.
        """
        base = _ms(datetime(2024, 1, 1, 12, 0, 0))
        engine, strategy, adapter = _build_engine()
        engine.event_buffer.window = 0
        engine.event_buffer.epsilon = 5_000  # 5s causal boundary

        # Gửi 5 ticks bình thường
        for i in range(5):
            engine.step(make_tick(base + i * 60_000, 40000.0))

        watermark_before = engine.event_buffer.engine_watermark
        ledger_trades_before = len(engine.ledger.trades)

        # Giả lập reconnect → Binance resend lại 3 candle cũ
        for i in range(3):
            ts_old = base + i * 60_000
            engine.event_buffer.push(
                event_type="TICK",
                timestamp=ts_old,
                payload=make_tick(ts_old, 40000.0),
                event_id=f"resend_{i}"  # event_id khác → qua dedup
            )

        # Flush buffer với current_time = watermark (sẽ không có gì ready)
        flushed = engine.event_buffer.flush_ready(watermark_before + 10_000)
        old_ticks = [e for e in flushed if e.timestamp < watermark_before - engine.event_buffer.epsilon]

        self.assertEqual(len(old_ticks), 0, "Tick cũ sau reconnect phải bị Causal Boundary chặn")
        self.assertEqual(len(engine.ledger.trades), ledger_trades_before,
                         "Ledger không thay đổi sau reconnect overlap")

    def test_dedup_by_symbol_timestamp_is_final(self):
        """
        Dedup key = symbol + open_time + is_final.
        Cùng candle (same timestamp) nhưng is_final khác nhau → 2 key khác nhau.
        Cùng key → chỉ xử lý 1 lần.
        """
        buf = EventBuffer(window_ms=0, epsilon_ms=10_000)
        base = _ms(datetime(2024, 1, 1, 12, 0, 0))

        tick_closed = make_tick(base, 40000.0, is_closed=True)
        tick_open = make_tick(base, 40005.0, is_closed=False)   # chưa đóng, key khác

        # Push tick đóng → chấp nhận
        buf.push("TICK", base, tick_closed)
        # Push tick đóng lại (duplicate) → bị chặn
        buf.push("TICK", base, tick_closed)
        # Push tick mở (key khác) → chấp nhận
        buf.push("TICK", base, tick_open)

        self.assertEqual(len(buf.events), 2, "1 tick đóng + 1 tick mở = 2 event trong buffer")


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Lag injection — EventBuffer reorder ticks đúng thứ tự
# ─────────────────────────────────────────────────────────────────────────────

class TestLagInjection(unittest.TestCase):
    def test_out_of_order_ticks_are_reordered(self):
        """
        Bơm 5 ticks theo thứ tự lộn xộn (lag injection).
        EventBuffer phải flush chúng theo thứ tự timestamp tăng dần.
        """
        base = _ms(datetime(2024, 1, 1, 12, 0, 0))
        buf = EventBuffer(window_ms=500, epsilon_ms=10_000)

        # Timestamps lộn xộn
        out_of_order = [
            base + 4 * 60_000,
            base + 2 * 60_000,
            base + 0 * 60_000,
            base + 3 * 60_000,
            base + 1 * 60_000,
        ]
        for ts in out_of_order:
            buf.push("TICK", ts, make_tick(ts, 40000.0))

        # Flush với current_time đủ lớn để tất cả sẵn sàng
        current_time = base + 10 * 60_000
        ready = buf.flush_ready(current_time)
        flushed_timestamps = [e.timestamp for e in ready]

        self.assertEqual(flushed_timestamps, sorted(out_of_order),
                         "EventBuffer phải flush theo thứ tự timestamp tăng dần")


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Out-of-order Fill + Late Candle Close → Không double PnL
# ─────────────────────────────────────────────────────────────────────────────

class TestOutOfOrderFillLateCandleClose(unittest.TestCase):
    def test_no_double_pnl_on_late_fill(self):
        """
        Kịch bản:
          T1: Nến mở, đặt lệnh BUY
          T2: Fill xảy ra (FillEvent bơm vào buffer)
          T3: Nến cùng timestamp T1 bị update lại (late kline update — mô phỏng Binance resend)
          T4: Nến mới T1+1m đến để flush buffer

        Kỳ vọng:
          - Ledger chỉ ghi nhận 1 trade (không double)
          - Position quantity đúng 1.0 (không bị double)
        """
        base = _ms(datetime(2024, 1, 1, 12, 0, 0))
        engine, strategy, adapter = _build_engine()
        engine.event_buffer.window = 500
        engine.event_buffer.epsilon = 10_000

        # T1: nến đầu tiên
        tick_t1 = make_tick(base, 40000.0)
        engine.step(tick_t1)

        # Đặt lệnh BUY và giả lập fill từ Exchange
        order_id = engine.place_limit_order("BUY", 40000.0, 1.0)
        strategy.tracked_orders.add(order_id)
        del adapter.active_orders[order_id]  # Exchange đã khớp

        trade_id = "trd_test_001"
        fill = FillEvent(
            trade_id=trade_id,
            order_id=order_id,
            symbol="BTC/USDT",
            side="BUY",
            price=40000.0,
            quantity=1.0,
            fee_amount=40.0,
            fee_asset="USDT",
            timestamp=base + 30_000
        )
        engine._route_fill_to_buffer(fill)
        adapter.trade_history.append({
            "trade_id": trade_id, "order_id": order_id,
            "symbol": "BTC/USDT", "side": "BUY",
            "price": 40000.0, "quantity": 1.0,
            "fee_amount": 40.0, "fee_asset": "USDT",
            "timestamp": base + 30_000
        })

        # T2: Binance resend lại cùng kline (late update, cùng open_time)
        # Dedup key giống nhau → bị chặn
        tick_t1_resend = make_tick(base, 40010.0, source="binance_ws")
        engine._route_fill_to_buffer  # không push tick_t1_resend vào engine
        # Simulate: WS provider gọi _process_kline cho cùng open_time → dedup chặn
        from data.providers.binance_websocket import BinanceWebSocketProvider
        ws = BinanceWebSocketProvider("BTCUSDT", "1m")
        collected = []
        ws._callback = lambda t: collected.append(t)
        # Gửi cùng 1 candle 2 lần (is_closed=True cùng open_time)
        msg = make_kline_msg(base, base + 59_999, 40010.0, is_closed=True)
        ws._on_message(None, json.dumps(msg))
        ws._on_message(None, json.dumps(msg))  # Duplicate
        self.assertEqual(len(collected), 1, "WS dedup tại source: duplicate candle bị chặn")

        # T4: tick mới đến → flush buffer, xử lý FillEvent
        tick_t2 = make_tick(base + 60_000, 40010.0)
        engine.step(tick_t2)

        # Assert: Ledger chỉ 1 trade
        pos = engine.ledger.rebuild_position("BTC/USDT")
        self.assertAlmostEqual(pos.quantity, 1.0, places=6,
                               msg="Quantity phải đúng 1.0, không bị double fill")
        self.assertEqual(len(engine.ledger.trades), 1,
                         "Ledger chỉ ghi nhận đúng 1 trade")

        # Thử push duplicate fill vào buffer → bị chặn
        fill_dup = FillEvent(
            trade_id=trade_id,  # Cùng trade_id
            order_id=order_id,
            symbol="BTC/USDT", side="BUY",
            price=40000.0, quantity=1.0,
            fee_amount=40.0, fee_asset="USDT",
            timestamp=base + 30_000
        )
        engine._route_fill_to_buffer(fill_dup)
        tick_t3 = make_tick(base + 2 * 60_000, 40020.0)
        engine.step(tick_t3)

        pos_after = engine.ledger.rebuild_position("BTC/USDT")
        self.assertAlmostEqual(pos_after.quantity, 1.0, places=6,
                               msg="Sau duplicate fill: quantity vẫn phải là 1.0")
        self.assertEqual(len(engine.ledger.trades), 1,
                         "Sau duplicate fill: Ledger vẫn chỉ 1 trade")


if __name__ == "__main__":
    unittest.main()
