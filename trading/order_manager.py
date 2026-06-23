import csv
import os
from datetime import datetime
from typing import Dict, List, Optional
from config import config
from utils.logger import get_logger

logger = get_logger(__name__)

class OrderManager:
    """Manages order execution and trade history"""
    
    def __init__(self, rest_client):
        self.client = rest_client
        self.trades_file = 'data/trades_history.csv'
        self._ensure_data_directory()
        self._init_csv()
    
    def _ensure_data_directory(self):
        """Ensure data directory exists"""
        os.makedirs('data', exist_ok=True)
    
    def _init_csv(self):
        """Initialize CSV file with headers if it doesn't exist"""
        if not os.path.exists(self.trades_file):
            with open(self.trades_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'symbol', 'side', 'level', 
                    'price', 'quantity', 'amount', 'profit', 'balance_after'
                ])
    
    def record_trade(self, side: str, level: int, price: float, 
                     quantity: float, amount: float, profit: float = 0):
        """Record trade in CSV file"""
        try:
            # Get current balance
            balance = self.client.get_account_balance('USDT') or 0
            
            with open(self.trades_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    config.SYMBOL,
                    side,
                    level,
                    f"{price:.2f}",
                    f"{quantity:.6f}",
                    f"{amount:.2f}",
                    f"{profit:.2f}",
                    f"{balance:.2f}"
                ])
            
            logger.debug(f"Trade recorded: {side} {quantity} @ {price}")
            
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
    
    def get_trade_history(self, limit: int = 100) -> List[Dict]:
        """Get recent trade history"""
        trades = []
        try:
            with open(self.trades_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in list(reader)[-limit:]:
                    trades.append(row)
        except Exception as e:
            logger.error(f"Failed to read trade history: {e}")
        
        return trades
    
    def calculate_daily_pnl(self) -> float:
        """Calculate today's P&L"""
        today = datetime.now().date().isoformat()
        total_profit = 0
        
        try:
            with open(self.trades_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['timestamp'].startswith(today) and row['side'] == 'SELL':
                        total_profit += float(row['profit'])
        except Exception as e:
            logger.error(f"Failed to calculate P&L: {e}")
        
        return total_profit