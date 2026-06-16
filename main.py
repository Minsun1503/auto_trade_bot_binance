import argparse
from datetime import datetime
import collections

from config.settings import load_settings_from_env
from strategies.state import BotState
from strategies.context import MarketContext
from strategies.grid_strategy import GridStrategy
from strategies.dca_strategy import DCAStrategy
from strategies.coordinator import Coordinator
from backtest.engine import TradingEngine, StrategyBase
from backtest.adapters.backtest_execution import BacktestExecutionAdapter
from backtest.execution import ExecutionMode
from core.events import EventBus, TickEvent
from data.providers.binance_historical import BinanceHistoricalProvider
from core.runner import EngineRunner

class CoordinatorBacktestAdapter(StrategyBase):
    """Adapter để nhúng Coordinator vào TradingEngine"""
    def __init__(self, coordinator: Coordinator):
        self.coordinator = coordinator
        self.prices = collections.deque(maxlen=200)
        self.max_high = 0.0
        
    def on_tick(self, tick: TickEvent, engine: TradingEngine):
        price = tick.close
        self.prices.append(price)
        
        if tick.high > self.max_high:
            self.max_high = tick.high
            
        ma50 = sum(list(self.prices)[-50:]) / min(50, len(self.prices)) if self.prices else price
        ma200 = sum(list(self.prices)[-200:]) / min(200, len(self.prices)) if self.prices else price
        
        drawdown = (self.max_high - price) / self.max_high if self.max_high > 0 else 0.0
        spread = (tick.high - tick.low) / tick.low if tick.low > 0 else 0.0
        
        context = MarketContext(
            price=price,
            ma50=ma50,
            ma200=ma200,
            drawdown=drawdown,
            volatility=0.0,
            spread=spread
        )
        self.coordinator.evaluate(context, tick.timestamp, engine)

    def on_order_fill(self, order_id: str, side: str, fill_price: float, quantity: float, engine: TradingEngine):
        self.coordinator.on_order_fill(order_id, side, fill_price, quantity, engine)

    def get_tracked_orders(self) -> list[str]:
        return self.coordinator.get_tracked_orders()

def _build_engine_and_runner(symbol: str, use_ui: bool, replay_file: str = None) -> tuple:
    """Factory: tạo TradingEngine + EngineRunner dùng chung cho mọi mode."""
    settings = load_settings_from_env()
    grid = GridStrategy(settings.grid)
    dca = DCAStrategy(settings.dca)
    event_bus = EventBus() if use_ui else EventBus()
    coordinator = Coordinator(grid, dca, settings.coordinator, event_bus=event_bus)
    adapter = CoordinatorBacktestAdapter(coordinator)
    execution_adapter = BacktestExecutionAdapter(mode=ExecutionMode.CONSERVATIVE)
    engine = TradingEngine(
        initial_capital=10000.0,
        strategy=adapter,
        execution_adapter=execution_adapter,
        symbol=symbol
    )
    engine.event_bus = event_bus
    if replay_file:
        import json
        with open(replay_file, 'r', encoding='utf-8') as f:
            snapshot_data = json.load(f)
        engine.load_snapshot(snapshot_data)
        print(f"Loaded snapshot from {replay_file}.")
    runner = EngineRunner(engine, event_bus)
    return engine, runner, coordinator, event_bus

def run_backtest(symbol: str, parquet_path: str, use_ui: bool = False, replay_file: str = None, replay_speed: float = 0.0):
    import os
    if not os.path.exists(parquet_path):
        print(f"File {parquet_path} không tồn tại. Vui lòng chạy scripts/fetch_binance_data.py trước.")
        return
    engine, runner, coordinator, event_bus = _build_engine_and_runner(symbol, use_ui, replay_file)
    if replay_speed > 0:
        provider = BinanceHistoricalProvider(parquet_path, realtime_sim=True, speed_multiplier=replay_speed)
    else:
        provider = BinanceHistoricalProvider(parquet_path)
    if use_ui:
        from ui.dashboard import DashboardApp
        app = DashboardApp(event_bus, runner)
        runner.start(provider)
        app.run()
    else:
        runner.start(provider)
        runner.wait()
        start_date = datetime.fromtimestamp(provider._df['timestamp'].iloc[0] / 1000.0)
        end_date = datetime.fromtimestamp(provider._df['timestamp'].iloc[-1] / 1000.0)
        result = engine.generate_result(start_date, end_date)
        result.print_summary()

def run_warmup_live(symbol: str, parquet_path: str, ws_symbol: str, interval: str = "1m", use_ui: bool = False, replay_file: str = None):
    """
    Mode B: Warmup → Live Handover
    ===================================
    Phase 1 (Warmup): Đọc Parquet (historical) để warm up các chỉ số (MA50, MA200).
    Phase 2 (Live):   Handover sang BinanceWebSocketProvider.
    
    Hard Boundary: market_watermark sau warmup trở thành "fence" tự động.
    Binance WS chỉ được accept tick có timestamp > watermark (do EngineRunner guard).
    """
    import os
    if not os.path.exists(parquet_path):
        print(f"Không tìm thấy {parquet_path}. Chạy fetch_binance_data.py trước.")
        return

    engine, runner, coordinator, event_bus = _build_engine_and_runner(symbol, use_ui, replay_file)

    # ---- Phase 1: Warmup (Historical, chạy nhanh) ----
    print(f"[DUAL-MODE] Phase 1/2: Warmup từ {parquet_path} ...")
    warmup_provider = BinanceHistoricalProvider(parquet_path)
    runner.start(warmup_provider)
    runner.wait()
    warmup_watermark = runner.market_watermark
    print(f"[DUAL-MODE] Warmup xong. Watermark = {warmup_watermark} ({datetime.fromtimestamp(warmup_watermark / 1000)})")

    # ---- Phase 2: Handover sang WebSocket ----
    print(f"[DUAL-MODE] Phase 2/2: Kết nối WebSocket {ws_symbol}@kline_{interval} ...")
    print(f"[DUAL-MODE] Tất cả tick có timestamp <= {warmup_watermark} sẽ bị tự động reject.")
    from data.providers.binance_websocket import BinanceWebSocketProvider
    ws_provider = BinanceWebSocketProvider(symbol=ws_symbol, interval=interval)
    
    # Runner giữ nguyên market_watermark từ Phase 1 — đảm bảo hard boundary
    runner._stop_requested = False
    runner._status = "RUNNING"
    runner.provider = ws_provider
    ws_provider.subscribe(runner.on_tick)

    import threading
    runner._provider_thread = threading.Thread(target=ws_provider.start, daemon=True)
    runner._provider_thread.start()
    runner._thread = threading.Thread(target=runner._run_loop, daemon=True, name="engine-loop")
    runner._thread.start()

    if use_ui:
        from ui.dashboard import DashboardApp
        app = DashboardApp(event_bus, runner)
        app.run()
    else:
        print("[DUAL-MODE] Ang chề stream... (Ctrl+C để dừng)")
        try:
            while runner._provider_thread.is_alive():
                import time; time.sleep(1)
        except KeyboardInterrupt:
            print("\n[DUAL-MODE] Dừng thủ công. Lưu Snapshot...")
            runner.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trade Bot - Binance Grid/DCA")
    parser.add_argument('--mode',
        choices=['backtest', 'warmup+live', 'testnet', 'live'],
        default='backtest',
        help='backtest=historical only, warmup+live=historical warmup then websocket'
    )
    parser.add_argument('--symbol', default='BTCUSDT', help='VD: BTCUSDT')
    parser.add_argument('--parquet', default='data/storage/BTCUSDT_1m_7d.parquet')
    parser.add_argument('--interval', default='1m', help='WS interval: 1m, 5m...')
    parser.add_argument('--ui', action='store_true')
    parser.add_argument('--replay', type=str, default=None)
    parser.add_argument('--replay-speed', type=float, default=0.0)

    args = parser.parse_args()
    # Normalize symbol: BTC/USDT -> BTCUSDT
    ws_symbol = args.symbol.replace('/', '')
    engine_symbol = args.symbol if '/' in args.symbol else args.symbol[:3] + '/' + args.symbol[3:]

    if args.mode == 'backtest':
        run_backtest(engine_symbol, args.parquet, args.ui, args.replay, args.replay_speed)
    elif args.mode == 'warmup+live':
        run_warmup_live(engine_symbol, args.parquet, ws_symbol, args.interval, args.ui, args.replay)
    else:
        print(f"Mode '{args.mode}' chua duoc implement.")
