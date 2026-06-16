from typing import List, Dict
from datetime import datetime
from .position import Trade, Position, PortfolioSnapshot

class Ledger:
    """
    Sổ cái chỉ thêm (Append-only). 
    Position không được lưu cứng, mà luôn là kết quả tính toán (rebuild) từ chuỗi Trade.
    """
    
    def __init__(self, initial_cash: float, quote_currency: str = "USDT"):
        self.initial_cash = initial_cash
        self.quote_currency = quote_currency
        self.trades: List[Trade] = []
        self.snapshots: List[PortfolioSnapshot] = []
        self._position_cache: Dict[str, Position] = {}
        
        # Dùng cho Replay / Restore
        self.cash_override = None
        self.initial_positions: Dict[str, Position] = {}
        
    def append_trade(self, trade: Trade):
        self.trades.append(trade)
        self._position_cache.pop(trade.symbol, None)
        
    def rebuild_position(self, symbol: str) -> Position:
        if symbol in self._position_cache:
            return self._position_cache[symbol]
            
        pos = Position(symbol=symbol)
        
        # Load initial position if it exists (for Replay)
        if symbol in self.initial_positions:
            init_pos = self.initial_positions[symbol]
            pos.quantity = init_pos.quantity
            pos.avg_price = init_pos.avg_price
            
        for t in self.trades:
            if t.symbol != symbol:
                continue
                
            pos.fees_accumulated[t.fee_asset] = pos.fees_accumulated.get(t.fee_asset, 0.0) + t.fee_amount
            
            if t.side == "BUY":
                total_value = (pos.quantity * pos.avg_price) + (t.quantity * t.price)
                pos.quantity += t.quantity
                if pos.quantity > 0:
                    pos.avg_price = total_value / pos.quantity
            elif t.side == "SELL":
                cost_of_sold = t.quantity * pos.avg_price
                revenue = t.quantity * t.price
                pos.realized_pnl += (revenue - cost_of_sold)
                
                pos.quantity -= t.quantity
                if pos.quantity <= 1e-8:
                    pos.quantity = 0.0
                    pos.avg_price = 0.0
                    
            pos.last_update = t.timestamp
            
        self._position_cache[symbol] = pos
        return pos
        
    def get_cash_balance(self) -> float:
        """Tính số dư quote currency (ví dụ: USDT)"""
        cash = self.cash_override if self.cash_override is not None else self.initial_cash
        for t in self.trades:
            trade_value = t.quantity * t.price
            if t.side == "BUY":
                cash -= trade_value
            elif t.side == "SELL":
                cash += trade_value
                
            # Trừ thẳng tiền mặt nếu fee được trả bằng quote currency
            if t.fee_asset == self.quote_currency:
                cash -= t.fee_amount
        return cash
        
    def restore_cash(self, cash: float):
        self.cash_override = cash
        
    def restore_position(self, symbol: str, quantity: float, avg_price: float):
        pos = Position(symbol=symbol)
        pos.quantity = quantity
        pos.avg_price = avg_price
        self.initial_positions[symbol] = pos
        self._position_cache.pop(symbol, None)
        
    @property
    def cash(self) -> float:
        return self.get_cash_balance()

    def get_total_equity(self, current_prices: Dict[str, float]) -> float:
        """Tổng vốn: Cash + Asset Value - Fee (đối với fee trả bằng tài sản khác)"""
        return self.get_cash_balance() + self.get_total_asset_value(current_prices)

    def get_total_fees_in_quote(self, current_prices: Dict[str, float]) -> float:
        """Quy đổi toàn bộ phí (USDT, BNB, BTC...) ra USDT để tính Net Profit"""
        symbols = set(t.symbol for t in self.trades)
        total_fee_in_quote = 0.0
        
        for sym in symbols:
            pos = self.rebuild_position(sym)
            for asset, amount in pos.fees_accumulated.items():
                if asset == self.quote_currency:
                    total_fee_in_quote += amount
                else:
                    # Tra cứu giá của fee_asset, ví dụ fee=BNB -> cần giá BNB/USDT
                    # Để đơn giản, giả sử current_prices chứa key BNB/USDT hoặc asset price
                    # Fallback là 0 nếu không tìm thấy giá quy đổi
                    price = current_prices.get(f"{asset}/{self.quote_currency}", 0.0)
                    total_fee_in_quote += amount * price
                    
        return total_fee_in_quote

    def get_gross_profit(self) -> float:
        """Gross Realized PNL (Chưa trừ phí)"""
        symbols = set(t.symbol for t in self.trades)
        total_realized = sum(self.rebuild_position(sym).realized_pnl for sym in symbols)
        return total_realized

    def get_net_profit(self, current_prices: Dict[str, float]) -> float:
        """Gross Realized PNL - Total Fees (in Quote)"""
        return self.get_gross_profit() - self.get_total_fees_in_quote(current_prices)
        
    def get_total_asset_value(self, current_prices: Dict[str, float]) -> float:
        symbols = set(t.symbol for t in self.trades) | set(self.initial_positions.keys())
        asset_value = 0.0
        for sym in symbols:
            pos = self.rebuild_position(sym)
            if pos.quantity > 0:
                price = current_prices.get(sym, pos.avg_price)
                asset_value += pos.quantity * price
                
        # Nếu fee trả bằng asset khác quote (vd BNB), cần trừ giá trị quy đổi của fee đó
        # (Vì cash_balance không trừ BNB fee, và BNB fee làm giảm tài sản ròng)
        other_fees_value = 0.0
        for sym in symbols:
            pos = self.rebuild_position(sym)
            for asset, amount in pos.fees_accumulated.items():
                if asset != self.quote_currency:
                    price = current_prices.get(f"{asset}/{self.quote_currency}", 0.0)
                    other_fees_value += amount * price
                    
        return asset_value - other_fees_value

    def record_snapshot(self, timestamp: datetime, current_prices: Dict[str, float]):
        """Chụp ảnh trạng thái tài khoản"""
        cash = self.get_cash_balance()
        total_equity = self.get_total_equity(current_prices)
        asset_value = total_equity - cash
        
        max_equity = max([s.total_equity for s in self.snapshots] + [self.initial_cash])
        max_equity = max(max_equity, total_equity)
        
        drawdown = (max_equity - total_equity) / max_equity if max_equity > 0 else 0.0
        
        snap = PortfolioSnapshot(
            timestamp=timestamp,
            cash=cash,
            asset_value=asset_value,
            total_equity=total_equity,
            drawdown=drawdown
        )
        self.snapshots.append(snap)
