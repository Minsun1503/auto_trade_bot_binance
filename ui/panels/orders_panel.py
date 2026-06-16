from textual.app import ComposeResult
from textual.widgets import DataTable
from textual.widgets import Static

class OrdersPanel(Static):
    def compose(self) -> ComposeResult:
        yield DataTable(id="orders_table")

    def on_mount(self) -> None:
        self.active_orders = {}
        table = self.query_one(DataTable)
        table.add_columns("Side", "Price", "Qty")

    def process_event(self, action, order_id, side, price, qty):
        if action == "CREATE":
            self.active_orders[order_id] = {'side': side, 'price': price, 'qty': qty}
        elif action in ["FILL", "CANCEL"]:
            if order_id in self.active_orders:
                del self.active_orders[order_id]

    def refresh_table(self):
        table = self.query_one(DataTable)
        table.clear()
        for k, o in self.active_orders.items():
            color = "green" if o['side'] == 'BUY' else "red"
            table.add_row(f"[{color}]{o['side']}[/{color}]", f"{o['price']:.2f}", f"{o['qty']:.4f}")
