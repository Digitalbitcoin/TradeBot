# web_server.py - Multi-user with per-user API keys
#!/usr/bin/env python3
"""
Web Server for Trading Bot Dashboard
Multi-user system with per-user API key management
"""

import sys
import json
import csv
import signal
import os
import time
import random
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS
from threading import Thread
import subprocess
from functools import wraps

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app, supports_credentials=True)

# Global variables
bot_process = None
pause_file = Path('bot.paused')
bot_starting = False
bot_data_cache = {
    'price': None,
    'balance': None,
    'position': None,
    'last_update': 0,
    'symbol': None,
    'username': None
}
price_history = []
MAX_PRICE_HISTORY = 500

# Import referral manager
try:
    from referral_manager import ReferralManager
    referral_manager = ReferralManager()
except:
    referral_manager = None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'success': False, 'message': 'Please login first'}), 401
        return f(*args, **kwargs)
    return decorated_function

def is_process_running(pid):
    """Check if a process with given PID is running"""
    try:
        if os.name == 'nt':
            import psutil
            return psutil.pid_exists(pid)
        else:
            os.kill(pid, 0)
            return True
    except:
        return False

def cleanup_stale_pid():
    pid_file = Path('bot.pid')
    if pid_file.exists():
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            if not is_process_running(pid):
                print(f"Removing stale PID file (PID {pid} not running)")
                pid_file.unlink()
        except:
            pid_file.unlink()

def get_config_values(username=None):
    """Get config values, optionally with user-specific API keys"""
    try:
        from config import config
        return {
            'use_testnet': getattr(config, 'USE_TESTNET', True),
            'symbol': getattr(config, 'SYMBOL', 'BTCUSDT'),
            'total_capital': getattr(config, 'TOTAL_CAPITAL', 1300),
            'base_position': getattr(config, 'BASE_POSITION', 100),
            'dump_thresholds': getattr(config, 'DUMP_THRESHOLDS', [2, 4, 6, 8]),
            'spike_thresholds': getattr(config, 'SPIKE_THRESHOLDS', [2, 4, 6, 8]),
            'sell_percentages': getattr(config, 'SELL_PERCENTAGES', [25, 25, 25, 25]),
            'enable_referral': getattr(config, 'ENABLE_REFERRAL', True),
            'referral_bonus': getattr(config, 'REFERRAL_BONUS', 10.0),
            'referral_commission': getattr(config, 'REFERRAL_COMMISSION', 5.0),
            'available_coins': getattr(config, 'AVAILABLE_COINS', 'BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT').split(',')
        }
    except Exception as e:
        print(f"Error reading config: {e}")
        return {
            'use_testnet': True,
            'symbol': 'BTCUSDT',
            'total_capital': 1300,
            'base_position': 100,
            'dump_thresholds': [2, 4, 6, 8],
            'spike_thresholds': [2, 4, 6, 8],
            'sell_percentages': [25, 25, 25, 25],
            'enable_referral': True,
            'referral_bonus': 10.0,
            'referral_commission': 5.0,
            'available_coins': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT']
        }

def get_user_api_keys(username):
    """Get API keys for a specific user from users.json"""
    if not referral_manager:
        return None, None
    
    users = referral_manager.users
    if username in users:
        user_data = users[username]
        return user_data.get('api_key'), user_data.get('api_secret')
    return None, None

def save_user_api_keys(username, api_key, api_secret, testnet=True):
    """Save API keys for a specific user"""
    if not referral_manager:
        return False
    
    users = referral_manager.users
    if username in users:
        users[username]['api_key'] = api_key
        users[username]['api_secret'] = api_secret
        users[username]['use_testnet'] = testnet
        referral_manager._save_users()
        return True
    return False

def get_bot_data(symbol=None, username=None):
    """Get real bot data for a specific user and symbol"""
    global bot_data_cache, price_history
    
    symbol = symbol or get_config_values().get('symbol', 'BTCUSDT')
    username = username or session.get('username')
    
    # Check if bot is running via PID file
    pid_file = Path('bot.pid')
    if not pid_file.exists():
        return None
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        if not is_process_running(pid):
            return None
    except Exception as e:
        return None
    
    # Get user's API keys
    api_key, api_secret = get_user_api_keys(username)
    if not api_key or not api_secret:
        return {'error': 'API keys not configured for this user'}
    
    # Fetch fresh data with user's credentials
    try:
        from binance.client import Client
        from binance.exceptions import BinanceAPIException
        
        client = Client(api_key, api_secret)
        
        # Set testnet if configured
        user_data = referral_manager.users.get(username, {})
        if user_data.get('use_testnet', True):
            client.API_URL = 'https://testnet.binance.vision/api'
            client.WAPI_URL = 'https://testnet.binance.vision/wapi'
        
        # Get current price
        ticker = client.get_symbol_ticker(symbol=symbol)
        price = float(ticker['price']) if ticker else None
        
        # Update price history with real data
        if price:
            now = datetime.now()
            price_history.append({
                'time': now.isoformat(),
                'price': float(price),
                'symbol': symbol
            })
            # Keep only the last MAX_PRICE_HISTORY entries
            if len(price_history) > MAX_PRICE_HISTORY:
                price_history = price_history[-MAX_PRICE_HISTORY:]
        
        # Get balance
        balance = None
        try:
            account = client.get_account()
            for bal in account['balances']:
                if bal['asset'] == 'USDT':
                    balance = float(bal['free'])
                    break
        except:
            pass
        
        # Get position info - simplified for demo
        # In a real implementation, you'd track positions per user/symbol
        position = bot_data_cache.get('position', {'position_active': False})
        
        bot_data_cache = {
            'price': price,
            'balance': balance,
            'position': position,
            'symbol': symbol,
            'username': username,
            'last_update': time.time()
        }
        
        return bot_data_cache
        
    except Exception as e:
        print(f"Error getting bot data for {username}: {e}")
        return {'error': str(e)}
    
def update_price_history(price, symbol=None):
    global price_history
    if price is None:
        return
    now = datetime.now()
    price_history.append({
        'time': now.isoformat(),
        'price': float(price),
        'symbol': symbol or 'BTCUSDT'
    })
    if len(price_history) > MAX_PRICE_HISTORY:
        price_history = price_history[-MAX_PRICE_HISTORY:]

def get_recent_prices_from_log():
    """Extract price data from the trading bot log file"""
    prices = []
    
    # First, get prices from the cache (most recent)
    if price_history:  # This references the global variable directly
        prices.extend(price_history)
    
    # Then, get prices from the log file
    log_file = Path('trading_bot.log')
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    # Look for price mentions in various formats
                    price = None
                    timestamp = None
                    
                    # Try to extract timestamp
                    if len(line) > 19:
                        try:
                            timestamp_str = line[:19]
                            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        except:
                            pass
                    
                    # Look for price patterns
                    # Pattern 1: "Current price: $XXXXX.XX" or "Price: $XXXXX.XX"
                    if 'Current' in line and '$' in line:
                        try:
                            price_part = line.split('$')[-1].strip()
                            price = float(price_part.split()[0])
                        except:
                            pass
                    
                    # Pattern 2: "BTCUSDT: $XXXXX.XX"
                    elif 'BTCUSDT' in line and '$' in line:
                        try:
                            price_part = line.split('$')[-1].strip()
                            price = float(price_part.split()[0])
                        except:
                            pass
                    
                    # Pattern 3: Any number that looks like a price with decimals
                    elif 'price' in line.lower() and '$' in line:
                        try:
                            import re
                            price_match = re.search(r'\$(\d+\.\d+)', line)
                            if price_match:
                                price = float(price_match.group(1))
                        except:
                            pass
                    
                    # If we found both timestamp and price, add to list
                    if timestamp and price is not None:
                        prices.append({
                            'time': timestamp.isoformat(),
                            'price': price
                        })
        except Exception as e:
            print(f"Error reading log file for prices: {e}")
    
    # Remove duplicates based on timestamp
    seen_times = set()
    unique_prices = []
    for p in prices:
        if p['time'] not in seen_times:
            seen_times.add(p['time'])
            unique_prices.append(p)
    
    # Sort by timestamp
    unique_prices.sort(key=lambda x: x['time'])
    
    # Update the global cache with the latest data
    if unique_prices:
        # Update the global variable directly (no global declaration needed at module level)
        price_history.clear()
        price_history.extend(unique_prices[-MAX_PRICE_HISTORY:])
    
    return unique_prices
    
def generate_mock_prices(count=200, start_price=65000, symbol='BTCUSDT'):
    prices = []
    base_prices = {
        'BTCUSDT': 65000, 'ETHUSDT': 3500, 'BNBUSDT': 600,
        'SOLUSDT': 150, 'XRPUSDT': 0.50, 'ADAUSDT': 0.35, 'DOGEUSDT': 0.12
    }
    current_price = base_prices.get(symbol, 65000) + (random.random() * 2000 - 1000)
    now = datetime.now()
    for i in range(count, 0, -1):
        timestamp = now - timedelta(minutes=i)
        variation = random.uniform(-0.002, 0.002)
        if random.random() < 0.02:
            variation *= random.uniform(3, 5)
        current_price *= (1 + variation)
        if symbol == 'BTCUSDT':
            current_price = max(60000, min(70000, current_price))
        elif symbol == 'ETHUSDT':
            current_price = max(3000, min(4000, current_price))
        elif symbol == 'BNBUSDT':
            current_price = max(500, min(700, current_price))
        elif symbol == 'SOLUSDT':
            current_price = max(120, min(180, current_price))
        elif symbol == 'XRPUSDT':
            current_price = max(0.40, min(0.60, current_price))
        elif symbol == 'ADAUSDT':
            current_price = max(0.30, min(0.40, current_price))
        elif symbol == 'DOGEUSDT':
            current_price = max(0.10, min(0.14, current_price))
        prices.append({
            'time': timestamp.isoformat(),
            'price': round(current_price, 2)
        })
    return prices

def get_trades_from_csv():
    trades = []
    trades_file = Path('data/trades_history.csv')
    if trades_file.exists():
        try:
            with open(trades_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    trade = {
                        'timestamp': row.get('timestamp', ''),
                        'side': row.get('side', ''),
                        'type': row.get('type', ''),
                        'price': float(row.get('price', 0)) if row.get('price') else 0,
                        'quantity': float(row.get('quantity', 0)) if row.get('quantity') else 0,
                        'amount': float(row.get('amount', 0)) if row.get('amount') else 0,
                        'level': row.get('level', '')
                    }
                    if row.get('profit'):
                        trade['profit'] = float(row.get('profit', 0))
                    trades.append(trade)
        except Exception as e:
            print(f"Error reading trades: {e}")
    return trades

# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/auth/check')
def check_auth():
    return jsonify({
        'logged_in': session.get('logged_in', False),
        'username': session.get('username', None)
    })

@app.route('/api/auth/login', methods=['POST'])
def login_user():
    if not referral_manager:
        return jsonify({'success': False, 'message': 'Referral system not available'})
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'})
    authenticated = referral_manager.authenticate_user(username, password)
    if authenticated:
        session['logged_in'] = True
        session['username'] = username
        
        # Get user data directly from users dict to ensure email is included
        user_data = referral_manager.users.get(username, {})
        summary = referral_manager.get_user_summary(username)
        
        # Ensure email is included in the response
        if summary:
            summary['email'] = user_data.get('email', '')
            summary['has_api_keys'] = bool(user_data.get('api_key') and user_data.get('api_secret'))
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': summary
        })
    else:
        return jsonify({'success': False, 'message': 'Invalid username or password'})

@app.route('/api/auth/register', methods=['POST'])
def register_user():
    if not referral_manager:
        return jsonify({'success': False, 'message': 'Referral system not available'})
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    username = data.get('username')
    password = data.get('password')
    email = data.get('email', '').strip()
    referral_code = data.get('referral_code')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'})
    
    # Check if username exists
    if username in referral_manager.users:
        return jsonify({'success': False, 'message': 'Username already exists'})
    
    # Create user with email
    result = referral_manager.register_user(username, password, email, referral_code)
    return jsonify(result)

@app.route('/api/auth/logout', methods=['POST'])
def logout_user():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/user/api-keys', methods=['GET'])
@login_required
def get_user_api_keys_route():
    """Get API key status for current user"""
    username = session.get('username')
    api_key, api_secret = get_user_api_keys(username)
    user_data = referral_manager.users.get(username, {})
    return jsonify({
        'success': True,
        'has_api_key': bool(api_key),
        'use_testnet': user_data.get('use_testnet', True),
        'api_key_masked': api_key[:8] + '...' + api_key[-4:] if api_key and len(api_key) > 12 else None
    })

@app.route('/api/user/api-keys', methods=['POST'])
@login_required
def save_user_api_keys_route():
    """Save API keys for the current user"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    api_key = data.get('api_key', '').strip()
    api_secret = data.get('api_secret', '').strip()
    use_testnet = data.get('testnet', True)
    
    if not api_key or not api_secret:
        return jsonify({'success': False, 'message': 'API Key and Secret are required'})
    
    username = session.get('username')
    if not username:
        return jsonify({'success': False, 'message': 'User not logged in'})
    
    # Test the API keys before saving
    try:
        from binance.client import Client
        from binance.exceptions import BinanceAPIException
        
        test_client = Client(api_key, api_secret)
        if use_testnet:
            test_client.API_URL = 'https://testnet.binance.vision/api'
            test_client.WAPI_URL = 'https://testnet.binance.vision/wapi'
        
        # Test connection
        test_client.ping()
        # Try to get account info to verify permissions
        test_client.get_account()
        
    except BinanceAPIException as e:
        return jsonify({
            'success': False, 
            'message': f'Invalid API keys: {e.message}',
            'error_code': e.code
        })
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Error testing API keys: {str(e)}'
        })
    
    # Save keys for user
    if save_user_api_keys(username, api_key, api_secret, use_testnet):
        return jsonify({'success': True, 'message': 'API keys saved successfully'})
    else:
        return jsonify({'success': False, 'message': 'Failed to save API keys'})

@app.route('/api/status')
@login_required
def get_status():
    global bot_starting
    symbol = request.args.get('symbol') or get_config_values().get('symbol', 'BTCUSDT')
    username = session.get('username')
    config_values = get_config_values()
    
    # Check if user has API keys
    api_key, api_secret = get_user_api_keys(username)
    has_api_keys = bool(api_key and api_secret)
    
    # Check if bot is running
    pid_file = Path('bot.pid')
    is_running = False
    pid = None
    
    if pid_file.exists():
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
                if is_process_running(pid):
                    is_running = True
                    if bot_starting:
                        print("Bot is now running!")
                        bot_starting = False
                else:
                    pid_file.unlink()
                    if bot_starting:
                        print("Bot failed to start - no process found")
                        bot_starting = False
        except:
            pass
    
    # Get real data only if bot is running and user has API keys
    bot_data = None
    if is_running and has_api_keys:
        bot_data = get_bot_data(symbol, username)
    
    status = {
        'running': is_running,
        'starting': bot_starting,
        'paused': pause_file.exists(),
        'mode': 'TESTNET' if config_values['use_testnet'] else 'MAINNET',
        'symbol': symbol,
        'total_capital': config_values['total_capital'],
        'base_position': config_values['base_position'],
        'dump_thresholds': config_values['dump_thresholds'],
        'spike_thresholds': config_values['spike_thresholds'],
        'sell_percentages': config_values['sell_percentages'],
        'available_coins': config_values.get('available_coins', ['BTCUSDT', 'ETHUSDT']),
        'current_price': bot_data.get('price') if bot_data and isinstance(bot_data, dict) else None,
        'balance': bot_data.get('balance') if bot_data and isinstance(bot_data, dict) else None,
        'position': bot_data.get('position') if bot_data and isinstance(bot_data, dict) else None,
        'has_api_keys': has_api_keys,
        'pid': pid,
        'logged_in': True,
        'username': username
    }
    
    if bot_data and isinstance(bot_data, dict) and 'error' in bot_data:
        status['error'] = bot_data['error']
    
    return jsonify(status)

@app.route('/api/price/history')
def get_price_history():
    hours = request.args.get('hours', 24, type=int)
    symbol = request.args.get('symbol', 'BTCUSDT')
    
    # First, try to get real data from the log file
    prices = get_recent_prices_from_log()
    
    # If we have real data, use it
    if len(prices) >= 10:
        # Filter by hours
        cutoff = datetime.now() - timedelta(hours=hours)
        filtered = [p for p in prices if datetime.fromisoformat(p['time']) > cutoff]
        
        # If we have enough data for the requested timeframe, return it
        if len(filtered) >= 5:
            return jsonify(filtered[-200:])
        
        # If not enough data for the timeframe, return what we have
        return jsonify(prices[-200:])
    
    # If no real data exists, use mock data
    # This will only happen when the bot has never run
    mock_prices = generate_mock_prices(200, 65000, symbol)
    return jsonify(mock_prices)

@app.route('/api/trades')
@login_required
def get_trades():
    limit = request.args.get('limit', 50, type=int)
    trades = get_trades_from_csv()
    return jsonify(trades[-limit:][::-1] if trades else [])

@app.route('/api/performance')
@login_required
def get_performance():
    trades = get_trades_from_csv()
    metrics = {
        'total_trades': len(trades),
        'total_buys': 0,
        'total_sells': 0,
        'total_profit': 0.0,
        'winning_trades': 0,
        'losing_trades': 0,
        'today_trades': 0,
        'today_profit': 0.0,
        'largest_profit': 0.0,
        'largest_loss': 0.0,
        'win_rate': 0
    }
    today = datetime.now().date()
    for trade in trades:
        if trade.get('side') == 'BUY':
            metrics['total_buys'] += 1
        elif trade.get('side') == 'SELL':
            metrics['total_sells'] += 1
            profit = trade.get('profit', 0)
            metrics['total_profit'] += profit
            if profit > 0:
                metrics['winning_trades'] += 1
            elif profit < 0:
                metrics['losing_trades'] += 1
            if profit > metrics['largest_profit']:
                metrics['largest_profit'] = profit
            if profit < metrics['largest_loss']:
                metrics['largest_loss'] = profit
            timestamp = trade.get('timestamp', '')
            if timestamp:
                try:
                    trade_date = datetime.fromisoformat(timestamp).date()
                    if trade_date == today:
                        metrics['today_trades'] += 1
                        metrics['today_profit'] += profit
                except:
                    pass
    if metrics['total_sells'] > 0:
        metrics['win_rate'] = (metrics['winning_trades'] / metrics['total_sells'] * 100)
    return jsonify(metrics)

@app.route('/api/logs')
@login_required
def get_logs():
    lines = request.args.get('lines', 100, type=int)
    logs = []
    log_file = Path('trading_bot.log')
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                for line in all_lines[-lines:]:
                    log_type = 'INFO'
                    if 'ERROR' in line:
                        log_type = 'ERROR'
                    elif 'BUY' in line or '📈' in line:
                        log_type = 'BUY'
                    elif 'SELL' in line or '📉' in line:
                        log_type = 'SELL'
                    elif 'WARNING' in line:
                        log_type = 'WARNING'
                    elif 'START' in line or 'STOP' in line:
                        log_type = 'SYSTEM'
                    logs.append({
                        'message': line.strip(),
                        'type': log_type,
                        'timestamp': line[:19] if len(line) > 19 else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
        except:
            pass
    if not logs:
        logs.append({
            'message': 'Bot is not running. Click START to begin trading.',
            'type': 'INFO',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify(logs[::-1])

@app.route('/api/control/start', methods=['POST'])
@login_required
def start_bot():
    global bot_process, bot_starting
    username = session.get('username')
    
    # Check if user has API keys configured
    api_key, api_secret = get_user_api_keys(username)
    if not api_key or not api_secret:
        return jsonify({
            'success': False, 
            'message': 'Please configure your API keys first'
        })
    
    try:
        data = request.get_json() or {}
        symbol = data.get('symbol')
        if symbol:
            try:
                os.environ['TRADING_SYMBOL'] = symbol
                print(f"Symbol changed to: {symbol}")
            except Exception as e:
                print(f"Error updating symbol: {e}")
        
        cleanup_stale_pid()
        pid_file = Path('bot.pid')
        if pid_file.exists():
            return jsonify({'success': False, 'message': 'Bot is already running'})
        if not Path('main.py').exists():
            return jsonify({'success': False, 'message': 'main.py not found!'})
        
        bot_starting = True
        if os.name == 'nt':
            bot_process = subprocess.Popen(
                [sys.executable, 'main.py'],
                cwd=Path(__file__).parent,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            bot_process = subprocess.Popen(
                [sys.executable, 'main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=Path(__file__).parent,
                start_new_session=True
            )
        print(f"Bot process started with PID: {bot_process.pid}")
        time.sleep(3)
        if pid_file.exists():
            print("Bot started successfully!")
            return jsonify({
                'success': True, 
                'message': 'Bot started successfully!',
                'starting': False
            })
        else:
            if bot_process.poll() is not None:
                print(f"Bot process exited with code: {bot_process.poll()}")
                bot_starting = False
                return jsonify({'success': False, 'message': 'Bot failed to start. Check the console for errors.'})
            else:
                return jsonify({
                    'success': True, 
                    'message': 'Bot is starting up...',
                    'starting': True
                })
    except Exception as e:
        bot_starting = False
        print(f"Error starting bot: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/control/stop', methods=['POST'])
@login_required
def stop_bot():
    global bot_starting, bot_data_cache, bot_process
    try:
        pid_file = Path('bot.pid')
        if not pid_file.exists():
            return jsonify({'success': False, 'message': 'Bot is not running'})
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        print(f"Stopping bot with PID: {pid}")
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(pid)], capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
        except:
            pass
        for i in range(10):
            if not is_process_running(pid):
                break
            time.sleep(1)
        if is_process_running(pid):
            print("Force killing bot process")
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
            else:
                os.kill(pid, signal.SIGKILL)
        pid_file.unlink()
        if pause_file.exists():
            pause_file.unlink()
        bot_starting = False
        bot_data_cache = {'price': None, 'balance': None, 'position': None, 'last_update': 0, 'symbol': None, 'username': None}
        print("Bot stopped successfully")
        return jsonify({'success': True, 'message': 'Bot stopped successfully'})
    except Exception as e:
        print(f"Error stopping bot: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/control/pause', methods=['POST'])
@login_required
def pause_bot():
    try:
        pid_file = Path('bot.pid')
        if not pid_file.exists():
            return jsonify({'success': False, 'message': 'Bot is not running'})
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        if not is_process_running(pid):
            pid_file.unlink()
            return jsonify({'success': False, 'message': 'Bot is not running'})
        pause_file.touch()
        if os.name != 'nt':
            os.kill(pid, signal.SIGSTOP)
        return jsonify({'success': True, 'message': 'Bot paused successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/control/resume', methods=['POST'])
@login_required
def resume_bot():
    try:
        pid_file = Path('bot.pid')
        if not pid_file.exists():
            return jsonify({'success': False, 'message': 'Bot is not running'})
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        if not is_process_running(pid):
            pid_file.unlink()
            return jsonify({'success': False, 'message': 'Bot is not running'})
        if pause_file.exists():
            pause_file.unlink()
        if os.name != 'nt':
            os.kill(pid, signal.SIGCONT)
        return jsonify({'success': True, 'message': 'Bot resumed successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/referral/stats')
@login_required
def get_referral_stats():
    if not referral_manager:
        return jsonify({'success': False, 'message': 'Referral system not available'})
    stats = referral_manager.get_referral_stats()
    return jsonify(stats)

@app.route('/api/referral/user/<username>')
@login_required
def get_user_referrals(username):
    if not referral_manager:
        return jsonify({'success': False, 'message': 'Referral system not available'})
    if session.get('username') != username:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    # Get user data directly to ensure email is included
    user_data = referral_manager.users.get(username, {})
    summary = referral_manager.get_user_summary(username)
    
    if not summary:
        return jsonify({'success': False, 'message': 'User not found'})
    
    # Ensure email is included
    summary['email'] = user_data.get('email', '')
    
    return jsonify({'success': True, 'data': summary})

@app.route('/api/referral/check/<code>')
def check_referral_code(code):
    if not referral_manager:
        return jsonify({'success': False, 'message': 'Referral system not available'})
    user = referral_manager.find_user_by_referral_code(code)
    if user:
        return jsonify({'success': True, 'valid': True, 'username': user.get('username')})
    else:
        return jsonify({'success': True, 'valid': False})

@app.route('/api/symbol/change', methods=['POST'])
@login_required
def change_symbol():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    symbol = data.get('symbol')
    if not symbol:
        return jsonify({'success': False, 'message': 'Symbol required'})
    try:
        os.environ['TRADING_SYMBOL'] = symbol
        return jsonify({'success': True, 'message': f'Symbol changed to {symbol}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    
# Add these routes to web_server.py after the existing routes
@app.route('/api/price/historical')
@login_required
def get_historical_prices():
    """Fetch historical price data from Binance"""
    symbol = request.args.get('symbol', 'BTCUSDT')
    interval = request.args.get('interval', '1h')  # 1m, 5m, 15m, 1h, 4h, 1d
    limit = request.args.get('limit', 100, type=int)
    
    username = session.get('username')
    api_key, api_secret = get_user_api_keys(username)
    
    if not api_key or not api_secret:
        return jsonify({'success': False, 'message': 'API keys not configured'})
    
    try:
        from binance.client import Client
        from binance.exceptions import BinanceAPIException
        
        client = Client(api_key, api_secret)
        
        # Set testnet if configured
        user_data = referral_manager.users.get(username, {})
        if user_data.get('use_testnet', True):
            client.API_URL = 'https://testnet.binance.vision/api'
            client.WAPI_URL = 'https://testnet.binance.vision/wapi'
        
        # Get klines (candlestick data)
        klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
        
        prices = []
        for kline in klines:
            timestamp = datetime.fromtimestamp(kline[0] / 1000)
            price = float(kline[4])  # Closing price
            prices.append({
                'time': timestamp.isoformat(),
                'price': price
            })
        
        return jsonify(prices)
        
    except BinanceAPIException as e:
        return jsonify({'success': False, 'message': f'Binance API error: {e.message}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error fetching historical data: {str(e)}'})

@app.route('/api/user/profile', methods=['PUT'])
@login_required
def update_user_profile():
    """Update user profile (email, password)"""
    username = session.get('username')
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    if not referral_manager or username not in referral_manager.users:
        return jsonify({'success': False, 'message': 'User not found'})
    
    user_data = referral_manager.users[username]
    
    # Update email
    if 'email' in data and data['email']:
        user_data['email'] = data['email']
        # Also update in the user's data for the summary
        user_data['email'] = data['email']
    
    # Update password
    if 'password' in data and data['password']:
        user_data['password'] = data['password']
    
    referral_manager._save_users()
    
    # Return updated user data
    summary = referral_manager.get_user_summary(username)
    summary['email'] = user_data.get('email', '')
    
    return jsonify({
        'success': True, 
        'message': 'Profile updated successfully',
        'user': summary
    })

@app.route('/api/user/api-keys/test', methods=['POST'])
@login_required
def test_api_keys_route():
    """Test API keys without saving them"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    api_key = data.get('api_key', '').strip()
    api_secret = data.get('api_secret', '').strip()
    use_testnet = data.get('testnet', True)
    
    if not api_key or not api_secret:
        return jsonify({'success': False, 'message': 'API Key and Secret are required'})
    
    try:
        from binance.client import Client
        from binance.exceptions import BinanceAPIException
        
        test_client = Client(api_key, api_secret)
        if use_testnet:
            test_client.API_URL = 'https://testnet.binance.vision/api'
            test_client.WAPI_URL = 'https://testnet.binance.vision/wapi'
        
        test_client.ping()
        test_client.get_account()
        
        return jsonify({'success': True, 'message': 'API keys are valid and working!'})
        
    except BinanceAPIException as e:
        return jsonify({'success': False, 'message': f'Invalid API keys: {e.message}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error testing API keys: {str(e)}'})

@app.route('/api/user/settings', methods=['PUT'])

@login_required
def update_user_settings():
    """Update user trading settings"""
    username = session.get('username')
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    if not referral_manager or username not in referral_manager.users:
        return jsonify({'success': False, 'message': 'User not found'})
    
    user_data = referral_manager.users[username]
    
    # Initialize settings if not exists
    if 'settings' not in user_data:
        user_data['settings'] = {}
    
    # Update settings
    settings = user_data['settings']
    if 'symbol' in data:
        settings['symbol'] = data['symbol']
    if 'total_capital' in data:
        settings['total_capital'] = data['total_capital']
    if 'base_position' in data:
        settings['base_position'] = data['base_position']
    if 'dump_thresholds' in data:
        settings['dump_thresholds'] = data['dump_thresholds']
    if 'spike_thresholds' in data:
        settings['spike_thresholds'] = data['spike_thresholds']
    
    referral_manager._save_users()
    return jsonify({'success': True, 'message': 'Settings saved successfully'})    

def run_server(port=5000):
    cleanup_stale_pid()
    print(f"\n{'='*60}")
    print(f"🤖 Trading Bot Dashboard")
    print(f"{'='*60}")
    print(f"📍 URL: http://localhost:{port}")
    print(f"📊 Multi-user trading dashboard")
    print(f"🔒 Each user has their own API keys")
    print(f"⚡ Press Ctrl+C to stop the server")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    run_server()