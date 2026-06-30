import sqlite3
import json
from datetime import datetime, timedelta

class FeatureStore:
    def __init__(self, db_path="feature_store.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()
        
    def _init_db(self):
        # We store events to compute sliding window features
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                user_id TEXT,
                device_id TEXT,
                ip_address TEXT,
                event_type TEXT,
                amount REAL,
                timestamp DATETIME
            )
        ''')
        
        # We store user profiles
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                kyc_status TEXT,
                email TEXT
            )
        ''')
        self.conn.commit()
        
    def add_user(self, user_id, kyc_status, email):
        self.cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, kyc_status, email)
            VALUES (?, ?, ?)
        ''', (user_id, kyc_status, email))
        self.conn.commit()
        
    def add_event(self, event):
        self.cursor.execute('''
            INSERT INTO events (event_id, user_id, device_id, ip_address, event_type, amount, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            event["event_id"],
            event["user_id"],
            event["device_id"],
            event["ip_address"],
            event["event_type"],
            event.get("amount", 0.0),
            event["timestamp"]
        ))
        self.conn.commit()
        
    def get_user_features(self, user_id, current_time_str):
        """
        Calculates features for a user based on historical events up to current_time.
        """
        current_time = datetime.fromisoformat(current_time_str)
        window_start_24h = (current_time - timedelta(hours=24)).isoformat()
        window_start_1h = (current_time - timedelta(hours=1)).isoformat()
        
        # Velocity Features (Last 24h)
        self.cursor.execute('''
            SELECT COUNT(*), SUM(amount) FROM events 
            WHERE user_id = ? AND timestamp >= ? AND timestamp <= ?
        ''', (user_id, window_start_24h, current_time_str))
        res_24h = self.cursor.fetchone()
        tx_count_24h = res_24h[0] or 0
        tx_amount_24h = res_24h[1] or 0.0
        
        # Velocity Features (Last 1h)
        self.cursor.execute('''
            SELECT COUNT(*) FROM events 
            WHERE user_id = ? AND timestamp >= ? AND timestamp <= ?
        ''', (user_id, window_start_1h, current_time_str))
        tx_count_1h = self.cursor.fetchone()[0] or 0
        
        # Distinct devices/IPs used by user in last 30 days
        window_start_30d = (current_time - timedelta(days=30)).isoformat()
        self.cursor.execute('''
            SELECT COUNT(DISTINCT device_id), COUNT(DISTINCT ip_address) FROM events 
            WHERE user_id = ? AND timestamp >= ?
        ''', (user_id, window_start_30d))
        res_distinct = self.cursor.fetchone()
        distinct_devices = res_distinct[0] or 0
        distinct_ips = res_distinct[1] or 0
        
        # Check if email is disposable
        self.cursor.execute('SELECT email, kyc_status FROM users WHERE user_id = ?', (user_id,))
        user_res = self.cursor.fetchone()
        is_disposable = False
        kyc_status = "UNKNOWN"
        if user_res:
            email, kyc_status = user_res
            if email and "disposable.com" in email:
                is_disposable = True
                
        return {
            "tx_count_24h": tx_count_24h,
            "tx_amount_24h": tx_amount_24h,
            "tx_count_1h": tx_count_1h,
            "distinct_devices_30d": distinct_devices,
            "distinct_ips_30d": distinct_ips,
            "is_disposable_email": is_disposable,
            "kyc_status": kyc_status
        }
        
    def get_device_features(self, device_id, current_time_str):
        """
        Calculates features for a specific device.
        """
        # How many distinct users have used this device?
        self.cursor.execute('''
            SELECT COUNT(DISTINCT user_id) FROM events 
            WHERE device_id = ?
        ''', (device_id,))
        distinct_users = self.cursor.fetchone()[0] or 0
        
        return {
            "distinct_users_on_device": distinct_users
        }
