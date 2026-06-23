#!/usr/bin/env python3
"""
Monitoring script to check bot status and performance
Works without psutil (uses system commands)
"""

import os
import sys
import csv
import subprocess
from datetime import datetime
from pathlib import Path
from colorama import init, Fore, Style

init(autoreset=True)


def check_pid_file():
    """Check if PID file exists and process is running"""
    pid_file = Path('bot.pid')
    
    if not pid_file.exists():
        return False, None
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process is running on Windows
        if os.name == 'nt':
            result = subprocess.run(
                f'tasklist /FI "PID eq {pid}" /FO CSV',
                capture_output=True,
                text=True,
                shell=True
            )
            if str(pid) in result.stdout:
                return True, pid
        else:  # Linux/Mac
            try:
                os.kill(pid, 0)
                return True, pid
            except OSError:
                pass
    except:
        pass
    
    return False, None


def check_process_by_name():
    """Check for python processes running main.py"""
    try:
        if os.name == 'nt':  # Windows
            # Method 1: Using tasklist
            result = subprocess.run(
                'tasklist /FI "IMAGENAME eq python.exe" /FO CSV',
                capture_output=True,
                text=True,
                shell=True
            )
            if 'python.exe' in result.stdout:
                # Check command line for main.py
                cmd_result = subprocess.run(
                    'wmic process where name="python.exe" get commandline',
                    capture_output=True,
                    text=True,
                    shell=True
                )
                if 'main.py' in cmd_result.stdout.lower():
                    return True
            
            # Method 2: Check for python processes directly
            result = subprocess.run(
                'wmic process where name="python.exe" get processid',
                capture_output=True,
                text=True,
                shell=True
            )
            return 'python.exe' in result.stdout
            
        else:  # Linux/Mac
            result = subprocess.run(
                ['pgrep', '-f', 'python.*main.py'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
            
    except Exception:
        return False


def get_today_stats():
    """Get today's trading stats"""
    trades_file = Path('data/trades_history.csv')
    
    if not trades_file.exists():
        return None
    
    today = datetime.now().date()
    trades_today = 0
    buys_today = 0
    sells_today = 0
    total_profit = 0.0
    
    try:
        with open(trades_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    timestamp = row.get('timestamp', '')
                    if timestamp:
                        # Try different date formats
                        trade_date = None
                        try:
                            trade_date = datetime.fromisoformat(timestamp).date()
                        except:
                            try:
                                trade_date = datetime.strptime(timestamp[:10], '%Y-%m-%d').date()
                            except:
                                continue
                        
                        if trade_date == today:
                            trades_today += 1
                            if row.get('side') == 'BUY':
                                buys_today += 1
                            elif row.get('side') == 'SELL':
                                sells_today += 1
                                try:
                                    total_profit += float(row.get('profit', 0))
                                except:
                                    pass
                except:
                    continue
    except Exception as e:
        print(f"Error reading trades: {e}")
    
    return {
        'trades': trades_today,
        'buys': buys_today,
        'sells': sells_today,
        'profit': total_profit
    }


def get_last_log_lines(lines=10):
    """Get recent log lines"""
    log_file = Path('logs/trading_bot.log')
    
    if not log_file.exists():
        return []
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            return all_lines[-lines:]
    except:
        return []


def main():
    """Main monitor function"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  BINANCE TRADING BOT MONITOR")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    
    # Check if bot is running
    is_running = False
    pid = None
    
    # Method 1: Check PID file
    pid_exists, found_pid = check_pid_file()
    if pid_exists:
        is_running = True
        pid = found_pid
    
    # Method 2: Check processes if PID file didn't work
    if not is_running:
        is_running = check_process_by_name()
    
    if is_running:
        print(f"{Fore.GREEN}✅ Bot Status: RUNNING{Style.RESET_ALL}")
        if pid:
            print(f"   Process ID: {pid}")
    else:
        print(f"{Fore.RED}❌ Bot Status: STOPPED{Style.RESET_ALL}")
        print("   To start the bot, run: python main.py")
    
    # Get today's stats
    stats = get_today_stats()
    if stats and stats['trades'] > 0:
        print(f"\n{Fore.YELLOW}📊 Today's Performance:{Style.RESET_ALL}")
        print(f"   📈 Total Trades: {stats['trades']}")
        print(f"   📥 Buys: {stats['buys']}")
        print(f"   📤 Sells: {stats['sells']}")
        profit_color = Fore.GREEN if stats['profit'] >= 0 else Fore.RED
        print(f"   💰 Profit: {profit_color}${stats['profit']:.2f}{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.YELLOW}📊 Today's Performance:{Style.RESET_ALL}")
        print(f"   No trades executed today")
    
    # Show last few log entries
    log_lines = get_last_log_lines(5)
    if log_lines:
        print(f"\n{Fore.CYAN}📝 Last Log Entries:{Style.RESET_ALL}")
        for line in log_lines[-5:]:
            line = line.strip()
            if 'ERROR' in line:
                print(f"   {Fore.RED}{line[:100]}{Style.RESET_ALL}")
            elif 'BUY' in line or 'SELL' in line:
                print(f"   {Fore.GREEN}{line[:100]}{Style.RESET_ALL}")
            else:
                print(f"   {line[:100]}")
    else:
        print(f"\n{Fore.CYAN}📝 Last Log Entries:{Style.RESET_ALL}")
        print(f"   No log file found")
    
    # Check trades file
    trades_file = Path('data/trades_history.csv')
    if trades_file.exists():
        file_size = trades_file.stat().st_size
        if file_size > 0:
            print(f"\n{Fore.GREEN}📁 Trade History: {trades_file} ({file_size} bytes){Style.RESET_ALL}")
        else:
            print(f"\n{Fore.YELLOW}📁 Trade History: Empty file{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.YELLOW}📁 Trade History: Not created yet{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


if __name__ == '__main__':
    main()