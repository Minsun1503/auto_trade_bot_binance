from dataclasses import dataclass
from datetime import datetime
from .state import BotState

@dataclass
class StateTransitionEvent:
    """Lịch sử chuyển đổi trạng thái của hệ thống"""
    old_state: BotState
    new_state: BotState
    reason: str
    timestamp: datetime
