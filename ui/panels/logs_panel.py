from textual.app import ComposeResult
from textual.widgets import RichLog
from textual.widgets import Static

class LogsPanel(Static):
    def compose(self) -> ComposeResult:
        yield RichLog(id="system_logs", highlight=True, markup=True, wrap=True)

    def write_log(self, message: str, level: str="INFO"):
        log = self.query_one(RichLog)
        color = "white"
        if level == "ERROR": color = "red"
        elif level == "WARNING": color = "yellow"
        log.write(f"[{color}]{message}[/{color}]")
