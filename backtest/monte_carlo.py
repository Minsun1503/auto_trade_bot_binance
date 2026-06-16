"""
Phase 3.5C - Block Bootstrap Monte Carlo
Thực hiện giả lập Monte Carlo dựa trên phương pháp Stationary Block Bootstrap với fixed seed và block size động.
Đo lường các mốc drawdown P50/P95/P99, worst drawdown, và xác suất sụt giảm tài sản (Prob of Drawdown > 25% / 50%).
"""
from typing import List, Dict
import numpy as np

def calculate_avg_losing_streak(trades_pnl: List[float]) -> float:
    """
    Tính độ dài chuỗi thua lỗ liên tiếp trung bình (PnL <= 0).
    Nếu không có chuỗi thua lỗ nào hoặc chuỗi trung bình < 1.0, trả về 1.0.
    """
    if not trades_pnl:
        return 1.0
    
    streaks = []
    current_streak = 0
    for pnl in trades_pnl:
        if pnl <= 0:
            current_streak += 1
        else:
            if current_streak > 0:
                streaks.append(current_streak)
                current_streak = 0
    if current_streak > 0:
        streaks.append(current_streak)
        
    if not streaks:
        return 1.0
    return float(np.mean(streaks))

def run_monte_carlo_simulation(
    trades_pnl: List[float],
    initial_capital: float,
    num_simulations: int = 1000,
    random_seed: int = 42
) -> Dict:
    """
    Chạy giả lập Monte Carlo sử dụng thuật toán Stationary Block Bootstrap.
    
    Args:
        trades_pnl: Danh sách lợi nhuận/thua lỗ thực tế của từng trade.
        initial_capital: Vốn ban đầu.
        num_simulations: Số lần giả lập (mặc định 1000).
        random_seed: Seed cố định cho numpy.random để đảm bảo tính tái lập.
        
    Returns:
        dict chứa các chỉ số phân vị drawdown và xác suất sụt giảm tài sản.
    """
    if not trades_pnl:
        return {
            "p50_dd": 0.0,
            "p95_dd": 0.0,
            "p99_dd": 0.0,
            "worst_dd": 0.0,
            "prob_dd_25": 0.0,
            "prob_dd_50": 0.0,
            "average_block_size": 1.0
        }
        
    np.random.seed(random_seed)
    n_trades = len(trades_pnl)
    
    # Tính block size trung bình dựa trên losing streak
    avg_losing_streak = calculate_avg_losing_streak(trades_pnl)
    # p là tham số của phân phối hình học xác định độ dài block trong Stationary Bootstrap
    p = 1.0 / avg_losing_streak
    
    drawdowns = []
    ruin_count_25 = 0
    ruin_count_50 = 0
    
    for _ in range(num_simulations):
        # Tạo chuỗi trades giả lập bằng Stationary Bootstrap
        sim_pnl = []
        # Khởi tạo chỉ mục ngẫu nhiên đầu tiên
        idx = np.random.randint(0, n_trades)
        
        while len(sim_pnl) < n_trades:
            sim_pnl.append(trades_pnl[idx])
            # Với xác suất p, chuyển sang bốc vị trí mới ngẫu nhiên
            if np.random.rand() < p:
                idx = np.random.randint(0, n_trades)
            else:
                # Với xác suất 1-p, chuyển sang index tiếp theo (tự động quay vòng đầu mảng)
                idx = (idx + 1) % n_trades
                
        # Dựng equity curve từ chuỗi trade giả lập
        sim_equity = [initial_capital]
        for pnl in sim_pnl:
            next_eq = max(0.0, sim_equity[-1] + pnl)
            sim_equity.append(next_eq)
            
        # Tính Max Drawdown của kịch bản này
        peak = sim_equity[0]
        max_sim_dd = 0.0
        hit_25 = False
        hit_50 = False
        
        for eq in sim_equity:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0.0
            if dd > max_sim_dd:
                max_sim_dd = dd
            if dd > 0.25:
                hit_25 = True
            if dd > 0.50:
                hit_50 = True
                
        drawdowns.append(max_sim_dd)
        if hit_25:
            ruin_count_25 += 1
        if hit_50:
            ruin_count_50 += 1
            
    return {
        "p50_dd": float(np.percentile(drawdowns, 50)),
        "p95_dd": float(np.percentile(drawdowns, 95)),
        "p99_dd": float(np.percentile(drawdowns, 99)),
        "worst_dd": float(np.max(drawdowns)),
        "prob_dd_25": ruin_count_25 / num_simulations,
        "prob_dd_50": ruin_count_50 / num_simulations,
        "average_block_size": avg_losing_streak
    }
