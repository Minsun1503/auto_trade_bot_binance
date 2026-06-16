from enum import Enum
import pandas as pd
from core.events import TickEvent

class ExecutionMode(Enum):
    OPTIMISTIC = "optimistic" # Giả định khớp lệnh ngay khi giá chạm
    CONSERVATIVE = "conservative" # Yêu cầu giá phải đâm xuyên qua một mức trượt giá (slippage) để đảm bảo thanh khoản

class ExecutionSimulator:
    """
    Giả lập khớp lệnh. Tách bạch hoàn toàn logic khớp lệnh khỏi logic của Strategy.
    Giải quyết vấn đề tự huyễn hoặc (ảo tưởng) khi backtest với nến (OHLC).
    """
    def __init__(self, mode: ExecutionMode = ExecutionMode.CONSERVATIVE, slippage_pct: float = 0.0005):
        self.mode = mode
        self.slippage_pct = slippage_pct
        
    def simulate_limit_buy(self, order_price: float, tick: TickEvent) -> bool:
        if self.mode == ExecutionMode.CONSERVATIVE:
            return tick.low < order_price  # Cần thấp HƠN
        else:
            return tick.low <= order_price # Bằng là khớp
            
    def simulate_limit_sell(self, order_price: float, tick: TickEvent) -> bool:
        if self.mode == ExecutionMode.CONSERVATIVE:
            return tick.high > order_price # Cần cao HƠN
        else:
            return tick.high >= order_price # Bằng là khớp
            
    def get_fill_price(self, order_price: float, side: str) -> float:
        # Dù conservative thì giá khớp vẫn tính là giá Limit mà ta đặt (Limit Order Guarantee)
        return order_price
