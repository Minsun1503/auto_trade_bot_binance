import os
import sys
import time
import logging
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def run_smoke_test():
    load_dotenv()
    
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        logger.error("!!! BINANCE_API_KEY or BINANCE_API_SECRET not found in .env !!!")
        logger.info("Please create a .env file in the root directory with:")
        logger.info("BINANCE_API_KEY=your_testnet_api_key")
        logger.info("BINANCE_API_SECRET=your_testnet_api_secret")
        return False
        
    logger.info("Initializing Binance Testnet (Sandbox) Adapter...")
    
    import ccxt
    try:
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        exchange.set_sandbox_mode(True)
    except Exception as e:
        logger.error(f"Failed to create CCXT Binance instance: {e}")
        return False
        
    logger.info("Performing clock synchronization check (5 iterations)...")
    offsets = []
    for i in range(5):
        try:
            local_time_ms = int(time.time() * 1000)
            exchange_time_ms = exchange.fetch_time()
            offset = exchange_time_ms - local_time_ms
            offsets.append(offset)
            logger.info(f"  Run #{i+1}: Local={local_time_ms} ms | Exchange={exchange_time_ms} ms | Offset={offset} ms")
            time.sleep(1)
        except Exception as e:
            logger.error(f"  Run #{i+1} failed: {e}")
            
    if len(offsets) == 0:
        logger.error("Failed to sync clock in all attempts.")
        return False
        
    avg_offset = sum(offsets) / len(offsets)
    max_offset = max(offsets)
    min_offset = min(offsets)
    
    logger.info(f"Clock Sync Stats: Min={min_offset:.1f}ms | Max={max_offset:.1f}ms | Avg={avg_offset:.1f}ms")
    
    if abs(max_offset) > 5000:
        logger.error(f"!!! CRITICAL WARNING: Max offset {max_offset:.1f} ms exceeds 5000 ms limit !!!")
        logger.error("Please sync your system clock to prevent recvWindow authentication failures on Binance REST API.")
    else:
        logger.info("Clock sync check passed (offset within acceptable 5000ms bounds).")
        
    logger.info("Fetching balances...")
    try:
        bal = exchange.fetch_balance()
        logger.info("Active Balances on Testnet:")
        for asset, asset_bal in bal.items():
            if isinstance(asset_bal, dict) and ('free' in asset_bal or 'used' in asset_bal):
                free = float(asset_bal.get('free', 0.0))
                used = float(asset_bal.get('used', 0.0))
                if free > 0 or used > 0:
                    logger.info(f"  {asset}: free={free:.8f} | used={used:.8f} | total={free+used:.8f}")
    except Exception as e:
        logger.error(f"Failed to fetch balances: {e}")
        
    logger.info("Fetching open orders...")
    try:
        orders = exchange.fetch_open_orders("BTC/USDT")
        logger.info(f"Open Orders (BTC/USDT): {len(orders)}")
        for o in orders:
            logger.info(f"  Order ID: {o['id']} | {o['side'].upper()} | Amount: {o['amount']} | Price: {o['price']} | Status: {o['status']}")
    except Exception as e:
        logger.error(f"Failed to fetch open orders: {e}")
        
    logger.info("Fetching recent trades...")
    try:
        trades = exchange.fetch_my_trades("BTC/USDT")
        logger.info(f"Recent Trades (BTC/USDT): {len(trades)}")
        for t in trades[:10]: # Print top 10 recent trades
            logger.info(f"  Trade ID: {t['id']} | Order ID: {t['order']} | {t['side'].upper()} | Amount: {t['amount']} | Price: {t['price']}")
    except Exception as e:
        logger.error(f"Failed to fetch recent trades: {e}")
        
    logger.info("Smoke test completed.")
    return True

if __name__ == "__main__":
    run_smoke_test()
