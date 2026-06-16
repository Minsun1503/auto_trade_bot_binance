# PROJECT SOURCE OF TRUTH (PSOT)
*Cập nhật tự động theo Quy tắc 16 (Universal Handover)*

## 1. Những gì đã hoàn thành gần nhất
**Phase 3/4: BinanceWebSocketProvider & Dual-mode Architecture**

- **EventBuffer nâng cấp** (`core/event_buffer.py`):
  - Thay `processed_event_ids` set vô hạn → `collections.OrderedDict` LRU cache (max 50k entry, tự evict entry cũ nhất).
  - Dedup key chuẩn: `symbol + open_time + is_final` cho TickEvent (không phải chỉ timestamp). Điều này ngăn bug kinh điển: candle chưa đóng (is_final=False) và candle đã đóng (is_final=True) cùng timestamp sẽ có 2 key riêng biệt, không bị nhầm lẫn.

- **Global Market Watermark** (`core/runner.py`):
  - `EngineRunner.market_watermark` là "fence" duy nhất kiểm soát tiến trình thời gian của toàn bộ hệ thống.
  - `on_tick()` reject ngay mọi tick có `timestamp <= market_watermark` từ bất kỳ Provider nào.
  - Watermark được cập nhật monotonically sau mỗi tick được Engine xử lý thành công.

- **BinanceWebSocketProvider** (`data/providers/binance_websocket.py`):
  - Thread model: WS Thread → on_message → normalize → dedup tại source → callback(TickEvent). Không bao giờ gọi engine.step() trực tiếp.
  - Chỉ emit TickEvent khi `is_closed == True` (RULE 1).
  - Heartbeat Watchdog thread: nếu > 90s không nhận message, tự force-disconnect để trigger reconnect.
  - Reconnect loop với exponential backoff (1s → 2s → ... → 60s max).
  - Khi reconnect: giữ nguyên `market_watermark` và buffer state → không reset Engine.
  - Dedup nhỏ tại source (`_last_seen` set với eviction FIFO, max 1000 entries).

- **Dual-mode Architecture** (`main.py`):
  - `--mode backtest`: chỉ chạy historical Parquet (deterministic, test).
  - `--mode warmup+live`: Phase 1 warmup từ Parquet (MA warm-up) → Phase 2 handover sang WebSocket. `market_watermark` từ Phase 1 tự động là "fence" chặn tick cũ từ WS.
  - Factory `_build_engine_and_runner()` dùng chung cho cả 2 mode.

- **Test suite mới** (`tests/test_websocket_chaos.py`): 6 tests, 100% pass:
  - WS mock vs Historical: cùng giá close sequence.
  - WS provider drop candles chưa đóng.
  - Watermark reject tick cũ sau reconnect overlap.
  - Dedup key: symbol+timestamp+is_final.
  - Lag injection: EventBuffer reorder ticks lộn xộn.
  - Out-of-order fill + late candle close: không double PnL.

## 2. Những "đặc sản" logic vừa tìm thấy (Crucial Context)
- **Single Source of Truth (`TickEvent`):** timestamp = int64 epoch ms. Không dùng datetime.
- **Buffer Watermark:** EventBuffer chặn event cũ hơn `watermark - epsilon`. Watermark monotonic.
- **Dedup key có is_final:** `symbol_ts_True` ≠ `symbol_ts_False`. Nếu không tách, candle update và candle close sẽ lẫn nhau trong dedup.
- **Không bao giờ snapshot Buffer:** Buffer là Transient. Snapshot chỉ lưu Ledger, Orders, trade_history.
- **Ownership Rule (Provider Identity):**
  - historical → chỉ dùng khi `watermark == 0` hoặc mode warmup.
  - websocket → là nguồn chính sau khi watermark đã được thiết lập.
  - `source` field trong TickEvent là identity tag.

## 3. Những việc còn dang dở (Next Steps)
- **Binance Testnet Execution Adapter (Phase 4 chính):**
  - Thay `BacktestExecutionAdapter` bằng một Adapter gọi API thật lên Binance Testnet.
  - Implement `place_limit_order`, `cancel_order`, `get_trade_history` thông qua REST API.
  - Reconcile order lifecycle: mở bot → query open orders từ Exchange → sync vào Ledger.
- **WebSocket live test thực tế:**
  - Chạy `python main.py --mode warmup+live` và để bot chạy 2-3 tiếng, theo dõi memory và reconnect behavior.
  - Verify `market_watermark` tăng đúng hướng sau mỗi nến 1 phút.
