"""
Phase 3.5D - Validation Runner & Checksum Manifest
Điều phối toàn bộ quy trình chạy backtest In-Sample (IS), Out-of-Sample (OOS), và Holdout Set.
Kiểm tra các cổng Hard Gates, tính toán mã checksum SHA-256 từ manifest file.
"""
import os
import json
import hashlib
from typing import Dict, List, Any, Type, Callable
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np

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
from backtest.benchmarks.buy_hold import run_buy_and_hold
from backtest.benchmarks.daily_dca import run_daily_dca
from backtest.monte_carlo import run_monte_carlo_simulation
from backtest.engine import TradingEngine, StrategyBase
from core.events import TickEvent
from core.interfaces.execution_adapter import ExecutionAdapter, FillEvent

def calculate_manifest_checksum(manifest_path: str, project_root: str = "") -> str:
    """
    Tính toán mã SHA-256 checksum của các file được chỉ định trong manifest file.
    """
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    files_to_hash = manifest.get("files", [])
    hasher = hashlib.sha256()
    
    # Sắp xếp danh sách file để đảm bảo tính nhất quán
    for relative_path in sorted(files_to_hash):
        full_path = os.path.join(project_root, relative_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File listed in manifest not found: {full_path}")
        with open(full_path, "rb") as bf:
            # Đọc theo block 64k để tránh ngốn RAM
            for chunk in iter(lambda: bf.read(65536), b""):
                hasher.update(chunk)
                
    # Lock dependencies lockfile hash nếu có cấu hình
    dep_hash = manifest.get("dependencies_lockfile_hash", "")
    if dep_hash:
        hasher.update(dep_hash.encode("utf-8"))
        
    return hasher.hexdigest()

class DummyAdapter(ExecutionAdapter):
    """Execution adapter giả lập đơn giản cho validation run."""
    def __init__(self):
        super().__init__()
        self.trades = []
        self.orders = []
        self._on_fill_callback = None
        
    def set_on_fill_callback(self, callback: Callable[[FillEvent], None]):
        self._on_fill_callback = callback
        
    def place_limit_order(self, symbol: str, side: str, price: float, quantity: float) -> str:
        import uuid
        oid = str(uuid.uuid4())
        self.orders.append({"id": oid, "side": side, "price": price, "quantity": quantity, "status": "OPEN"})
        return oid
        
    def cancel_order(self, symbol: str, order_id: str):
        pass
        
    def cancel_all_orders(self, symbol: str):
        pass
        
    def get_active_orders(self, symbol: str) -> List[Dict]:
        return [o for o in self.orders if o["status"] == "OPEN"]
        
    def execute_market_order(self, symbol: str, side: str, quantity: float, current_price: float, timestamp: datetime):
        import uuid
        tid = str(uuid.uuid4())
        oid = str(uuid.uuid4())
        # Lưu trade history dạng CCXT trade
        trade = {
            "trade_id": tid,
            "order_id": oid,
            "symbol": symbol,
            "side": side,
            "price": current_price,
            "quantity": quantity,
            "fee_amount": quantity * 0.001 * current_price if side == "BUY" else quantity * 0.001,
            "fee_asset": "USDT" if side == "BUY" else "BTC",
            "timestamp": int(timestamp.timestamp() * 1000)
        }
        self.trades.append(trade)
        # Báo về callback fill ngay lập tức
        if self._on_fill_callback:
            from core.interfaces.execution_adapter import FillEvent
            fill = FillEvent(
                trade_id=tid, order_id=oid, symbol=symbol, side=side,
                price=current_price, quantity=quantity,
                fee_amount=trade["fee_amount"], fee_asset=trade["fee_asset"],
                timestamp=int(timestamp.timestamp() * 1000)
            )
            self._on_fill_callback(fill)
            
    def get_trade_history(self, symbol: str) -> List[Dict]:
        return self.trades
        
    def on_tick(self, tick):
        pass
        
    def restore_orders(self, orders: List[Dict[str, Any]]):
        self.orders = orders
        
    def restore_trades(self, trades: List[Dict[str, Any]]):
        self.trades = trades

class StrategyAdapter(StrategyBase):
    """Adapter để nhúng IStrategy (như GridStrategy) vào TradingEngine"""
    def __init__(self, strategy: Any):
        self.strategy = strategy
        self.prices = []
        self.max_high = 0.0
        
    def on_tick(self, tick: TickEvent, engine: TradingEngine):
        price = tick.close
        self.prices.append(price)
        if tick.high > self.max_high:
            self.max_high = tick.high
            
        ma50 = sum(self.prices[-50:]) / min(50, len(self.prices)) if self.prices else price
        ma200 = sum(self.prices[-200:]) / min(200, len(self.prices)) if self.prices else price
        
        drawdown = (self.max_high - price) / self.max_high if self.max_high > 0 else 0.0
        spread = (tick.high - tick.low) / tick.low if tick.low > 0 else 0.0
        
        from strategies.context import MarketContext
        context = MarketContext(
            price=price,
            ma50=ma50,
            ma200=ma200,
            drawdown=drawdown,
            volatility=0.0,
            spread=spread
        )
        if not self.strategy.is_running():
            self.strategy.start(engine)
        self.strategy.process_tick(context, datetime.fromtimestamp(tick.timestamp / 1000.0), engine)
        
    def on_order_fill(self, order_id: str, side: str, fill_price: float, quantity: float, engine: TradingEngine):
        self.strategy.on_order_fill(order_id, side, fill_price, quantity, engine)
        
    def get_tracked_orders(self) -> List[str]:
        return self.strategy.get_tracked_orders()

def run_single_period_backtest(
    strategy_class: Type[Any],
    strategy_config: Any,
    data: pd.DataFrame,
    start_date: datetime,
    end_date: datetime,
    initial_capital: float,
    warmup_candles: int,
    symbol: str = "BTC/USDT"
) -> Dict[str, Any]:
    """
    Chạy backtest trên 1 phân đoạn thời gian (có tính Warmup).
    """
    # Khởi tạo Strategy và Engine
    import logging
    logging.getLogger("backtest.engine").setLevel(logging.WARNING)
    
    strategy_instance = strategy_class(strategy_config)
    strategy = StrategyAdapter(strategy_instance)
    
    from backtest.adapters.backtest_execution import BacktestExecutionAdapter
    from backtest.execution import ExecutionMode
    adapter = BacktestExecutionAdapter(mode=ExecutionMode.CONSERVATIVE, fee_rate=0.001)
    
    engine = TradingEngine(initial_capital=initial_capital, strategy=strategy, execution_adapter=adapter, symbol=symbol)
    
    # Cho phép Engine chạy trong chế độ bảo vệ/không dừng đột ngột nếu chỉ lệch nhẹ
    engine.reconciliation_mode = "protect"
    
    # Nạp dữ liệu qua event ticks
    # Data đã có sẵn warmup. Ta cấp ticks cho engine từ đầu.
    # Nhưng chỉ ghi nhận kết quả sau khi vượt qua warmup.
    warmup_cutoff_ts = start_date.timestamp() * 1000.0
    
    # Replay data
    for i in range(len(data)):
        row = data.iloc[i]
        ts_ms = data.index[i].timestamp() * 1000.0
        
        tick = TickEvent(
            symbol=symbol,
            timestamp=int(ts_ms),
            open=float(row["open"]) if "open" in row else float(row["close"]),
            high=float(row["high"]) if "high" in row else float(row["close"]),
            low=float(row["low"]) if "low" in row else float(row["close"]),
            close=float(row["close"]),
            volume=float(row["volume"]) if "volume" in row else 0.0,
            is_closed=True,
            source="backtest"
        )
        
        # Nạp tick vào engine
        engine.step(tick)
        
    # Tạo kết quả thô của engine
    raw_result = engine.generate_result(start_date, end_date)
    
    # Cắt bỏ dữ liệu warmup ra khỏi phân tích
    # 1. Lọc trades
    cropped_trades = []
    for t in engine.ledger.trades:
        t_time = datetime.fromtimestamp(t.timestamp / 1000.0, tz=timezone.utc) if isinstance(t.timestamp, (int, float)) else t.timestamp
        if start_date.tzinfo is None:
            if t_time.tzinfo is not None:
                t_time = t_time.replace(tzinfo=None)
        else:
            if t_time.tzinfo is None:
                t_time = t_time.replace(tzinfo=timezone.utc)
        if t_time >= start_date:
            cropped_trades.append(t)
    
    # Consolidation: gom nhóm trades độc lập (roundtrips)
    # Định nghĩa: trades được gom dựa trên net position.
    # Một roundtrip bắt đầu từ lúc position = 0 sang khác 0, và kết thúc khi position trở về 0 (hoặc thay đổi chiều).
    # Để đơn giản và chính xác: gom các lệnh liên tiếp cùng chiều hoặc tính PnL theo FIFO.
    # Ở đây chúng ta sẽ gom các trades liên tiếp cho đến khi net position hoàn toàn về 0.
    roundtrip_pnls = []
    current_pos = 0.0
    current_cost = 0.0
    pnl_accumulated = 0.0
    
    for t in cropped_trades:
        # PnL thô từ bán: (Sell price - Buy price) * Qty
        # Chúng ta giả lập FIFO hoặc trung bình giá đơn giản
        qty = t.quantity
        price = t.price
        if t.side == "BUY":
            current_cost = (current_cost * current_pos + price * qty) / (current_pos + qty) if (current_pos + qty) > 0 else 0.0
            current_pos += qty
        else: # SELL
            # Thực hiện bán: chốt lời/lỗ so với current_cost
            trade_pnl = (price - current_cost) * qty
            pnl_accumulated += trade_pnl
            current_pos -= qty
            if abs(current_pos) < 1e-8:
                roundtrip_pnls.append(pnl_accumulated)
                pnl_accumulated = 0.0
                current_cost = 0.0
                current_pos = 0.0
                
    # Nếu cuối cùng vị thế vẫn chưa đóng hoàn toàn, ta đóng giả lập ở giá cuối
    if abs(current_pos) > 1e-8 and len(data) > 0:
        last_price = float(data["close"].iloc[-1])
        trade_pnl = (last_price - current_cost) * current_pos
        pnl_accumulated += trade_pnl
        roundtrip_pnls.append(pnl_accumulated)
        
    # 2. Lọc equity curve
    snapshots = []
    for s in engine.ledger.snapshots:
        s_time = s.timestamp
        if start_date.tzinfo is None:
            if s_time.tzinfo is not None:
                s_time = s_time.replace(tzinfo=None)
        else:
            if s_time.tzinfo is None:
                s_time = s_time.replace(tzinfo=timezone.utc)
        if s_time >= start_date:
            snapshots.append(s)
            
    if not snapshots and len(engine.ledger.snapshots) > 0:
        snapshots = [engine.ledger.snapshots[-1]]
        
    equity_curve = [s.total_equity for s in snapshots]
    if not equity_curve:
        equity_curve = [initial_capital]
        
    # Tính toán daily returns từ cropped equity curve
    daily_equities = []
    last_day = None
    for s in snapshots:
        day_date = s.timestamp.date()
        if day_date != last_day:
            daily_equities.append(s.total_equity)
            last_day = day_date
            
    daily_returns = []
    if len(daily_equities) >= 2:
        for j in range(1, len(daily_equities)):
            r = (daily_equities[j] - daily_equities[j-1]) / daily_equities[j-1] if daily_equities[j-1] > 0 else 0.0
            daily_returns.append(r)
            
    # Tính toán metrics chi tiết cho strategy
    strategy_roi = calculate_roi(initial_capital, equity_curve[-1])
    cagr = calculate_cagr(initial_capital, equity_curve[-1], start_date, end_date)
    max_dd = calculate_max_drawdown(equity_curve)
    
    sharpe = calculate_annualized_sharpe(daily_returns)
    sortino = calculate_annualized_sortino(daily_returns)
    calmar = calculate_calmar_ratio(cagr, max_dd)
    
    net_profit = equity_curve[-1] - initial_capital
    max_dd_amount = max_dd * max(equity_curve)
    recovery = calculate_recovery_factor(net_profit, max_dd_amount)
    
    pf = calculate_profit_factor(roundtrip_pnls)
    expectancy = calculate_expectancy(roundtrip_pnls)
    
    # Exposure ratio
    # Xây dựng danh sách vị thế theo từng tick sau warmup
    active_ticks = 0
    total_ticks_after_warmup = 0
    # Engine lưu vị thế lịch sử gián tiếp qua events hoặc ta ước lượng từ snapshots
    # Để chính xác, ta duyệt snapshots sau warmup
    for s in snapshots:
        total_ticks_after_warmup += 1
        # Nếu asset_value > 0 thì đang nắm vị thế
        if s.asset_value > 1e-8:
            active_ticks += 1
    exposure = active_ticks / total_ticks_after_warmup if total_ticks_after_warmup > 0 else 0.0
    
    # Trade frequency
    freq = calculate_trade_frequency(len(roundtrip_pnls), start_date, end_date)
    
    return {
        "roi": strategy_roi,
        "cagr": cagr,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "recovery_factor": recovery,
        "profit_factor": pf,
        "expectancy": expectancy,
        "exposure_ratio": exposure,
        "trades_per_day": freq["trades_per_day"],
        "trades_per_month": freq["trades_per_month"],
        "trade_count": len(roundtrip_pnls),
        "roundtrip_pnls": roundtrip_pnls,
        "equity_curve": equity_curve,
        "final_equity": equity_curve[-1]
    }
