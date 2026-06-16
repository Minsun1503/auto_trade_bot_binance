import threading
import time
import queue
import logging
import json
import os
from datetime import datetime
from backtest.engine import TradingEngine
from core.events import EventBus, CommandEvent, LogEvent, SystemHealthEvent, TickEvent

from core.interfaces.data_provider import MarketDataProvider

class EngineRunner:
    def __init__(self, engine: TradingEngine, event_bus: EventBus):
        self.engine = engine
        self.event_bus = event_bus
        self._thread = None
        self._provider_thread = None
        self._is_paused = False
        self._stop_requested = False
        self._status = "STOPPED"
        self._last_tick_time = None
        self.provider = None
        
        # Global Market Watermark: Single source of truth cho tiến trình thời gian
        # Mọi tick từ bất kỳ Provider nào đều phải vượt qua ngưỡng này
        self.market_watermark: int = 0
        
        import queue
        self.command_queue = queue.Queue()
        self.tick_queue = queue.Queue(maxsize=1000)
        
    def start(self, provider: MarketDataProvider):
        self._status = "RUNNING"
        self._stop_requested = False
        self.provider = provider
        self.provider.subscribe(self.on_tick)
        
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        self._provider_thread = threading.Thread(target=self.provider.start, daemon=True)
        self._provider_thread.start()
        
    def on_tick(self, tick: TickEvent):
        # Global Watermark Guard: loại bỏ tick cũ từ bất kỳ Provider nào
        # Đây là hàng phòng thủ đầu tiên chống drift giữa Historical và WebSocket
        if tick.timestamp <= self.market_watermark:
            logger.debug(
                f"[RUNNER] Tick bị reject (watermark): {tick.symbol} ts={tick.timestamp} "
                f"<= watermark={self.market_watermark} source={tick.source}"
            )
            return
        # Blocking put enables backpressure to the Provider thread
        while not self._stop_requested:
            try:
                self.tick_queue.put(tick, timeout=0.5)
                break
            except queue.Full:
                continue
        
    def pause(self):
        if not self._is_paused:
            self._is_paused = True
            self._status = "PAUSED"
            self.event_bus.publish(LogEvent(message="ENGINE PAUSED", level="WARNING"))
        
    def resume(self):
        if self._is_paused:
            self._is_paused = False
            self._status = "RUNNING"
            self.event_bus.publish(LogEvent(message="ENGINE RESUMED", level="INFO"))
        
    def stop(self):
        self._stop_requested = True
        if self.provider:
            self.provider.stop()
        self._status = "STOPPING"
        
    def wait(self):
        if self._provider_thread and self._provider_thread.is_alive():
            self._provider_thread.join(timeout=2.0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._status = "STOPPED"
        
    def process_command(self, cmd: CommandEvent):
        self.command_queue.put(cmd)
            
    def _save_snapshot(self):
        if not os.path.exists("snapshots"):
            os.makedirs("snapshots")
        filename = f"snapshots/snapshot_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}.json"
        
        pos = self.engine.ledger.rebuild_position(self.engine.symbol)
        last_price = self.engine.last_price
        
        data_core = {
            "schema_version": 1,
            "created_at": datetime.now().isoformat(),
            "state": self.engine.strategy.coordinator.state.name if hasattr(self.engine.strategy, 'coordinator') else "UNKNOWN",
            "cash": self.engine.ledger.cash,
            "positions": {
                pos.symbol: {
                    "quantity": pos.quantity,
                    "avg_price": pos.avg_price
                }
            } if pos.quantity > 0 else {},
            "orders": self.engine.get_active_orders(),
            "trades": self.engine.execution_adapter.get_trade_history(self.engine.symbol),
            "equity": self.engine.ledger.get_total_equity({self.engine.symbol: last_price}),
            "peak_equity": self.engine.peak_equity,
            "max_drawdown": self.engine.max_drawdown
        }
        
        import hashlib
        checksum_str = json.dumps(data_core, sort_keys=True)
        checksum = hashlib.sha256(checksum_str.encode()).hexdigest()
        
        data_core["checksum"] = checksum
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data_core, f, indent=4)
            
        self.event_bus.publish(LogEvent(message=f"SNAPSHOT SAVED: {filename}", level="INFO"))
            
    def publish_health(self):
        self.event_bus.publish(SystemHealthEvent(
            queue_size=self.event_bus.queue.qsize(),
            engine_status=self._status,
            last_tick=self._last_tick_time
        ))

    def _run_loop(self):
        import queue
        self.publish_health()
        
        is_first_tick = True
        
        while not self._stop_requested:
            # Process pending commands
            while not self.command_queue.empty():
                cmd = self.command_queue.get()
                if cmd.command == "PAUSE": self.pause()
                elif cmd.command == "RESUME": self.resume()
                elif cmd.command == "SNAPSHOT": self._save_snapshot()
                elif cmd.command == "QUIT": self.stop()
                
            if self._is_paused:
                time.sleep(0.1)
                continue
                
            try:
                tick = self.tick_queue.get(timeout=0.1)
                
                if is_first_tick:
                    self.engine.buy_price_bh = tick.close
                    self.engine.quantity_bh = self.engine.initial_capital / self.engine.buy_price_bh
                    is_first_tick = False
                    
                self.engine.step(tick)
                self._last_tick_time = tick.timestamp
                # Cập nhật market_watermark monotonically sau khi Engine đã xử lý tick
                if tick.timestamp > self.market_watermark:
                    self.market_watermark = tick.timestamp
                
            except queue.Empty:
                # If provider stopped and queue empty, we are done
                if self.provider and getattr(self.provider, '_stop_requested', False) and self.tick_queue.empty():
                    break
                continue
            
        if not self._stop_requested:
            self._status = "COMPLETED"
        self.publish_health()
