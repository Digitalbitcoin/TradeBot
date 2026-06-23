"""
Price Poller - REST API-based price feed
Reliable alternative when WebSocket is unavailable
"""

import time
import threading
from typing import Callable, Optional
from binance_client.rest_client import BinanceRestClient
from utils.logger import get_logger

logger = get_logger(__name__)

class PricePoller:
    """
    Polls price using REST API at regular intervals
    Provides price updates similar to WebSocket
    """
    
    def __init__(self, callback: Callable, symbol: str = None, interval: float = 1.0):
        """
        Initialize price poller
        
        Args:
            callback: Function to call with price data
            symbol: Trading symbol (default from config)
            interval: Polling interval in seconds
        """
        self.callback = callback
        self.interval = interval
        self.running = False
        self.thread = None
        self.client = BinanceRestClient()
        self.last_price = None
        self.symbol = symbol
        self.price_updates = 0
        
        # Get symbol from config if not provided
        if not self.symbol:
            from config import config
            self.symbol = config.SYMBOL
        
        logger.info(f"Price poller initialized for {self.symbol} (interval: {interval}s)")
    
    def start(self):
        """Start polling for prices"""
        if self.running:
            logger.warning("Price poller already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        logger.info(f"✅ Price poller started for {self.symbol}")
    
    def stop(self):
        """Stop polling"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Price poller stopped")
    
    def _poll_loop(self):
        """Main polling loop"""
        consecutive_errors = 0
        
        while self.running:
            try:
                # Get current price
                price = self.client.get_symbol_price(self.symbol)
                
                if price is not None:
                    consecutive_errors = 0
                    
                    # Only send update if price changed (optional)
                    # if price != self.last_price:
                    self.price_updates += 1
                    
                    # Create price data in same format as WebSocket
                    price_data = {
                        'price': price,
                        'quantity': 0,
                        'time': int(time.time() * 1000),
                        'symbol': self.symbol,
                        'source': 'REST_POLLER'
                    }
                    
                    # Send to callback
                    try:
                        self.callback(price_data)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                    
                    self.last_price = price
                    
                    # Log every 100 updates
                    if self.price_updates % 100 == 0:
                        logger.debug(f"Price updates: {self.price_updates}, Current: ${price:.8f}")
                
                else:
                    consecutive_errors += 1
                    if consecutive_errors <= 3:
                        logger.warning(f"Failed to get price (attempt {consecutive_errors})")
                    elif consecutive_errors == 4:
                        logger.error("Multiple price fetch failures - check API connection")
                
                # Wait for next poll
                time.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"Price poller error: {e}")
                time.sleep(self.interval * 2)  # Wait longer on error
    
    def get_current_price(self) -> Optional[float]:
        """Get current price immediately"""
        return self.client.get_symbol_price(self.symbol)
    
    def get_stats(self) -> dict:
        """Get poller statistics"""
        return {
            'price_updates': self.price_updates,
            'last_price': self.last_price,
            'running': self.running,
            'interval': self.interval,
            'symbol': self.symbol
        }