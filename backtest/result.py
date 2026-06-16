from dataclasses import dataclass
from datetime import datetime

@dataclass
class BacktestResult:
    start_date: datetime
    end_date: datetime
    
    initial_capital: float
    final_equity: float
    
    strategy_roi: float
    buyhold_roi: float
    excess_return: float
    
    cagr: float
    max_drawdown: float
    
    total_trades: int
    win_rate: float
    
    gross_profit: float
    net_profit: float
    total_fees_usdt: float
    
    def print_summary(self):
        print("="*40)
        print("BACKTEST RESULT SUMMARY")
        print("="*40)
        print(f"Period:       {self.start_date.strftime('%Y-%m-%d')} -> {self.end_date.strftime('%Y-%m-%d')}")
        print(f"Capital:      ${self.initial_capital:,.2f} -> ${self.final_equity:,.2f}")
        print("-"*40)
        print(f"Strategy ROI: {self.strategy_roi*100:+.2f}%")
        print(f"Buy&Hold ROI: {self.buyhold_roi*100:+.2f}%")
        print(f"Excess Return:{self.excess_return*100:+.2f}%")
        print("-"*40)
        print(f"CAGR:         {self.cagr*100:.2f}%")
        print(f"Max Drawdown: {self.max_drawdown*100:.2f}%")
        print(f"Total Trades: {self.total_trades}")
        print(f"Win Rate:     {self.win_rate*100:.2f}%")
        print("-"*40)
        print(f"Gross Profit: ${self.gross_profit:,.2f}")
        print(f"Total Fees:   ${self.total_fees_usdt:,.2f}")
        print(f"Net Profit:   ${self.net_profit:,.2f}")
        print("="*40)
