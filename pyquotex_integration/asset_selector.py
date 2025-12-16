"""Asset auto-selection module for finding best trading candidates."""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from .client import PyQuotexClient
from .config import QuotexConfig


@dataclass
class AssetInfo:
    """Asset information with payout and availability."""
    name: str
    category: str
    is_open: bool
    payout: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def score(self) -> float:
        """Calculate asset score based on payout and availability."""
        if not self.is_open:
            return 0.0
        return self.payout
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "category": self.category,
            "is_open": self.is_open,
            "payout": self.payout,
            "score": self.score,
            "last_updated": self.last_updated.isoformat()
        }


class AssetSelector:
    """
    Asset auto-selection module that queries payouts,
    filters for availability, and exposes best candidates.
    """
    
    def __init__(self, client: PyQuotexClient, config: QuotexConfig):
        """
        Initialize asset selector.
        
        Args:
            client: PyQuotexClient instance
            config: Configuration object
        """
        self.client = client
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(config.log_level)
        
        self._assets: Dict[str, AssetInfo] = {}
        self._running = False
        self._update_task: Optional[asyncio.Task] = None
        self._update_interval = 60.0
        self._callbacks: List[Callable] = []
        
    @property
    def is_running(self) -> bool:
        """Check if auto-update is running."""
        return self._running
    
    @property
    def available_assets(self) -> List[AssetInfo]:
        """Get list of available assets."""
        return [
            asset for asset in self._assets.values()
            if asset.is_open
        ]
    
    @property
    def best_assets(self) -> List[AssetInfo]:
        """Get list of best assets sorted by score."""
        available = self.available_assets
        return sorted(available, key=lambda a: a.score, reverse=True)
    
    async def start_auto_update(self, interval: float = 60.0) -> None:
        """
        Start automatic asset information updates.
        
        Args:
            interval: Update interval in seconds
        """
        if self._running:
            self.logger.warning("Auto-update already running")
            return
        
        self._update_interval = interval
        self._running = True
        self._update_task = asyncio.create_task(self._update_loop())
        self.logger.info(f"Asset auto-update started (interval: {interval}s)")
    
    async def stop_auto_update(self) -> None:
        """Stop automatic asset information updates."""
        if not self._running:
            return
        
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Asset auto-update stopped")
    
    def register_callback(self, callback: Callable[[List[AssetInfo]], None]) -> None:
        """
        Register a callback to be invoked when assets are updated.
        
        Args:
            callback: Function to call with updated asset list
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)
            self.logger.debug(f"Registered callback: {callback}")
    
    def unregister_callback(self, callback: Callable) -> None:
        """
        Unregister a callback.
        
        Args:
            callback: Callback to unregister
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            self.logger.debug(f"Unregistered callback: {callback}")
    
    async def update_assets(self) -> bool:
        """
        Update asset information from API.
        
        Returns:
            True if update successful, False otherwise
        """
        if not self.client.is_connected:
            self.logger.error("Client not connected")
            return False
        
        try:
            self.logger.debug("Updating asset information...")
            
            assets_data = await self.client.get_assets()
            
            if not assets_data:
                self.logger.warning("No assets data received")
                return False
            
            updated_assets = []
            
            for asset_data in assets_data:
                asset_name = asset_data["name"]
                
                payout = await self._get_asset_payout(asset_name)
                
                asset_info = AssetInfo(
                    name=asset_name,
                    category=asset_data.get("category", "other"),
                    is_open=asset_data.get("is_open", False),
                    payout=payout,
                    last_updated=datetime.now()
                )
                
                self._assets[asset_name] = asset_info
                updated_assets.append(asset_info)
            
            self.logger.info(f"Updated {len(updated_assets)} assets")
            
            await self._notify_callbacks(updated_assets)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating assets: {e}", exc_info=True)
            return False
    
    async def _get_asset_payout(self, asset_name: str) -> float:
        """
        Get payout percentage for an asset.
        
        Args:
            asset_name: Asset name
            
        Returns:
            Payout percentage
        """
        try:
            if self.config.dry_run:
                import random
                return random.uniform(80, 90)
            else:
                if hasattr(self.client._api, "get_payment"):
                    payout = await asyncio.to_thread(
                        self.client._api.get_payment,
                        asset_name
                    )
                    return payout if payout else 0.0
                else:
                    return 85.0
                    
        except Exception as e:
            self.logger.debug(f"Error getting payout for {asset_name}: {e}")
            return 0.0
    
    def get_asset(self, name: str) -> Optional[AssetInfo]:
        """
        Get asset information by name.
        
        Args:
            name: Asset name
            
        Returns:
            AssetInfo object or None if not found
        """
        return self._assets.get(name)
    
    def filter_assets(
        self,
        min_payout: Optional[float] = None,
        categories: Optional[List[str]] = None,
        only_open: bool = True,
        preferred: bool = False
    ) -> List[AssetInfo]:
        """
        Filter assets based on criteria.
        
        Args:
            min_payout: Minimum payout percentage
            categories: List of categories to include
            only_open: Only include open assets
            preferred: Only include preferred assets
            
        Returns:
            List of matching assets
        """
        min_payout = min_payout or self.config.min_payout
        
        filtered = []
        
        for asset in self._assets.values():
            if only_open and not asset.is_open:
                continue
            
            if asset.payout < min_payout:
                continue
            
            if categories and asset.category not in categories:
                continue
            
            if preferred and asset.name not in self.config.preferred_assets:
                continue
            
            filtered.append(asset)
        
        return sorted(filtered, key=lambda a: a.score, reverse=True)
    
    def get_best_asset(
        self,
        min_payout: Optional[float] = None,
        categories: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None
    ) -> Optional[AssetInfo]:
        """
        Get the best available asset based on criteria.
        
        Args:
            min_payout: Minimum payout percentage
            categories: List of categories to include
            exclude: List of asset names to exclude
            
        Returns:
            Best AssetInfo or None if no match found
        """
        filtered = self.filter_assets(
            min_payout=min_payout,
            categories=categories,
            only_open=True
        )
        
        if exclude:
            filtered = [a for a in filtered if a.name not in exclude]
        
        return filtered[0] if filtered else None
    
    def get_top_assets(
        self,
        count: int = 5,
        min_payout: Optional[float] = None,
        categories: Optional[List[str]] = None
    ) -> List[AssetInfo]:
        """
        Get top N assets by score.
        
        Args:
            count: Number of assets to return
            min_payout: Minimum payout percentage
            categories: List of categories to include
            
        Returns:
            List of top assets
        """
        filtered = self.filter_assets(
            min_payout=min_payout,
            categories=categories,
            only_open=True
        )
        
        return filtered[:count]
    
    async def _update_loop(self) -> None:
        """Periodic update loop."""
        while self._running:
            try:
                await self.update_assets()
                await asyncio.sleep(self._update_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in update loop: {e}", exc_info=True)
                await asyncio.sleep(self._update_interval)
    
    async def _notify_callbacks(self, assets: List[AssetInfo]) -> None:
        """Notify registered callbacks of asset updates."""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(assets)
                else:
                    callback(assets)
            except Exception as e:
                self.logger.error(f"Error in asset update callback: {e}", exc_info=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get asset selector statistics."""
        return {
            "total_assets": len(self._assets),
            "available_assets": len(self.available_assets),
            "is_running": self._running,
            "update_interval": self._update_interval,
            "callbacks_registered": len(self._callbacks)
        }
