"""Connection watchdog for monitoring and auto-reconnecting."""

import asyncio
import logging
from typing import Optional, Callable
from datetime import datetime

from .client import PyQuotexClient, ConnectionState
from .config import QuotexConfig


class ConnectionWatchdog:
    """
    Monitors connection health, detects disconnects, and handles
    auto-reconnection with exponential back-off.
    """
    
    def __init__(
        self,
        client: PyQuotexClient,
        config: QuotexConfig,
        on_reconnect: Optional[Callable] = None
    ):
        """
        Initialize connection watchdog.
        
        Args:
            client: PyQuotexClient instance to monitor
            config: Configuration object
            on_reconnect: Optional callback to invoke after successful reconnect
        """
        self.client = client
        self.config = config
        self.on_reconnect = on_reconnect
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(config.log_level)
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._consecutive_failures = 0
        self._last_ping_time: Optional[datetime] = None
        self._last_failure_time: Optional[datetime] = None
        self._total_reconnects = 0
        
    @property
    def is_running(self) -> bool:
        """Check if watchdog is running."""
        return self._running
    
    @property
    def stats(self) -> dict:
        """Get watchdog statistics."""
        return {
            "consecutive_failures": self._consecutive_failures,
            "total_reconnects": self._total_reconnects,
            "last_ping_time": self._last_ping_time.isoformat() if self._last_ping_time else None,
            "last_failure_time": self._last_failure_time.isoformat() if self._last_failure_time else None,
            "is_running": self._running
        }
    
    async def start(self) -> None:
        """Start the watchdog monitoring."""
        if self._running:
            self.logger.warning("Watchdog already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        self.logger.info("Connection watchdog started")
    
    async def stop(self) -> None:
        """Stop the watchdog monitoring."""
        if not self._running:
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Connection watchdog stopped")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.ping_interval)
                
                if not self._running:
                    break
                
                ping_success = await self._check_connection()
                
                if ping_success:
                    self._last_ping_time = datetime.now()
                    
                    if self._consecutive_failures > 0:
                        self.logger.info("Connection recovered")
                        self._consecutive_failures = 0
                else:
                    self._consecutive_failures += 1
                    self._last_failure_time = datetime.now()
                    
                    self.logger.warning(
                        f"Connection check failed "
                        f"(consecutive failures: {self._consecutive_failures})"
                    )
                    
                    await self._handle_disconnect()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in watchdog monitor loop: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def _check_connection(self) -> bool:
        """
        Check connection health.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        if self.client.state != ConnectionState.CONNECTED:
            return False
        
        try:
            return await self.client.ping()
        except Exception as e:
            self.logger.error(f"Ping error: {e}")
            return False
    
    async def _handle_disconnect(self) -> None:
        """Handle detected disconnect and attempt reconnection."""
        self.logger.warning("Disconnect detected, initiating reconnection...")
        
        retry_count = 0
        
        while self._running and retry_count < self.config.reconnect_max_retries:
            delay = self._calculate_backoff_delay(retry_count)
            
            self.logger.info(
                f"Reconnection attempt {retry_count + 1}/"
                f"{self.config.reconnect_max_retries} in {delay:.1f}s"
            )
            
            await asyncio.sleep(delay)
            
            if not self._running:
                break
            
            try:
                await self.client.disconnect()
                await asyncio.sleep(1)
                
                success = await self.client.connect()
                
                if success:
                    self.logger.info("Reconnection successful")
                    self._total_reconnects += 1
                    self._consecutive_failures = 0
                    
                    if self.on_reconnect:
                        try:
                            if asyncio.iscoroutinefunction(self.on_reconnect):
                                await self.on_reconnect()
                            else:
                                self.on_reconnect()
                        except Exception as e:
                            self.logger.error(f"Error in reconnect callback: {e}")
                    
                    return
                else:
                    self.logger.error(f"Reconnection attempt {retry_count + 1} failed")
                    retry_count += 1
                    
            except Exception as e:
                self.logger.error(
                    f"Error during reconnection attempt {retry_count + 1}: {e}",
                    exc_info=True
                )
                retry_count += 1
        
        if retry_count >= self.config.reconnect_max_retries:
            self.logger.error(
                f"Failed to reconnect after {self.config.reconnect_max_retries} attempts"
            )
    
    def _calculate_backoff_delay(self, retry_count: int) -> float:
        """
        Calculate exponential back-off delay.
        
        Args:
            retry_count: Current retry attempt number
            
        Returns:
            Delay in seconds
        """
        delay = self.config.reconnect_base_delay * (
            self.config.reconnect_exponential_base ** retry_count
        )
        return min(delay, self.config.reconnect_max_delay)
    
    async def force_reconnect(self) -> bool:
        """
        Force an immediate reconnection attempt.
        
        Returns:
            True if reconnection successful, False otherwise
        """
        self.logger.info("Forcing reconnect...")
        
        try:
            await self.client.disconnect()
            await asyncio.sleep(1)
            success = await self.client.connect()
            
            if success:
                self._total_reconnects += 1
                self._consecutive_failures = 0
                
                if self.on_reconnect:
                    try:
                        if asyncio.iscoroutinefunction(self.on_reconnect):
                            await self.on_reconnect()
                        else:
                            self.on_reconnect()
                    except Exception as e:
                        self.logger.error(f"Error in reconnect callback: {e}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error during forced reconnect: {e}", exc_info=True)
            return False
