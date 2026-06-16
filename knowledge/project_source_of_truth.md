# PROJECT SOURCE OF TRUTH (PSOT)
*Cập nhật tự động theo Quy tắc 16 (Universal Handover)*

## 1. Những gì đã hoàn thành gần nhất
**Phase 4A: Binance Testnet Read-Only & State Reconciliation**

- **Duy nhất hóa Identity Layer**:
  - `TradingEngine.step()` không còn tự sinh hay can thiệp vào `event_id`. `EventBuffer._make_dedup_key` là nguồn quyền lực duy nhất định danh sự kiện.

- **Đồng bộ Watermark**:
  - `TradingEngine._flush_buffer` cập nhật watermark chỉ sau khi Ledger commit xong.
  - `EngineRunner` đồng bộ `market_watermark` sau khi `engine.step()` hoàn tất để tránh race conditions.

- **BinanceTestnetExecutionAdapter** (`backtest/adapters/binance_testnet.py`):
  - Kế thừa `ExecutionAdapter`, sử dụng `ccxt.binance` sandbox mode.
  - Hoàn tất các cổng đọc dữ liệu an toàn (Read-Only): `get_balances`, `get_active_orders`, `get_trade_history`.
  - Tính toán và cache `exchange_time_offset_ms` từ exchange clocks để phòng tránh lỗi authentication `recvWindow`.
  - Khóa chặt các hàm gửi lệnh mua/bán/hủy bằng `TradingDisabledError("Testnet adapter running in READ_ONLY mode")`.

- **Phân cấp Đối chiếu (Reconciliation System)**:
  - **Light Reconciliation**: Chạy sau mỗi fill locally (< 1ms, không gọi mạng), kiểm tra cấu trúc/số dư không âm.
  - **Full Reconciliation**: Gọi REST API sàn (khi startup, restore, reconnect, và định kỳ 60s).
    - So khớp số dư chính xác với epsilon dung sai: `abs(ledger_btc - exchange_btc) < RECONCILE_BTC_EPSILON` (1e-8) và `abs(ledger_usdt - exchange_usdt) < RECONCILE_USDT_EPSILON` (0.01).
    - So khớp vòng đời lệnh (Order State Machine): Map từ CCXT string sang explicit `OrderState` Enum.
    - **Trade History Supremacy**: Rebuild position từ danh sách private trades của Exchange. Nếu lệch so với Ledger -> overwrite ledger (supremacy).
    - **Severity levels**:
      - Level 1 (Warning): Lệch số dư nằm trong dung sai -> Warning log.
      - Level 2 (Protect): Lệch trạng thái lệnh hoặc số dư vượt quá tolerance -> Chuyển sang `PROTECT` mode, hủy toàn bộ lệnh, pause strategy.
      - Level 3 (Critical): Lệch cấu trúc Ledger/Trade rebuild -> Snapshot lập tức và Halt `EngineRunner`.

- **Smoke Test Script** (`scripts/testnet_smoke_test.py`):
  - Đo clock offset 5 lần liên tiếp tính toán `avg_offset` và `max_offset` (báo động đỏ nếu `max_offset > 5000ms`).
  - Kiểm tra kết nối, lấy số dư, open orders và trade history.

- **Kiểm thử tự động** (`tests/test_websocket_chaos.py`):
  - Bổ sung `test_price_gap_with_instant_fill_spike` (kiểm tra buffer xử lý burst fill nhiều lệnh cùng timestamp).
  - Bổ sung `test_existing_position_on_startup_triggers_protect` (kiểm tra exchange có BTC mà Ledger rỗng -> kích hoạt PROTECT mode ngay lập tức).
  - 100% test suite vượt qua thành công.

- **Phase 3.5A: Core Metrics Implementation**:
  - Tách biệt hoàn toàn logic so sánh và kiểm định chiến lược khỏi `TradingEngine` (Đảm bảo tính cô lập kiến trúc).
  - Hoàn thiện `backtest/metrics.py` cung cấp các hàm đo lường rủi ro và hiệu năng chuyên sâu:
    - Annualized Sharpe & Sortino dựa trên daily equity returns (chuẩn 365 ngày của crypto).
    - Calmar Ratio, Recovery Factor, Profit Factor.
    - Expectancy (kỳ vọng toán học của giao dịch).
    - Exposure Ratio (tỷ lệ thời gian có vị thế, hỗ trợ phát hiện Buy & Hold trá hình).
    - Trade Frequency (tần suất giao dịch theo ngày/tháng).
  - Hoàn thiện bộ unit test toàn diện `tests/test_metrics.py` bao phủ tất cả các hàm chỉ số toán học.

## 2. Những "đặc sản" logic vừa tìm thấy (Crucial Context)
- **Clock Sync offset**: Bắt buộc lưu trữ `exchange_time_offset_ms` để đồng bộ hóa các lệnh gọi API có ký (signature) trong CCXT.
- **Rebuild Supremacy**: Không tin Ledger khi đối chiếu chéo; danh sách lịch sử trade của sàn là sự thật tối cao nhất để sinh ra Position hiện tại.
- **Tolerance Epsilon**: Epsilon dung sai phải lưu trữ tại config vì mỗi symbol (BTC vs DOGE) có bước giá và mức độ làm tròn khác nhau.
- **Crypto-centric Metrics Annualization**: Đối với thị trường Crypto, hệ số chuẩn hóa theo năm là 365 ngày (thay vì 252 ngày như chứng khoán truyền thống).

## 3. Những việc còn dang dở (Next Steps)
- **Phase 3.5B: Benchmarks Module**: Hiện thực hóa `buy_hold.py` và `daily_dca.py` độc lập dưới `backtest/benchmarks/`.
- **Phase 3.5C: Block Bootstrap Monte Carlo**: Hiện thực hóa `backtest/monte_carlo.py` sử dụng Stationary Block Bootstrap dựa trên losing streak trung bình thực tế để giữ nguyên tương quan chuỗi thời gian.
- **Phase 3.5D: Validation Runner**: Hiện thực hóa `backtest/validation.py` với các cổng Hard Gates, OOS Sharpe Degradation Gate, và cơ chế check SHA-256 Code Freeze qua `strategy_manifest.json`.
- **Phase 3.5E: Reporter Integration**: Kết xuất báo cáo đối chiếu chéo ra file `strategy_validation_report.md` dạng Markdown hoàn chỉnh.

