from typing import List, Dict
from datetime import datetime
import numpy as np

def calculate_roi(initial: float, final: float) -> float:
    return (final - initial) / initial if initial > 0 else 0.0

def calculate_cagr(initial: float, final: float, start_date: datetime, end_date: datetime) -> float:
    days = (end_date - start_date).days
    if days <= 0 or initial <= 0:
        return 0.0
    years = days / 365.25
    if final / initial <= 0:
        return -1.0 # 100% loss or invalid negative final capital
    return (final / initial) ** (1 / years) - 1

def calculate_max_drawdown(equity_curve: List[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd

def calculate_annualized_sharpe(daily_returns: List[float], risk_free_rate: float = 0.0) -> float:
    """
    Tính Annualized Sharpe Ratio dựa trên daily equity returns.
    Tần suất chuẩn cho crypto là 365 ngày/năm.
    """
    if len(daily_returns) < 2:
        return 0.0
    mean_return = np.mean(daily_returns)
    std_dev = np.std(daily_returns)
    if std_dev == 0:
        return 0.0
    return ((mean_return - risk_free_rate) / std_dev) * np.sqrt(365)

def calculate_annualized_sortino(daily_returns: List[float], risk_free_rate: float = 0.0) -> float:
    """
    Tính Annualized Sortino Ratio dựa trên daily equity returns.
    Tần suất chuẩn cho crypto là 365 ngày/năm.
    """
    if len(daily_returns) < 2:
        return 0.0
    mean_return = np.mean(daily_returns)
    downside = [r for r in daily_returns if r < 0]
    if not downside:
        return 999.0  # Không có rủi ro giảm giá
    downside_std = np.std(downside)
    if downside_std == 0:
        return 0.0
    return ((mean_return - risk_free_rate) / downside_std) * np.sqrt(365)

def calculate_calmar_ratio(annualized_return: float, max_drawdown: float) -> float:
    """
    Calmar Ratio = Annualized Return / |Max Drawdown|
    """
    if abs(max_drawdown) < 1e-6:
        return 999.0 if annualized_return > 0 else 0.0
    return annualized_return / abs(max_drawdown)

def calculate_recovery_factor(net_profit: float, max_drawdown_amount: float) -> float:
    """
    Recovery Factor = Net Profit / |Max Drawdown (in absolute cash value)|
    Hoặc Net Profit % / |Max Drawdown %|.
    Dưới đây tính theo giá trị tuyệt đối cash value.
    """
    if abs(max_drawdown_amount) < 1e-6:
        return 999.0 if net_profit > 0 else 0.0
    return net_profit / abs(max_drawdown_amount)

def calculate_profit_factor(trades_pnl: List[float]) -> float:
    """
    Profit Factor = sum(profits) / sum(losses) (losses as positive value)
    """
    profits = [p for p in trades_pnl if p > 0]
    losses = [abs(p) for p in trades_pnl if p < 0]
    sum_profits = sum(profits)
    sum_losses = sum(losses)
    if sum_losses == 0:
        return 999.0 if sum_profits > 0 else 0.0
    return sum_profits / sum_losses

def calculate_expectancy(trades_pnl: List[float]) -> float:
    """
    Expectancy = (WinRate * AvgWin) - (LoseRate * AvgLoss) (AvgLoss as positive value)
    """
    if not trades_pnl:
        return 0.0
    wins = [p for p in trades_pnl if p > 0]
    losses = [abs(p) for p in trades_pnl if p < 0]
    
    total = len(trades_pnl)
    win_rate = len(wins) / total
    lose_rate = len(losses) / total
    
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = np.mean(losses) if losses else 0.0
    
    return (win_rate * avg_win) - (lose_rate * avg_loss)

def calculate_exposure_ratio(position_history: List[float]) -> float:
    """
    Exposure Ratio = Số lượng mẫu có nắm vị thế / Tổng số mẫu
    """
    if not position_history:
        return 0.0
    active_samples = sum(1 for qty in position_history if abs(qty) > 1e-8)
    return active_samples / len(position_history)

def calculate_trade_frequency(total_trades: int, start_date: datetime, end_date: datetime) -> Dict[str, float]:
    """
    Tính toán số giao dịch trên ngày và tháng.
    """
    days = (end_date - start_date).days
    if days <= 0:
        return {"trades_per_day": 0.0, "trades_per_month": 0.0}
    trades_per_day = total_trades / days
    trades_per_month = trades_per_day * 30.4375
    return {
        "trades_per_day": trades_per_day,
        "trades_per_month": trades_per_month
    }

