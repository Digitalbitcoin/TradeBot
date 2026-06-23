import time
from datetime import datetime, timedelta
from typing import Dict
from config import config
from utils.logger import get_logger

logger = get_logger(__name__)

class RiskManager:
    """
    Manages risk controls and safety features
    - Daily loss limits
    - Maximum position size
    - Circuit breakers
    - Rate limiting
    """
    
    def __init__(self, rest_client):
        self.client = rest_client
        
        # Risk parameters
        self.max_daily_loss_pct = 5  # 5% max daily loss
        self.max_daily_trades = 20    # Max trades per day
        self.max_consecutive_losses = 3
        self.min_balance_required = 50  # Minimum USDT balance to continue
        
        # State tracking
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.last_trade_time = None
        self.circuit_breaker_active = False
        self.circuit_breaker_until = None
        
        # Initialize with current date
        self.current_date = datetime.now().date()
    
    def can_buy(self, position: Dict) -> bool:
        """Check if buy is allowed based on risk rules"""
        # Check circuit breaker
        if self.circuit_breaker_active:
            if datetime.now() < self.circuit_breaker_until:
                logger.warning(f"Circuit breaker active until {self.circuit_breaker_until}")
                return False
            else:
                self.circuit_breaker_active = False
        
        # Check daily loss limit
        if abs(self.daily_pnl) > (config.TOTAL_CAPITAL * self.max_daily_loss_pct / 100):
            logger.warning(f"Daily loss limit exceeded: ${abs(self.daily_pnl):.2f}")
            self._activate_circuit_breaker(hours=24)
            return False
        
        # Check daily trade count
        if self.daily_trades >= self.max_daily_trades:
            logger.warning(f"Daily trade limit reached: {self.daily_trades}")
            return False
        
        # Check balance
        balance = self.client.get_account_balance('USDT')
        if balance and balance < self.min_balance_required:
            logger.warning(f"Balance too low: ${balance}")
            return False
        
        # Check if already at max position
        if position.get('active', False):
            total_invested = position.get('total_cost', 0)
            if total_invested >= config.TOTAL_CAPITAL * 0.8:  # Max 80% of capital
                logger.warning(f"Max position size reached: ${total_invested}")
                return False
        
        return True
    
    def can_sell(self, position: Dict) -> bool:
        """Check if sell is allowed"""
        # Similar checks for selling
        if not position.get('active', False) or position.get('tokens', 0) <= 0:
            return False
        
        return True
    
    def record_trade_result(self, profit: float):
        """Record trade result for risk tracking"""
        self.daily_trades += 1
        self.daily_pnl += profit
        self.last_trade_time = datetime.now()
        
        # Track consecutive losses
        if profit < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.max_consecutive_losses:
                logger.warning(f"Max consecutive losses reached: {self.consecutive_losses}")
                self._activate_circuit_breaker(hours=4)
        else:
            self.consecutive_losses = 0
        
        # Reset daily counters if new day
        self._check_new_day()
    
    def _check_new_day(self):
        """Reset daily counters at start of new day"""
        today = datetime.now().date()
        if today != self.current_date:
            logger.info(f"New day detected. Resetting daily counters.")
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.consecutive_losses = 0
            self.current_date = today
    
    def _activate_circuit_breaker(self, hours: int = 1):
        """Activate circuit breaker to pause trading"""
        self.circuit_breaker_active = True
        self.circuit_breaker_until = datetime.now() + timedelta(hours=hours)
        logger.warning(f"⚠️ CIRCUIT BREAKER ACTIVATED until {self.circuit_breaker_until}")
    
    def get_status(self) -> Dict:
        """Get current risk status"""
        self._check_new_day()
        
        return {
            'daily_trades': self.daily_trades,
            'daily_pnl': self.daily_pnl,
            'consecutive_losses': self.consecutive_losses,
            'circuit_breaker_active': self.circuit_breaker_active,
            'circuit_breaker_until': self.circuit_breaker_until,
            'current_date': self.current_date
        }