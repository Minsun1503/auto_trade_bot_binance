from abc import ABC, abstractmethod
from typing import Callable, List, Dict, Any
from datetime import datetime
import pandas as pd
from dataclasses import dataclass
from core.events import TickEvent

@dataclass
class FillEvent:
    trade_id: str
    order_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    fee_amount: float
    fee_asset: str
    timestamp: int # ms epoch

class ExecutionAdapter(ABC):
    """
    Interface cho mọi Adapter khớp lệnh (Backtest, Paper Trading, Live)
    """
    
    @abstractmethod
    def set_on_fill_callback(self, callback: Callable[[FillEvent], None]):
        """Engine sẽ cung cấp callback này để nhận FillEvent từ Adapter"""
        pass
        
    @abstractmethod
    def place_limit_order(self, symbol: str, side: str, price: float, quantity: float) -> str:
        """Đặt lệnh Limit, trả về order_id"""
        pass
        
    @abstractmethod
    def execute_market_order(self, symbol: str, side: str, quantity: float, current_price: float, timestamp: datetime) -> str:
        """Thực thi ngay lệnh Market, trả về order_id"""
        pass
        
    @abstractmethod
    def cancel_order(self, symbol: str, order_id: str):
        """Hủy lệnh"""
        pass
        
    @abstractmethod
    def cancel_all_orders(self, symbol: str):
        """Hủy toàn bộ lệnh của symbol"""
        pass
        
    @abstractmethod
    def get_active_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Lấy danh sách lệnh đang chờ khớp"""
        pass
        
    @abstractmethod
    def restore_orders(self, orders: List[Dict[str, Any]]):
        """Khôi phục các lệnh đã có từ trước (ví dụ sau khi restart)"""
        pass
        
    @abstractmethod
    def get_trade_history(self, symbol: str) -> List[Dict[str, Any]]:
        """Lấy lịch sử giao dịch (mô phỏng exchange API)"""
        pass
        
    @abstractmethod
    def restore_trades(self, trades: List[Dict[str, Any]]):
        """Khôi phục lịch sử giao dịch cho Simulator"""
        pass
        
    @abstractmethod
    def on_tick(self, tick: TickEvent):
        """Dành cho Backtest/Paper để nhận data giả lập khớp lệnh. Live Adapter có thể bỏ qua."""
        pass
