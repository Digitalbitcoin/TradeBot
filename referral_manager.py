# referral_manager.py - Updated with API key support
"""
Referral Manager - Handles referral tracking and bonuses
"""

import json
import csv
import os
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from config import config
from utils.logger import get_logger

logger = get_logger(__name__)

class ReferralManager:
    """Manages referral system and bonuses"""
    
    def __init__(self):
        self.users_file = 'data/users.json'
        self.referrals_file = 'data/referrals.csv'
        self._ensure_data_directory()
        self._init_referral_files()
        self.users = self._load_users()
    
    def _ensure_data_directory(self):
        os.makedirs('data', exist_ok=True)
    
    def _init_referral_files(self):
        if not os.path.exists(self.referrals_file):
            with open(self.referrals_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'referrer_id', 'referred_id', 
                    'bonus_amount', 'commission', 'status'
                ])
    
    def _load_users(self) -> Dict:
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_users(self):
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving users: {e}")
    
    def _generate_referral_code(self) -> str:
        existing_codes = set()
        for user_data in self.users.values():
            code = user_data.get('referral_code')
            if code:
                existing_codes.add(code)
        
        max_attempts = 1000
        for _ in range(max_attempts):
            code = str(random.randint(10000000, 99999999))
            if code not in existing_codes:
                return code
        return str(int(time.time()))[-8:]
    
    def register_user(self, username: str, password: str, email: str = None, 
                      referral_code: str = None) -> Dict:
        if username in self.users:
            return {'success': False, 'message': 'Username already exists'}
        
        user_id = f"user_{int(time.time())}_{random.randint(1000, 9999)}"
        user_referral_code = self._generate_referral_code()
        
        user_data = {
            'id': user_id,
            'username': username,
            'password': password,
            'email': email,
            'referral_code': user_referral_code,
            'referred_by': None,
            'balance': 0.0,
            'total_bonus': 0.0,
            'referrals': [],
            'registration_date': datetime.now().isoformat(),
            'active': True,
            # API key fields
            'api_key': None,
            'api_secret': None,
            'use_testnet': True,
            'has_api_keys': False
        }
        
        if referral_code and config.ENABLE_REFERRAL:
            referrer = self.find_user_by_referral_code(referral_code)
            if referrer:
                user_data['referred_by'] = referrer['id']
                referrer['referrals'].append(user_id)
                
                bonus = config.REFERRAL_BONUS
                referrer['balance'] += bonus
                referrer['total_bonus'] += bonus
                
                self._record_referral(referrer['id'], user_id, bonus, 'bonus')
                logger.info(f"Referral bonus: {referrer['username']} earned ${bonus}")
                
                self._save_users()
            else:
                return {'success': False, 'message': 'Invalid referral code'}
        
        self.users[username] = user_data
        self._save_users()
        logger.info(f"New user registered: {username}")
        
        return {
            'success': True,
            'message': 'Registration successful',
            'user': {
                'username': username,
                'user_id': user_id,
                'referral_code': user_referral_code,
                'referred_by': user_data['referred_by']
            }
        }
    
    def find_user_by_referral_code(self, referral_code: str) -> Optional[Dict]:
        for username, user_data in self.users.items():
            if user_data.get('referral_code') == referral_code:
                return user_data
        return None
    
    def get_user_referrals(self, username: str) -> List[Dict]:
        if username not in self.users:
            return []
        
        user_data = self.users[username]
        referrals = []
        
        for referred_id in user_data.get('referrals', []):
            for other_username, other_data in self.users.items():
                if other_data.get('id') == referred_id:
                    referrals.append({
                        'username': other_username,
                        'registration_date': other_data.get('registration_date'),
                        'status': 'active' if other_data.get('active', True) else 'inactive'
                    })
                    break
        
        return referrals
    
    def _record_referral(self, referrer_id: str, referred_id: str, 
                         amount: float, status: str = 'pending'):
        try:
            with open(self.referrals_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    referrer_id,
                    referred_id,
                    f"{amount:.2f}",
                    '',
                    status
                ])
        except Exception as e:
            logger.error(f"Error recording referral: {e}")
    
    def calculate_referral_commission(self, username: str, trade_amount: float) -> float:
        if not config.ENABLE_REFERRAL:
            return 0.0
        
        if username not in self.users:
            return 0.0
        
        user_data = self.users[username]
        referrer_id = user_data.get('referred_by')
        
        if not referrer_id:
            return 0.0
        
        referrer_username = None
        for uname, data in self.users.items():
            if data.get('id') == referrer_id:
                referrer_username = uname
                break
        
        if not referrer_username:
            return 0.0
        
        commission = trade_amount * (config.REFERRAL_COMMISSION / 100)
        self.users[referrer_username]['balance'] += commission
        self._record_referral(referrer_id, user_data['id'], commission, 'commission')
        self._save_users()
        
        return commission
    
    def get_user_summary(self, username: str) -> Dict:
        if username not in self.users:
            return {}
        
        user_data = self.users[username]
        referrals = self.get_user_referrals(username)
        
        return {
            'username': username,
            'user_id': user_data.get('id'),
            'referral_code': user_data.get('referral_code'),
            'referred_by': user_data.get('referred_by'),
            'balance': user_data.get('balance', 0.0),
            'total_bonus': user_data.get('total_bonus', 0.0),
            'referral_count': len(referrals),
            'referrals': referrals,
            'registration_date': user_data.get('registration_date'),
            'active': user_data.get('active', True),
            'has_api_keys': bool(user_data.get('api_key') and user_data.get('api_secret')),
            'use_testnet': user_data.get('use_testnet', True)
        }
    
    def get_referral_stats(self) -> Dict:
        total_users = len(self.users)
        total_referrals = 0
        total_bonus = 0.0
        
        for user_data in self.users.values():
            total_referrals += len(user_data.get('referrals', []))
            total_bonus += user_data.get('total_bonus', 0.0)
        
        return {
            'total_users': total_users,
            'total_referrals': total_referrals,
            'total_bonus_distributed': total_bonus,
            'referral_enabled': config.ENABLE_REFERRAL,
            'referral_bonus': config.REFERRAL_BONUS,
            'referral_commission': config.REFERRAL_COMMISSION
        }
    
    def authenticate_user(self, username: str, password: str) -> bool:
        if username not in self.users:
            return False
        return self.users[username].get('password') == password
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        for username, user_data in self.users.items():
            if user_data.get('id') == user_id:
                return user_data
        return None
    
    # In referral_manager.py, update the get_user_summary method:

def get_user_summary(self, username):
    """Get user summary including referrals and earnings"""
    if username not in self.users:
        return None
    
    user = self.users[username]
    
    # Get referrals list
    referrals = []
    for ref_username in user.get('referrals', []):
        if ref_username in self.users:
            ref_user = self.users[ref_username]
            referrals.append({
                'username': ref_username,
                'email': ref_user.get('email', ''),
                'registration_date': ref_user.get('registration_date', ''),
                'status': 'active'
            })
    
    return {
        'username': username,
        'email': user.get('email', ''),  # Make sure email is included
        'referral_code': user.get('referral_code', ''),
        'referral_count': len(user.get('referrals', [])),
        'balance': user.get('balance', 0),
        'total_bonus': user.get('total_bonus', 0),
        'referrals': referrals,
        'registration_date': user.get('registration_date', ''),
        'has_api_keys': bool(user.get('api_key') and user.get('api_secret'))
    }