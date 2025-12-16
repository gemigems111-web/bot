"""PyQuotex client wrapper encapsulating pyquotex.stable_api functionality."""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from enum import Enum

from .config import QuotexConfig


class ConnectionState(Enum):
    """Connection state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


class PyQuotexClient:
    """
    Wrapper for pyquotex.stable_api providing connection management,
    balance queries, asset information, trading, and candle streaming.
    """
    
    def __init__(self, config: QuotexConfig):
        """
        Initialize PyQuotex client.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(config.log_level)
        
        self._api: Optional[Any] = None
        self._state = ConnectionState.DISCONNECTED
        self._connection_lock = asyncio.Lock()
        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        self._candle_callbacks: Dict[str, List[Callable]] = {}
        
    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._state == ConnectionState.CONNECTED
    
    async def connect(self) -> bool:
        """
        Connect to Quotex API.
        
        Returns:
            True if connection successful, False otherwise
        """
        async with self._connection_lock:
            if self._state == ConnectionState.CONNECTED:
                self.logger.info("Already connected")
                return True
            
            self._state = ConnectionState.CONNECTING
            self.logger.info("Connecting to Quotex API...")
            
            try:
                if self.config.dry_run:
                    self.logger.info("Dry run mode: simulating connection")
                    await asyncio.sleep(0.5)
                    self._api = DryRunAPI(self.config)
                else:
                    from quotexapi.stable_api import Quotex
                    self._api = Quotex(
                        email=self.config.email,
                        password=self.config.password
                    )
                    check, reason = await asyncio.to_thread(self._api.connect)
                    
                    if not check:
                        self.logger.error(f"Connection failed: {reason}")
                        self._state = ConnectionState.DISCONNECTED
                        return False
                
                self._state = ConnectionState.CONNECTED
                self.logger.info("Successfully connected to Quotex API")
                return True
                
            except Exception as e:
                self.logger.error(f"Connection error: {e}", exc_info=True)
                self._state = ConnectionState.DISCONNECTED
                return False
    
    async def disconnect(self) -> None:
        """Disconnect from Quotex API."""
        async with self._connection_lock:
            if self._state == ConnectionState.DISCONNECTED:
                return
            
            self.logger.info("Disconnecting from Quotex API...")
            
            try:
                await self._cleanup_subscriptions()
                
                if self._api and not self.config.dry_run:
                    await asyncio.to_thread(self._api.close)
                
                self._api = None
                self._state = ConnectionState.DISCONNECTED
                self.logger.info("Disconnected successfully")
                
            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}", exc_info=True)
                self._state = ConnectionState.DISCONNECTED
    
    async def ping(self) -> bool:
        """
        Ping the API to check connection health.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        if not self.is_connected:
            return False
        
        try:
            if self.config.dry_run:
                await asyncio.sleep(0.1)
                return True
            else:
                balance = await asyncio.wait_for(
                    asyncio.to_thread(self._api.get_balance),
                    timeout=self.config.ping_timeout
                )
                return balance is not None
                
        except asyncio.TimeoutError:
            self.logger.warning("Ping timeout")
            return False
        except Exception as e:
            self.logger.error(f"Ping error: {e}")
            return False
    
    async def get_balance(self) -> Optional[Dict[str, float]]:
        """
        Get account balance.
        
        Returns:
            Dictionary with balance information or None on error
        """
        if not self.is_connected:
            self.logger.error("Not connected")
            return None
        
        try:
            if self.config.dry_run:
                return await self._api.get_balance()
            else:
                balance = await asyncio.to_thread(self._api.get_balance)
                return {
                    "real": balance if balance else 0.0,
                    "demo": 0.0
                }
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}", exc_info=True)
            return None
    
    async def get_assets(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get available trading assets.
        
        Returns:
            List of asset information dictionaries or None on error
        """
        if not self.is_connected:
            self.logger.error("Not connected")
            return None
        
        try:
            if self.config.dry_run:
                return await self._api.get_assets()
            else:
                assets = await asyncio.to_thread(self._api.get_all_asset_name)
                if not assets:
                    return []
                
                asset_list = []
                for asset_name in assets:
                    try:
                        is_open = await asyncio.to_thread(self._api.check_asset_open, asset_name)
                        asset_list.append({
                            "name": asset_name,
                            "is_open": is_open,
                            "category": self._categorize_asset(asset_name)
                        })
                    except Exception:
                        continue
                
                return asset_list
                
        except Exception as e:
            self.logger.error(f"Error getting assets: {e}", exc_info=True)
            return None
    
    async def buy(
        self,
        asset: str,
        amount: float,
        direction: str,
        duration: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Place a trade.
        
        Args:
            asset: Asset name
            amount: Stake amount
            direction: "call" or "put"
            duration: Trade duration in seconds
            
        Returns:
            Trade information dictionary or None on error
        """
        if not self.is_connected:
            self.logger.error("Not connected")
            return None
        
        try:
            self.logger.info(
                f"Placing trade: {asset} {direction.upper()} "
                f"${amount} for {duration}s"
            )
            
            if self.config.dry_run:
                return await self._api.buy(asset, amount, direction, duration)
            else:
                status, trade_id = await asyncio.to_thread(
                    self._api.buy,
                    amount,
                    asset,
                    direction,
                    duration
                )
                
                if status != "error":
                    return {
                        "id": trade_id,
                        "asset": asset,
                        "amount": amount,
                        "direction": direction,
                        "duration": duration,
                        "timestamp": datetime.now().isoformat(),
                        "status": status
                    }
                else:
                    self.logger.error(f"Trade failed: {trade_id}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error placing trade: {e}", exc_info=True)
            return None
    
    async def buy_and_check_win(
        self,
        asset: str,
        amount: float,
        direction: str,
        duration: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Place a trade and wait for result.
        
        Args:
            asset: Asset name
            amount: Stake amount
            direction: "call" or "put"
            duration: Trade duration in seconds
            
        Returns:
            Trade result dictionary or None on error
        """
        trade = await self.buy(asset, amount, direction, duration)
        if not trade:
            return None
        
        try:
            await asyncio.sleep(duration + 5)
            
            if self.config.dry_run:
                result = await self._api.check_win(trade["id"])
                if result:
                    trade["result"] = result
                    trade["profit"] = result.get("profit", 0)
                    trade["win"] = result.get("win", False)
            else:
                result = await asyncio.to_thread(
                    self._api.check_win,
                    trade["id"]
                )
                
                if result:
                    trade["result"] = result
                    trade["profit"] = result.get("profit", 0)
                    trade["win"] = result.get("win", False)
            
            return trade
                
        except Exception as e:
            self.logger.error(f"Error checking trade result: {e}", exc_info=True)
            return trade
    
    async def get_candles(
        self,
        asset: str,
        period: int = 60,
        count: int = 100
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch historical candles.
        
        Args:
            asset: Asset name
            period: Candle period in seconds
            count: Number of candles to fetch
            
        Returns:
            List of candle dictionaries or None on error
        """
        if not self.is_connected:
            self.logger.error("Not connected")
            return None
        
        try:
            if self.config.dry_run:
                return await self._api.get_candles(asset, period, count)
            else:
                candles = await asyncio.to_thread(
                    self._api.get_candles,
                    asset,
                    period,
                    count
                )
                return candles if candles else []
                
        except Exception as e:
            self.logger.error(f"Error fetching candles: {e}", exc_info=True)
            return None
    
    async def subscribe_candles(
        self,
        asset: str,
        period: int,
        callback: Callable[[Dict[str, Any]], None]
    ) -> bool:
        """
        Subscribe to real-time candle updates.
        
        Args:
            asset: Asset name
            period: Candle period in seconds
            callback: Function to call with candle data
            
        Returns:
            True if subscription successful, False otherwise
        """
        if not self.is_connected:
            self.logger.error("Not connected")
            return False
        
        try:
            sub_key = f"{asset}_{period}"
            
            if sub_key not in self._candle_callbacks:
                self._candle_callbacks[sub_key] = []
            
            self._candle_callbacks[sub_key].append(callback)
            
            if sub_key not in self._subscriptions:
                if self.config.dry_run:
                    await self._start_dry_run_candle_stream(asset, period)
                else:
                    await asyncio.to_thread(
                        self._api.start_candles_stream,
                        asset,
                        period
                    )
                
                self._subscriptions[sub_key] = {
                    "asset": asset,
                    "period": period,
                    "active": True
                }
                
                asyncio.create_task(self._candle_dispatcher(sub_key))
            
            self.logger.info(f"Subscribed to candles: {sub_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error subscribing to candles: {e}", exc_info=True)
            return False
    
    async def unsubscribe_candles(self, asset: str, period: int) -> bool:
        """
        Unsubscribe from candle updates.
        
        Args:
            asset: Asset name
            period: Candle period in seconds
            
        Returns:
            True if unsubscription successful, False otherwise
        """
        sub_key = f"{asset}_{period}"
        
        if sub_key in self._subscriptions:
            self._subscriptions[sub_key]["active"] = False
            
            if not self.config.dry_run and self._api:
                try:
                    await asyncio.to_thread(
                        self._api.stop_candles_stream,
                        asset,
                        period
                    )
                except Exception as e:
                    self.logger.error(f"Error stopping candle stream: {e}")
            
            del self._subscriptions[sub_key]
            if sub_key in self._candle_callbacks:
                del self._candle_callbacks[sub_key]
            
            self.logger.info(f"Unsubscribed from candles: {sub_key}")
            return True
        
        return False
    
    async def _candle_dispatcher(self, sub_key: str) -> None:
        """Dispatch candle updates to callbacks."""
        while sub_key in self._subscriptions and self._subscriptions[sub_key]["active"]:
            try:
                if self.config.dry_run:
                    await asyncio.sleep(1)
                    candle = await self._api.get_latest_candle(sub_key)
                else:
                    candle_data = getattr(self._api, "candles", {}).get(sub_key)
                    if candle_data:
                        candle = candle_data[-1] if isinstance(candle_data, list) else candle_data
                    else:
                        candle = None
                
                if candle and sub_key in self._candle_callbacks:
                    for callback in self._candle_callbacks[sub_key]:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(candle)
                            else:
                                callback(candle)
                        except Exception as e:
                            self.logger.error(f"Error in candle callback: {e}")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in candle dispatcher: {e}")
                await asyncio.sleep(1)
    
    async def _start_dry_run_candle_stream(self, asset: str, period: int) -> None:
        """Start simulated candle stream for dry run mode."""
        pass
    
    async def _cleanup_subscriptions(self) -> None:
        """Clean up all active subscriptions."""
        for sub_key in list(self._subscriptions.keys()):
            asset = self._subscriptions[sub_key]["asset"]
            period = self._subscriptions[sub_key]["period"]
            await self.unsubscribe_candles(asset, period)
    
    def _categorize_asset(self, asset_name: str) -> str:
        """Categorize asset by name."""
        if any(curr in asset_name for curr in ["USD", "EUR", "GBP", "JPY", "AUD", "CAD"]):
            return "forex"
        elif any(crypto in asset_name for crypto in ["BTC", "ETH", "LTC", "XRP"]):
            return "crypto"
        else:
            return "other"


class DryRunAPI:
    """Simulated API for dry run mode."""
    
    def __init__(self, config: QuotexConfig):
        self.config = config
        self.balance = 10000.0
        self.trades = {}
        self.candle_streams = {}
        
    async def get_balance(self) -> Dict[str, float]:
        """Get simulated balance."""
        return {"real": self.balance, "demo": 0.0}
    
    async def get_assets(self) -> List[Dict[str, Any]]:
        """Get simulated assets."""
        return [
            {"name": "EURUSD", "is_open": True, "category": "forex", "payout": 85},
            {"name": "GBPUSD", "is_open": True, "category": "forex", "payout": 83},
            {"name": "USDJPY", "is_open": True, "category": "forex", "payout": 84},
            {"name": "BTCUSD", "is_open": True, "category": "crypto", "payout": 80},
            {"name": "ETHUSD", "is_open": True, "category": "crypto", "payout": 81},
        ]
    
    async def buy(
        self,
        asset: str,
        amount: float,
        direction: str,
        duration: int
    ) -> Dict[str, Any]:
        """Simulate trade placement."""
        import random
        trade_id = f"dry_run_{random.randint(10000, 99999)}"
        
        trade = {
            "id": trade_id,
            "asset": asset,
            "amount": amount,
            "direction": direction,
            "duration": duration,
            "timestamp": datetime.now().isoformat(),
            "status": "opened"
        }
        
        self.trades[trade_id] = trade
        return trade
    
    async def check_win(self, trade_id: str) -> Dict[str, Any]:
        """Simulate checking trade result."""
        import random
        
        if trade_id not in self.trades:
            return None
        
        trade = self.trades[trade_id]
        win = random.choice([True, False])
        profit = trade["amount"] * 0.85 if win else -trade["amount"]
        
        self.balance += profit
        
        return {
            "win": win,
            "profit": profit,
            "close_price": random.uniform(1.0, 2.0)
        }
    
    async def get_candles(
        self,
        asset: str,
        period: int,
        count: int
    ) -> List[Dict[str, Any]]:
        """Get simulated candles."""
        import random
        candles = []
        base_price = 1.1
        
        for i in range(count):
            timestamp = datetime.now().timestamp() - (count - i) * period
            open_price = base_price + random.uniform(-0.01, 0.01)
            close_price = open_price + random.uniform(-0.005, 0.005)
            high_price = max(open_price, close_price) + random.uniform(0, 0.003)
            low_price = min(open_price, close_price) - random.uniform(0, 0.003)
            
            candles.append({
                "timestamp": timestamp,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": random.uniform(100, 1000)
            })
            
            base_price = close_price
        
        return candles
    
    async def get_latest_candle(self, sub_key: str) -> Dict[str, Any]:
        """Get latest simulated candle."""
        import random
        
        if sub_key not in self.candle_streams:
            self.candle_streams[sub_key] = 1.1
        
        base_price = self.candle_streams[sub_key]
        open_price = base_price
        close_price = open_price + random.uniform(-0.005, 0.005)
        high_price = max(open_price, close_price) + random.uniform(0, 0.003)
        low_price = min(open_price, close_price) - random.uniform(0, 0.003)
        
        self.candle_streams[sub_key] = close_price
        
        return {
            "timestamp": datetime.now().timestamp(),
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": random.uniform(100, 1000)
        }
