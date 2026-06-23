"""
Trading Strategy Module - Spike/Dump Strategy
Implements the core trading logic with proper risk management
"""

import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from config import config
from binance_client.rest_client import BinanceRestClient
from trading.order_manager import OrderManager
from trading.risk_manager import RiskManager
from utils.logger import get_logger
from utils.helpers import calculate_quantity

logger = get_logger(__name__)


class SpikeDumpStrategy:
    """
    Implements the spike (sell) and dump (buy) trading strategy
    Buy when price drops (dump), sell when price rises (spike)
    
    Strategy Logic:
    1. Reference Price: Set at bot start or after position is fully closed
    2. Buy Levels: Price drops of 2%, 4%, 6%, 8% from reference price
    3. Sell Levels: Price spikes of 2%, 4%, 6%, 8% from average cost
    4. Position Sizing: Doubles each level (100, 200, 400, 600)
    5. Profit Taking: Tiered selling (25% at each spike level)
    """
    
    def __init__(self, rest_client: BinanceRestClient):
        self.client = rest_client
        self.order_manager = OrderManager(rest_client)
        self.risk_manager = RiskManager(rest_client)
        
        # Trading parameters from config
        self.symbol = config.SYMBOL
        self.total_capital = config.TOTAL_CAPITAL
        self.base_position = config.BASE_POSITION
        self.dump_thresholds = config.DUMP_THRESHOLDS  # [2, 4, 6, 8]
        self.spike_thresholds = config.SPIKE_THRESHOLDS  # [2, 4, 6, 8]
        self.sell_percentages = config.SELL_PERCENTAGES  # [25, 25, 25, 25]
        
        # Trading state
        self.position = {
            'active': False,
            'tokens': 0.0,
            'avg_cost': 0.0,
            'total_cost': 0.0,
            'buys': [],  # List of buy levels executed
            'sold_levels': []  # List of sell levels executed
        }
        
        # Price tracking
        self.reference_price = None  # Starting price for dump calculations
        self.day_high = 0.0
        self.day_low = float('inf')
        self.last_price = None
        
        # Precision formatters (set by main bot)
        self.format_quantity = None
        self.format_price = None
        self.step_size = 0.00001  # Default value
        self.tick_size = 0.01  # Default value
        self.min_qty = 0.00001  # Default value
        self.min_notional = 10.0  # Default value
        
        # Performance tracking
        self.total_buys = 0
        self.total_sells = 0
        self.total_profit = 0.0
        
        # Initialize with current price
        self._initialize_reference()
    
    def calculate_buy_amount(self, level: int) -> float:
        """
        Calculate buy amount based on level
        
        Args:
            level: Buy level (1-4)
            
        Returns:
            Amount in USDT to spend
        """
        if level == 1:
            return self.base_position
        elif level == 2:
            return self.base_position * 2
        elif level == 3:
            return self.base_position * 4
        elif level == 4:
            return self.base_position * 6
        else:
            return self.base_position * (2 ** (level - 1))
    
    def calculate_position_size(self, current_price: float) -> Dict:
        """
        Calculate current position metrics
        
        Args:
            current_price: Current market price
            
        Returns:
            Dict with position metrics
        """
        if not self.position['active'] or self.position['tokens'] <= 0:
            return {
                'value': 0.0,
                'unrealized_pnl': 0.0,
                'unrealized_pnl_pct': 0.0,
                'break_even_price': 0.0
            }
        
        position_value = self.position['tokens'] * current_price
        unrealized_pnl = position_value - self.position['total_cost']
        unrealized_pnl_pct = (unrealized_pnl / self.position['total_cost']) * 100 if self.position['total_cost'] > 0 else 0
        
        return {
            'value': position_value,
            'unrealized_pnl': unrealized_pnl,
            'unrealized_pnl_pct': unrealized_pnl_pct,
            'break_even_price': self.position['avg_cost']
        }
    
    def _initialize_reference(self):
        """Set initial reference price for dump calculations"""
        try:
            price = self.client.get_symbol_price(self.symbol)
            if price and price > 0:
                self.reference_price = price
                self.day_high = price
                self.day_low = price
                self.last_price = price
                logger.info(f"🎯 Reference price set to ${price:.2f}")
            else:
                logger.warning("⚠️ Could not fetch initial price, using default")
                self.reference_price = 50000.0  # Fallback for BTC
        except Exception as e:
            logger.error(f"Error initializing reference price: {e}")
            self.reference_price = 50000.0  # Fallback
    
    def update_price(self, current_price: float) -> List[Tuple[str, int]]:
        """
        Update price and check for trading signals
        
        Args:
            current_price: Current market price
            
        Returns:
            List of (signal_type, level) tuples
        """
        if not current_price or current_price <= 0:
            return []
        
        self.last_price = current_price
        self.day_high = max(self.day_high, current_price)
        self.day_low = min(self.day_low, current_price)
        
        signals = []
        
        # Check for dump (buy) signal
        dump_signal = self._check_dump_signal(current_price)
        if dump_signal:
            signals.append(('BUY', dump_signal))
            logger.debug(f"📊 Dump signal at level {dump_signal} - Price: ${current_price:.2f}")
        
        # Check for spike (sell) signal
        spike_signal = self._check_spike_signal(current_price)
        if spike_signal:
            signals.append(('SELL', spike_signal))
            logger.debug(f"📊 Spike signal at level {spike_signal} - Price: ${current_price:.2f}")
        
        return signals
    
    def _check_dump_signal(self, current_price: float) -> Optional[int]:
        """
        Check if price dumped enough to trigger a buy
        
        Formula: (reference_price - current_price) / reference_price * 100 >= threshold
        
        Example:
            reference_price = $100, current_price = $96
            drop_percent = (100 - 96) / 100 * 100 = 4%
            If threshold is 4%, trigger Level 2 buy
        
        Args:
            current_price: Current market price
            
        Returns:
            Level number if signal triggered, None otherwise
        """
        if not self.reference_price or self.reference_price <= 0:
            return None
        
        if current_price <= 0:
            return None
        
        # Calculate drop percentage from reference
        drop_percent = (self.reference_price - current_price) / self.reference_price * 100
        
        # Only log if drop is significant for debugging
        if drop_percent > 0.1:
            logger.debug(f"Drop: {drop_percent:.2f}% - Ref: ${self.reference_price:.2f} → Current: ${current_price:.2f}")
        
        # Get already executed buy levels
        executed_levels = [buy['level'] for buy in self.position['buys']]
        
        # Check each threshold (must be triggered in order)
        for i, threshold in enumerate(self.dump_thresholds):
            level = i + 1
            
            # Can only trigger if previous levels were executed
            if level > 1 and (level - 1) not in executed_levels:
                continue
            
            if level not in executed_levels and drop_percent >= threshold:
                logger.info(f"📉 DUMP SIGNAL: Level {level} - Drop: {drop_percent:.2f}% (Threshold: {threshold}%)")
                logger.info(f"   Reference: ${self.reference_price:.2f} → Current: ${current_price:.2f}")
                return level
        
        return None
    
    def _check_spike_signal(self, current_price: float) -> Optional[int]:
        """
        Check if price spiked enough to trigger a sell
        
        Formula: (current_price - avg_cost) / avg_cost * 100 >= threshold
        
        Example:
            avg_cost = $94.89, current_price = $98.69
            spike_percent = (98.69 - 94.89) / 94.89 * 100 = 4%
            If threshold is 4%, trigger Level 2 sell
        
        Args:
            current_price: Current market price
            
        Returns:
            Level number if signal triggered, None otherwise
        """
        if not self.position['active'] or self.position['tokens'] <= 0:
            return None
        
        if self.position['avg_cost'] <= 0:
            return None
        
        if current_price <= 0:
            return None
        
        # Calculate spike percentage from average cost
        spike_percent = (current_price - self.position['avg_cost']) / self.position['avg_cost'] * 100
        
        # Get already executed sell levels
        sold_levels = self.position.get('sold_levels', [])
        
        # Check each threshold (must be triggered in order)
        for i, threshold in enumerate(self.spike_thresholds):
            level = i + 1
            
            # Can only trigger if previous levels were executed
            if level > 1 and (level - 1) not in sold_levels:
                continue
            
            if level not in sold_levels and spike_percent >= threshold:
                logger.info(f"📈 SPIKE SIGNAL: Level {level} - Spike: {spike_percent:.2f}% (Threshold: {threshold}%)")
                logger.info(f"   Avg Cost: ${self.position['avg_cost']:.2f} → Current: ${current_price:.2f}")
                return level
        
        return None
    
    def execute_buy(self, level: int, current_price: float, formatted_quantity: float = None):
        """
        Execute buy order at specified level
        
        Args:
            level: Buy level (1-4)
            current_price: Current price
            formatted_quantity: Pre-formatted quantity (optional)
        """
        try:
            # Calculate buy amount based on level
            amount = self.calculate_buy_amount(level)
            
            # Use formatted quantity if provided, otherwise calculate
            if formatted_quantity is not None and formatted_quantity > 0:
                quantity = formatted_quantity
                amount = quantity * current_price
            else:
                quantity = calculate_quantity(amount, current_price)
            
            # Validate quantity
            if quantity <= 0:
                logger.warning(f"Calculated quantity is zero for level {level}")
                return None
            
            # Check available balance
            usdt_balance = self.client.get_account_balance('USDT')
            if usdt_balance is None:
                logger.warning("⚠️ Could not check balance (IP may not be whitelisted)")
                logger.warning("   Proceeding with order...")
            elif usdt_balance < amount:
                logger.warning(f"Insufficient balance: Need ${amount:.2f}, have ${usdt_balance:.2f}")
                return None
            
            # Apply quantity formatting if available
            if self.format_quantity:
                formatted_qty = self.format_quantity(quantity)
                if formatted_qty > 0:
                    quantity = formatted_qty
                    logger.debug(f"Quantity formatted: {quantity:.8f}")
            
            # Ensure minimum quantity (with None check)
            min_qty_val = self.min_qty if self.min_qty is not None else 0.00001
            if quantity < min_qty_val:
                logger.warning(f"Quantity {quantity:.8f} is below minimum {min_qty_val:.8f}")
                quantity = min_qty_val
            
            # Check minimum order value (with None check)
            min_notional_val = self.min_notional if self.min_notional is not None else 10.0
            order_value = quantity * current_price
            if order_value < min_notional_val:
                logger.warning(f"Order value ${order_value:.2f} below minimum ${min_notional_val:.2f}")
                return None
            
            logger.info(f"💰 Executing BUY Level {level}:")
            logger.info(f"   Amount: ${amount:.2f}")
            logger.info(f"   Price: ${current_price:.2f}")
            logger.info(f"   Quantity: {quantity:.8f}")
            logger.info(f"   Order Value: ${order_value:.2f}")
            
            # Place market buy order
            order = self.client.place_market_order(self.symbol, 'BUY', quantity)
            
            if order:
                # Update position
                self.position['tokens'] += quantity
                self.position['total_cost'] += amount
                self.position['avg_cost'] = self.position['total_cost'] / self.position['tokens']
                self.position['active'] = True
                self.position['buys'].append({
                    'level': level,
                    'price': current_price,
                    'amount': amount,
                    'quantity': quantity,
                    'time': datetime.now().isoformat()
                })
                
                self.total_buys += 1
                
                logger.info(f"✅ BUY EXECUTED: Level {level} - {quantity:.8f} {self.symbol} @ ${current_price:.2f}")
                logger.info(f"   Position: {self.position['tokens']:.8f} tokens @ ${self.position['avg_cost']:.2f} avg")
                
                # Record trade
                self.order_manager.record_trade('BUY', level, current_price, quantity, amount)
                
                return order
            
            return None
            
        except Exception as e:
            logger.error(f"Error executing buy: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def execute_sell(self, level: int, current_price: float, formatted_quantity: float = None):
        """
        Execute sell order at specified level
        
        Args:
            level: Sell level (1-4)
            current_price: Current price
            formatted_quantity: Pre-formatted quantity (optional)
        """
        try:
            if not self.position['active'] or self.position['tokens'] <= 0:
                logger.warning("No active position to sell")
                return None
            
            # Calculate percentage to sell
            sell_percentage = self.sell_percentages[level - 1] / 100
            
            # Use formatted quantity if provided, otherwise calculate
            if formatted_quantity is not None and formatted_quantity > 0:
                quantity_to_sell = formatted_quantity
            else:
                quantity_to_sell = self.position['tokens'] * sell_percentage
            
            if quantity_to_sell <= 0:
                logger.warning(f"Quantity to sell is zero at level {level}")
                return None
            
            # Apply quantity formatting if available
            if self.format_quantity:
                formatted_qty = self.format_quantity(quantity_to_sell)
                if formatted_qty > 0:
                    quantity_to_sell = formatted_qty
            
            # Ensure we don't sell more than we have
            if quantity_to_sell > self.position['tokens']:
                quantity_to_sell = self.position['tokens']
                logger.info(f"Adjusting sell quantity to full position: {quantity_to_sell:.8f}")
            
            # Calculate expected proceeds
            proceeds = quantity_to_sell * current_price
            cost_basis = quantity_to_sell * self.position['avg_cost']
            expected_profit = proceeds - cost_basis
            
            logger.info(f"💰 Executing SELL Level {level}:")
            logger.info(f"   Percentage: {sell_percentage * 100}% of position")
            logger.info(f"   Quantity: {quantity_to_sell:.8f}")
            logger.info(f"   Price: ${current_price:.2f}")
            logger.info(f"   Expected Profit: ${expected_profit:.2f}")
            
            # Place market sell order
            order = self.client.place_market_order(self.symbol, 'SELL', quantity_to_sell)
            
            if order:
                # Update position
                self.position['tokens'] -= quantity_to_sell
                self.position['total_cost'] -= cost_basis
                
                # Check if position is closed
                if self.position['tokens'] < 0.00000001:
                    self.position['active'] = False
                    self.position['tokens'] = 0.0
                    self.position['total_cost'] = 0.0
                    self.position['avg_cost'] = 0.0
                    self.position['buys'] = []
                    logger.info("🏁 Position fully closed")
                
                # Track sold levels
                if 'sold_levels' not in self.position:
                    self.position['sold_levels'] = []
                self.position['sold_levels'].append(level)
                
                self.total_sells += 1
                self.total_profit += expected_profit
                
                # Record profit with risk manager
                self.risk_manager.record_trade_result(expected_profit)
                
                logger.info(f"✅ SELL EXECUTED: Level {level} - {quantity_to_sell:.8f} {self.symbol} @ ${current_price:.2f}")
                logger.info(f"   Profit on this sale: ${expected_profit:.2f}")
                
                # Record trade
                self.order_manager.record_trade('SELL', level, current_price, quantity_to_sell, proceeds, expected_profit)
                
                return order
            
            return None
            
        except Exception as e:
            logger.error(f"Error executing sell: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_status(self) -> Dict:
        """Get current strategy status with detailed metrics"""
        try:
            position_metrics = self.calculate_position_size(self.last_price if self.last_price else 0)
            
            return {
                # Position status
                'position_active': self.position['active'],
                'tokens': self.position['tokens'],
                'avg_cost': self.position['avg_cost'],
                'total_invested': self.position['total_cost'],
                'position_value': position_metrics['value'],
                'unrealized_pnl': position_metrics['unrealized_pnl'],
                'unrealized_pnl_pct': position_metrics['unrealized_pnl_pct'],
                
                # Price tracking
                'current_price': self.last_price if self.last_price else 0,
                'day_high': self.day_high if self.day_high != float('inf') else 0,
                'day_low': self.day_low if self.day_low != float('inf') else 0,
                'reference_price': self.reference_price if self.reference_price else 0,
                
                # Levels
                'buy_levels_executed': [b['level'] for b in self.position['buys']],
                'sell_levels_executed': self.position.get('sold_levels', []),
                
                # Performance
                'total_buys': self.total_buys,
                'total_sells': self.total_sells,
                'total_profit': self.total_profit,
                
                # Next thresholds
                'next_buy_threshold': self._get_next_buy_threshold(),
                'next_sell_threshold': self._get_next_sell_threshold()
            }
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {
                'position_active': False,
                'tokens': 0.0,
                'avg_cost': 0.0,
                'total_invested': 0.0,
                'current_price': 0,
                'buy_levels_executed': [],
                'sell_levels_executed': []
            }
    
    def _get_next_buy_threshold(self) -> Optional[float]:
        """Get next buy threshold percentage"""
        try:
            executed_levels = [b['level'] for b in self.position['buys']]
            next_level = len(executed_levels) + 1
            
            if next_level <= len(self.dump_thresholds):
                return self.dump_thresholds[next_level - 1]
            return None
        except Exception:
            return None
    
    def _get_next_sell_threshold(self) -> Optional[float]:
        """Get next sell threshold percentage"""
        try:
            sold_levels = self.position.get('sold_levels', [])
            next_level = len(sold_levels) + 1
            
            if next_level <= len(self.spike_thresholds) and self.position['active']:
                return self.spike_thresholds[next_level - 1]
            return None
        except Exception:
            return None
    
    def reset_position(self):
        """Reset the current position"""
        self.position = {
            'active': False,
            'tokens': 0.0,
            'avg_cost': 0.0,
            'total_cost': 0.0,
            'buys': [],
            'sold_levels': []
        }
        logger.info("Position reset")
    
    def reset_reference_price(self):
        """Reset reference price to current price"""
        try:
            current_price = self.client.get_symbol_price(self.symbol)
            if current_price and current_price > 0:
                self.reference_price = current_price
                logger.info(f"Reference price reset to ${current_price:.2f}")
        except Exception as e:
            logger.error(f"Error resetting reference price: {e}")
    
    def get_average_cost(self) -> float:
        """Get current average cost"""
        return self.position['avg_cost']
    
    def get_total_tokens(self) -> float:
        """Get total tokens held"""
        return self.position['tokens']
    
    def is_in_position(self) -> bool:
        """Check if in a position"""
        return self.position['active'] and self.position['tokens'] > 0


__all__ = ['SpikeDumpStrategy']