import uuid
import logging
from typing import Callable, List, Dict, Any
from datetime import datetime
import pandas as pd

from core.interfaces.execution_adapter import ExecutionAdapter, FillEvent
from core.events import TickEvent
from backtest.execution import ExecutionSimulator, ExecutionMode

logger = logging.getLogger(__name__)

class BacktestExecutionAdapter(ExecutionAdapter):
    def __init__(self, mode: ExecutionMode = ExecutionMode.CONSERVATIVE, fee_rate: float = 0.001, fee_asset: str = "USDT"):
        self.mode = mode
        self.simulator = ExecutionSimulator(mode=mode)
        self.fee_rate = fee_rate
        self.fee_asset = fee_asset
        self.active_orders: Dict[str, dict] = {}
        self.trade_history: List[Dict[str, Any]] = []
        self._on_fill_callback: Optional[Callable[[FillEvent], None]] = None
        self.delay_fills_ticks = 0
        self._delayed_fills: List[tuple] = [] # (ticks_remaining, FillEvent)

    def set_on_fill_callback(self, callback: Callable[[FillEvent], None]):
        self._on_fill_callback = callback
        
    def place_limit_order(self, symbol: str, side: str, price: float, quantity: float) -> str:
        order_id = f"ord_{uuid.uuid4().hex[:8]}"
        self.active_orders[order_id] = {
            'id': order_id,
            'symbol': symbol,
            'side': side.upper(),
            'price': price,
            'quantity': quantity,
            'status': 'NEW'
        }
        logger.info(f"    [ORDER CREATED] {side} {quantity:.4f} @ {price:.2f} (ID: {order_id})")
        return order_id
        
    def execute_market_order(self, symbol: str, side: str, quantity: float, current_price: float, timestamp: datetime) -> str:
        trade_value = quantity * current_price
        fee_amount = trade_value * self.fee_rate
        
        trade_id = f"mkt_{uuid.uuid4().hex[:8]}"
        order_id = f"ord_{uuid.uuid4().hex[:8]}"
        
        ts_ms = int(timestamp.timestamp() * 1000) if isinstance(timestamp, datetime) else int(timestamp)
        
        # Thêm vào lịch sử trade
        self.trade_history.append({
            "trade_id": trade_id,
            "order_id": order_id,
            "symbol": symbol,
            "side": side.upper(),
            "price": current_price,
            "quantity": quantity,
            "fee_amount": fee_amount,
            "fee_asset": self.fee_asset,
            "timestamp": ts_ms
        })
        
        if self._on_fill_callback:
            fill = FillEvent(
                trade_id=trade_id,
                order_id=order_id,
                symbol=symbol,
                side=side.upper(),
                price=current_price,
                quantity=quantity,
                fee_amount=fee_amount if self.fee_asset == "USDT" else fee_amount * 0.002,
                fee_asset=self.fee_asset,
                timestamp=ts_ms
            )
            if self.delay_fills_ticks > 0:
                self._delayed_fills.append((self.delay_fills_ticks, fill))
            else:
                self._on_fill_callback(fill)
            
        return order_id
        
    def cancel_order(self, symbol: str, order_id: str):
        if order_id in self.active_orders:
            del self.active_orders[order_id]
        logger.info(f"    [ORDER CANCELED] ID: {order_id}")
        
    def cancel_all_orders(self, symbol: str):
        self.active_orders = {k: v for k, v in self.active_orders.items() if v['symbol'] != symbol}
        logger.info("    [ALL ORDERS CANCELED]")
        
    def get_active_orders(self, symbol: str) -> List[Dict[str, Any]]:
        return [o for o in self.active_orders.values() if o['symbol'] == symbol]
        
    def restore_orders(self, orders: List[Dict[str, Any]]):
        self.active_orders.clear()
        for o in orders:
            self.active_orders[o['id']] = o
        logger.info(f"    [ADAPTER RESTORED] {len(self.active_orders)} active orders")
        
    def get_trade_history(self, symbol: str) -> List[Dict[str, Any]]:
        return [t for t in self.trade_history if t['symbol'] == symbol]
        
    def restore_trades(self, trades: List[Dict[str, Any]]):
        self.trade_history = trades.copy()
        
    def on_tick(self, tick: TickEvent):
        # Chỉ lấy order để duyệt, tránh mutate khi đang iterate
        current_orders = list(self.active_orders.values())
        
        fills_to_notify = []
        orders_to_remove = []
        
        for order in current_orders:
            if order['status'] != 'NEW':
                continue
                
            is_filled = False
            fill_price = 0.0
            
            if order['side'] == 'BUY':
                is_filled = self.simulator.simulate_limit_buy(order['price'], tick)
            elif order['side'] == 'SELL':
                is_filled = self.simulator.simulate_limit_sell(order['price'], tick)
                
            if is_filled:
                fill_price = self.simulator.get_fill_price(order['price'], order['side'])
                
                # Tính fee giả lập
                trade_value = fill_price * order['quantity']
                fee_amount = trade_value * self.fee_rate
                
                trade_id = f"trd_{uuid.uuid4().hex[:8]}"
                fill = FillEvent(
                    trade_id=trade_id,
                    order_id=order['id'],
                    symbol=order['symbol'],
                    side=order['side'],
                    price=fill_price,
                    quantity=order['quantity'],
                    fee_amount=fee_amount if self.fee_asset == "USDT" else fee_amount * 0.002,
                    fee_asset=self.fee_asset,
                    timestamp=tick.timestamp
                )
                fills_to_notify.append(fill)
                self.trade_history.append({
                    "trade_id": trade_id,
                    "order_id": order['id'],
                    "symbol": order['symbol'],
                    "side": order['side'],
                    "price": fill_price,
                    "quantity": order['quantity'],
                    "fee_amount": fee_amount,
                    "fee_asset": self.fee_asset,
                    "timestamp": tick.timestamp
                })
                orders_to_remove.append(order['id'])
                
        for order_id in orders_to_remove:
            if order_id in self.active_orders:
                del self.active_orders[order_id]
        
        # Fire events
        if self._on_fill_callback:
            for fill in fills_to_notify:
                if self.delay_fills_ticks > 0:
                    self._delayed_fills.append((self.delay_fills_ticks, fill))
                else:
                    self._on_fill_callback(fill)
                    
        # Process delayed fills
        if self._delayed_fills:
            new_delayed = []
            for ticks, fill in self._delayed_fills:
                if ticks <= 1:
                    if self._on_fill_callback:
                        self._on_fill_callback(fill)
                else:
                    new_delayed.append((ticks - 1, fill))
            self._delayed_fills = new_delayed
