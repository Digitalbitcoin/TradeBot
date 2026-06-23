#!/usr/bin/env python3
"""
Binance Trading Bot - Spike/Dump Strategy
Using REST API Polling (Reliable for Testnet)
"""

import os
import time
import signal
import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from colorama import init, Fore, Style

from config import config
from binance_client.rest_client import BinanceRestClient
from binance_client.price_poller import PricePoller
from trading.strategy import SpikeDumpStrategy
from trading.risk_manager import RiskManager
from utils.logger import setup_logging, get_logger

# Initialize colorama for colored console output
init(autoreset=True)

# Setup logging
setup_logging(config.LOG_LEVEL, config.LOG_FILE)
logger = get_logger(__name__)


class TradingBot:
    """Main trading bot controller"""
    
    def __init__(self):
        self.running = False
        self.rest_client = None
        self.price_poller = None
        self.strategy = None
        self.risk_manager = None
        
        # Statistics
        self.start_time = None
        self.price_updates = 0
        self.signals_triggered = 0
        
        # Exchange info for precision
        self.exchange_info = None
        self.step_size = 0.00001  # Default values
        self.min_qty = 0.00001
        self.tick_size = 0.01
        self.min_notional = 10.0  # Default value
        
        # PID file path
        self.pid_file = Path('bot.pid')
        
    def format_quantity(self, quantity):
        """
        Format quantity according to Binance step size
        Prevents precision errors when placing orders
        """
        if quantity is None or quantity <= 0:
            return 0
        
        if not self.step_size:
            return quantity
        
        try:
            # Convert to Decimal for precise rounding
            step = Decimal(str(self.step_size))
            quant = Decimal(str(quantity))
            
            # Round down to step size
            rounded = (quant // step) * step
            
            # Convert back to float with correct precision
            precision = len(str(self.step_size).rstrip('0').split('.')[-1]) if '.' in str(self.step_size) else 0
            result = float(rounded) if precision == 0 else round(float(rounded), precision)
            
            # Ensure minimum quantity
            if self.min_qty and result < self.min_qty:
                result = self.min_qty
            
            return result
            
        except Exception as e:
            logger.error(f"Error formatting quantity: {e}")
            return quantity
    
    def format_price(self, price):
        """
        Format price according to Binance tick size
        """
        if not price or price <= 0:
            return price
        
        if not self.tick_size:
            return price
        
        try:
            tick = Decimal(str(self.tick_size))
            price_dec = Decimal(str(price))
            
            # Round to tick size
            rounded = (price_dec // tick) * tick
            
            precision = len(str(self.tick_size).rstrip('0').split('.')[-1]) if '.' in str(self.tick_size) else 0
            return float(rounded) if precision == 0 else round(float(rounded), precision)
            
        except Exception as e:
            logger.error(f"Error formatting price: {e}")
            return price
    
    def get_exchange_info(self):
        """Get exchange info for precision handling"""
        try:
            exchange_info = self.rest_client.client.get_symbol_info(config.SYMBOL)
            
            if exchange_info:
                # Get filters
                filters = {f['filterType']: f for f in exchange_info.get('filters', [])}
                
                # Lot size filter (for quantity)
                if 'LOT_SIZE' in filters:
                    self.step_size = float(filters['LOT_SIZE'].get('stepSize', 0.00001))
                    self.min_qty = float(filters['LOT_SIZE'].get('minQty', 0.00001))
                    logger.info(f"Step size: {self.step_size}, Min quantity: {self.min_qty}")
                
                # Price filter
                if 'PRICE_FILTER' in filters:
                    self.tick_size = float(filters['PRICE_FILTER'].get('tickSize', 0.01))
                    logger.info(f"Tick size: {self.tick_size}")
                
                # Min notional filter
                if 'MIN_NOTIONAL' in filters:
                    self.min_notional = float(filters['MIN_NOTIONAL'].get('minNotional', 10.0))
                    logger.info(f"Min order value: ${self.min_notional}")
                
                return True
                
        except Exception as e:
            logger.warning(f"Could not get exchange info: {e}")
        
        # Set defaults (already set in __init__)
        logger.info(f"Using default precision: Step={self.step_size}, MinQty={self.min_qty}, MinNotional={self.min_notional}")
        
        return False
    
    def _save_pid(self):
        """Save current process ID to file"""
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
            logger.info(f"✅ PID saved to {self.pid_file}: {os.getpid()}")
            return True
        except Exception as e:
            logger.warning(f"Could not save PID file: {e}")
            return False
    
    def _remove_pid(self):
        """Remove PID file"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
                logger.info(f"✅ PID file removed: {self.pid_file}")
            return True
        except Exception as e:
            logger.warning(f"Could not remove PID file: {e}")
            return False
    
    def _check_pid(self):
        """Check if another instance is running"""
        if self.pid_file.exists():
            try:
                with open(self.pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                # Check if process is running
                if os.name == 'nt':  # Windows
                    try:
                        import psutil
                        if psutil.pid_exists(pid):
                            logger.warning(f"Another instance is running with PID {pid}")
                            return True
                    except:
                        # Fallback for Windows without psutil
                        result = os.system(f'tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul')
                        if result == 0:
                            logger.warning(f"Another instance may be running with PID {pid}")
                            return True
                else:  # Linux/Mac
                    try:
                        os.kill(pid, 0)
                        logger.warning(f"Another instance is running with PID {pid}")
                        return True
                    except OSError:
                        pass  # Process not running
            except (ValueError, FileNotFoundError, PermissionError):
                pass
        
        return False
    
    def initialize(self):
        """Initialize bot components"""
        logger.info("=" * 60)
        logger.info(f"🚀 Starting Binance Trading Bot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"📊 Symbol: {config.SYMBOL}")
        logger.info(f"💰 Total Capital: ${config.TOTAL_CAPITAL}")
        logger.info(f"🎯 Base Position: ${config.BASE_POSITION}")
        logger.info(f"🧪 Testnet Mode: {config.USE_TESTNET}")
        logger.info("=" * 60)
        
        # Check if another instance is running
        if self._check_pid():
            logger.error("❌ Another instance is already running. Exiting.")
            return False
        
        try:
            # Initialize REST client
            self.rest_client = BinanceRestClient()
            
            # Get exchange info for precision
            self.get_exchange_info()
            
            # Test connection by getting price
            test_price = self.rest_client.get_symbol_price()
            if test_price:
                logger.info(f"✅ Connected to Binance. Current price: ${test_price:.4f}")
            else:
                logger.warning("⚠️  Could not fetch initial price, but continuing...")
            
            # Check account balance (optional - may fail if IP not whitelisted)
            try:
                balance = self.rest_client.get_account_balance('USDT')
                if balance is not None:
                    logger.info(f"💰 Account USDT Balance: ${balance:.4f}")
                    
                    if balance < config.TOTAL_CAPITAL:
                        logger.warning(f"⚠️ Balance (${balance:.4f}) is less than configured capital (${config.TOTAL_CAPITAL})")
                else:
                    logger.warning("⚠️ Could not fetch balance (IP may not be whitelisted)")
                    logger.warning("   Trading will still work, but balance checks disabled")
            except Exception as e:
                logger.warning(f"Balance check failed: {e}")
                logger.warning("   Continuing without balance checks")
            
            # Initialize strategy with precision formatters
            self.strategy = SpikeDumpStrategy(self.rest_client)
            
            # Add precision formatters to strategy
            self.strategy.format_quantity = self.format_quantity
            self.strategy.format_price = self.format_price
            self.strategy.step_size = self.step_size
            self.strategy.tick_size = self.tick_size
            self.strategy.min_qty = self.min_qty
            self.strategy.min_notional = self.min_notional
            
            # Initialize risk manager
            self.risk_manager = RiskManager(self.rest_client)
            
            # Initialize price poller (REST-based, no WebSocket)
            self.price_poller = PricePoller(
                callback=self.on_price_update,
                symbol=config.SYMBOL,
                interval=1.0  # Update every second
            )
            
            logger.info("✅ Bot initialized successfully")
            logger.info(f"📡 Using REST API polling for price data (interval: 1s)")
            logger.info(f"🔧 Precision: Step={self.step_size}, Tick={self.tick_size}, MinQty={self.min_qty}, MinNotional=${self.min_notional}")
            
            # Save PID after successful initialization
            self._save_pid()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def on_price_update(self, price_data):
        """Handle real-time price updates from price poller"""
        self.price_updates += 1
        price = price_data['price']
        
        # Update strategy with new price
        signals = self.strategy.update_price(price)
        
        # Process any trading signals
        for signal_type, level in signals:
            self.signals_triggered += 1
            
            if signal_type == 'BUY':
                logger.info(f"{Fore.GREEN}🔔 BUY SIGNAL DETECTED - Level {level} @ ${price:.4f}{Style.RESET_ALL}")
                
                # Check risk limits before buying
                if self.risk_manager.can_buy(self.strategy.position):
                    try:
                        # Calculate amount based on level
                        amount = self.strategy.calculate_buy_amount(level)
                        
                        # Calculate quantity
                        quantity = amount / price
                        
                        # Format quantity with proper precision
                        formatted_quantity = self.format_quantity(quantity)
                        
                        # Check minimum order value (with None check)
                        order_value = formatted_quantity * price
                        min_notional_value = self.min_notional if self.min_notional is not None else 10.0
                        
                        if order_value < min_notional_value:
                            logger.warning(f"Order value ${order_value:.4f} is below minimum ${min_notional_value:.4f}")
                            continue
                        
                        # Check if quantity is valid
                        if formatted_quantity <= 0:
                            logger.warning(f"Calculated quantity is zero for level {level}")
                            continue
                        
                        # Execute buy with formatted quantity
                        logger.info(f"💰 Attempting BUY: {formatted_quantity:.8f} {config.SYMBOL} @ ${price:.4f}")
                        self.strategy.execute_buy(level, price, formatted_quantity)
                        
                    except Exception as e:
                        logger.error(f"Error executing buy: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    logger.warning("Buy blocked by risk manager")
            
            elif signal_type == 'SELL':
                logger.info(f"{Fore.YELLOW}🔔 SELL SIGNAL DETECTED - Level {level} @ ${price:.4f}{Style.RESET_ALL}")
                
                # Check risk limits before selling
                if self.risk_manager.can_sell(self.strategy.position):
                    try:
                        # Calculate quantity to sell
                        sell_percentage = config.SELL_PERCENTAGES[level - 1] / 100
                        quantity_to_sell = self.strategy.position['tokens'] * sell_percentage
                        
                        # Format quantity
                        formatted_quantity = self.format_quantity(quantity_to_sell)
                        
                        # Check if quantity is valid
                        if formatted_quantity <= 0:
                            logger.warning(f"Calculated sell quantity is zero for level {level}")
                            continue
                        
                        # Execute sell with formatted quantity
                        logger.info(f"💰 Attempting SELL: {formatted_quantity:.8f} {config.SYMBOL} @ ${price:.4f}")
                        self.strategy.execute_sell(level, price, formatted_quantity)
                        
                    except Exception as e:
                        logger.error(f"Error executing sell: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    logger.warning("Sell blocked by risk manager")
        
        # Print status every 100 updates
        if self.price_updates % 100 == 0:
            self._print_status()
    
    def _print_status(self):
        """Print current bot status"""
        status = self.strategy.get_status()
        
        print(f"\n{Fore.CYAN}{'='*50}")
        print(f"📊 BOT STATUS - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*50}{Style.RESET_ALL}")
        
        print(f"💰 Current Price: ${status.get('current_price', 0):.4f}")
        
        if status.get('position_active', False):
            unrealized = status.get('unrealized_pnl', 0)
            pnl_color = Fore.GREEN if unrealized >= 0 else Fore.RED
            
            print(f"\n{Fore.YELLOW}📈 ACTIVE POSITION:{Style.RESET_ALL}")
            print(f"  📦 Tokens: {status.get('tokens', 0):.8f}")
            print(f"  💵 Avg Cost: ${status.get('avg_cost', 0):.4f}")
            print(f"  💰 Total Invested: ${status.get('total_invested', 0):.4f}")
            print(f"  {pnl_color}📊 Unrealized P&L: ${unrealized:.4f}{Style.RESET_ALL}")
            print(f"  🎯 Buy Levels: {status.get('buy_levels_executed', [])}")
            print(f"  🏁 Sell Levels: {status.get('sell_levels_executed', [])}")
        else:
            print(f"\n{Fore.GREEN}💼 NO ACTIVE POSITION{Style.RESET_ALL}")
        
        print(f"\n{Fore.CYAN}📈 STATS:{Style.RESET_ALL}")
        print(f"  🔄 Price Updates: {self.price_updates}")
        print(f"  ⚡ Signals Triggered: {self.signals_triggered}")
        
        # Risk metrics
        if self.risk_manager:
            try:
                risk_status = self.risk_manager.get_status()
                print(f"  📊 Daily Trades: {risk_status.get('daily_trades', 0)}")
                print(f"  💰 Daily P&L: ${risk_status.get('daily_pnl', 0):.4f}")
            except:
                pass
        
        # Show precision settings
        min_notional_val = self.min_notional if self.min_notional is not None else 10.0
        print(f"  🔧 Precision: Step={self.step_size}, Tick={self.tick_size}, MinOrder=${min_notional_val}")
    
    def start(self):
        """Start the trading bot"""
        if not self.initialize():
            logger.error("Failed to initialize bot. Exiting.")
            return
        
        self.running = True
        self.start_time = datetime.now()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("Bot started. Waiting for price updates...")
        print(f"\n{Fore.GREEN}{'='*60}")
        print("✅ BOT IS RUNNING")
        print(f"{'='*60}{Style.RESET_ALL}")
        print("📡 Using REST API polling for real-time prices")
        print("💡 The bot will buy on price dips and sell on price spikes")
        print("⚡  Press Ctrl+C to stop the bot\n")
        
        # Start price poller
        self.price_poller.start()
        
        # Keep main thread alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.stop()
    
    def stop(self):
        """Stop the trading bot gracefully"""
        logger.info("🛑 Stopping bot...")
        self.running = False
        
        # Stop price poller
        if self.price_poller:
            try:
                self.price_poller.stop()
            except:
                pass
        
        # Remove PID file
        self._remove_pid()
        
        if self.start_time:
            runtime = datetime.now() - self.start_time
            logger.info(f"⏱️ Runtime: {runtime}")
        
        logger.info(f"📊 Total price updates: {self.price_updates}")
        logger.info(f"⚡ Total signals: {self.signals_triggered}")
        
        # Print final status
        self._print_status()
        
        print(f"\n{Fore.CYAN}👋 Bot stopped. Goodbye!{Style.RESET_ALL}")
    
    def signal_handler(self, sig, frame):
        """Handle shutdown signals"""
        print(f"\n{Fore.YELLOW}Received shutdown signal. Cleaning up...{Style.RESET_ALL}")
        self.stop()
        sys.exit(0)


def main():
    """Main entry point"""
    bot = TradingBot()
    bot.start()


if __name__ == "__main__":
    main()