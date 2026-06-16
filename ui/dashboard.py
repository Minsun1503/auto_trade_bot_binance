import time
from textual.app import App, ComposeResult
from textual.binding import Binding

from core.events import (
    EventBus, CommandEvent, StateTransitionEvent, EquityUpdateEvent,
    OrderEvent, TradeEvent, LogEvent, SystemHealthEvent
)
from ui.panels.status_panel import StatusPanel
from ui.panels.health_panel import HealthPanel
from ui.panels.equity_panel import EquityPanel
from ui.panels.orders_panel import OrdersPanel
from ui.panels.trades_panel import TradesPanel
from ui.panels.logs_panel import LogsPanel

class DashboardApp(App):
    CSS_PATH = "dashboard.css"
    BINDINGS = [
        Binding("p", "pause_engine", "Pause Engine"),
        Binding("r", "resume_engine", "Resume Engine"),
        Binding("s", "snapshot", "Save Snapshot"),
        Binding("d", "disconnect", "Drop Data (10s)"),
        Binding("t", "torture", "Toggle Torture Mode"),
        Binding("i", "drift", "Toggle Time Drift"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, event_bus: EventBus, runner):
        super().__init__()
        self.event_bus = event_bus
        self.runner = runner
        self.last_equity_update = 0
        self.frames = 0
        self.events_processed = 0
        self.last_fps_time = time.time()
        self.current_fps = 0.0
        self.current_eps = 0.0

    def compose(self) -> ComposeResult:
        yield StatusPanel(id="status_panel")
        yield HealthPanel(id="health_panel")
        yield EquityPanel(id="equity_panel")
        yield OrdersPanel(id="orders_panel")
        yield TradesPanel(id="trades_panel")
        yield LogsPanel(id="logs_panel")

    def on_mount(self) -> None:
        self.set_interval(0.1, self.poll_events)
        self.set_interval(0.5, self.refresh_heavy_ui)
        self.set_interval(1.0, self.update_fps)

    def update_fps(self):
        now = time.time()
        dt = now - self.last_fps_time
        if dt > 0:
            self.current_fps = self.frames / dt
            self.current_eps = self.events_processed / dt
        self.frames = 0
        self.events_processed = 0
        self.last_fps_time = now

    def poll_events(self):
        self.frames += 1
        events = self.event_bus.get_all()
        self.events_processed += len(events)
        
        needs_order_refresh = False
        needs_trade_refresh = False
        
        for e in events:
            if isinstance(e, StateTransitionEvent):
                self.query_one(StatusPanel).update_state(e.to_state)
                self.query_one(LogsPanel).write_log(f"TRANSITION: {e.from_state} -> {e.to_state} | {e.reason}", "WARNING")
                
            elif isinstance(e, OrderEvent):
                self.query_one(OrdersPanel).process_event(e.action, e.order_id, e.side, e.price, e.quantity)
                needs_order_refresh = True
                
            elif isinstance(e, TradeEvent):
                self.query_one(TradesPanel).process_event(e.side, e.price, e.quantity, e.fee)
                needs_trade_refresh = True
                
            elif isinstance(e, LogEvent):
                self.query_one(LogsPanel).write_log(e.message, e.level)

        if needs_order_refresh:
            self.query_one(OrdersPanel).refresh_table()
        if needs_trade_refresh:
            self.query_one(TradesPanel).refresh_table()
            
        # Handle telemetry lock-free
        eq_event = self.event_bus.latest_equity
        if eq_event:
            self.query_one(StatusPanel).update_equity(
                symbol="BTC/USDT", 
                equity=eq_event.equity, cash=eq_event.cash, asset=eq_event.asset_value,
                roi=eq_event.roi, dd=eq_event.drawdown
            )
            # Dùng throttle/debounce cho plot để không bị giật, 
            # tuy nhiên `EquityPanel` sẽ handle việc add point và limit max point.
            # We add point every poll if there's an update
            self.query_one(EquityPanel).add_point(eq_event.equity)
            
        health_event = self.event_bus.latest_health
        if health_event:
            self.query_one(HealthPanel).update_health(
                health_event.queue_size, 
                health_event.engine_status, 
                health_event.last_tick, 
                self.current_fps,
                self.current_eps
            )

    def refresh_heavy_ui(self):
        self.query_one(EquityPanel).refresh_plot()

    def action_pause_engine(self):
        self.runner.process_command(CommandEvent(command="PAUSE"))
        self.query_one(LogsPanel).write_log("USER COMMAND: PAUSE", "WARNING")

    def action_resume_engine(self):
        self.runner.process_command(CommandEvent(command="RESUME"))
        self.query_one(LogsPanel).write_log("USER COMMAND: RESUME", "WARNING")

    def action_snapshot(self):
        self.runner.process_command(CommandEvent(command="SNAPSHOT"))
        self.query_one(LogsPanel).write_log("USER COMMAND: SAVE SNAPSHOT", "WARNING")

    def action_quit_app(self):
        self.runner.process_command(CommandEvent(command="QUIT"))
        self.exit()

    def action_disconnect(self):
        if hasattr(self.runner, 'provider') and hasattr(self.runner.provider, 'drop_data_for'):
            self.runner.provider.drop_data_for(10)
            self.query_one(LogsPanel).write_log("USER COMMAND: FAKE DISCONNECT (10s)", "ERROR")

    def action_torture(self):
        if hasattr(self.runner, 'provider') and hasattr(self.runner.provider, 'torture_mode'):
            provider = self.runner.provider
            if provider.torture_mode:
                provider.disable_torture_mode()
                self.query_one(LogsPanel).write_log("USER COMMAND: TORTURE MODE DISABLED", "INFO")
            else:
                provider.enable_torture_mode()
                self.query_one(LogsPanel).write_log("USER COMMAND: TORTURE MODE ENABLED", "ERROR")

    def action_drift(self):
        if hasattr(self.runner, 'provider') and hasattr(self.runner.provider, 'time_drift_mode'):
            provider = self.runner.provider
            if provider.time_drift_mode:
                provider.disable_time_drift()
                self.query_one(LogsPanel).write_log("USER COMMAND: TIME DRIFT DISABLED", "INFO")
            else:
                provider.enable_time_drift()
                self.query_one(LogsPanel).write_log("USER COMMAND: TIME DRIFT ENABLED", "ERROR")
