"""PyQuotex Integration - A comprehensive wrapper for pyquotex.stable_api."""

from .client import PyQuotexClient
from .config import QuotexConfig
from .session import SessionContext
from .asset_selector import AssetSelector
from .async_queue import AsyncRequestQueue
from .watchdog import ConnectionWatchdog

__version__ = "0.1.0"
__all__ = [
    "PyQuotexClient",
    "QuotexConfig",
    "SessionContext",
    "AssetSelector",
    "AsyncRequestQueue",
    "ConnectionWatchdog",
]
