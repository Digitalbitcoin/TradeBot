#!/usr/bin/env python3
"""
Check bot status and strategy state for SPOT trading
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from binance_client.rest_client import BinanceRestClient
from trading.strategy import SpikeDumpStrategy


def check_status():
    """Check spot bot status"""
    
    print("=" * 60)
    print("SPOT BOT STATUS CHECK")
    print("=" * 60)
    
    # Try different possible attribute names
    symbol = getattr(config, 'SYMBOL', getattr(config, 'TRADING_SYMBOL', 'BTCUSDT'))
    total_capital = getattr(config, 'TOTAL_CAPITAL', getattr(config, 'TOTAL_CAPITAL_USD', 1300))
    base_position = getattr(config, 'BASE_POSITION', 100)
    use_testnet = getattr(config, 'USE_TESTNET', True)
    
    print(f"\nMode: {'TESTNET' if use_testnet else 'MAINNET'}")
    print(f"Symbol: {symbol}")
    print(f"Total Capital: ${total_capital}")
    print(f"Base Position: ${base_position}")
    print(f"Dump Thresholds: {config.DUMP_THRESHOLDS}%")
    print(f"Spike Thresholds: {config.SPIKE_THRESHOLDS}%")
    
    try:
        # Initialize client
        print("\n1. Initializing Binance client...")
        client = BinanceRestClient()
        print("   ✅ Client initialized")
        
        # Get current price
        current_price = client.get_symbol_price(symbol)
        if current_price:
            print(f"   ✅ Current Price: ${current_price:.2f}")
        else:
            print("   ❌ Could not fetch price")
            return
        
        # Get account balance
        print("\n2. Account Balance:")
        balance = client.get_account_balance('USDT')
        if balance is not None:
            print(f"   USDT Balance: ${balance:.2f}")
        else:
            print("   ⚠️ Could not fetch balance (IP may not be whitelisted)")
        
        # Initialize strategy
        print("\n3. Initializing Strategy...")
        strategy = SpikeDumpStrategy(client)
        
        # Get strategy status
        status = strategy.get_status()
        
        print(f"\n4. Strategy Status:")
        print(f"   Reference Price: ${status.get('reference_price', 0):.2f}")
        print(f"   Position Active: {status.get('position_active', False)}")
        print(f"   Tokens Held: {status.get('tokens', 0):.8f}")
        print(f"   Avg Cost: ${status.get('avg_cost', 0):.2f}")
        print(f"   Total Invested: ${status.get('total_invested', 0):.2f}")
        print(f"   Unrealized P&L: ${status.get('unrealized_pnl', 0):.2f}")
        print(f"   Buy Levels Executed: {status.get('buy_levels_executed', [])}")
        print(f"   Sell Levels Executed: {status.get('sell_levels_executed', [])}")
        
        # Calculate required drops for buy signals
        reference_price = status.get('reference_price', 0)
        if reference_price > 0:
            print(f"\n5. Required Drops for Buy Signals:")
            for i, threshold in enumerate(config.DUMP_THRESHOLDS):
                level = i + 1
                target_price = reference_price * (1 - threshold / 100)
                drop_needed = threshold
                current_drop = (reference_price - current_price) / reference_price * 100
                
                if level not in status.get('buy_levels_executed', []):
                    if current_drop >= threshold:
                        status_emoji = "✅ READY"
                    else:
                        status_emoji = "❌ Need more drop"
                    
                    print(f"   Level {level}: Need ${target_price:.2f} ({drop_needed}% drop)")
                    print(f"            Current drop: {current_drop:.2f}% - {status_emoji}")
        
        # Calculate required spikes for sell signals
        if status.get('position_active') and status.get('avg_cost', 0) > 0:
            avg_cost = status.get('avg_cost', 0)
            print(f"\n6. Required Spikes for Sell Signals:")
            for i, threshold in enumerate(config.SPIKE_THRESHOLDS):
                level = i + 1
                target_price = avg_cost * (1 + threshold / 100)
                spike_needed = threshold
                current_spike = (current_price - avg_cost) / avg_cost * 100
                
                if level not in status.get('sell_levels_executed', []):
                    if current_spike >= threshold:
                        status_emoji = "✅ READY"
                    else:
                        status_emoji = "❌ Need more spike"
                    
                    print(f"   Level {level}: Need ${target_price:.2f} ({spike_needed}% spike)")
                    print(f"            Current spike: {current_spike:.2f}% - {status_emoji}")
        else:
            print(f"\n6. Sell Signals: No active position")
        
        # Check if we're in a position
        if status.get('position_active'):
            print(f"\n7. Current Position Details:")
            print(f"   Tokens: {status['tokens']:.8f}")
            print(f"   Avg Cost: ${status['avg_cost']:.2f}")
            print(f"   Current Price: ${current_price:.2f}")
            print(f"   Unrealized P&L: ${status['unrealized_pnl']:.2f}")
            
            # Calculate profit target
            if status['avg_cost'] > 0:
                profit_pct = (current_price - status['avg_cost']) / status['avg_cost'] * 100
                print(f"   Profit %: {profit_pct:.2f}%")
                
                # Next sell threshold
                next_level = len(status.get('sell_levels_executed', [])) + 1
                if next_level <= len(config.SPIKE_THRESHOLDS):
                    next_threshold = config.SPIKE_THRESHOLDS[next_level - 1]
                    next_target = status['avg_cost'] * (1 + next_threshold / 100)
                    need_more = next_target - current_price
                    print(f"   Next Sell Level {next_level}: ${next_target:.2f} ({next_threshold}%)")
                    print(f"   Need: +${need_more:.2f} ({need_more/status['avg_cost']*100:.2f}%)")
        
        # Check trading permissions
        print(f"\n8. Trading Permissions:")
        try:
            # Try to get exchange info
            exchange_info = client.client.get_symbol_info(symbol)
            if exchange_info:
                print(f"   ✅ Trading enabled for {symbol}")
                
                # Get filters
                filters = {f['filterType']: f for f in exchange_info.get('filters', [])}
                if 'LOT_SIZE' in filters:
                    step_size = float(filters['LOT_SIZE'].get('stepSize', 0.00001))
                    min_qty = float(filters['LOT_SIZE'].get('minQty', 0))
                    print(f"   Min Quantity: {min_qty}")
                    print(f"   Step Size: {step_size}")
            else:
                print(f"   ⚠️ Could not get exchange info")
        except Exception as e:
            print(f"   ⚠️ Could not check permissions: {e}")
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        
        if reference_price > 0 and current_price:
            if current_price < reference_price:
                print(f"📉 Market is DOWN {((reference_price - current_price)/reference_price*100):.2f}% from reference")
                print("   Watching for buy signals...")
            else:
                print(f"📈 Market is UP {((current_price - reference_price)/reference_price*100):.2f}% from reference")
                print("   Watching for sell signals...")
        
        if status.get('position_active'):
            print("\n💼 You have an ACTIVE POSITION")
            if status['unrealized_pnl'] > 0:
                print(f"   📈 Unrealized Profit: ${status['unrealized_pnl']:.2f}")
            else:
                print(f"   📉 Unrealized Loss: ${status['unrealized_pnl']:.2f}")
        else:
            print("\n💼 NO ACTIVE POSITION")
            print("   Bot is waiting for price drops to buy")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error checking status: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_status()