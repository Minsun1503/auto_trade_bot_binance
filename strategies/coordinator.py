import logging
from typing import List, Protocol
from datetime import datetime
from config.settings import CoordinatorConfig
from .state import BotState
from .context import MarketContext
from .transition import StateTransitionEvent
from core.events import EventBus

logger = logging.getLogger(__name__)

class IStrategy(Protocol):
    def start(self, engine): ...
    def stop(self, engine): ...
    def is_running(self) -> bool: ...
    def process_tick(self, context: MarketContext, timestamp: datetime, engine): ...
    def on_order_fill(self, order_id: str, side: str, price: float, quantity: float, engine): ...
    def get_tracked_orders(self) -> List[str]: ...

class Coordinator:
    def __init__(self, grid: IStrategy, dca: IStrategy, config: CoordinatorConfig, event_bus: EventBus = None):
        self.state = BotState.INIT
        self.grid = grid
        self.dca = dca
        self.config = config
        self.transitions: List[StateTransitionEvent] = []
        self.event_bus = event_bus
        
    def _transition_to(self, new_state: BotState, reason: str, timestamp: datetime):
        event = StateTransitionEvent(self.state, new_state, reason, timestamp)
        self.transitions.append(event)
        self.state = new_state
        logger.info(f"[{timestamp}] TRANSITION: {event.old_state.value} -> {event.new_state.value} | Reason: {reason}")
        if self.event_bus:
            self.event_bus.publish(event)
        
    def evaluate(self, context: MarketContext, timestamp: datetime, engine):
        if context.spread > self.config.max_spread_pct:
            if self.state != BotState.PAUSE:
                self.grid.stop(engine)
                self.dca.stop(engine)
                self._transition_to(BotState.PAUSE, f"Spread > {self.config.max_spread_pct}", timestamp)
            return
            
        if self.state == BotState.INIT:
            self.grid.start(engine)
            self._transition_to(BotState.GRID, "Bắt đầu với GRID", timestamp)
            
        elif self.state == BotState.GRID:
            if context.drawdown >= self.config.drawdown_trigger:
                self.grid.stop(engine)
                self.dca.start(engine)
                self._transition_to(BotState.DCA, f"Drawdown >= {self.config.drawdown_trigger}", timestamp)
                
        elif self.state == BotState.DCA:
            recovery_dd = self.config.drawdown_trigger / 2.0
            if context.drawdown <= recovery_dd and context.price > context.ma50 and context.price > context.ma200:
                self.dca.stop(engine)
                self.grid.start(engine)
                self._transition_to(BotState.GRID, "Phục hồi. Kích hoạt lại GRID", timestamp)
                
        elif self.state == BotState.PAUSE:
            if context.spread <= self.config.max_spread_pct:
                if context.drawdown >= self.config.drawdown_trigger:
                    self.dca.start(engine)
                    self._transition_to(BotState.DCA, "Spread bình thường. DCA", timestamp)
                else:
                    self.grid.start(engine)
                    self._transition_to(BotState.GRID, "Spread bình thường. GRID", timestamp)

        # Delegate tick to active strategy
        if self.grid.is_running():
            self.grid.process_tick(context, timestamp, engine)
        if self.dca.is_running():
            self.dca.process_tick(context, timestamp, engine)

    def on_order_fill(self, order_id: str, side: str, price: float, quantity: float, engine):
        # Route fill event to running strategies
        if self.grid.is_running():
            self.grid.on_order_fill(order_id, side, price, quantity, engine)
        if self.dca.is_running():
            self.dca.on_order_fill(order_id, side, price, quantity, engine)
            
    def get_tracked_orders(self) -> List[str]:
        return self.grid.get_tracked_orders() + self.dca.get_tracked_orders()
