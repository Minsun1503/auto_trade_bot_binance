from textual.app import ComposeResult
from textual.widgets import Static
from textual_plotext import PlotextPlot

class EquityPanel(Static):
    def compose(self) -> ComposeResult:
        yield PlotextPlot(id="equity_plot")

    def on_mount(self) -> None:
        self.points = []
        self.max_points = 500
        
    def add_point(self, value: float):
        self.points.append(value)
        if len(self.points) > self.max_points:
            self.points = self.points[-self.max_points:]
            
    def refresh_plot(self):
        if not self.points: return
        plot = self.query_one(PlotextPlot)
        plt = plot.plt
        plt.clear_data()
        plt.plot(self.points, marker="dot", color="green")
        plt.title("Equity Curve")
        plot.refresh()
