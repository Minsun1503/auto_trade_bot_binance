from dataclasses import dataclass

@dataclass
class MarketContext:
    """Đóng gói dữ liệu thị trường đã xử lý. Mọi logic đánh giá đều thông qua đây."""
    price: float
    
    ma50: float
    ma200: float
    
    drawdown: float
    
    volatility: float
    spread: float
