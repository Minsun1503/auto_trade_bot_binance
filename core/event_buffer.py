import heapq
import uuid
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

@dataclass(order=True)
class BufferEvent:
    timestamp: int
    sequence_number: int
    event_id: str = field(compare=False)
    source_id: str = field(compare=False)
    event_type: str = field(compare=False)
    payload: Any = field(compare=False)

class EventBuffer:
    """
    Priority-queue-based event buffer với:
    - Causal ordering (watermark): chặn event quá cũ (timestamp < watermark - epsilon)
    - Deduplication: key = symbol + open_time + is_final cho TickEvent, event_id cho FillEvent
    - LRU cache giới hạn kích thước tối đa để tránh memory leak
    """
    MAX_DEDUP_CACHE = 50_000  # Tối đa 50k entry dedup

    def __init__(self, window_ms: int = 2000, epsilon_ms: int = 10000):
        self.window = window_ms    # ms: event phải chờ ít nhất window_ms trước khi flush
        self.epsilon = epsilon_ms  # ms: ngưỡng Causal Boundary
        self.events: List[BufferEvent] = []  # Min-heap theo (timestamp, sequence_number)
        # OrderedDict dùng làm LRU cache: key -> None
        self._dedup_cache: OrderedDict = OrderedDict()
        self.engine_watermark: Optional[int] = None
        self._seq_counter = 0

    def _make_dedup_key(self, event_type: str, event_id: str, payload: Any) -> str:
        """
        Tạo dedup key đúng chuẩn:
        - TickEvent: symbol + open_time + is_final  (tránh candle update tạo duplicate)
        - FillEvent / khác: event_id được cung cấp từ bên ngoài
        """
        if event_type == "TICK" and payload is not None:
            is_final = getattr(payload, 'is_closed', True)
            symbol = getattr(payload, 'symbol', 'UNKNOWN')
            ts = getattr(payload, 'timestamp', 0)
            return f"tick_{symbol}_{ts}_{is_final}"
        return event_id

    def _add_to_dedup(self, key: str):
        """Thêm key vào LRU cache, loại bỏ entry cũ nhất nếu tràn."""
        if key in self._dedup_cache:
            # Move to end (most recently used)
            self._dedup_cache.move_to_end(key)
            return False  # Đây là duplicate
        self._dedup_cache[key] = None
        if len(self._dedup_cache) > self.MAX_DEDUP_CACHE:
            self._dedup_cache.popitem(last=False)  # Loại bỏ entry cũ nhất
        return True  # Key mới, không phải duplicate

    def push(
        self,
        event_type: str,
        timestamp: int,
        payload: Any,
        event_id: str = None,
        source_id: str = "system"
    ):
        if event_id is None:
            event_id = f"ev_{uuid.uuid4().hex[:8]}"

        dedup_key = self._make_dedup_key(event_type, event_id, payload)
        if not self._add_to_dedup(dedup_key):
            logger.debug(f"[BUFFER] Duplicate bị chặn: {dedup_key}")
            return

        # Causal ordering: chặn event quá cũ (vi phạm Causal Boundary)
        if self.engine_watermark is not None and timestamp < self.engine_watermark - self.epsilon:
            logger.warning(
                f"[BUFFER] Causal Boundary violated: {dedup_key} ts={timestamp}, "
                f"watermark={self.engine_watermark}. Bỏ qua."
            )
            return

        self._seq_counter += 1
        ev = BufferEvent(
            timestamp=timestamp,
            sequence_number=self._seq_counter,
            event_id=dedup_key,
            source_id=source_id,
            event_type=event_type,
            payload=payload
        )
        heapq.heappush(self.events, ev)

    def flush_ready(self, current_time: int) -> List[BufferEvent]:
        """
        Flush tất cả event đã 'stable' (cũ hơn current_time - window_ms).
        SAU KHI flush, watermark sẽ được Engine._flush_buffer cập nhật (không phải ở đây).
        Buffer chỉ có nhiệm vụ sort và trả về — Engine quyết định commit timing.
        """
        ready = []
        while self.events:
            ev = self.events[0]
            if current_time - ev.timestamp >= self.window:
                ready.append(heapq.heappop(self.events))
            else:
                break
        return ready
