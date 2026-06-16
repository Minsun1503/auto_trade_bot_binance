from enum import Enum

class OrderState(Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

def map_order_state(status_str: str) -> OrderState:
    """
    Map a status string from Binance/CCXT to the OrderState Enum.
    """
    if not status_str:
        return OrderState.NEW
        
    status = status_str.upper().strip()
    
    # CCXT common mappings
    if status in ("OPEN", "NEW"):
        return OrderState.NEW
    elif status == "PARTIALLY_FILLED":
        return OrderState.PARTIALLY_FILLED
    elif status in ("CLOSED", "FILLED"):
        return OrderState.FILLED
    elif status in ("CANCELED", "CANCELLED"):
        return OrderState.CANCELED
    elif status == "REJECTED":
        return OrderState.REJECTED
    elif status == "EXPIRED":
        return OrderState.EXPIRED
        
    # Fallback to NEW
    return OrderState.NEW
