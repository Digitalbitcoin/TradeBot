"""
Trading Module
Core trading logic including strategy execution, order management, and risk controls

Sub-modules:
- strategy: Spike/Dump trading strategy implementation
- order_manager: Trade recording and history management
- risk_manager: Risk controls and circuit breakers
"""

__all__ = [
    'SpikeDumpStrategy',
    'OrderManager',
    'RiskManager'
]

# Module metadata
__version__ = "1.0.0"
__author__ = "Trading Bot"

# Lazy loading function
def __getattr__(name):
    """Lazy import for better startup performance"""
    if name == 'SpikeDumpStrategy':
        from trading.strategy import SpikeDumpStrategy
        return SpikeDumpStrategy
    elif name == 'OrderManager':
        from trading.order_manager import OrderManager
        return OrderManager
    elif name == 'RiskManager':
        from trading.risk_manager import RiskManager
        return RiskManager
    raise AttributeError(f"module {__name__} has no attribute {name}")

def __dir__():
    """Show available attributes"""
    return sorted(__all__)