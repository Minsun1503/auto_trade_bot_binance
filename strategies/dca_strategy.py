import logging
from config.settings import DCAConfig
from .coordinator import IStrategy

logger = logging.getLogger(__name__)

class DCAStrategy(IStrategy):
    def __init__(self, config: DCAConfig):
        self.config = config
        self._is_running = False
        self.last_buy_time = None
        
    def start(self, engine):
        if not self._is_running:
            self._is_running = True
            
    def stop(self, engine):
        if self._is_running:
            self._is_running = False
            
    def is_running(self) -> bool:
        return self._is_running
        
    def process_tick(self, context, timestamp, engine):
        if not self._is_running:
            return
            
        if self.last_buy_time is None or (timestamp - self.last_buy_time).total_seconds() / 60 >= self.config.interval_candles:
            
            buy_amount = self.config.base_order_size
            if context.drawdown >= self.config.drawdown_trigger:
                buy_amount *= self.config.drawdown_multiplier
                
            cash = engine.ledger.get_cash_balance()
            if cash >= buy_amount:
                qty = buy_amount / context.price
                engine.execute_market_order("BUY", qty, context.price, timestamp)
                self.last_buy_time = timestamp
                logger.info(f"    [DCA] Thực hiện gom hàng {qty:.4f} @ {context.price}. Cash còn lại: {cash - buy_amount:.2f}")
            else:
                logger.warning(f"    [DCA] BỎ QUA GOM HÀNG! Không đủ tiền mặt. Yêu cầu: {buy_amount}, Có: {cash}")

    def on_order_fill(self, order_id: str, side: str, price: float, quantity: float, engine):
        pass # DCA gom thẳng market, không xài limit trong case này (hoặc có thể nhưng ta đang ưu tiên đơn giản)

    def get_tracked_orders(self) -> list[str]:
        return []
