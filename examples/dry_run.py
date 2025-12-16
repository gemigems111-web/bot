"""
Dry run demonstration of PyQuotex integration.

This script demonstrates:
- Login and connection
- Balance and asset fetching
- Continuous candle streaming
- Reconnect handling via simulated disconnects
- Asset auto-selection
- Async queue processing
"""

import asyncio
import logging
import sys
from datetime import datetime

sys.path.insert(0, "/home/engine/project")

from pyquotex_integration import (
    PyQuotexClient,
    QuotexConfig,
    SessionContext,
    AssetSelector,
    AsyncRequestQueue,
    ConnectionWatchdog
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)


class DryRunDemo:
    """Dry run demonstration orchestrator."""
    
    def __init__(self):
        self.config = QuotexConfig(
            dry_run=True,
            ping_interval=10.0,
            log_level="INFO"
        )
        
        self.client = PyQuotexClient(self.config)
        self.session = SessionContext(self.client, self.config)
        self.asset_selector = AssetSelector(self.client, self.config)
        self.request_queue = AsyncRequestQueue(self.client, self.config)
        self.watchdog = ConnectionWatchdog(
            self.client,
            self.config,
            on_reconnect=self.on_reconnect
        )
        
        self.candle_count = 0
        self.running = True
    
    async def on_reconnect(self):
        """Callback invoked after successful reconnection."""
        logger.info("=== RECONNECT CALLBACK TRIGGERED ===")
        await self.session.update_balance()
        await self.asset_selector.update_assets()
    
    async def candle_callback(self, candle):
        """Callback for real-time candle updates."""
        self.candle_count += 1
        if self.candle_count % 10 == 0:
            logger.info(
                f"Received {self.candle_count} candles - Latest: "
                f"O:{candle['open']:.5f} H:{candle['high']:.5f} "
                f"L:{candle['low']:.5f} C:{candle['close']:.5f}"
            )
    
    async def asset_update_callback(self, assets):
        """Callback for asset updates."""
        logger.info(f"Assets updated: {len(assets)} available")
        
        best = self.asset_selector.get_best_asset()
        if best:
            logger.info(
                f"Best asset: {best.name} (payout: {best.payout:.1f}%, "
                f"category: {best.category})"
            )
    
    async def run(self):
        """Run the dry run demonstration."""
        logger.info("=" * 60)
        logger.info("PyQuotex Integration - Dry Run Demonstration")
        logger.info("=" * 60)
        
        try:
            logger.info("\n[1/8] Connecting to Quotex API...")
            connected = await self.client.connect()
            
            if not connected:
                logger.error("Failed to connect")
                return
            
            logger.info("✓ Connected successfully")
            
            logger.info("\n[2/8] Initializing session and fetching balance...")
            await self.session.initialize()
            logger.info(
                f"✓ Balance: ${self.session.current_balance:.2f}"
            )
            
            logger.info("\n[3/8] Fetching available assets...")
            assets = await self.client.get_assets()
            logger.info(f"✓ Found {len(assets)} assets")
            
            for asset in assets[:5]:
                logger.info(
                    f"  - {asset['name']}: {'OPEN' if asset['is_open'] else 'CLOSED'} "
                    f"({asset['category']})"
                )
            
            logger.info("\n[4/8] Starting connection watchdog...")
            await self.watchdog.start()
            logger.info("✓ Watchdog started")
            
            logger.info("\n[5/8] Starting async request queue...")
            await self.request_queue.start()
            logger.info("✓ Request queue started")
            
            logger.info("\n[6/8] Starting asset auto-selection...")
            self.asset_selector.register_callback(self.asset_update_callback)
            await self.asset_selector.start_auto_update(interval=30.0)
            await self.asset_selector.update_assets()
            logger.info("✓ Asset selector started")
            
            top_assets = self.asset_selector.get_top_assets(count=3)
            logger.info("\nTop 3 assets by payout:")
            for i, asset in enumerate(top_assets, 1):
                logger.info(
                    f"  {i}. {asset.name}: {asset.payout:.1f}% "
                    f"({'OPEN' if asset.is_open else 'CLOSED'})"
                )
            
            logger.info("\n[7/8] Subscribing to real-time candle stream...")
            if top_assets:
                asset = top_assets[0].name
                logger.info(f"Subscribing to {asset} candles...")
                
                await self.request_queue.subscribe_candles(
                    asset=asset,
                    period=60,
                    callback=self.candle_callback
                )
                
                logger.info("✓ Subscribed to candle stream")
            
            logger.info("\n[8/8] Streaming candles (30 seconds)...")
            logger.info("Candles will be logged every 10 updates...")
            
            await asyncio.sleep(30)
            
            logger.info("\n=== Testing reconnect handling ===")
            logger.info("Simulating disconnect by forcing reconnection...")
            
            reconnect_success = await self.watchdog.force_reconnect()
            
            if reconnect_success:
                logger.info("✓ Reconnection successful")
                logger.info("Balance after reconnect: $%.2f", self.session.current_balance)
            else:
                logger.error("✗ Reconnection failed")
            
            logger.info("\nContinuing candle stream for 20 more seconds...")
            await asyncio.sleep(20)
            
            logger.info("\n=== Final Statistics ===")
            
            session_stats = self.session.get_stats_summary()
            logger.info(f"Session balance: ${session_stats['account']['balance_real']:.2f}")
            logger.info(f"Total candles received: {self.candle_count}")
            
            watchdog_stats = self.watchdog.stats
            logger.info(f"Watchdog stats:")
            logger.info(f"  - Total reconnects: {watchdog_stats['total_reconnects']}")
            logger.info(f"  - Consecutive failures: {watchdog_stats['consecutive_failures']}")
            
            queue_stats = self.request_queue.stats
            logger.info(f"Request queue stats:")
            logger.info(f"  - Processed: {queue_stats['processed_count']}")
            logger.info(f"  - Failed: {queue_stats['failed_count']}")
            
            asset_stats = self.asset_selector.get_stats()
            logger.info(f"Asset selector stats:")
            logger.info(f"  - Total assets: {asset_stats['total_assets']}")
            logger.info(f"  - Available: {asset_stats['available_assets']}")
            
        except KeyboardInterrupt:
            logger.info("\nInterrupted by user")
        except Exception as e:
            logger.error(f"Error during demonstration: {e}", exc_info=True)
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources."""
        logger.info("\n=== Cleaning up ===")
        
        try:
            logger.info("Stopping asset selector...")
            await self.asset_selector.stop_auto_update()
            
            logger.info("Stopping request queue...")
            await self.request_queue.stop()
            
            logger.info("Stopping watchdog...")
            await self.watchdog.stop()
            
            logger.info("Stopping session updates...")
            await self.session.stop_auto_update()
            
            logger.info("Disconnecting client...")
            await self.client.disconnect()
            
            logger.info("✓ Cleanup complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)


async def main():
    """Main entry point."""
    demo = DryRunDemo()
    await demo.run()
    
    logger.info("\n" + "=" * 60)
    logger.info("Dry run demonstration completed successfully!")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nExiting...")
