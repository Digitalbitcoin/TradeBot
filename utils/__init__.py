"""
Utilities Module
Helper functions and logging utilities for the trading bot

Sub-modules:
- logger: Logging configuration and setup
- helpers: Helper functions for calculations and formatting
"""

__all__ = [
    'setup_logging',
    'get_logger',
    'calculate_quantity',
    'format_price',
    'calculate_percentage_change'
]

# Module metadata
__version__ = "1.0.0"
__author__ = "Trading Bot"

# Lazy loading function
def __getattr__(name):
    """Lazy import for better startup performance"""
    if name in ['setup_logging', 'get_logger']:
        from utils.logger import setup_logging, get_logger
        if name == 'setup_logging':
            return setup_logging
        return get_logger
    elif name in ['calculate_quantity', 'format_price', 'calculate_percentage_change']:
        from utils.helpers import calculate_quantity, format_price, calculate_percentage_change
        if name == 'calculate_quantity':
            return calculate_quantity
        elif name == 'format_price':
            return format_price
        return calculate_percentage_change
    raise AttributeError(f"module {__name__} has no attribute {name}")

def __dir__():
    """Show available attributes"""
    return sorted(__all__)