import math
from decimal import Decimal, ROUND_DOWN

def calculate_quantity(amount_usdt: float, price: float) -> float:
    """
    Calculate quantity to buy with proper precision
    Binance has minimum quantity and step size requirements
    """
    if price <= 0:
        return 0
    
    # Calculate raw quantity
    raw_quantity = amount_usdt / price
    
    # Round down to appropriate precision (adjust based on symbol)
    # For BTCUSDT, typical step size is 0.00001
    step_size = 0.00001
    precision = int(round(-math.log10(step_size)))
    
    # Round down to step size
    quantity = math.floor(raw_quantity / step_size) * step_size
    
    return round(quantity, precision)

def format_price(price: float) -> str:
    """Format price for display"""
    if price < 0.01:
        return f"${price:.6f}"
    elif price < 1:
        return f"${price:.4f}"
    else:
        return f"${price:.2f}"

def calculate_percentage_change(old_price: float, new_price: float) -> float:
    """Calculate percentage change"""
    if old_price == 0:
        return 0
    return ((new_price - old_price) / old_price) * 100