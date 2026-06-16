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

- **Phase 3.5B: Benchmarks Module**:
  - Cô lập hoàn toàn benchmarks khỏi TradingEngine dưới `backtest/benchmarks/`.
  - Hoàn thiện `buy_hold.py` (tính toán hiệu suất của phương án Buy & Hold BTC).
  - Hoàn thiện `daily_dca.py` (tính toán hiệu suất của DCA tích lũy BTC hàng ngày).
  - Xây dựng bộ unit test đầy đủ `tests/test_benchmarks.py` để xác thực tính đúng đắn cho cả hai module benchmark.

- **Phase 3.5C: Block Bootstrap Monte Carlo**:
  - Hiện thực hóa `backtest/monte_carlo.py` sử dụng thuật toán Stationary Block Bootstrap.
  - Tự động hóa tính toán block size trung bình dựa trên losing streak trung bình của In-Sample.
  - Cố định random seed (seed = 42) để đảm bảo tính tái lập (reproducibility) 100% của các mô phỏng.
  - Đo lường và kết xuất các phân vị Drawdown (P50, P95, P99, Worst) và các xác suất sụt giảm tài sản (Prob of DD > 25% và > 50%), đảm bảo an toàn vốn (Spot max 0.0 cap).
  - Xây dựng unit test kiểm thử toàn diện trong `tests/test_monte_carlo.py`.

- **Phase 3.5D: Validation Runner**:
  - Hiện thực hóa `backtest/validation.py` làm trình điều phối chạy độc lập 3 tập dữ liệu.
  - Triển khai thuật toán gom nhóm giao dịch độc lập (Roundtrip Trade Consolidation) để tính toán chính xác số lượng trades thực tế.
  - Tích hợp cơ chế tính toán SHA-256 Checksum từ `strategy_manifest.json` phục vụ Code Freeze.
  - Xây dựng unit test kiểm định trong `tests/test_validation.py`.

- **Phase 3.5E: Reporter Integration**:
  - Hiện thực hóa `scripts/run_strategy_validation.py` thu thập kết quả, chạy giả lập Monte Carlo, DCA, Buy & Hold và xuất báo cáo Markdown hoàn chỉnh ra file `strategy_validation_report.md`.
  - Tích hợp cảnh báo vi phạm Hard Gates trực quan trên console CLI.
  - Xác thực thành công pipeline kiểm định bằng lệnh `--sample-only` trên dữ liệu rút gọn.

## 2. Những "đặc sản" logic vừa tìm thấy (Crucial Context)
- **Clock Sync offset**: Bắt buộc lưu trữ `exchange_time_offset_ms` để đồng bộ hóa các lệnh gọi API có ký (signature) trong CCXT.
- **Rebuild Supremacy**: Không tin Ledger khi đối chiếu chéo; danh sách lịch sử trade của sàn là sự thật tối cao nhất để sinh ra Position hiện tại.
- **Tolerance Epsilon**: Epsilon dung sai phải lưu trữ tại config vì mỗi symbol (BTC vs DOGE) có bước giá và mức độ làm tròn khác nhau.
- **Crypto-centric Metrics Annualization**: Đối với thị trường Crypto, hệ số chuẩn hóa theo năm là 365 ngày (thay vì 252 ngày như chứng khoán truyền thống).
- **Spot Ruin Safety**: Trong mô phỏng Spot Monte Carlo, giá trị tài sản ròng tối thiểu được giới hạn ở 0.0 (không thể có nợ âm), giúp các thước đo drawdown không vượt quá 100% một cách phi thực tế.
- **Independent Roundtrip Trade Consolidation**: Các trades được gom nhóm dựa trên sự thay đổi của net position từ 0 sang khác 0 và trở lại 0 để tính toán số lượng giao dịch độc lập chính xác nhất.
- **Dynamic Timezone Alignment**: Đồng bộ động múi giờ giữa các nến thị trường (thường là UTC) và mốc thời gian naive datetime của runner/test suite để phòng ngừa lỗi TypeError trong Pandas.

## 3. Những việc còn dang dở (Next Steps)
- **Phê duyệt báo cáo & Chạy Full Backtest 12 tháng**: Chạy pipeline không có `--sample-only` để nạp đủ dữ liệu 12 tháng đầy đủ và tiến hành tối ưu hóa tham số cho chiến lược nếu trượt cổng kiểm soát (Hard Gates).
- **Phase 4B: Manually Order Testing**: Tiến hành test đặt/hủy lệnh thủ công với size nhỏ nhất trên Binance Testnet sau khi chiến lược được chứng minh và phê duyệt.





