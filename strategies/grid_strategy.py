import logging
from dataclasses import dataclass
from typing import Literal, Dict, Optional
from config.settings import GridConfig
from .coordinator import IStrategy

logger = logging.getLogger(__name__)

@dataclass
class GridOrder:
    order_id: str
    level_price: float
    side: Literal["BUY", "SELL"]
    quantity: float

class GridStrategy(IStrategy):
    def __init__(self, config: GridConfig):
        self.config = config
        self._is_running = False
        self.active_orders: Dict[str, GridOrder] = {}
        self.active_levels = set() # Store (round(price,2), side) to prevent duplicates
        
        self.step_size = 0.0
        self.base_price = 0.0
        self._initialized = False
        
    def start(self, engine):
        if not self._is_running:
            self._is_running = True
            
    def stop(self, engine):
        if self._is_running:
            self._is_running = False
            self._initialized = False # Bắt buộc phải setup lại Grid khi start lại
            # Hủy toàn bộ lệnh của Grid
            for o_id in list(self.active_orders.keys()):
                engine.cancel_order(o_id)
            self.active_orders.clear()
            self.active_levels.clear()
            logger.info("    [GRID] STOPPED. Đã hủy toàn bộ lệnh Grid.")
            
    def is_running(self) -> bool:
        return self._is_running
        
    def _round(self, price: float):
        return round(price, 4)
        
    def _place_grid_order(self, engine, side: str, level_price: float, qty: float):
        key = (self._round(level_price), side)
        if key in self.active_levels:
            logger.debug(f"    [GRID] Bỏ qua lệnh {side} @ {level_price} do đã tồn tại.")
            return
            
        # Kiểm tra tiền/coin nghiêm ngặt
        if side == "BUY":
            cash = engine.ledger.get_cash_balance()
            req = level_price * qty
            if cash < req:
                logger.warning(f"    [GRID] Bỏ qua BUY @ {level_price}. Không đủ tiền. Yêu cầu: {req}, Có: {cash}")
                return
        elif side == "SELL":
            pos = engine.ledger.rebuild_position(engine.symbol)
            if pos.quantity < qty:
                logger.warning(f"    [GRID] Bỏ qua SELL @ {level_price}. Không đủ coin. Yêu cầu: {qty}, Có: {pos.quantity}")
                return
                
        o_id = engine.place_limit_order(side, level_price, qty)
        self.active_orders[o_id] = GridOrder(o_id, level_price, side, qty)
        self.active_levels.add(key)

    def process_tick(self, context, timestamp, engine):
        if not self._is_running:
            return
            
        if not self._initialized:
            self.base_price = context.price
            upper_price = self.base_price * (1 + self.config.upper_bound_pct)
            lower_price = self.base_price * (1 + self.config.lower_bound_pct)
            self.step_size = (upper_price - lower_price) / self.config.levels
            
            total_cap = engine.initial_capital * self.config.capital_allocation_pct
            cap_per_level = total_cap / self.config.levels
            
            logger.info(f"    [GRID] KHỞI TẠO. Base: {self.base_price}. Step: {self.step_size}. Cap/Level: {cap_per_level}")
            
            # Tính lượng coin cần thiết để rải lệnh SELL
            qty_to_buy = 0.0
            for i in range(self.config.levels + 1):
                level_price = lower_price + i * self.step_size
                if level_price > self.base_price:
                    qty_to_buy += cap_per_level / level_price
            
            # Rebalance (Mua thêm hoặc Bán bớt nếu trước đó đã gom DCA)
            pos = engine.ledger.rebuild_position(engine.symbol)
            shortfall = qty_to_buy - pos.quantity
            
            # Ngăn ngừa sai số làm trade quá nhỏ
            min_trade_size = 0.0001
            if shortfall > min_trade_size:
                logger.info(f"    [GRID REBALANCE] Cần mua thêm {shortfall:.4f} coin")
                engine.execute_market_order("BUY", shortfall, self.base_price, timestamp)
            elif shortfall < -min_trade_size:
                logger.info(f"    [GRID REBALANCE] Đang dư thừa, bán bớt {-shortfall:.4f} coin")
                engine.execute_market_order("SELL", abs(shortfall), self.base_price, timestamp)
                
            # Đặt lệnh Grid ban đầu
            for i in range(self.config.levels + 1):
                level_price = lower_price + i * self.step_size
                qty = cap_per_level / level_price
                if level_price < self.base_price:
                    self._place_grid_order(engine, "BUY", level_price, qty)
                elif level_price > self.base_price:
                    self._place_grid_order(engine, "SELL", level_price, qty)
                    
            self._initialized = True

    def on_order_fill(self, order_id: str, side: str, price: float, quantity: float, engine):
        if order_id in self.active_orders:
            grid_order = self.active_orders.pop(order_id)
            old_key = (self._round(grid_order.level_price), side)
            if old_key in self.active_levels:
                self.active_levels.remove(old_key)
            
            logger.info(f"    [GRID] Phát hiện {side} khớp ở {grid_order.level_price}. Đặt lệnh Counter...")
            
            # Counter-order logic (Lifecyle: Buy -> Sell, Sell -> Buy)
            if side == "BUY":
                next_level = grid_order.level_price + self.step_size
                self._place_grid_order(engine, "SELL", next_level, quantity)
            elif side == "SELL":
                next_level = grid_order.level_price - self.step_size
                self._place_grid_order(engine, "BUY", next_level, quantity)

    def get_tracked_orders(self) -> list[str]:
        return list(self.active_orders.keys())
