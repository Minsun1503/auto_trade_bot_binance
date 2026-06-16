"""
Phase 3.5B - Benchmarks Module
Buy & Hold: mua toàn bộ vốn tại nến đầu tiên, giữ đến nến cuối cùng, không giao dịch gì thêm.
Được dùng làm baseline đối chiếu chéo với Strategy trong strategy_validation_report.md.
"""
from typing import Dict
import pandas as pd

from backtest.metrics import (
    calculate_roi,
    calculate_cagr,
    calculate_max_drawdown,
    calculate_annualized_sharpe,
    calculate_annualized_sortino,
    calculate_calmar_ratio,
    calculate_recovery_factor,
)


def run_buy_and_hold(data: pd.DataFrame, initial_capital: float) -> Dict:
    """
    Tính hiệu năng Buy & Hold độc lập trên tập data (không qua TradingEngine).

    Args:
        data: DataFrame OHLCV với DatetimeIndex (cột 'close' bắt buộc). Caller chịu
              trách nhiệm cắt bỏ warmup window khỏi `data` trước khi gọi hàm này,
              vì warmup không thuộc phạm vi đo lường kết quả.
        initial_capital: Vốn khởi điểm bằng quote currency (USDT).

    Returns:
        dict chứa roi, cagr, max_drawdown, sharpe, sortino, calmar, recovery_factor,
        equity_curve (List[float]) và metadata start/end date.
    """
    if data is None or len(data) == 0:
        return _empty_result(initial_capital)

    df = data.sort_index()
    entry_price = float(df["close"].iloc[0])
    exit_price = float(df["close"].iloc[-1])

    if entry_price <= 0:
        return _empty_result(initial_capital)

    quantity = initial_capital / entry_price

    # Equity curve: mark-to-market mỗi nến bằng quantity cố định * close price
    equity_curve = (df["close"].astype(float) * quantity).tolist()

    final_equity = quantity * exit_price
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
        "label": "Buy & Hold",
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
        "entry_price": entry_price,
        "exit_price": exit_price,
        "quantity": quantity,
    }


def _equity_curve_to_daily_returns(index: pd.DatetimeIndex, equity_curve: list) -> list:
    """Resample equity curve (tần suất bất kỳ) xuống daily close-of-day để tính return."""
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
        "label": "Buy & Hold",
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
        "entry_price": 0.0,
        "exit_price": 0.0,
        "quantity": 0.0,
    }
