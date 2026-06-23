# config.py - Updated with coin list
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

class Config:
    """Configuration class for trading bot"""
    
    # Binance API
    BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
    BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
    
    # Trading parameters
    TOTAL_CAPITAL = float(os.getenv('TOTAL_CAPITAL', 1300))
    BASE_POSITION = float(os.getenv('BASE_POSITION', 100))
    SYMBOL = os.getenv('TRADING_SYMBOL', 'BTCUSDT')
    
    # Available coins for trading
    AVAILABLE_COINS = os.getenv('AVAILABLE_COINS', 'BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,ADAUSDT,DOGEUSDT,DOTUSDT,LINKUSDT')
    
    # Thresholds
    DUMP_THRESHOLDS = [float(x) for x in os.getenv('DUMP_THRESHOLDS', '2,4,6,8').split(',')]
    SPIKE_THRESHOLDS = [float(x) for x in os.getenv('SPIKE_THRESHOLDS', '2,4,6,8').split(',')]
    SELL_PERCENTAGES = [float(x) for x in os.getenv('SELL_PERCENTAGES', '25,25,25,25').split(',')]
    
    # Testnet
    USE_TESTNET = os.getenv('USE_TESTNET', 'true').lower() == 'true'
    TESTNET_API_KEY = os.getenv('TESTNET_API_KEY')
    TESTNET_API_SECRET = os.getenv('TESTNET_API_SECRET')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/trading_bot.log')
    
    # Registration & Referral Settings
    ENABLE_REFERRAL = os.getenv('ENABLE_REFERRAL', 'true').lower() == 'true'
    REFERRAL_BONUS = float(os.getenv('REFERRAL_BONUS', 10.0))
    REFERRAL_COMMISSION = float(os.getenv('REFERRAL_COMMISSION', 5.0))
    ENABLE_REGISTRATION = os.getenv('ENABLE_REGISTRATION', 'true').lower() == 'true'
    MIN_REFERRAL_BALANCE = float(os.getenv('MIN_REFERRAL_BALANCE', 100.0))
    
    @property
    def ws_url(self):
        """Get correct WebSocket URL based on testnet setting"""
        if self.USE_TESTNET:
            return "wss://testnet.binance.vision/ws"
        else:
            return "wss://stream.binance.com:9443/ws"
    
    @property
    def combined_ws_url(self):
        """Get combined stream WebSocket URL"""
        if self.USE_TESTNET:
            return "wss://testnet.binance.vision/stream"
        else:
            return "wss://stream.binance.com:9443/stream"
    
    def get_coin_list(self):
        """Get list of available coins"""
        return [c.strip() for c in self.AVAILABLE_COINS.split(',') if c.strip()]
    
    def validate(self):
        """Validate configuration"""
        if not self.BINANCE_API_KEY:
            print("⚠️  BINANCE_API_KEY not found in .env file")
            return False
        
        if not self.BINANCE_API_SECRET:
            print("⚠️  BINANCE_API_SECRET not found in .env file")
            return False
        
        if self.USE_TESTNET:
            print("⚠️  Running in TESTNET mode")
            print(f"   WebSocket URL: {self.ws_url}")
        else:
            print("🔴 Running in MAINNET mode - Real money!")
        
        return True

# Create global config instance
config = Config()