#!/usr/bin/env python3
"""
Test Binance API Connection
Run this to verify your API keys are working
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from binance_client.rest_client import BinanceRestClient

def test_api_connection():
    """Test API connection with current config"""
    
    print("=" * 60)
    print("Binance API Connection Test")
    print("=" * 60)
    
    print(f"\nConfiguration:")
    print(f"  Testnet Mode: {config.USE_TESTNET}")
    print(f"  Symbol: {config.SYMBOL}")
    
    if config.USE_TESTNET:
        print(f"  API Key: {config.TESTNET_API_KEY[:10]}...{config.TESTNET_API_KEY[-5:] if config.TESTNET_API_KEY else 'NOT SET'}")
        print(f"  API Secret: {'*' * 10 if config.TESTNET_API_SECRET else 'NOT SET'}")
    else:
        print(f"  API Key: {config.BINANCE_API_KEY[:10]}...{config.BINANCE_API_KEY[-5:] if config.BINANCE_API_KEY else 'NOT SET'}")
        print(f"  API Secret: {'*' * 10 if config.BINANCE_API_SECRET else 'NOT SET'}")
    
    print("\n" + "-" * 60)
    print("Testing connection...")
    print("-" * 60)
    
    try:
        # Initialize client
        client = BinanceRestClient()
        
        # Test connection
        print("✅ API client initialized")
        
        # Get price
        price = client.get_symbol_price()
        if price:
            print(f"✅ Current {config.SYMBOL} price: ${price:.2f}")
        else:
            print("❌ Could not fetch price")
        
        # Get balance
        balance = client.get_account_balance('USDT')
        if balance is not None:
            print(f"✅ USDT Balance: ${balance:.2f}")
        else:
            print("⚠️  Could not fetch balance (may not have USDT)")
        
        print("\n" + "=" * 60)
        print("✅ API connection successful!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\n" + "=" * 60)
        print("TROUBLESHOOTING:")
        print("=" * 60)
        print("\n1. Make sure you're using the correct API keys:")
        print(f"   - Testnet mode: {config.USE_TESTNET}")
        print("   - For testnet, get keys from: https://testnet.binance.vision/")
        print("   - For mainnet, get keys from: https://www.binance.com/en/support/faq/how-to-create-api-keys-on-binance-360002502072")
        print("\n2. Check API permissions:")
        print("   - Enable 'Enable Spot & Margin Trading'")
        print("   - Disable withdrawal permissions for security")
        print("\n3. Check IP whitelist:")
        print("   - If IP restriction is enabled, add your current IP")
        print(f"   - Your IP: {get_current_ip()}")
        print("\n4. Verify .env file exists and has correct format:")
        print("   - File location: .env")
        print("   - No spaces around = signs")
        print("   - No quotes around values")
        return False

def get_current_ip():
    """Get current IP address"""
    try:
        import requests
        response = requests.get('https://api.ipify.org', timeout=5)
        return response.text
    except:
        return "Could not detect"

if __name__ == "__main__":
    test_api_connection()