from typing import List
from datetime import datetime
import numpy as np

def calculate_roi(initial: float, final: float) -> float:
    return (final - initial) / initial if initial > 0 else 0.0

def calculate_cagr(initial: float, final: float, start_date: datetime, end_date: datetime) -> float:
    days = (end_date - start_date).days
    if days <= 0 or initial <= 0:
        return 0.0
    years = days / 365.25
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

def calculate_sharpe(returns: List[float], risk_free_rate: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    mean_return = np.mean(returns)
    std_dev = np.std(returns)
    if std_dev == 0:
        return 0.0
    return (mean_return - risk_free_rate) / std_dev

def calculate_sortino(returns: List[float], risk_free_rate: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    mean_return = np.mean(returns)
    downside = [r for r in returns if r < 0]
    if not downside:
        return 0.0 # Infinite Sortino, basically no downside
    downside_std = np.std(downside)
    if downside_std == 0:
        return 0.0
    return (mean_return - risk_free_rate) / downside_std
