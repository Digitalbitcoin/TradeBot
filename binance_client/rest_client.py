from binance.client import Client
from binance.exceptions import BinanceAPIException
from config import config
from utils.logger import get_logger

logger = get_logger(__name__)

class BinanceRestClient:
    def __init__(self):
        """Initialize Binance REST client"""
        # Get API keys based on mode
        if config.USE_TESTNET:
            api_key = config.TESTNET_API_KEY or config.BINANCE_API_KEY
            api_secret = config.TESTNET_API_SECRET or config.BINANCE_API_SECRET
            self.base_url = "https://testnet.binance.vision"
        else:
            api_key = config.BINANCE_API_KEY
            api_secret = config.BINANCE_API_SECRET
            self.base_url = "https://api.binance.com"
        
        # Validate keys
        if not api_key or not api_secret:
            logger.error("API keys are missing! Please check your .env file")
            logger.error(f"Testnet mode: {config.USE_TESTNET}")
            logger.error(f"API Key present: {bool(api_key)}")
            logger.error(f"API Secret present: {bool(api_secret)}")
            raise ValueError("Missing API credentials")
        
        try:
            # Initialize client
            self.client = Client(api_key, api_secret)
            
            # Set testnet URL if using testnet
            if config.USE_TESTNET:
                self.client.API_URL = 'https://testnet.binance.vision/api'
                self.client.WAPI_URL = 'https://testnet.binance.vision/wapi'
                
            logger.info(f"Binance client initialized. Testnet mode: {config.USE_TESTNET}")
            
            # Test connection
            self.test_connection()
            
        except Exception as e:
            logger.error(f"Failed to initialize Binance client: {e}")
            raise
    
    def test_connection(self):
        """Test API connection"""
        try:
            # Simple ping to test connection
            self.client.ping()
            logger.info("API connection successful")
            
            # Try to get account info (this will fail if keys are invalid)
            account = self.client.get_account()
            logger.info("Account verified successfully")
            return True
            
        except BinanceAPIException as e:
            logger.error(f"API Error: {e}")
            logger.error(f"Error code: {e.code}")
            logger.error(f"Error message: {e.message}")
            
            if e.code == -2015:
                logger.error("=" * 60)
                logger.error("INVALID API KEY ERROR")
                logger.error("=" * 60)
                logger.error("Possible causes:")
                logger.error("1. API key is from mainnet but using testnet (or vice versa)")
                logger.error("2. API key is expired or revoked")
                logger.error("3. IP address not whitelisted")
                logger.error("4. API key doesn't have spot trading permissions")
                logger.error("")
                logger.error("To fix:")
                logger.error("1. For testnet: Get keys from https://testnet.binance.vision/")
                logger.error("2. For mainnet: Ensure 'Enable Spot Trading' is checked")
                logger.error("3. Add your IP to whitelist if enabled")
                logger.error("4. Regenerate API keys if needed")
            
            raise
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            raise
    
    def get_account_balance(self, asset='USDT'):
        """Get balance for specific asset"""
        try:
            account = self.client.get_account()
            for balance in account['balances']:
                if balance['asset'] == asset:
                    free_balance = float(balance['free'])
                    logger.info(f"{asset} balance: {free_balance}")
                    return free_balance
            return 0
        except BinanceAPIException as e:
            logger.error(f"Error fetching balance: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None
    
    def get_symbol_price(self, symbol=None):
        """Get current price for symbol"""
        symbol = symbol or config.SYMBOL
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            price = float(ticker['price'])
            logger.debug(f"Current {symbol} price: {price}")
            return price
        except BinanceAPIException as e:
            logger.error(f"Error fetching price: {e}")
            return None
    
    def place_limit_order(self, symbol, side, quantity, price):
        """Place limit order"""
        try:
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                type='LIMIT',
                timeInForce='GTC',
                quantity=quantity,
                price=str(price)
            )
            logger.info(f"Order placed: {side} {quantity} {symbol} @ {price}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Order failed: {e}")
            return None
    
    def place_market_order(self, symbol, side, quantity):
        """Place market order"""
        try:
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=quantity
            )
            logger.info(f"Market order executed: {side} {quantity} {symbol}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Market order failed: {e}")
            return None