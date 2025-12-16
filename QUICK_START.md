# Quick Start Guide

## Installation

```bash
# Install from source
pip install -r requirements.txt

# Or install as package
pip install -e .
```

## 30-Second Demo

Run the dry run demonstration:

```bash
python examples/dry_run.py
```

This will:
- Connect to API (simulated)
- Fetch balance and assets
- Stream real-time candles
- Demonstrate reconnection
- Show comprehensive statistics

## 5-Minute Integration

```python
import asyncio
from pyquotex_integration import (
    PyQuotexClient,
    QuotexConfig,
    SessionContext,
    ConnectionWatchdog
)

async def main():
    # Configuration
    config = QuotexConfig(
        email="your-email@example.com",
        password="your-password",
        dry_run=False  # Set to True for testing
    )
    
    # Initialize
    client = PyQuotexClient(config)
    session = SessionContext(client, config)
    watchdog = ConnectionWatchdog(client, config)
    
    # Connect
    await client.connect()
    await session.initialize()
    await watchdog.start()
    
    print(f"Balance: ${session.current_balance:.2f}")
    
    # Place a trade
    trade = await session.record_trade(
        asset="EURUSD",
        amount=1.0,
        direction="call",
        duration=60,
        wait_for_result=True
    )
    
    if trade:
        print(f"Result: {'WIN' if trade.win else 'LOSS'}")
        print(f"Profit: ${trade.profit:.2f}")
    
    # Cleanup
    await watchdog.stop()
    await client.disconnect()

asyncio.run(main())
```

## Key Features at a Glance

### 1. Connection Management
```python
client = PyQuotexClient(config)
await client.connect()
```

### 2. Auto-Reconnect
```python
watchdog = ConnectionWatchdog(client, config)
await watchdog.start()
```

### 3. Asset Selection
```python
selector = AssetSelector(client, config)
await selector.update_assets()
best = selector.get_best_asset()
print(f"Best: {best.name} ({best.payout}%)")
```

### 4. Non-Blocking Requests
```python
queue = AsyncRequestQueue(client, config)
await queue.start()
await queue.get_candles("EURUSD", 60, 100, callback=my_callback)
```

### 5. Session Tracking
```python
session = SessionContext(client, config)
await session.initialize()
stats = session.get_stats_summary()
print(f"Win rate: {stats['account']['win_rate']:.1f}%")
```

## Configuration Options

### Via Code
```python
config = QuotexConfig(
    email="your@email.com",
    password="password",
    dry_run=True,
    ping_interval=30.0,
    min_payout=85.0
)
```

### Via Environment
```bash
export QUOTEX_EMAIL="your@email.com"
export QUOTEX_PASSWORD="password"
```

## Testing

### Run All Tests
```bash
python examples/test_features.py
```

### Dry Run (No Real Trading)
```python
config = QuotexConfig(dry_run=True)
```

## Common Patterns

### Pattern 1: Simple Trading Bot
```python
async def trading_bot():
    config = QuotexConfig(dry_run=True)
    client = PyQuotexClient(config)
    session = SessionContext(client, config)
    selector = AssetSelector(client, config)
    
    await client.connect()
    await session.initialize()
    await selector.update_assets()
    
    # Get best asset
    best = selector.get_best_asset(min_payout=85.0)
    
    # Place trade
    if best:
        trade = await session.record_trade(
            asset=best.name,
            amount=1.0,
            direction="call",
            duration=60
        )
```

### Pattern 2: Candle Streaming
```python
async def stream_candles():
    config = QuotexConfig(dry_run=True)
    client = PyQuotexClient(config)
    queue = AsyncRequestQueue(client, config)
    
    await client.connect()
    await queue.start()
    
    def on_candle(response):
        if response.success:
            print(f"New candles: {len(response.data)}")
    
    await queue.subscribe_candles(
        asset="EURUSD",
        period=60,
        callback=on_candle
    )
    
    await asyncio.sleep(60)  # Stream for 1 minute
```

### Pattern 3: Robust Connection
```python
async def robust_connection():
    config = QuotexConfig(
        dry_run=False,
        ping_interval=30.0,
        reconnect_max_retries=10
    )
    
    client = PyQuotexClient(config)
    
    def on_reconnect():
        print("Reconnected! Updating data...")
    
    watchdog = ConnectionWatchdog(
        client,
        config,
        on_reconnect=on_reconnect
    )
    
    await client.connect()
    await watchdog.start()
    
    # Your trading logic here...
    
    await watchdog.stop()
    await client.disconnect()
```

## Troubleshooting

### Connection Issues
- Enable dry run mode for testing: `dry_run=True`
- Check credentials in environment variables
- Increase ping timeout: `ping_timeout=15.0`

### Performance
- Adjust worker count in AsyncRequestQueue
- Tune update intervals for AssetSelector and SessionContext
- Monitor queue statistics: `queue.stats`

### Debugging
- Set log level to DEBUG: `log_level="DEBUG"`
- Check watchdog stats: `watchdog.stats`
- Review session summary: `session.get_stats_summary()`

## Next Steps

1. **Read the README.md** for comprehensive documentation
2. **Run dry_run.py** to see all features in action
3. **Study examples/** directory for more patterns
4. **Enable production mode** by setting `dry_run=False`
5. **Implement your strategy** using the provided modules

## Support

- Check logs for detailed error messages
- All components expose statistics via `.stats` or `.get_stats()`
- Use dry run mode extensively before going live
- Monitor connection health with watchdog

## Safety First

⚠️ **Always test with dry_run=True before real trading!**

✅ Use environment variables for credentials
✅ Enable connection watchdog for production
✅ Monitor session statistics
✅ Implement proper error handling
