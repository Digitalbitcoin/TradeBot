"""
Binance Client Module
Handles all Binance API interactions including REST and WebSocket connections

Sub-modules:
- rest_client: REST API operations (orders, balances, market data)
- websocket_client: Real-time WebSocket streaming
"""

# Lazy imports to avoid circular dependencies
__all__ = [
    'BinanceRestClient',
    'BinanceWebSocketClient',
    'CombinedWebSocketClient'
]

# Module metadata
__version__ = "1.0.0"
__author__ = "Trading Bot"

# Lazy loading function
def __getattr__(name):
    """Lazy import for better startup performance and to handle missing deps gracefully"""
    if name == 'BinanceRestClient':
        from binance_client.rest_client import BinanceRestClient
        return BinanceRestClient
    elif name == 'BinanceWebSocketClient':
        from binance_client.websocket_client import BinanceWebSocketClient
        return BinanceWebSocketClient
    elif name == 'CombinedWebSocketClient':
        from binance_client.websocket_client import CombinedWebSocketClient
        return CombinedWebSocketClient
    raise AttributeError(f"module {__name__} has no attribute {name}")

def __dir__():
    """Show available attributes"""
    return sorted(__all__)