# User-specific config for abbyyy
# This file is auto-generated - DO NOT EDIT

import os
from pathlib import Path

class Config:
    """User-specific configuration"""
    
    # User's API Keys - Clean and validated
    BINANCE_API_KEY = r"6qOniqeXEszJb2qoFNMweS2ZCfhqXZORAcNtI2HBcerxQ7Tc8OTP0z6BiD1J0tia"
    BINANCE_API_SECRET = r"wkvfoHR1PRBqZiie60D5H2VVr5xda7SvejhMXfdC6I4BR221q6stGGQmF0q1bYMZ"
    
    # Testnet setting
    USE_TESTNET = True
    
    # API URLs (set based on testnet)
    API_URL = "https://testnet.binance.vision/api"
    WAPI_URL = "https://testnet.binance.vision/wapi"
    
    # Trading parameters
    TOTAL_CAPITAL = 1000
    BASE_POSITION = 100
    SYMBOL = "BTCUSDT"
    
    # Available coins
    AVAILABLE_COINS = "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,ADAUSDT,DOGEUSDT,DOTUSDT,LINKUSDT"
    
    # Thresholds
    DUMP_THRESHOLDS = [0]
    SPIKE_THRESHOLDS = [0]
    SELL_PERCENTAGES = [25.0, 25.0, 25.0, 25.0]
    
    # Logging
    LOG_LEVEL = "INFO"
    LOG_FILE = "logs/trading_bot_abbyyy.log"
    
    # Referral settings
    ENABLE_REFERRAL = True
    REFERRAL_BONUS = 10.0
    REFERRAL_COMMISSION = 5.0
    
    @property
    def ws_url(self):
        return "wss://testnet.binance.vision/ws"
    
    @property
    def combined_ws_url(self):
        return "wss://testnet.binance.vision/stream"
    
    def get_coin_list(self):
        return [c.strip() for c in self.AVAILABLE_COINS.split(',') if c.strip()]

# Create config instance
config = Config()
