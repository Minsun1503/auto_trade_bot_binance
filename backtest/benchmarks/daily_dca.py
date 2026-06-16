"""
Phase 3.5B - Benchmarks Module
Daily DCA: chia đều vốn khởi điểm cho tổng số ngày và mua BTC đều đặn vào nến đầu tiên của mỗi ngày.
Được dùng làm baseline đối chiếu chéo với Strategy trong strategy_validation_report.md.
"""
from typing import Dict
import pandas as pd
import numpy as np

from backtest.metrics import (
    calculate_roi,
    calculate_cagr,
    calculate_max_drawdown,
    calculate_annualized_sharpe,
    calculate_annualized_sortino,
    calculate_calmar_ratio,
    calculate_recovery_factor,
)


def run_daily_dca(data: pd.DataFrame, initial_capital: float) -> Dict:
    """
    Tính hiệu năng Daily DCA độc lập trên tập data (không qua TradingEngine).

    Args:
        data: DataFrame OHLCV với DatetimeIndex (cột 'close' bắt buộc). Caller chịu
              trách nhiệm cắt bỏ warmup window khỏi `data` trước khi gọi hàm này.
        initial_capital: Vốn khởi điểm bằng quote currency (USDT).

    Returns:
        dict chứa roi, cagr, max_drawdown, sharpe, sortino, calmar, recovery_factor,
        equity_curve (List[float]) và metadata start/end date.
    """
    if data is None or len(data) == 0:
        return _empty_result(initial_capital)

    df = data.sort_index()
    unique_days = df.index.normalize().unique()
    num_days = len(unique_days)

    if num_days <= 0:
        return _empty_result(initial_capital)

    cash_per_day = initial_capital / num_days

    # Khởi tạo các cột/mảng để tính toán vị thế và cash tại mỗi tick
    cash_series = pd.Series(initial_capital, index=df.index)
    qty_series = pd.Series(0.0, index=df.index)

    # Tìm index của nến đầu tiên trong mỗi ngày để thực hiện mua DCA
    first_tick_indices = df.groupby(df.index.normalize()).apply(lambda x: x.index[0])
    
    current_cash = initial_capital
    current_qty = 0.0

    # Lập lịch mua DCA
    for day in unique_days:
        idx = first_tick_indices[day]
        close_price = float(df.loc[idx, "close"])
        if close_price > 0:
            qty_bought = cash_per_day / close_price
            current_cash -= cash_per_day
            current_qty += qty_bought
        # Ghi nhận trạng thái từ thời điểm mua này trở đi
        cash_series.loc[idx:] = current_cash
        qty_series.loc[idx:] = current_qty

    # Tính toán Equity Curve tại từng tick = cash + qty * close
    equity_curve_series = cash_series + qty_series * df["close"].astype(float)
    equity_curve = equity_curve_series.tolist()

    final_equity = float(equity_curve[-1])
    roi = calculate_roi(initial_capital, final_equity)

    start_date = df.index[0].to_pydatetime()
    end_date = df.index[-1].to_pydatetime()
    cagr = calculate_cagr(initial_capital, final_equity, start_date, end_date)
    max_dd = calculate_max_drawdown(equity_curve)

    daily_returns = _equity_curve_to_daily_returns(df.index, equity_curve)
    sharpe = calculate_annualized_sharpe(daily_returns)
    sortino = calculate_annualized_sortino(daily_returns)
    calmar = calculate_calmar_ratio(cagr, max_dd)

    net_profit = final_equity - initial_capital
    max_dd_amount = max_dd * max(equity_curve) if equity_curve else 0.0
    recovery = calculate_recovery_factor(net_profit, max_dd_amount)

    return {
        "label": "Daily DCA",
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": initial_capital,
        "final_equity": final_equity,
        "roi": roi,
        "cagr": cagr,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "recovery_factor": recovery,
        "net_profit": net_profit,
        "equity_curve": equity_curve,
        "final_quantity": current_qty,
        "remaining_cash": current_cash,
    }


def _equity_curve_to_daily_returns(index: pd.DatetimeIndex, equity_curve: list) -> list:
    """Resample equity curve xuống daily close-of-day để tính return."""
    if not equity_curve:
        return []
    series = pd.Series(equity_curve, index=index)
    daily = series.resample("1D").last().dropna()
    if len(daily) < 2:
        return []
    returns = daily.pct_change().dropna().tolist()
    return returns


def _empty_result(initial_capital: float) -> Dict:
    return {
        "label": "Daily DCA",
        "start_date": None,
        "end_date": None,
        "initial_capital": initial_capital,
        "final_equity": initial_capital,
        "roi": 0.0,
        "cagr": 0.0,
        "max_drawdown": 0.0,
        "sharpe": 0.0,
        "sortino": 0.0,
        "calmar": 0.0,
        "recovery_factor": 0.0,
        "net_profit": 0.0,
        "equity_curve": [],
        "final_quantity": 0.0,
        "remaining_cash": initial_capital,
    }
