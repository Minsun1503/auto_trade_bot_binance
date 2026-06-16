from datetime import datetime
import pandas as pd
from backtest.engine import StrategyBase, TradingEngine

from core.events import TickEvent

class DCABacktester(StrategyBase):
    """
    Chiến lược DCA Trading.
    """
    def __init__(self, amount_usdt: float, frequency: str = "weekly"):
        self.amount_usdt = amount_usdt
        self.frequency = frequency
        self.last_buy_date = None
        
    def on_tick(self, tick: TickEvent, engine: TradingEngine):
        current_price = tick.close
        dt_time = datetime.fromtimestamp(tick.timestamp / 1000.0)
        
        # Logic trigger theo chu kỳ (ví dụ: Thứ 2 hàng tuần)
        if self.frequency == "weekly" and dt_time.weekday() == 0:
            if self.last_buy_date is None or (dt_time.date() - self.last_buy_date).days >= 7:
                # Mua Market (ở đây giả lập Limit bằng giá Close của nến)
                qty = self.amount_usdt / current_price
                # Mua luôn tại current_price 
                # (Với Optimistic mode thì sẽ khớp ngay cây nến tiếp theo)
                engine.place_limit_order("BUY", current_price * 1.01, qty) # Đặt cao hơn tí để cắn ngay
                
                self.last_buy_date = dt_time.date()
