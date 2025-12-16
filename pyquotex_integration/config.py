"""Configuration for PyQuotex integration."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QuotexConfig:
    """Configuration for Quotex API connection."""
    
    email: str = os.getenv("QUOTEX_EMAIL", "")
    password: str = os.getenv("QUOTEX_PASSWORD", "")
    
    # Connection watchdog settings
    ping_interval: float = 30.0
    ping_timeout: float = 10.0
    reconnect_max_retries: int = 10
    reconnect_base_delay: float = 1.0
    reconnect_max_delay: float = 300.0
    reconnect_exponential_base: float = 2.0
    
    # Asset selection settings
    min_payout: float = 80.0
    preferred_assets: list[str] = field(default_factory=lambda: ["EURUSD", "GBPUSD", "USDJPY"])
    
    # Async queue settings
    request_queue_maxsize: int = 100
    callback_timeout: float = 30.0
    
    # Session settings
    dry_run: bool = False
    default_stake: float = 1.0
    balance_update_interval: float = 5.0
    
    # Logging
    log_level: str = "INFO"
    
    def validate(self) -> None:
        """Validate configuration."""
        if not self.dry_run and (not self.email or not self.password):
            raise ValueError("Email and password are required when not in dry run mode")
        if self.ping_interval <= 0:
            raise ValueError("ping_interval must be positive")
        if self.reconnect_base_delay <= 0:
            raise ValueError("reconnect_base_delay must be positive")
        if self.min_payout < 0 or self.min_payout > 100:
            raise ValueError("min_payout must be between 0 and 100")
