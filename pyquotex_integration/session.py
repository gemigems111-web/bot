"""Session context for managing account state and trade history."""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

from .client import PyQuotexClient
from .config import QuotexConfig


@dataclass
class TradeRecord:
    """Record of a single trade."""
    trade_id: str
    asset: str
    amount: float
    direction: str
    duration: int
    timestamp: datetime
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    profit: float = 0.0
    win: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trade_id": self.trade_id,
            "asset": self.asset,
            "amount": self.amount,
            "direction": self.direction,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "result": self.result,
            "profit": self.profit,
            "win": self.win
        }


@dataclass
class AccountInfo:
    """Account information and statistics."""
    balance_real: float = 0.0
    balance_demo: float = 0.0
    initial_balance: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    @property
    def roi(self) -> float:
        """Calculate return on investment percentage."""
        if self.initial_balance == 0:
            return 0.0
        return (self.total_profit / self.initial_balance) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "balance_real": self.balance_real,
            "balance_demo": self.balance_demo,
            "initial_balance": self.initial_balance,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_profit": self.total_profit,
            "win_rate": self.win_rate,
            "roi": self.roi,
            "last_updated": self.last_updated.isoformat()
        }


class SessionContext:
    """
    Session context managing account information and trade history.
    Updates account info after every executed trade.
    """
    
    def __init__(self, client: PyQuotexClient, config: QuotexConfig):
        """
        Initialize session context.
        
        Args:
            client: PyQuotexClient instance
            config: Configuration object
        """
        self.client = client
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(config.log_level)
        
        self.account = AccountInfo()
        self.trades: List[TradeRecord] = []
        
        self._running = False
        self._update_task: Optional[asyncio.Task] = None
        
    @property
    def is_running(self) -> bool:
        """Check if auto-update is running."""
        return self._running
    
    @property
    def current_balance(self) -> float:
        """Get current balance."""
        return self.account.balance_real
    
    @property
    def trade_history(self) -> List[TradeRecord]:
        """Get trade history."""
        return self.trades.copy()
    
    async def initialize(self) -> bool:
        """
        Initialize session by fetching current account info.
        
        Returns:
            True if initialization successful, False otherwise
        """
        self.logger.info("Initializing session context...")
        
        try:
            balance_info = await self.client.get_balance()
            
            if not balance_info:
                self.logger.error("Failed to get balance")
                return False
            
            self.account.balance_real = balance_info.get("real", 0.0)
            self.account.balance_demo = balance_info.get("demo", 0.0)
            self.account.initial_balance = self.account.balance_real
            self.account.last_updated = datetime.now()
            
            self.logger.info(
                f"Session initialized - Balance: ${self.account.balance_real:.2f}"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing session: {e}", exc_info=True)
            return False
    
    async def start_auto_update(self) -> None:
        """Start automatic balance updates."""
        if self._running:
            self.logger.warning("Auto-update already running")
            return
        
        self._running = True
        self._update_task = asyncio.create_task(self._update_loop())
        self.logger.info("Session auto-update started")
    
    async def stop_auto_update(self) -> None:
        """Stop automatic balance updates."""
        if not self._running:
            return
        
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Session auto-update stopped")
    
    async def update_balance(self) -> bool:
        """
        Update account balance from API.
        
        Returns:
            True if update successful, False otherwise
        """
        try:
            balance_info = await self.client.get_balance()
            
            if not balance_info:
                return False
            
            self.account.balance_real = balance_info.get("real", 0.0)
            self.account.balance_demo = balance_info.get("demo", 0.0)
            self.account.last_updated = datetime.now()
            
            self.logger.debug(f"Balance updated: ${self.account.balance_real:.2f}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating balance: {e}", exc_info=True)
            return False
    
    async def record_trade(
        self,
        asset: str,
        amount: float,
        direction: str,
        duration: int = 60,
        wait_for_result: bool = True
    ) -> Optional[TradeRecord]:
        """
        Execute and record a trade.
        
        Args:
            asset: Asset name
            amount: Stake amount
            direction: "call" or "put"
            duration: Trade duration in seconds
            wait_for_result: If True, wait for trade result
            
        Returns:
            TradeRecord object or None on error
        """
        if self.config.dry_run:
            self.logger.info(f"DRY RUN: Would place {direction} trade on {asset} for ${amount}")
        
        try:
            if wait_for_result:
                trade_info = await self.client.buy_and_check_win(
                    asset, amount, direction, duration
                )
            else:
                trade_info = await self.client.buy(
                    asset, amount, direction, duration
                )
            
            if not trade_info:
                self.logger.error("Trade placement failed")
                return None
            
            trade_record = TradeRecord(
                trade_id=trade_info["id"],
                asset=asset,
                amount=amount,
                direction=direction,
                duration=duration,
                timestamp=datetime.fromisoformat(trade_info["timestamp"]),
                status=trade_info.get("status", "pending"),
                result=trade_info.get("result"),
                profit=trade_info.get("profit", 0.0),
                win=trade_info.get("win")
            )
            
            self.trades.append(trade_record)
            
            await self._update_stats(trade_record)
            
            await self.update_balance()
            
            self.logger.info(
                f"Trade recorded: {asset} {direction.upper()} ${amount} "
                f"{'WIN' if trade_record.win else 'LOSS' if trade_record.win is False else 'PENDING'}"
            )
            
            return trade_record
            
        except Exception as e:
            self.logger.error(f"Error recording trade: {e}", exc_info=True)
            return None
    
    async def _update_stats(self, trade: TradeRecord) -> None:
        """Update account statistics based on trade result."""
        self.account.total_trades += 1
        
        if trade.win is True:
            self.account.winning_trades += 1
            self.account.total_profit += trade.profit
        elif trade.win is False:
            self.account.losing_trades += 1
            self.account.total_profit += trade.profit
    
    async def _update_loop(self) -> None:
        """Periodic balance update loop."""
        while self._running:
            try:
                await self.update_balance()
                await asyncio.sleep(self.config.balance_update_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in update loop: {e}", exc_info=True)
                await asyncio.sleep(self.config.balance_update_interval)
    
    def get_recent_trades(self, count: int = 10) -> List[TradeRecord]:
        """
        Get most recent trades.
        
        Args:
            count: Number of trades to return
            
        Returns:
            List of recent trades
        """
        return self.trades[-count:] if self.trades else []
    
    def get_winning_trades(self) -> List[TradeRecord]:
        """Get all winning trades."""
        return [t for t in self.trades if t.win is True]
    
    def get_losing_trades(self) -> List[TradeRecord]:
        """Get all losing trades."""
        return [t for t in self.trades if t.win is False]
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Get comprehensive statistics summary."""
        return {
            "account": self.account.to_dict(),
            "total_trades": len(self.trades),
            "recent_trades": [t.to_dict() for t in self.get_recent_trades(5)]
        }
    
    def reset(self) -> None:
        """Reset session context (clear history but keep current balance)."""
        self.logger.info("Resetting session context...")
        
        current_balance = self.account.balance_real
        
        self.account = AccountInfo(
            balance_real=current_balance,
            initial_balance=current_balance
        )
        self.trades.clear()
        
        self.logger.info("Session context reset")
