"""
Test script to verify all PyQuotex integration features.
"""

import asyncio
import logging
import sys

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
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)


async def test_client():
    """Test PyQuotexClient basic functionality."""
    logger.info("Testing PyQuotexClient...")
    
    config = QuotexConfig(dry_run=True)
    client = PyQuotexClient(config)
    
    # Test connection
    assert await client.connect(), "Connection failed"
    assert client.is_connected, "Not connected"
    logger.info("✓ Connection test passed")
    
    # Test balance
    balance = await client.get_balance()
    assert balance is not None, "Balance is None"
    assert "real" in balance, "Balance missing 'real' key"
    logger.info(f"✓ Balance test passed: ${balance['real']:.2f}")
    
    # Test assets
    assets = await client.get_assets()
    assert assets is not None, "Assets is None"
    assert len(assets) > 0, "No assets returned"
    logger.info(f"✓ Assets test passed: {len(assets)} assets")
    
    # Test candles
    candles = await client.get_candles("EURUSD", 60, 10)
    assert candles is not None, "Candles is None"
    assert len(candles) > 0, "No candles returned"
    logger.info(f"✓ Candles test passed: {len(candles)} candles")
    
    # Test ping
    ping_result = await client.ping()
    assert ping_result, "Ping failed"
    logger.info("✓ Ping test passed")
    
    # Test disconnect
    await client.disconnect()
    assert not client.is_connected, "Still connected after disconnect"
    logger.info("✓ Disconnect test passed")
    
    logger.info("✓ All PyQuotexClient tests passed\n")


async def test_watchdog():
    """Test ConnectionWatchdog functionality."""
    logger.info("Testing ConnectionWatchdog...")
    
    config = QuotexConfig(dry_run=True, ping_interval=2.0)
    client = PyQuotexClient(config)
    
    await client.connect()
    
    reconnect_triggered = []
    
    def on_reconnect():
        reconnect_triggered.append(True)
    
    watchdog = ConnectionWatchdog(client, config, on_reconnect=on_reconnect)
    
    # Start watchdog
    await watchdog.start()
    assert watchdog.is_running, "Watchdog not running"
    logger.info("✓ Watchdog start test passed")
    
    # Wait for a few pings
    await asyncio.sleep(5)
    
    # Force reconnect
    success = await watchdog.force_reconnect()
    assert success, "Force reconnect failed"
    assert len(reconnect_triggered) > 0, "Reconnect callback not triggered"
    logger.info("✓ Force reconnect test passed")
    
    # Check stats
    stats = watchdog.stats
    assert stats["total_reconnects"] > 0, "No reconnects recorded"
    logger.info(f"✓ Stats test passed: {stats['total_reconnects']} reconnects")
    
    # Stop watchdog
    await watchdog.stop()
    assert not watchdog.is_running, "Watchdog still running"
    logger.info("✓ Watchdog stop test passed")
    
    await client.disconnect()
    
    logger.info("✓ All ConnectionWatchdog tests passed\n")


async def test_async_queue():
    """Test AsyncRequestQueue functionality."""
    logger.info("Testing AsyncRequestQueue...")
    
    config = QuotexConfig(dry_run=True)
    client = PyQuotexClient(config)
    
    await client.connect()
    
    queue = AsyncRequestQueue(client, config)
    
    # Start queue
    await queue.start()
    assert queue.is_running, "Queue not running"
    logger.info("✓ Queue start test passed")
    
    # Test balance request
    response = await queue.get_balance()
    assert response.success, "Balance request failed"
    assert response.data is not None, "No balance data"
    logger.info(f"✓ Balance request test passed: ${response.data['real']:.2f}")
    
    # Test assets request
    response = await queue.get_assets()
    assert response.success, "Assets request failed"
    assert len(response.data) > 0, "No assets data"
    logger.info(f"✓ Assets request test passed: {len(response.data)} assets")
    
    # Test candles request with callback
    callback_triggered = []
    
    def candle_callback(response):
        callback_triggered.append(response.success)
    
    await queue.get_candles(
        asset="EURUSD",
        period=60,
        count=10,
        callback=candle_callback
    )
    
    await asyncio.sleep(1)
    assert len(callback_triggered) > 0, "Callback not triggered"
    logger.info("✓ Candles request with callback test passed")
    
    # Check stats
    stats = queue.stats
    assert stats["processed_count"] > 0, "No requests processed"
    logger.info(f"✓ Stats test passed: {stats['processed_count']} processed")
    
    # Stop queue
    await queue.stop()
    assert not queue.is_running, "Queue still running"
    logger.info("✓ Queue stop test passed")
    
    await client.disconnect()
    
    logger.info("✓ All AsyncRequestQueue tests passed\n")


async def test_asset_selector():
    """Test AssetSelector functionality."""
    logger.info("Testing AssetSelector...")
    
    config = QuotexConfig(dry_run=True, min_payout=80.0)
    client = PyQuotexClient(config)
    
    await client.connect()
    
    selector = AssetSelector(client, config)
    
    # Update assets
    success = await selector.update_assets()
    assert success, "Asset update failed"
    logger.info("✓ Asset update test passed")
    
    # Test available assets
    available = selector.available_assets
    assert len(available) > 0, "No available assets"
    logger.info(f"✓ Available assets test passed: {len(available)} assets")
    
    # Test best assets
    best = selector.best_assets
    assert len(best) > 0, "No best assets"
    logger.info(f"✓ Best assets test passed: top payout {best[0].payout:.1f}%")
    
    # Test get best asset
    best_asset = selector.get_best_asset()
    assert best_asset is not None, "No best asset found"
    logger.info(f"✓ Get best asset test passed: {best_asset.name}")
    
    # Test filtering
    filtered = selector.filter_assets(min_payout=85.0)
    logger.info(f"✓ Filter test passed: {len(filtered)} assets above 85%")
    
    # Test top assets
    top_3 = selector.get_top_assets(count=3)
    assert len(top_3) <= 3, "Too many assets returned"
    logger.info(f"✓ Top assets test passed: {len(top_3)} assets")
    
    # Test auto-update
    callback_triggered = []
    
    def update_callback(assets):
        callback_triggered.append(len(assets))
    
    selector.register_callback(update_callback)
    await selector.start_auto_update(interval=2.0)
    await asyncio.sleep(3)
    assert len(callback_triggered) > 0, "Callback not triggered"
    logger.info("✓ Auto-update with callback test passed")
    
    # Stop auto-update
    await selector.stop_auto_update()
    assert not selector.is_running, "Selector still running"
    logger.info("✓ Stop auto-update test passed")
    
    await client.disconnect()
    
    logger.info("✓ All AssetSelector tests passed\n")


async def test_session():
    """Test SessionContext functionality."""
    logger.info("Testing SessionContext...")
    
    config = QuotexConfig(dry_run=True)
    client = PyQuotexClient(config)
    
    await client.connect()
    
    session = SessionContext(client, config)
    
    # Initialize session
    success = await session.initialize()
    assert success, "Session initialization failed"
    assert session.current_balance > 0, "Balance is zero"
    logger.info(f"✓ Initialization test passed: ${session.current_balance:.2f}")
    
    # Test balance update
    success = await session.update_balance()
    assert success, "Balance update failed"
    logger.info("✓ Balance update test passed")
    
    # Test trade recording
    trade = await session.record_trade(
        asset="EURUSD",
        amount=1.0,
        direction="call",
        duration=60,
        wait_for_result=True
    )
    assert trade is not None, "Trade recording failed"
    assert trade.asset == "EURUSD", "Wrong asset"
    assert trade.amount == 1.0, "Wrong amount"
    logger.info(f"✓ Trade recording test passed: {'WIN' if trade.win else 'LOSS'}")
    
    # Test trade history
    history = session.trade_history
    assert len(history) == 1, "Wrong number of trades"
    logger.info(f"✓ Trade history test passed: {len(history)} trade")
    
    # Test stats
    stats = session.get_stats_summary()
    assert stats["account"]["total_trades"] == 1, "Wrong trade count"
    logger.info("✓ Stats summary test passed")
    
    # Test recent trades
    recent = session.get_recent_trades(count=5)
    assert len(recent) == 1, "Wrong number of recent trades"
    logger.info("✓ Recent trades test passed")
    
    await client.disconnect()
    
    logger.info("✓ All SessionContext tests passed\n")


async def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("PyQuotex Integration - Feature Tests")
    logger.info("=" * 60 + "\n")
    
    try:
        await test_client()
        await test_watchdog()
        await test_async_queue()
        await test_asset_selector()
        await test_session()
        
        logger.info("=" * 60)
        logger.info("✓ ALL TESTS PASSED!")
        logger.info("=" * 60)
        
    except AssertionError as e:
        logger.error(f"✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"✗ ERROR: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
