"""
BinanceWebSocketProvider
========================
Kết nối Binance kline WebSocket stream (wss://stream.binance.com/ws/<symbol>@kline_<interval>)
và convert JSON message → TickEvent để feed vào EventBuffer / tick_queue của EngineRunner.

Kiến trúc Thread:
    WS Thread (websocket-client) → on_message → normalize → dedup → callback(TickEvent)
                                                                            ↓
                                                                     EngineRunner.on_tick()
                                                                            ↓
                                                                      tick_queue

KHÔNG được:
  - Gọi trực tiếp engine.step() từ WS thread
  - Mutate Ledger từ WS thread

"""
import json
import logging
import threading
import time
from typing import Callable, Optional, Set

from core.interfaces.data_provider import MarketDataProvider
from core.events import TickEvent

logger = logging.getLogger(__name__)

BINANCE_WS_BASE = "wss://stream.binance.com:9443/ws"


class BinanceWebSocketProvider(MarketDataProvider):
    """
    Provider nhận kline stream từ Binance WebSocket.

    - Chỉ emit TickEvent khi nến đã đóng (is_closed == True).
    - Dedup nội bộ tại source trước khi gọi callback.
    - Tự động reconnect khi mất kết nối hoặc heartbeat timeout.
    - KHÔNG reset market_watermark hay Engine state khi reconnect.
    """

    HEARTBEAT_TIMEOUT_S = 90    # Reconnect nếu > 90s không có message
    MAX_RECONNECT_DELAY_S = 60  # Backoff tối đa 60 giây

    def __init__(self, symbol: str, interval: str = "1m"):
        """
        Args:
            symbol: VD "BTCUSDT" (không dùng dấu /)
            interval: VD "1m", "5m"
        """
        self.symbol = symbol.upper()
        self.interval = interval
        self._callback: Optional[Callable[[TickEvent], None]] = None

        self._running = False
        self._stop_requested = False
        self._ws = None
        self._ws_thread: Optional[threading.Thread] = None
        self._watchdog_thread: Optional[threading.Thread] = None

        # Dedup cache nhỏ tại source: set các open_time ms đã emit
        # Kích thước tối đa 1000 entry (1000 nến 1m ≈ ~16h)
        self._last_seen: Set[str] = set()
        self._last_seen_list: list = []  # Để biết thứ tự và evict
        self._MAX_SEEN = 1000

        self._last_message_time: float = 0.0
        self._reconnect_count = 0
        self._on_connect_callback: Optional[Callable[[], None]] = None

    def subscribe(self, callback: Callable[[TickEvent], None]):
        self._callback = callback

    def start(self):
        """Bắt đầu WS loop. Blocking cho đến khi stop() được gọi."""
        self._stop_requested = False
        self._running = True
        logger.info(f"[WS] Khởi động provider: {self.symbol}@kline_{self.interval}")

        # Watchdog chạy song song để detect heartbeat timeout
        self._watchdog_thread = threading.Thread(
            target=self._heartbeat_watchdog, daemon=True, name="ws-watchdog"
        )
        self._watchdog_thread.start()

        self._connect_loop()

    def stop(self):
        """Dừng provider và đóng WS connection."""
        logger.info("[WS] Stop requested.")
        self._stop_requested = True
        self._running = False
        self._disconnect()

    def get_current_time(self) -> int:
        return int(time.time() * 1000)

    # ----------------------------------------------------------------
    # Internal WebSocket Lifecycle
    # ----------------------------------------------------------------

    def _stream_url(self) -> str:
        sym = self.symbol.lower()
        return f"{BINANCE_WS_BASE}/{sym}@kline_{self.interval}"

    def _connect_loop(self):
        """
        Vòng lặp reconnect với exponential backoff.
        Giữ nguyên watermark và buffer state sau mỗi lần reconnect.
        """
        delay = 1
        while not self._stop_requested:
            try:
                self._run_ws()
            except Exception as e:
                if self._stop_requested:
                    break
                logger.error(f"[WS] Kết nối lỗi: {e}. Reconnect sau {delay}s...")
                time.sleep(delay)
                delay = min(delay * 2, self.MAX_RECONNECT_DELAY_S)
                self._reconnect_count += 1
                logger.info(f"[WS] Đang reconnect (lần #{self._reconnect_count})...")
            else:
                if not self._stop_requested:
                    logger.warning("[WS] Connection closed bất ngờ. Reconnect sau 2s...")
                    time.sleep(2)

    def _run_ws(self):
        """Khởi tạo và chạy một websocket connection duy nhất."""
        try:
            import websocket
        except ImportError:
            raise RuntimeError(
                "Thiếu thư viện websocket-client. Chạy: pip install websocket-client"
            )

        url = self._stream_url()
        logger.info(f"[WS] Kết nối tới: {url}")

        ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._ws = ws
        # run_forever block cho đến khi close
        ws.run_forever(ping_interval=20, ping_timeout=10)

    def _disconnect(self):
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    # ----------------------------------------------------------------
    # WebSocket Callbacks
    # ----------------------------------------------------------------

    def _on_open(self, ws):
        self._last_message_time = time.time()
        logger.info(f"[WS] Kết nối thành công: {self.symbol}@kline_{self.interval}")
        if self._on_connect_callback:
            try:
                self._on_connect_callback()
            except Exception as e:
                logger.error(f"[WS] Failed to invoke on_connect_callback: {e}")

    def _on_message(self, ws, message: str):
        self._last_message_time = time.time()
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.warning(f"[WS] Message không hợp lệ (JSONDecodeError): {message[:100]}")
            return

        if "k" not in data:
            # Có thể là ping/pong message, bỏ qua
            return

        k = data["k"]
        self._process_kline(k)

    def _on_error(self, ws, error):
        logger.error(f"[WS] Lỗi: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"[WS] Đóng kết nối: code={close_status_code} msg={close_msg}")

    # ----------------------------------------------------------------
    # Kline Processing
    # ----------------------------------------------------------------

    def _process_kline(self, k: dict):
        """
        RULE 1: Chỉ emit TickEvent khi nến đã đóng (is_closed == True).
        Nến đang mở → cập nhật giá UI nếu cần, nhưng KHÔNG đẩy vào Engine.

        RULE 2: Dedup theo open_time + is_final tại source.
        """
        is_closed: bool = bool(k.get("x", False))

        # === RULE 1: Engine chỉ nhận nến đã đóng ===
        if not is_closed:
            return

        open_time_ms: int = int(k["t"])
        close_time_ms: int = int(k["T"])

        # Dedup key: symbol + open_time + is_final
        dedup_key = f"{self.symbol}_{open_time_ms}_{is_closed}"
        if self._is_seen(dedup_key):
            logger.debug(f"[WS] Duplicate bị chặn tại source: {dedup_key}")
            return

        tick = TickEvent(
            timestamp=close_time_ms,   # Dùng close_time làm timestamp (giống Parquet schema)
            symbol=self.symbol,
            open=float(k["o"]),
            high=float(k["h"]),
            low=float(k["l"]),
            close=float(k["c"]),
            volume=float(k["v"]),
            is_closed=True,
            source="binance_ws",
        )

        if self._callback:
            self._callback(tick)
        else:
            logger.warning("[WS] Không có callback. Tick bị bỏ qua.")

    # ----------------------------------------------------------------
    # Heartbeat Watchdog
    # ----------------------------------------------------------------

    def _heartbeat_watchdog(self):
        """
        Thread kiểm tra heartbeat. Nếu quá HEARTBEAT_TIMEOUT_S giây không có message,
        đóng connection để trigger reconnect trong _connect_loop().
        """
        while not self._stop_requested:
            time.sleep(15)  # Check mỗi 15 giây
            if not self._running or self._stop_requested:
                break
            elapsed = time.time() - self._last_message_time
            if self._last_message_time > 0 and elapsed > self.HEARTBEAT_TIMEOUT_S:
                logger.warning(
                    f"[WS] Heartbeat timeout ({elapsed:.0f}s). Force disconnect để trigger reconnect."
                )
                self._disconnect()

    # ----------------------------------------------------------------
    # Dedup Cache (nhỏ gọn, tại source)
    # ----------------------------------------------------------------

    def _is_seen(self, key: str) -> bool:
        """Trả về True nếu key đã được thấy (duplicate). Cập nhật cache nếu chưa."""
        if key in self._last_seen:
            return True
        self._last_seen.add(key)
        self._last_seen_list.append(key)
        if len(self._last_seen_list) > self._MAX_SEEN:
            old = self._last_seen_list.pop(0)
            self._last_seen.discard(old)
        return False
