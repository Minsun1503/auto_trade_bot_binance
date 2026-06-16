import time
from textual.app import ComposeResult
from textual.widgets import DataTable
from textual.widgets import Static

class TradesPanel(Static):
    def compose(self) -> ComposeResult:
        yield DataTable(id="trades_table")

    def on_mount(self) -> None:
        self.trades = []
        table = self.query_one(DataTable)
        table.add_columns("Side", "Price", "Qty", "Fee")

    def process_event(self, side, price, qty, fee):
        self.trades.insert(0, {'side': side, 'price': price, 'qty': qty, 'fee': fee})
        if len(self.trades) > 50:
            self.trades.pop()

    def refresh_table(self):
        table = self.query_one(DataTable)
        table.clear()
        for t in self.trades:
            color = "green" if t['side'] == 'BUY' else "red"
            table.add_row(f"[{color}]{t['side']}[/{color}]", f"{t['price']:.2f}", f"{t['qty']:.4f}", f"{t['fee']:.4f}")
