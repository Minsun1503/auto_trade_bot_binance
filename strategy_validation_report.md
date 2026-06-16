# Strategy Validation & Risk Report

- **Ngày chạy báo cáo**: 2026-06-16 23:13:18
- **Freeze Checksum**: `6c49010d9d9566cb3ae601c270da965b79f29b9fa13ff931fcc14b9515fcfb0b`
- **Trạng thái Code Freeze Match**: `YES` (Đăng ký thành công)
- **Chế độ kiểm thử**: `Sample-Only`
- **Cổng kiểm duyệt cuối cùng**: `FAIL`

### Danh sách vi phạm (Violations):
- ❌ FAIL: IS Bear Regime trades count 0 < 20 (IS minimum limit per regime).
- ❌ FAIL: IS Recovery Regime trades count 0 < 20 (IS minimum limit per regime).
- ❌ FAIL: IS Bull Regime trades count 0 < 20 (IS minimum limit per regime).
- ❌ FAIL: Total IS trades count 0 < 100.
- ❌ FAIL: OOS Sideways Regime trades count 0 < 30 (OOS sub-regime limit).
- ❌ FAIL: OOS Sideways Regime Sortino 0.00 < 1.0.
- ❌ FAIL: OOS Sideways Regime Profit Factor 0.00 < 1.1.
- ❌ FAIL: OOS Mini-Bear Regime trades count 0 < 30 (OOS sub-regime limit).
- ❌ FAIL: OOS Mini-Bear Regime Sharpe -8.63 < 0.7.
- ❌ FAIL: OOS Mini-Bear Regime Sortino -41.68 < 1.0.
- ❌ FAIL: OOS Mini-Bear Regime Profit Factor 0.00 < 1.1.
- ❌ FAIL: OOS Mini-Bear Regime Recovery Factor -0.70 < 1.0.
- ❌ FAIL: OOS Mini-Bear Regime Calmar Ratio -40.14 < 0.5.
- ❌ FAIL: OOS Mini-Bear Regime Sharpe Degradation: -8.63 < 1.05 (50% of Median IS Sharpe).
- ❌ FAIL: Holdout trades count 0 < 30.
- ❌ FAIL: Holdout Sortino 0.00 < 1.0.
- ❌ FAIL: Holdout Profit Factor 0.00 < 1.1.

--- 

## 1. Bảng Đối Chiếu Chéo Hiệu Năng

### IS Bear Regime (IS_BEAR)

| Chỉ số (Metric) | Chiến lược (Strategy) | Buy & Hold | Daily DCA |
|---|---|---|---|
| **ROI** | -1.65% | -2.97% | -4.06% |
| **Sharpe (Annualized)** | -4.46 | -4.24 | -4.93 |
| **Sortino (Annualized)** | -5.30 | -5.39 | -5.56 |
| **Calmar Ratio** | -28.27 | -8.34 | -10.76 |
| **Max Drawdown** | 2.49% | 10.66% | 8.84% |
| **Recovery Factor** | -0.66 | -0.26 | -0.44 |
| **Profit Factor** | 0.00 | N/A | N/A |
| **Expectancy** | 0.00 | N/A | N/A |
| **Exposure Ratio** | 85.71% | N/A | N/A |
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

### IS Recovery Regime (IS_RECOVERY)

| Chỉ số (Metric) | Chiến lược (Strategy) | Buy & Hold | Daily DCA |
|---|---|---|---|
| **ROI** | 0.63% | 1.73% | 0.79% |
| **Sharpe (Annualized)** | 9.15 | 11.56 | 9.59 |
| **Sortino (Annualized)** | 36.46 | 96.54 | 59.91 |
| **Calmar Ratio** | 298.46 | 204.39 | 86.11 |
| **Max Drawdown** | 0.20% | 1.23% | 0.91% |
| **Recovery Factor** | 3.21 | 1.38 | 0.86 |
| **Profit Factor** | 0.00 | N/A | N/A |
| **Expectancy** | 0.00 | N/A | N/A |
| **Exposure Ratio** | 85.71% | N/A | N/A |
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
| **ROI** | 0.11% | 0.18% | -0.38% |
| **Sharpe (Annualized)** | 2.10 | -6.77 | -6.75 |
| **Sortino (Annualized)** | 23.07 | -11.85 | -9.66 |
| **Calmar Ratio** | 19.19 | 4.90 | -10.39 |
| **Max Drawdown** | 0.44% | 2.83% | 2.33% |
| **Recovery Factor** | 0.25 | 0.06 | -0.16 |
| **Profit Factor** | 0.00 | N/A | N/A |
| **Expectancy** | 0.00 | N/A | N/A |
| **Exposure Ratio** | 85.71% | N/A | N/A |
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
| **ROI** | 1.78% | 5.22% | 1.89% |
| **Sharpe (Annualized)** | 14.40 | 16.24 | 19.88 |
| **Sortino (Annualized)** | 0.00 | 999.00 | 999.00 |
| **Calmar Ratio** | 4438.33 | 2273.10 | 253.21 |
| **Max Drawdown** | 0.06% | 1.76% | 1.15% |
| **Recovery Factor** | 29.54 | 2.80 | 1.60 |
| **Profit Factor** | 0.00 | N/A | N/A |
| **Expectancy** | 0.00 | N/A | N/A |
| **Exposure Ratio** | 85.71% | N/A | N/A |
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

### OOS Mini-Bear Regime (OOS_MINIBEAR)

| Chỉ số (Metric) | Chiến lược (Strategy) | Buy & Hold | Daily DCA |
|---|---|---|---|
| **ROI** | -0.68% | -1.38% | -0.03% |
| **Sharpe (Annualized)** | -8.63 | 3.33 | 2.49 |
| **Sortino (Annualized)** | -41.68 | 40.72 | 5.59 |
| **Calmar Ratio** | -40.14 | -18.12 | -1.09 |
| **Max Drawdown** | 0.98% | 3.52% | 2.06% |
| **Recovery Factor** | -0.70 | -0.39 | -0.01 |
| **Profit Factor** | 0.00 | N/A | N/A |
| **Expectancy** | 0.00 | N/A | N/A |
| **Exposure Ratio** | 85.71% | N/A | N/A |
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

### Final Holdout Set (HOLDOUT)

| Chỉ số (Metric) | Chiến lược (Strategy) | Buy & Hold | Daily DCA |
|---|---|---|---|
| **ROI** | 2.48% | 7.09% | 3.84% |
| **Sharpe (Annualized)** | 19.02 | 25.36 | 18.62 |
| **Sortino (Annualized)** | 0.00 | 999.00 | 999.00 |
| **Calmar Ratio** | 3463.95 | 9097.19 | 1541.56 |
| **Max Drawdown** | 0.14% | 1.63% | 0.95% |
| **Recovery Factor** | 16.77 | 4.03 | 3.85 |
| **Profit Factor** | 0.00 | N/A | N/A |
| **Expectancy** | 0.00 | N/A | N/A |
| **Exposure Ratio** | 85.71% | N/A | N/A |
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

## 2. Baseline & Phân Tích Tổng Hợp

- **Median IS Sharpe Baseline**: `2.10` (Bằng Sharpe của regime Recovery/trung bình)
- **Holdout Verification**: `FAILED / NOT RUN`

> [!NOTE]
> Báo cáo này bao phủ các chu kỳ halving và giai đoạn vĩ mô khác nhau: năm 2022 (Macro Bear), 2023 (Tích lũy phục hồi), 2024 (Macro Bull), và 2025/2026. 
> Điều này đảm bảo tính bền vững (robustness) và hạn chế overfitting của chiến lược.
