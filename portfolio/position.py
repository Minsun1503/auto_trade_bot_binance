from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Dict

@dataclass
class Trade:
    """Đại diện cho một giao dịch đã được thực thi (Source of Truth)"""
    trade_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float
    price: float
    fee_amount: float
    fee_asset: str
    timestamp: datetime

@dataclass
class Position:
    """Kết quả tính toán trạng thái của một đồng coin (Từ việc replay Trade)"""
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0
    
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    
    # Lưu chính xác loại tài sản đã dùng để trả phí
    fees_accumulated: Dict[str, float] = field(default_factory=dict)
    
    last_update: datetime = None

@dataclass
class PortfolioSnapshot:
    """Ảnh chụp tài khoản để vẽ Equity Curve khi backtest"""
    timestamp: datetime
    cash: float
    asset_value: float
    total_equity: float
    drawdown: float
