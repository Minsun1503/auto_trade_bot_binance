# Strategy Validation & Risk Report

- **Ngày chạy báo cáo**: 2026-06-16 23:26:40
- **Freeze Checksum**: `6c49010d9d9566cb3ae601c270da965b79f29b9fa13ff931fcc14b9515fcfb0b`
- **Trạng thái Code Freeze Match**: `YES` (Đăng ký thành công)
- **Chế độ kiểm thử**: `Full 12-Month`
- **Cổng kiểm duyệt cuối cùng**: `FAIL`

### Danh sách vi phạm (Violations):
- ❌ FAIL: IS Bear Regime trades count 1 < 20 (IS minimum limit per regime).
- ❌ FAIL: IS Recovery Regime trades count 0 < 20 (IS minimum limit per regime).
- ❌ FAIL: IS Bull Regime trades count 0 < 20 (IS minimum limit per regime).
- ❌ FAIL: Total IS trades count 1 < 100.
- ❌ FAIL: OOS Sideways Regime trades count 3 < 30 (OOS sub-regime limit).
- ❌ FAIL: OOS Sideways Regime Sharpe -0.13 < 0.7.
- ❌ FAIL: OOS Sideways Regime Sortino -0.20 < 1.0.
- ❌ FAIL: OOS Sideways Regime Recovery Factor -0.14 < 1.0.
- ❌ FAIL: OOS Sideways Regime Calmar Ratio -0.59 < 0.5.
- ❌ FAIL: OOS Sideways Regime Sharpe Degradation: -0.13 < 1.26 (50% of Median IS Sharpe).
- ❌ FAIL: OOS Mini-Bear Regime trades count 6 < 30 (OOS sub-regime limit).
- ❌ FAIL: OOS Mini-Bear Regime Sharpe 0.43 < 0.7.
- ❌ FAIL: OOS Mini-Bear Regime Sortino 0.69 < 1.0.
- ❌ FAIL: OOS Mini-Bear Regime Recovery Factor 0.23 < 1.0.
- ❌ FAIL: OOS Mini-Bear Regime Sharpe Degradation: 0.43 < 1.26 (50% of Median IS Sharpe).
- ❌ FAIL: Holdout trades count 1 < 30.
- ❌ FAIL: Holdout Sharpe -1.61 < 0.7.
- ❌ FAIL: Holdout Sortino -2.56 < 1.0.
- ❌ FAIL: Holdout Recovery Factor -0.64 < 1.0.
- ❌ FAIL: Holdout Calmar Ratio -2.18 < 0.5.

--- 

## 1. Bảng Đối Chiếu Chéo Hiệu Năng

### IS Bear Regime (IS_BEAR)

| Chỉ số (Metric) | Chiến lược (Strategy) | Buy & Hold | Daily DCA |
|---|---|---|---|
| **ROI** | -27.55% | -38.13% | -6.61% |
| **Sharpe (Annualized)** | -2.39 | -2.19 | -0.52 |
| **Sortino (Annualized)** | -3.27 | -2.85 | -0.77 |
| **Calmar Ratio** | -1.94 | -1.53 | -1.08 |
| **Max Drawdown** | 37.42% | 55.89% | 22.25% |
| **Recovery Factor** | -0.73 | -0.64 | -0.29 |
| **Profit Factor** | 0.00 | N/A | N/A |
| **Expectancy** | -1315.94 | N/A | N/A |
| **Exposure Ratio** | 98.94% | N/A | N/A |
| **Trades Count** | 1 | N/A | N/A |
| **Trades / Month** | 0.3 | N/A | N/A |

**Monte Carlo Drawdown (Strategy):**
- Median Drawdown (P50): 13.16%
- MC P95 Drawdown (độ bền rủi ro): 13.16%
- MC P99 Drawdown (rủi ro đuôi): 13.16%
- Worst Drawdown: 13.16%
- Xác suất sụt giảm > 25% (Prob DD > 25%): 0.00%
- Xác suất sụt giảm > 50% (Prob DD > 50%): 0.00%
- Average Losing Streak (Block Size): 1.00 trades

---

### IS Recovery Regime (IS_RECOVERY)

| Chỉ số (Metric) | Chiến lược (Strategy) | Buy & Hold | Daily DCA |
|---|---|---|---|
| **ROI** | 26.51% | 72.06% | 27.78% |
| **Sharpe (Annualized)** | 3.58 | 4.19 | 2.84 |
| **Sortino (Annualized)** | 7.13 | 8.52 | 5.32 |
| **Calmar Ratio** | 17.64 | 37.02 | 10.70 |
| **Max Drawdown** | 9.21% | 22.35% | 16.21% |
| **Recovery Factor** | 2.27 | 1.83 | 1.31 |
| **Profit Factor** | 0.00 | N/A | N/A |
| **Expectancy** | 0.00 | N/A | N/A |
| **Exposure Ratio** | 98.91% | N/A | N/A |
| **Trades Count** | 0 | N/A | N/A |
| **Trades / Month** | 0.0 | N/A | N/A |

**Monte Carlo Drawdown (Strategy):**
- Median Drawdown (P50): 0.00%
- MC P95 Drawdown (độ bền rủi ro): 0.00%
- MC P99 Drawdown (rủi ro đuôi): 0.00%
- Worst Drawdown: 0.00%
- Xác suất sụt giảm > 25% (Prob DD > 25%): 0.00%
- Xác suất sụt giảm > 50% (Prob DD > 50%): 0.00%
- Average Losing Streak (Block Size): 1.00 trades

---

### IS Bull Regime (IS_BULL)

| Chỉ số (Metric) | Chiến lược (Strategy) | Buy & Hold | Daily DCA |
|---|---|---|---|
| **ROI** | 15.62% | 42.31% | 1.78% |
| **Sharpe (Annualized)** | 2.52 | 2.62 | 0.38 |
| **Sortino (Annualized)** | 4.61 | 4.08 | 0.48 |
| **Calmar Ratio** | 9.34 | 16.47 | 0.45 |
| **Max Drawdown** | 8.72% | 19.77% | 16.71% |
| **Recovery Factor** | 1.42 | 1.24 | 0.09 |
| **Profit Factor** | 0.00 | N/A | N/A |
| **Expectancy** | 0.00 | N/A | N/A |
| **Exposure Ratio** | 98.91% | N/A | N/A |
| **Trades Count** | 0 | N/A | N/A |
| **Trades / Month** | 0.0 | N/A | N/A |

**Monte Carlo Drawdown (Strategy):**
- Median Drawdown (P50): 0.00%
- MC P95 Drawdown (độ bền rủi ro): 0.00%
- MC P99 Drawdown (rủi ro đuôi): 0.00%
- Worst Drawdown: 0.00%
- Xác suất sụt giảm > 25% (Prob DD > 25%): 0.00%
- Xác suất sụt giảm > 50% (Prob DD > 50%): 0.00%
- Average Losing Streak (Block Size): 1.00 trades

---

### OOS Sideways Regime (OOS_SIDEWAYS)

| Chỉ số (Metric) | Chiến lược (Strategy) | Buy & Hold | Daily DCA |
|---|---|---|---|
| **ROI** | -1.46% | -11.82% | -11.20% |
| **Sharpe (Annualized)** | -0.13 | -0.83 | -1.41 |
| **Sortino (Annualized)** | -0.20 | -1.22 | -1.83 |
| **Calmar Ratio** | -0.59 | -1.35 | -2.18 |
| **Max Drawdown** | 9.90% | 29.83% | 17.72% |
| **Recovery Factor** | -0.14 | -0.34 | -0.62 |
| **Profit Factor** | 999.00 | N/A | N/A |
| **Expectancy** | 108.75 | N/A | N/A |
| **Exposure Ratio** | 98.91% | N/A | N/A |
| **Trades Count** | 3 | N/A | N/A |
| **Trades / Month** | 1.0 | N/A | N/A |

**Monte Carlo Drawdown (Strategy):**
- Median Drawdown (P50): 0.00%
- MC P95 Drawdown (độ bền rủi ro): 0.00%
- MC P99 Drawdown (rủi ro đuôi): 0.00%
- Worst Drawdown: 0.00%
- Xác suất sụt giảm > 25% (Prob DD > 25%): 0.00%
- Xác suất sụt giảm > 50% (Prob DD > 50%): 0.00%
- Average Losing Streak (Block Size): 1.00 trades

---

### OOS Mini-Bear Regime (OOS_MINIBEAR)

| Chỉ số (Metric) | Chiến lược (Strategy) | Buy & Hold | Daily DCA |
|---|---|---|---|
| **ROI** | 1.28% | -5.29% | -3.77% |
| **Sharpe (Annualized)** | 0.43 | -0.20 | -0.58 |
| **Sortino (Annualized)** | 0.69 | -0.27 | -0.66 |
| **Calmar Ratio** | 0.97 | -1.10 | -0.99 |
| **Max Drawdown** | 5.38% | 17.81% | 14.47% |
| **Recovery Factor** | 0.23 | -0.27 | -0.24 |
| **Profit Factor** | 20.32 | N/A | N/A |
| **Expectancy** | 60.88 | N/A | N/A |
| **Exposure Ratio** | 98.94% | N/A | N/A |
| **Trades Count** | 6 | N/A | N/A |
| **Trades / Month** | 2.0 | N/A | N/A |

**Monte Carlo Drawdown (Strategy):**
- Median Drawdown (P50): 0.18%
- MC P95 Drawdown (độ bền rủi ro): 0.38%
- MC P99 Drawdown (rủi ro đuôi): 0.55%
- Worst Drawdown: 0.57%
- Xác suất sụt giảm > 25% (Prob DD > 25%): 0.00%
- Xác suất sụt giảm > 50% (Prob DD > 50%): 0.00%
- Average Losing Streak (Block Size): 1.00 trades

---

### Final Holdout Set (HOLDOUT)

| Chỉ số (Metric) | Chiến lược (Strategy) | Buy & Hold | Daily DCA |
|---|---|---|---|
| **ROI** | -14.85% | -22.09% | -9.41% |
| **Sharpe (Annualized)** | -1.61 | -1.53 | -1.23 |
| **Sortino (Annualized)** | -2.56 | -2.10 | -1.81 |
| **Calmar Ratio** | -2.18 | -1.66 | -2.28 |
| **Max Drawdown** | 22.17% | 38.59% | 14.62% |
| **Recovery Factor** | -0.64 | -0.51 | -0.64 |
| **Profit Factor** | 999.00 | N/A | N/A |
| **Expectancy** | 1924.97 | N/A | N/A |
| **Exposure Ratio** | 98.91% | N/A | N/A |
| **Trades Count** | 1 | N/A | N/A |
| **Trades / Month** | 0.3 | N/A | N/A |

**Monte Carlo Drawdown (Strategy):**
- Median Drawdown (P50): 0.00%
- MC P95 Drawdown (độ bền rủi ro): 0.00%
- MC P99 Drawdown (rủi ro đuôi): 0.00%
- Worst Drawdown: 0.00%
- Xác suất sụt giảm > 25% (Prob DD > 25%): 0.00%
- Xác suất sụt giảm > 50% (Prob DD > 50%): 0.00%
- Average Losing Streak (Block Size): 1.00 trades

---

## 2. Baseline & Phân Tích Tổng Hợp

- **Median IS Sharpe Baseline**: `2.52` (Bằng Sharpe của regime Recovery/trung bình)
- **Holdout Verification**: `FAILED / NOT RUN`

> [!NOTE]
> Báo cáo này bao phủ các chu kỳ halving và giai đoạn vĩ mô khác nhau: năm 2022 (Macro Bear), 2023 (Tích lũy phục hồi), 2024 (Macro Bull), và 2025/2026. 
> Điều này đảm bảo tính bền vững (robustness) và hạn chế overfitting của chiến lược.
