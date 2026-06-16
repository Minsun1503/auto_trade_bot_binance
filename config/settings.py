import os
from dataclasses import dataclass, field
from typing import List

@dataclass
class CoordinatorConfig:
    drawdown_trigger: float = 0.20
    recovery_fast_ma: int = 50
    recovery_slow_ma: int = 200
    max_spread_pct: float = 0.005
    min_balance_usdt: float = 50.0

@dataclass
class GridConfig:
    levels: int = 10
    upper_bound_pct: float = 0.15
    lower_bound_pct: float = -0.15
    capital_allocation_pct: float = 0.80

@dataclass
class DCAConfig:
    base_order_size: float = 100.0
    drawdown_trigger: float = 0.25 # Drop 25% from where? Or just global drawdown.
    drawdown_multiplier: float = 2.0
    interval_candles: int = 10080 # 1 week (10080 minutes)

@dataclass
class PortfolioConfig:
    base_currency: str = "USDT"
    maker_fee_rate: float = 0.001
    taker_fee_rate: float = 0.001
    reconcile_btc_epsilon: float = 1e-8
    reconcile_usdt_epsilon: float = 0.01

@dataclass
class TelegramConfig:
    enabled: bool = False
    admin_id: int = 0
    alerts: List[str] = field(default_factory=lambda: ["state_change", "pause_trigger"])

@dataclass
class AppSettings:
    testnet: bool = True
    data_dir: str = "data_cache"
    log_dir: str = "logs"
    
    coordinator: CoordinatorConfig = field(default_factory=CoordinatorConfig)
    grid: GridConfig = field(default_factory=GridConfig)
    dca: DCAConfig = field(default_factory=DCAConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)

def load_settings_from_env() -> AppSettings:
    return AppSettings()
