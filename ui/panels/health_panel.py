from textual.app import ComposeResult
from textual.widgets import Static

class HealthPanel(Static):
    def compose(self) -> ComposeResult:
        yield Static("Event Queue: 0", id="health_queue")
        yield Static("Engine: STOPPED", id="health_engine")
        yield Static("Last Tick: ---", id="health_tick")
        yield Static("UI FPS: ---", id="health_fps")
        yield Static("Events/s: 0.0", id="health_eps")

    def update_health(self, qsize, status, last_tick, fps, eps):
        self.query_one("#health_queue").update(f"Event Queue: {qsize}")
        self.query_one("#health_engine").update(f"Engine: {status}")
        tick_str = last_tick.strftime('%H:%M:%S') if last_tick else "---"
        self.query_one("#health_tick").update(f"Last Tick: {tick_str}")
        self.query_one("#health_fps").update(f"UI FPS: {fps:.1f}")
        self.query_one("#health_eps").update(f"Events/s: {eps:.1f}")
