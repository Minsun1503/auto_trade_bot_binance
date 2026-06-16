import queue
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

@dataclass
class Event:
    timestamp: int = field(init=False)
    
    def __post_init__(self):
        if not hasattr(self, 'timestamp'):
            import time
            self.timestamp = int(time.time() * 1000)

@dataclass
class TickEvent(Event):
    timestamp: int # ms epoch
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool
    source: str
    
    def __post_init__(self):
        # Override post_init so we don't overwrite timestamp with datetime.now()
        pass

@dataclass
class TradeEvent(Event):
    side: str
    price: float
    quantity: float
    fee: float

@dataclass
class OrderEvent(Event):
    action: str # CREATE, FILL, CANCEL
    order_id: str
    side: str
    price: float
    quantity: float

@dataclass
class StateTransitionEvent(Event):
    from_state: str
    to_state: str
    reason: str

@dataclass
class EquityUpdateEvent(Event):
    equity: float
    cash: float
    asset_value: float
    roi: float
    drawdown: float

@dataclass
class LogEvent(Event):
    message: str
    level: str = "INFO"

@dataclass
class CommandEvent(Event):
    command: str # PAUSE, RESUME, SNAPSHOT, QUIT
    payload: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SystemHealthEvent(Event):
    queue_size: int
    engine_status: str
    last_tick: Optional[datetime] = None
    events_per_sec: float = 0.0

class EventBus:
    def __init__(self, maxsize: int = 20000):
        self.queue = queue.Queue(maxsize=maxsize)
        
        # Telemetry pattern (Lock-free updates)
        self.latest_equity: Optional[EquityUpdateEvent] = None
        self.latest_health: Optional[SystemHealthEvent] = None
        
    def publish(self, event: Event):
        if isinstance(event, EquityUpdateEvent):
            self.latest_equity = event
        elif isinstance(event, SystemHealthEvent):
            self.latest_health = event
        else:
            try:
                self.queue.put_nowait(event)
            except queue.Full:
                pass # Drop logs or others if full to prevent blocking
            
    def get_all(self) -> List[Event]:
        events = []
        while not self.queue.empty():
            try:
                events.append(self.queue.get_nowait())
            except queue.Empty:
                break
        return events
