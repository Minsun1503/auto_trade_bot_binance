from abc import ABC, abstractmethod
from typing import Callable, Any
from datetime import datetime
import pandas as pd

from core.events import TickEvent

class MarketDataProvider(ABC):
    """
    Interface cho Nguồn dữ liệu (Historical, Realtime Simulation, Live WebSocket)
    """
    
    @abstractmethod
    def start(self):
        """Khởi động luồng cung cấp dữ liệu"""
        pass
        
    @abstractmethod
    def stop(self):
        """Dừng cung cấp dữ liệu"""
        pass
        
    @abstractmethod
    def subscribe(self, callback: Callable[[TickEvent], None]):
        """Đăng ký callback nhận dữ liệu."""
        pass
        
    @abstractmethod
    def get_current_time(self) -> datetime:
        """Lấy thời gian hiện tại của Market (không được dùng datetime.now() trong Engine)"""
        pass
