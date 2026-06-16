from textual.app import ComposeResult
from textual.widgets import Static

class StatusPanel(Static):
    def compose(self) -> ComposeResult:
        yield Static("State: INIT", id="status_state")
        yield Static("Symbol: ---", id="status_symbol")
        yield Static("Equity: $0.00", id="status_equity")
        yield Static("Cash: $0.00", id="status_cash")
        yield Static("Asset: $0.00", id="status_asset")
        yield Static("ROI: 0.00%", id="status_roi")
        yield Static("Max DD: 0.00%", id="status_dd")

    def update_equity(self, symbol, equity, cash, asset, roi, dd):
        self.query_one("#status_symbol").update(f"Symbol: {symbol}")
        self.query_one("#status_equity").update(f"Equity: ${equity:,.2f}")
        self.query_one("#status_cash").update(f"Cash: ${cash:,.2f}")
        self.query_one("#status_asset").update(f"Asset: ${asset:,.2f}")
        color_roi = "green" if roi >= 0 else "red"
        self.query_one("#status_roi").update(f"ROI: [{color_roi}]{roi*100:+.2f}%[/{color_roi}]")
        self.query_one("#status_dd").update(f"Max DD: {dd*100:.2f}%")

    def update_state(self, state):
        self.query_one("#status_state").update(f"State: {state}")
