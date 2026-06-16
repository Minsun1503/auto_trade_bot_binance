import pandas as pd
from datetime import datetime
import uuid
import os
import logging
from typing import Dict, Any, List

from portfolio.ledger import Ledger
from portfolio.position import Trade
from .result import BacktestResult
from .metrics import calculate_roi, calculate_cagr, calculate_max_drawdown
from core.events import EventBus, OrderEvent, TradeEvent, EquityUpdateEvent, LogEvent, CommandEvent, TickEvent
from core.interfaces.execution_adapter import ExecutionAdapter, FillEvent
from core.event_buffer import EventBuffer

class ReconciliationMode:
    STRICT = "strict"
    PROTECT = "protect"

logger = logging.getLogger(__name__)

class StrategyBase:
    def on_tick(self, tick: TickEvent, engine: 'TradingEngine'): pass
    def on_order_fill(self, order_id: str, side: str, fill_price: float, quantity: float, engine: 'TradingEngine'): pass

class TradingEngine:
    def __init__(
        self, 
        initial_capital: float, 
        strategy: StrategyBase,
        execution_adapter: ExecutionAdapter,
        symbol: str = "BTC/USDT",
    ):
        self.initial_capital = initial_capital
        self.strategy = strategy
        self.symbol = symbol
        self.ledger = Ledger(initial_cash=initial_capital, quote_currency=symbol.split('/')[1])
        
        self.execution_adapter = execution_adapter
        self.execution_adapter.set_on_fill_callback(self._route_fill_to_buffer)
        
        self.event_buffer = EventBuffer(window_ms=2000, epsilon_ms=10000) # 2s window, 10s epsilon
        self.event_bus = None
        self.reconciliation_mode = ReconciliationMode.STRICT
        
        # Load tolerances from config
        from config.settings import load_settings_from_env
        try:
            settings = load_settings_from_env()
            self.btc_epsilon = settings.portfolio.reconcile_btc_epsilon
            self.usdt_epsilon = settings.portfolio.reconcile_usdt_epsilon
        except Exception:
            self.btc_epsilon = 1e-8
            self.usdt_epsilon = 0.01
        
        self.filled_orders_count = 0
        self._processed_trade_ids = set()
        self.peak_equity = initial_capital
        self.max_drawdown = 0.0
        self.last_snapshot_day = None
        self.last_price = 0.0
        self.buy_price_bh = 0.0
        self.quantity_bh = 0.0
        
    def load_snapshot(self, snapshot_data: dict):
        import hashlib
        import json
        
        # Verify checksum
        checksum = snapshot_data.pop('checksum', None)
        if checksum:
            computed = hashlib.sha256(json.dumps(snapshot_data, sort_keys=True).encode()).hexdigest()
            if checksum != computed:
                logger.error("WARNING: snapshot integrity failed (checksum mismatch)")
                raise ValueError("WARNING: snapshot integrity failed")
                
        self.ledger.restore_cash(snapshot_data.get('cash', self.initial_capital))
        
        positions = snapshot_data.get('positions', {})
        for sym, pos_data in positions.items():
            self.ledger.restore_position(sym, pos_data.get('quantity', 0.0), pos_data.get('avg_price', 0.0))
            
        self.peak_equity = snapshot_data.get('peak_equity', self.initial_capital)
        self.max_drawdown = snapshot_data.get('max_drawdown', 0.0)
        
        state_str = snapshot_data.get('state', 'INIT')
        if hasattr(self.strategy, 'coordinator'):
            from strategies.state import BotState
            for state_enum in BotState:
                if state_enum.name == state_str:
                    self.strategy.coordinator.state = state_enum
                    break
                    
        orders = snapshot_data.get('orders', [])
        self.execution_adapter.restore_orders(orders)
        trades = snapshot_data.get('trades', [])
        self.execution_adapter.restore_trades(trades)
        
        if hasattr(self.strategy, 'tracked_orders'):
            # This handles dummy strategy in tests or actual strategies
            pass
            
        # Sync lost fills from Exchange (Adapter) to Ledger
        self._sync_with_exchange()
        
    def _sync_with_exchange(self):
        adapter_trades = self.execution_adapter.get_trade_history(self.symbol)
        ledger_trade_ids = {t.trade_id for t in self.ledger.trades}
        
        for t in adapter_trades:
            if t['trade_id'] not in ledger_trade_ids:
                logger.warning(f"[RECOVERY] Phục hồi Fill bị mất (nằm trong buffer cũ): {t['trade_id']}")
                # Process directly, bypass EventBuffer because this is historical catch-up
                fill = FillEvent(
                    trade_id=t['trade_id'],
                    order_id=t['order_id'],
                    symbol=t['symbol'],
                    side=t['side'],
                    price=t['price'],
                    quantity=t['quantity'],
                    fee_amount=t['fee_amount'],
                    fee_asset=t['fee_asset'],
                    timestamp=t['timestamp']
                )
                self.on_order_filled(fill)
        
    def place_limit_order(self, side: str, price: float, quantity: float) -> str:
        order_id = self.execution_adapter.place_limit_order(self.symbol, side, price, quantity)
        if self.event_bus:
            self.event_bus.publish(OrderEvent(action="CREATE", order_id=order_id, side=side.upper(), price=price, quantity=quantity))
        return order_id
        
    def cancel_order(self, order_id: str):
        self.execution_adapter.cancel_order(self.symbol, order_id)
        if self.event_bus:
            self.event_bus.publish(OrderEvent(action="CANCEL", order_id=order_id, side="", price=0.0, quantity=0.0))
        
    def cancel_all_orders(self):
        orders = self.get_active_orders()
        self.execution_adapter.cancel_all_orders(self.symbol)
        if self.event_bus:
            for o in orders:
                self.event_bus.publish(OrderEvent(action="CANCEL", order_id=o['id'], side=o['side'], price=o['price'], quantity=o['quantity']))

    def get_active_orders(self) -> List[Dict[str, Any]]:
        return self.execution_adapter.get_active_orders(self.symbol)
        
    def execute_market_order(self, side: str, quantity: float, current_price: float, timestamp: datetime):
        self.execution_adapter.execute_market_order(self.symbol, side, quantity, current_price, timestamp)
        
    def _route_fill_to_buffer(self, fill_event: FillEvent):
        self.event_buffer.push(
            event_type="FILL",
            timestamp=fill_event.timestamp,
            payload=fill_event,
            event_id=fill_event.trade_id,
            source_id="adapter"
        )
        
    def on_order_filled(self, fill_event: FillEvent):
        # Run Light Reconciliation
        self.audit_light_reconciliation(fill_event)

        if fill_event.trade_id in self._processed_trade_ids:
            logger.warning(f"    [DUPLICATE FILL] Đã bỏ qua trade_id {fill_event.trade_id} cho order_id {fill_event.order_id}")
            return
            
        self._processed_trade_ids.add(fill_event.trade_id)
        
        trade = Trade(
            trade_id=fill_event.trade_id,
            symbol=fill_event.symbol,
            side=fill_event.side,
            quantity=fill_event.quantity,
            price=fill_event.price,
            fee_amount=fill_event.fee_amount,
            fee_asset=fill_event.fee_asset,
            timestamp=fill_event.timestamp
        )
        self.ledger.append_trade(trade)
        self.filled_orders_count += 1
        
        logger.info(f"    [ORDER FILLED] {fill_event.side} {fill_event.quantity:.4f} @ {fill_event.price:.2f} | Fee: {trade.fee_amount:.4f} {trade.fee_asset}")
        
        if self.event_bus:
            self.event_bus.publish(OrderEvent(action="FILL", order_id=fill_event.order_id, side=fill_event.side, price=fill_event.price, quantity=fill_event.quantity))
            self.event_bus.publish(TradeEvent(side=fill_event.side, price=fill_event.price, quantity=fill_event.quantity, fee=trade.fee_amount))
            
        self.strategy.on_order_fill(fill_event.order_id, fill_event.side, fill_event.price, fill_event.quantity, self)

    def step(self, tick: TickEvent):
        if not tick.is_closed:
            return

        # Engine không tự tạo event_id.
        # EventBuffer là authority duy nhất cho identity qua _make_dedup_key(symbol+ts+is_final).
        self.event_buffer.push(
            event_type="TICK",
            timestamp=tick.timestamp,
            payload=tick,
            source_id=tick.source
        )

        self._flush_buffer(tick.timestamp)
        
    def _flush_buffer(self, current_time: int):
        ready_events = self.event_buffer.flush_ready(current_time)
        for ev in ready_events:
            if ev.event_type == "TICK":
                self._process_tick(ev.payload)
            elif ev.event_type == "FILL":
                self.on_order_filled(ev.payload)

        # Reconcile AFTER the entire batch is committed to Ledger
        if ready_events:
            self.audit_state_reconciliation()

        # Watermark update AFTER Ledger commit — không update trước.
        # Nếu update trước: late fill có thể bị reject dù hợp lệ.
        # Nếu update sau: watermark chính xác phản ánh trạng thái đã commit.
        if ready_events:
            max_committed_ts = max(e.timestamp for e in ready_events)
            if self.event_buffer.engine_watermark is None or max_committed_ts > self.event_buffer.engine_watermark:
                self.event_buffer.engine_watermark = max_committed_ts
                
    def _process_tick(self, tick: TickEvent):
        # We can still log with datetime for readability
        dt_time = datetime.fromtimestamp(tick.timestamp / 1000.0)
        logger.info(f"--- TICK {dt_time} | O:{tick.open} H:{tick.high} L:{tick.low} C:{tick.close} ---")
        if self.event_bus:
            self.event_bus.publish(LogEvent(message=f"TICK {dt_time} | C:{tick.close}"))
            
        current_price = tick.close
        self.last_price = current_price
        current_prices = {self.symbol: current_price}
        
        # Để Adapter giả lập việc khớp lệnh
        self.execution_adapter.on_tick(tick)
        
        self.strategy.on_tick(tick, self)
        
        # Tick-by-tick Drawdown Calculation
        current_equity = self.ledger.get_total_equity(current_prices)
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        dd = (self.peak_equity - current_equity) / self.peak_equity
        if dd > self.max_drawdown:
            self.max_drawdown = dd
            
        if self.event_bus:
            roi = calculate_roi(self.initial_capital, current_equity)
            pos = self.ledger.rebuild_position(self.symbol)
            asset_value = pos.quantity * current_price
            self.event_bus.publish(EquityUpdateEvent(
                equity=current_equity, cash=self.ledger.cash, 
                asset_value=asset_value, roi=roi, drawdown=dd
            ))
        
        if self.last_snapshot_day != dt_time.date():
            self.ledger.record_snapshot(dt_time, current_prices)
            self.last_snapshot_day = dt_time.date()
            
    def emergency_stop(self):
        logger.error("!!! EMERGENCY STOP INITIATED !!!")
        if self.event_bus:
            self.event_bus.publish(LogEvent(message="EMERGENCY STOP. Bấm Q để thoát.", level="ERROR"))
            self.event_bus.publish(CommandEvent(command="PAUSE"))
            self.event_bus.publish(CommandEvent(command="SNAPSHOT"))

    def audit_state_reconciliation(self):
        try:
            # 1. Compare Strategy Orders vs ExecutionAdapter Orders
            tracked_by_strategy = set(self.strategy.get_tracked_orders())
            tracked_by_adapter = set([o['id'] for o in self.get_active_orders()])
            
            # Lưu ý: Sẽ có những lệnh Adapter đang giữ nhưng Strategy không biết (vì chưa route về),
            # Hoặc Strategy giữ nhưng Adapter đã cancel mà Fill chưa kịp tới. 
            # Tuy nhiên Ledger là Truth. Trong Backtest đồng bộ thì phải y hệt nhau.
            # NẾU có EventBuffer, những order thiếu bên Adapter PHẢI đang nằm trong Buffer dưới dạng FillEvent.
            missing_in_adapter = tracked_by_strategy - tracked_by_adapter
            if missing_in_adapter:
                pending_fill_orders = set([ev.payload.order_id for ev in self.event_buffer.events if ev.event_type == "FILL"])
                unaccounted = missing_in_adapter - pending_fill_orders
                if unaccounted:
                    raise ValueError(f"State Mismatch! Orders tracked by Strategy but lost: {unaccounted}")
                
            # 2. Check position logic constraint (No shorting currently)
            pos = self.ledger.rebuild_position(self.symbol)
            if pos.quantity < -1e-8:
                raise ValueError(f"State Mismatch! Short position not allowed: {pos.quantity}")
                
        except Exception as e:
            if self.reconciliation_mode == ReconciliationMode.STRICT:
                raise e
            else:
                logger.error(f"Reconciliation Failed: {str(e)}. Triggering Emergency Stop.")
                self.emergency_stop()

    def audit_light_reconciliation(self, fill_event: FillEvent):
        """
        Light Reconciliation (Runs after every fill processed locally, < 1ms, no network calls)
        """
        logger.info(f"[LIGHT RECONCILE] Checking fill {fill_event.trade_id} for order {fill_event.order_id}")
        
        # 1. Check positive fill quantity
        if fill_event.quantity <= 0:
            raise ValueError(f"[LIGHT RECONCILE] Invalid non-positive fill quantity: {fill_event.quantity}")
            
        # 2. Check no negative position (Spot-only)
        pos = self.ledger.rebuild_position(self.symbol)
        if pos.quantity < -1e-8:
            logger.critical(f"[LIGHT RECONCILE] Level 3 Critical Mismatch: Negative spot position: {pos.quantity}")
            self.emergency_stop()
            raise ValueError(f"[LIGHT RECONCILE] Level 3 Critical: Negative spot position: {pos.quantity}")

    def audit_full_reconciliation(self):
        """
        Full Reconciliation (startup, restore, reconnect, and periodically via REST API)
        """
        logger.info("[FULL RECONCILE] Performing full exchange state reconciliation...")
        
        if not hasattr(self.execution_adapter, 'get_balances'):
            logger.info("[FULL RECONCILE] Adapter does not support exchange balance querying. Skipping.")
            return

        # 1. Fetch Balances & Orders from Exchange
        balances = self.execution_adapter.get_balances()
        base_asset = self.symbol.split('/')[0]
        quote_asset = self.symbol.split('/')[1]
        
        exchange_base_total = balances.get(base_asset, {}).get('total', 0.0)
        exchange_quote_total = balances.get(quote_asset, {}).get('total', 0.0)

        pos = self.ledger.rebuild_position(self.symbol)
        ledger_base_qty = pos.quantity
        ledger_quote_qty = self.ledger.cash

        # 2. Rebuild Position from Exchange Trade History (Supremacy)
        trades = self.execution_adapter.get_trade_history(self.symbol)
        rebuilt_base_qty = 0.0
        for t in trades:
            qty = float(t['quantity'])
            if t['side'] == 'BUY':
                rebuilt_base_qty += qty
            elif t['side'] == 'SELL':
                rebuilt_base_qty -= qty

        if abs(rebuilt_base_qty - ledger_base_qty) > self.btc_epsilon:
            logger.critical(
                f"[FULL RECONCILE] Level 3 Critical Mismatch: Position rebuilt from exchange trades ({rebuilt_base_qty:.8f}) "
                f"differs from ledger position ({ledger_base_qty:.8f}). Overwriting ledger."
            )
            # Rebuild Supremacy: overwrite ledger
            self.ledger.restore_position(self.symbol, rebuilt_base_qty, pos.avg_price)
            self.emergency_stop()
            return

        # 3. Check Quantity and Cash tolerances (Level 2 Protect if >= epsilon)
        base_diff = abs(ledger_base_qty - exchange_base_total)
        quote_diff = abs(ledger_quote_qty - exchange_quote_total)

        if (0 < base_diff < self.btc_epsilon) or (0 < quote_diff < self.usdt_epsilon):
            logger.warning(
                f"[FULL RECONCILE] Level 1 Warning: Minor asset balance drift (within tolerance). "
                f"{base_asset} diff: {base_diff:.8f}, {quote_asset} diff: {quote_diff:.4f}"
            )
        elif base_diff >= self.btc_epsilon or quote_diff >= self.usdt_epsilon:
            logger.error(
                f"[FULL RECONCILE] Level 2 Protect: Significant asset mismatch! "
                f"{base_asset}: Ledger={ledger_base_qty:.8f}, Exchange={exchange_base_total:.8f} (diff={base_diff:.8f} >= {self.btc_epsilon}). "
                f"{quote_asset}: Ledger={ledger_quote_qty:.4f}, Exchange={exchange_quote_total:.4f} (diff={quote_diff:.4f} >= {self.usdt_epsilon})."
            )
            self.reconciliation_mode = ReconciliationMode.PROTECT
            try:
                self.cancel_all_orders()
            except Exception:
                pass
            if self.event_bus:
                self.event_bus.publish(CommandEvent(command="PAUSE"))
                self.event_bus.publish(CommandEvent(command="SNAPSHOT"))

        # 4. Order State Machine Matching
        exchange_open_orders = {o['id']: o for o in self.execution_adapter.get_active_orders(self.symbol)}
        tracked_orders = self.strategy.get_tracked_orders()
        
        from core.order_state import OrderState, map_order_state
        for order_id in tracked_orders:
            if order_id not in exchange_open_orders:
                # If coordinator thinks it is active but it is filled on exchange
                recent_filled_ids = {t['order_id'] for t in trades}
                if order_id in recent_filled_ids:
                    logger.error(
                        f"[FULL RECONCILE] Level 2 Protect: Order {order_id} filled on Exchange but ACTIVE in Coordinator!"
                    )
                    self.reconciliation_mode = ReconciliationMode.PROTECT
                    # Cancel all orders to protect account
                    try:
                        self.cancel_all_orders()
                    except Exception:
                        pass
                    if self.event_bus:
                        self.event_bus.publish(CommandEvent(command="PAUSE"))
                        self.event_bus.publish(CommandEvent(command="SNAPSHOT"))

    def generate_result(self, start_date: datetime, end_date: datetime) -> BacktestResult:
        current_prices = {self.symbol: self.last_price}
        self.ledger.record_snapshot(end_date, current_prices)
        
        self._export_equity_curve()
        
        final_equity = self.ledger.get_total_equity(current_prices)
        strategy_roi = calculate_roi(self.initial_capital, final_equity)
        
        buyhold_equity = self.quantity_bh * self.last_price
        buyhold_roi = calculate_roi(self.initial_capital, buyhold_equity)
        
        excess_return = strategy_roi - buyhold_roi
        cagr = calculate_cagr(self.initial_capital, final_equity, start_date, end_date)
        
        total_trades = len(self.ledger.trades)
        win_trades = sum(1 for t in self.ledger.trades if t.side == "SELL")
        win_rate = (win_trades / total_trades) if total_trades > 0 else 0.0
        
        logger.info(f"==========================================")
        logger.info(f"SANITY CHECK: Filled Orders ({self.filled_orders_count}) == Ledger Trades ({total_trades})")
        logger.info(f"==========================================")
        
        return BacktestResult(
            start_date=start_date, end_date=end_date,
            initial_capital=self.initial_capital, final_equity=final_equity,
            strategy_roi=strategy_roi, buyhold_roi=buyhold_roi,
            excess_return=excess_return, cagr=cagr, max_drawdown=self.max_drawdown,
            total_trades=total_trades, win_rate=win_rate,
            gross_profit=self.ledger.get_gross_profit(),
            net_profit=self.ledger.get_net_profit(current_prices),
            total_fees_usdt=self.ledger.get_total_fees_in_quote(current_prices)
        )

    def _export_equity_curve(self, filename="equity_curve.csv"):
        data = []
        for s in self.ledger.snapshots:
            data.append({
                "timestamp": s.timestamp, "cash": s.cash,
                "asset_value": s.asset_value, "total_equity": s.total_equity,
                "drawdown": s.drawdown
            })
        df_eq = pd.DataFrame(data)
        out_path = os.path.join(os.getcwd(), filename)
        df_eq.to_csv(out_path, index=False)
