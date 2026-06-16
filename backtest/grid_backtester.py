from datetime import datetime
import pandas as pd
from backtest.engine import StrategyBase, TradingEngine

from core.events import TickEvent

class GridBacktester(StrategyBase):
    """
    Chiến lược Grid Trading thuần túy, tương thích với TradingEngine.
    """
    def __init__(self, lower_price: float, upper_price: float, grids: int, order_size_usdt: float):
        self.lower_price = lower_price
        self.upper_price = upper_price
        self.grids = grids
        self.order_size_usdt = order_size_usdt
        self.initialized = False
        
    def _calculate_levels(self):
        step = (self.upper_price - self.lower_price) / self.grids
        return [self.lower_price + i * step for i in range(self.grids + 1)]
        
    def on_tick(self, tick: TickEvent, engine: TradingEngine):
        current_price = tick.close
        
        # Chỉ khởi tạo lưới 1 lần khi bắt đầu
        if not self.initialized:
            levels = self._calculate_levels()
            for level in levels:
                if level < current_price:
                    # Đặt sẵn limit buy ở dưới
                    qty = self.order_size_usdt / level
                    engine.place_limit_order("BUY", level, qty)
            self.initialized = True
            
        # Các logic tái tạo lưới khi lệnh BUY khớp để đặt lệnh SELL (và ngược lại)
        # Sẽ được implement chi tiết trong giai đoạn hoàn thiện logic
        pass
