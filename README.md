# PyQuotex Integration

A comprehensive wrapper for `pyquotex.stable_api` providing production-ready features for trading automation.

## Features

### 🔌 PyQuotexClient Wrapper
Encapsulates all core `pyquotex.stable_api` functionality:
- **Connection Management**: Async connect/disconnect with state tracking
- **Balance Queries**: Real-time account balance retrieval
- **Asset Information**: List and filter available trading assets
- **Trading**: Place trades with `buy()` and `buy_and_check_win()`
- **Candle Data**: Fetch historical candles and subscribe to real-time updates
- **Subscription Management**: Manage WebSocket subscriptions for live data

### 🔍 Connection Watchdog
Monitors and maintains connection health:
- **Health Checks**: Periodic ping to detect disconnects
- **Auto-Reconnect**: Exponential back-off reconnection strategy
- **Failure Logging**: Comprehensive logging of all connection issues
- **Statistics**: Track reconnection attempts and success rates
- **Callbacks**: Custom callbacks on successful reconnection

### ⚡ Async Request Queue
Non-blocking request processing:
- **Async-Safe**: Queue candle and trade requests without blocking UI
- **Worker Pool**: Multiple workers for parallel request processing
- **Callbacks**: Optional callbacks for request completion
- **Timeout Handling**: Configurable timeouts for all operations
- **Statistics**: Monitor queue size and processing metrics

### 🎯 Asset Auto-Selection
Intelligent asset selection:
- **Payout Queries**: Fetch and track asset payout percentages
- **Availability Filtering**: Filter by open/closed status
- **Best Candidates**: Rank assets by payout and availability
- **Auto-Update**: Periodic refresh of asset information
- **Callbacks**: Notifications on asset updates

### 📊 Session Context
Comprehensive session management:
- **Real Balances**: Track real account balances and stakes
- **Trade History**: Record all executed trades
- **Performance Metrics**: Win rate, ROI, profit/loss tracking
- **Auto-Update**: Periodic balance refresh
- **Statistics**: Comprehensive session analytics

### 🧪 Dry Run Mode
Safe testing environment:
- **Simulated Trading**: Test without real money
- **Mock Data**: Realistic simulated balance, assets, and candles
- **Full Functionality**: All features work in dry run mode
- **Reconnect Testing**: Simulate and test reconnection handling

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

### Basic Usage

```python
import asyncio
from pyquotex_integration import (
    PyQuotexClient,
    QuotexConfig,
    SessionContext,
    AssetSelector,
    AsyncRequestQueue,
    ConnectionWatchdog
)

async def main():
    # Configure (dry run mode for testing)
    config = QuotexConfig(
        email="your-email@example.com",
        password="your-password",
        dry_run=True  # Set to False for real trading
    )
    
    # Initialize client
    client = PyQuotexClient(config)
    await client.connect()
    
    # Get balance
    balance = await client.get_balance()
    print(f"Balance: ${balance['real']:.2f}")
    
    # Get assets
    assets = await client.get_assets()
    print(f"Available assets: {len(assets)}")
    
    # Place a trade (dry run)
    trade = await client.buy(
        asset="EURUSD",
        amount=1.0,
        direction="call",
        duration=60
    )
    print(f"Trade placed: {trade}")
    
    await client.disconnect()

asyncio.run(main())
```

### With Connection Watchdog

```python
async def main():
    config = QuotexConfig(
        dry_run=True,
        ping_interval=30.0,
        reconnect_max_retries=10
    )
    
    client = PyQuotexClient(config)
    await client.connect()
    
    # Start watchdog
    watchdog = ConnectionWatchdog(client, config)
    await watchdog.start()
    
    # Your trading logic here...
    await asyncio.sleep(300)
    
    # Cleanup
    await watchdog.stop()
    await client.disconnect()
```

### With Asset Auto-Selection

```python
async def main():
    config = QuotexConfig(dry_run=True, min_payout=85.0)
    
    client = PyQuotexClient(config)
    await client.connect()
    
    # Initialize asset selector
    selector = AssetSelector(client, config)
    await selector.start_auto_update(interval=60.0)
    await selector.update_assets()
    
    # Get best assets
    best_asset = selector.get_best_asset()
    print(f"Best asset: {best_asset.name} ({best_asset.payout}%)")
    
    top_5 = selector.get_top_assets(count=5)
    for asset in top_5:
        print(f"  {asset.name}: {asset.payout}%")
    
    await selector.stop_auto_update()
    await client.disconnect()
```

### With Async Request Queue

```python
async def candle_callback(response):
    if response.success:
        print(f"Received candles: {len(response.data)}")
    else:
        print(f"Error: {response.error}")

async def main():
    config = QuotexConfig(dry_run=True)
    
    client = PyQuotexClient(config)
    await client.connect()
    
    # Start request queue
    queue = AsyncRequestQueue(client, config)
    await queue.start()
    
    # Submit non-blocking requests
    await queue.get_candles(
        asset="EURUSD",
        period=60,
        count=100,
        callback=candle_callback
    )
    
    # Wait for processing
    await asyncio.sleep(5)
    
    await queue.stop()
    await client.disconnect()
```

### Complete Example with Session Context

```python
async def main():
    config = QuotexConfig(dry_run=True)
    
    client = PyQuotexClient(config)
    session = SessionContext(client, config)
    
    await client.connect()
    await session.initialize()
    
    print(f"Initial balance: ${session.current_balance:.2f}")
    
    # Record a trade
    trade = await session.record_trade(
        asset="EURUSD",
        amount=1.0,
        direction="call",
        duration=60,
        wait_for_result=True
    )
    
    if trade:
        print(f"Trade result: {'WIN' if trade.win else 'LOSS'}")
        print(f"Profit: ${trade.profit:.2f}")
    
    # Get statistics
    stats = session.get_stats_summary()
    print(f"Win rate: {stats['account']['win_rate']:.1f}%")
    print(f"Total profit: ${stats['account']['total_profit']:.2f}")
    
    await client.disconnect()
```

## Dry Run Demonstration

Run the complete demonstration showing all features:

```bash
python examples/dry_run.py
```

This demonstration shows:
1. Connection to Quotex API (simulated)
2. Balance and asset fetching
3. Connection watchdog with auto-reconnect
4. Async request queue processing
5. Asset auto-selection and ranking
6. Real-time candle streaming
7. Simulated reconnection handling
8. Comprehensive statistics

## Configuration

All settings can be configured via `QuotexConfig`:

```python
config = QuotexConfig(
    # Authentication
    email="your-email@example.com",
    password="your-password",
    
    # Watchdog settings
    ping_interval=30.0,              # Ping every 30 seconds
    ping_timeout=10.0,                # Timeout after 10 seconds
    reconnect_max_retries=10,         # Max 10 reconnection attempts
    reconnect_base_delay=1.0,         # Start with 1 second delay
    reconnect_max_delay=300.0,        # Max 5 minute delay
    reconnect_exponential_base=2.0,   # Exponential multiplier
    
    # Asset selection
    min_payout=80.0,                  # Minimum 80% payout
    preferred_assets=["EURUSD", "GBPUSD"],
    
    # Queue settings
    request_queue_maxsize=100,        # Max 100 queued requests
    callback_timeout=30.0,            # 30 second callback timeout
    
    # Session settings
    dry_run=True,                     # Enable dry run mode
    default_stake=1.0,                # Default $1 stake
    balance_update_interval=5.0,      # Update balance every 5s
    
    # Logging
    log_level="INFO"                  # INFO, DEBUG, WARNING, ERROR
)
```

## Environment Variables

Configuration can also be set via environment variables:

```bash
export QUOTEX_EMAIL="your-email@example.com"
export QUOTEX_PASSWORD="your-password"
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Terminal UI / Strategy               │
└───────────────────┬─────────────────────────────────┘
                    │
        ┌───────────┴──────────────┐
        │   AsyncRequestQueue      │  ← Non-blocking requests
        └───────────┬──────────────┘
                    │
        ┌───────────┴──────────────┐
        │    PyQuotexClient        │  ← API wrapper
        └───────────┬──────────────┘
                    │
        ┌───────────┴──────────────┐
        │  quotexapi.stable_api    │  ← PyQuotex library
        └──────────────────────────┘

    ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
    │ ConnectionWatchdog│ │ AssetSelector  │ │ SessionContext │
    └────────────────┘  └────────────────┘  └────────────────┘
         Monitors              Selects            Tracks
       Connection           Best Assets          Account
```

## Error Handling

All methods include comprehensive error handling and logging:

```python
try:
    balance = await client.get_balance()
    if balance is None:
        logger.error("Failed to get balance")
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
```

## Testing

The dry run mode provides a safe environment for testing:

```python
# Enable dry run mode
config = QuotexConfig(dry_run=True)

# All operations will be simulated
client = PyQuotexClient(config)
await client.connect()  # Simulated connection

# Simulated data
balance = await client.get_balance()  # Returns mock balance
assets = await client.get_assets()    # Returns mock assets
candles = await client.get_candles("EURUSD", 60, 100)  # Mock candles

# Simulated trades (no real money)
trade = await client.buy("EURUSD", 1.0, "call", 60)
```

## Production Deployment

For production use:

1. **Disable dry run mode**:
   ```python
   config = QuotexConfig(dry_run=False)
   ```

2. **Use environment variables for credentials**:
   ```bash
   export QUOTEX_EMAIL="your-email"
   export QUOTEX_PASSWORD="your-password"
   ```

3. **Enable watchdog**:
   ```python
   watchdog = ConnectionWatchdog(client, config)
   await watchdog.start()
   ```

4. **Monitor logs**:
   ```python
   logging.basicConfig(
       level=logging.INFO,
       filename="trading.log",
       format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
   )
   ```

5. **Use session context**:
   ```python
   session = SessionContext(client, config)
   await session.initialize()
   await session.start_auto_update()
   ```

## License

This project is provided as-is for integration with PyQuotex.

## Disclaimer

**This software is for educational purposes only. Trading involves risk. Use at your own discretion.**
