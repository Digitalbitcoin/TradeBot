#!/usr/bin/env python3
"""
Verify all modules are properly configured
Run this to test imports before starting the bot
"""

import sys
import os

def test_imports():
    """Test all module imports"""
    print("=" * 50)
    print("Testing Module Imports")
    print("=" * 50)
    
    results = []
    
    # Test 1: Check Python version
    print(f"\n1. Python Version: {sys.version}")
    results.append(True)
    
    # Test 2: Check if required packages are installed
    print("\n2. Checking Required Packages...")
    packages = {
        'binance': 'python-binance',
        'websocket': 'websocket-client',
        'dotenv': 'python-dotenv',
        'colorama': 'colorama',
        'requests': 'requests'
    }
    
    for package, install_name in packages.items():
        try:
            __import__(package)
            print(f"   ✅ {install_name} installed")
            results.append(True)
        except ImportError:
            print(f"   ❌ {install_name} NOT installed")
            print(f"      Run: pip install {install_name}")
            results.append(False)
    
    # Test 3: Test pandas (optional)
    print("\n3. Optional Packages...")
    try:
        import pandas
        print("   ✅ pandas installed (optional)")
        results.append(True)
    except ImportError:
        print("   ⚠️ pandas NOT installed (using CSV fallback)")
        results.append(True)  # Not critical
    
    # Test 4: Test local modules
    print("\n4. Testing Local Modules...")
    
    # Add project root to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    modules_to_test = [
        ('config', 'config module'),
        ('binance_client', 'binance_client package'),
        ('trading', 'trading package'),
        ('utils', 'utils package'),
        ('data', 'data package'),
        ('logs', 'logs package')
    ]
    
    for module, name in modules_to_test:
        try:
            __import__(module)
            print(f"   ✅ {name} loaded")
            results.append(True)
        except ImportError as e:
            print(f"   ❌ {name} failed: {e}")
            results.append(False)
    
    # Test 5: Test main imports
    print("\n5. Testing Main Imports...")
    
    try:
        from config import config
        print("   ✅ Config imported")
        results.append(True)
    except Exception as e:
        print(f"   ❌ Config import failed: {e}")
        results.append(False)
    
    try:
        from binance_client import BinanceRestClient
        print("   ✅ BinanceRestClient imported")
        results.append(True)
    except Exception as e:
        print(f"   ❌ BinanceRestClient import failed: {e}")
        results.append(False)
    
    try:
        from trading import SpikeDumpStrategy
        print("   ✅ SpikeDumpStrategy imported")
        results.append(True)
    except Exception as e:
        print(f"   ❌ SpikeDumpStrategy import failed: {e}")
        results.append(False)
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ ALL TESTS PASSED! ({passed}/{total})")
        print("\nYour bot is ready to run!")
        return True
    else:
        print(f"❌ {total - passed} TESTS FAILED")
        print("\nPlease fix the issues above before running the bot.")
        return False

if __name__ == "__main__":
    success = test_imports()
    
    if not success:
        print("\nQuick Fix Commands:")
        print("  pip install python-binance websocket-client python-dotenv colorama requests")
        print("  pip install pandas  # optional")
        print("\nIf still having issues, check:")
        print("  1. Virtual environment is activated")
        print("  2. All __init__.py files are in place")
        print("  3. No syntax errors in your code")
    
    sys.exit(0 if success else 1)