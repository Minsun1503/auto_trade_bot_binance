import os
import time
import logging
from datetime import datetime
from typing import Callable, List, Dict, Any
import ccxt
from dotenv import load_dotenv

from core.interfaces.execution_adapter import ExecutionAdapter, FillEvent
from core.events import TickEvent

logger = logging.getLogger(__name__)

class TradingDisabledError(Exception):
    pass

class BinanceTestnetExecutionAdapter(ExecutionAdapter):
    def __init__(self, api_key: str = None, api_secret: str = None):
        load_dotenv()
        
        self.api_key = api_key or os.getenv("BINANCE_API_KEY")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET")
        
        # Initialize CCXT Binance in Sandbox (Testnet) Mode
        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
        })
        self.exchange.set_sandbox_mode(True)
        
        self._on_fill_callback = None
        self.exchange_time_offset_ms = 0
        
        self._sync_clock()
        
    def _sync_clock(self):
        try:
            local_time_ms = int(time.time() * 1000)
            exchange_time_ms = self.exchange.fetch_time()
            self.exchange_time_offset_ms = exchange_time_ms - local_time_ms
            logger.info(f"[TESTNET] Clock synchronized. Offset: {self.exchange_time_offset_ms} ms")
        except Exception as e:
            logger.error(f"[TESTNET] Failed to sync clock with exchange: {e}")
            
    def get_adjusted_time_ms(self) -> int:
        return int(time.time() * 1000) + self.exchange_time_offset_ms

    def set_on_fill_callback(self, callback: Callable[[FillEvent], None]):
        self._on_fill_callback = callback

    def place_limit_order(self, symbol: str, side: str, price: float, quantity: float) -> str:
        raise TradingDisabledError("Testnet adapter running in READ_ONLY mode")

    def execute_market_order(self, symbol: str, side: str, quantity: float, current_price: float, timestamp: datetime) -> str:
        raise TradingDisabledError("Testnet adapter running in READ_ONLY mode")

    def cancel_order(self, symbol: str, order_id: str):
        raise TradingDisabledError("Testnet adapter running in READ_ONLY mode")

    def cancel_all_orders(self, symbol: str):
        raise TradingDisabledError("Testnet adapter running in READ_ONLY mode")

    def get_active_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch open orders from Binance Testnet"""
        try:
            orders = self.exchange.fetch_open_orders(symbol)
            return [
                {
                    'id': o['id'],
                    'symbol': o['symbol'],
                    'side': o['side'].upper(),
                    'price': float(o['price']),
                    'quantity': float(o['amount']),
                    'status': o['status'].upper()
                } for o in orders
            ]
        except Exception as e:
            logger.error(f"[TESTNET] Failed to fetch open orders: {e}")
            return []

    def restore_orders(self, orders: List[Dict[str, Any]]):
        pass

    def get_trade_history(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch private trade history from Binance Testnet"""
        try:
            trades = self.exchange.fetch_my_trades(symbol)
            return [
                {
                    'trade_id': t['id'],
                    'order_id': t['order'],
                    'symbol': t['symbol'],
                    'side': t['side'].upper(),
                    'price': float(t['price']),
                    'quantity': float(t['amount']),
                    'fee_amount': float(t['fee']['cost']) if t['fee'] else 0.0,
                    'fee_asset': t['fee']['currency'] if t['fee'] else 'USDT',
                    'timestamp': int(t['timestamp'])
                } for t in trades
            ]
        except Exception as e:
            logger.error(f"[TESTNET] Failed to fetch trade history: {e}")
            return []

    def restore_trades(self, trades: List[Dict[str, Any]]):
        pass

    def get_balances(self) -> Dict[str, Dict[str, float]]:
        """Fetch asset balances from Binance Testnet"""
        try:
            bal = self.exchange.fetch_balance()
            result = {}
            for asset, asset_bal in bal.items():
                if isinstance(asset_bal, dict) and ('free' in asset_bal or 'used' in asset_bal):
                    free = float(asset_bal.get('free', 0.0))
                    used = float(asset_bal.get('used', 0.0))
                    if free > 0 or used > 0:
                        result[asset] = {'free': free, 'used': used, 'total': free + used}
            return result
        except Exception as e:
            logger.error(f"[TESTNET] Failed to fetch balance: {e}")
            return {}

    def on_tick(self, tick: TickEvent):
        pass
