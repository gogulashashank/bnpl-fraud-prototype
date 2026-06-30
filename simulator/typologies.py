import random
import uuid
from datetime import datetime, timedelta

def generate_ato_events(user, device_pool, ip_pool, start_time):
    """
    Simulates Account Takeover.
    Signals: Sudden device/browser change, new IP geolocation, 
    password reset (or login) followed by high-value transactions.
    """
    events = []
    # Hacker uses a completely new device and IP
    hacker_device = f"dev_{uuid.uuid4().hex[:8]}"
    hacker_ip = f"193.10.{random.randint(1, 255)}.{random.randint(1, 255)}"
    
    current_time = start_time
    
    # 1. Login event with new device/IP
    events.append({
        "event_id": str(uuid.uuid4()),
        "timestamp": current_time.isoformat(),
        "user_id": user["user_id"],
        "event_type": "LOGIN",
        "device_id": hacker_device,
        "ip_address": hacker_ip,
        "amount": 0.0,
        "merchant": "",
        "status": "SUCCESS"
    })
    
    # 2. Burst of high-value transactions or BNPL application
    for i in range(3):
        current_time += timedelta(minutes=random.randint(1, 5))
        events.append({
            "event_id": str(uuid.uuid4()),
            "timestamp": current_time.isoformat(),
            "user_id": user["user_id"],
            "event_type": "TRANSACTION",
            "device_id": hacker_device,
            "ip_address": hacker_ip,
            "amount": round(random.uniform(500, 1500), 2),
            "merchant": "Luxury Electronics",
            "status": "SUCCESS"
        })
    return events

def generate_synthetic_identity_events(device_id, ip_address, start_time, base_email_domain="disposable.com"):
    """
    Simulates Synthetic Identity BNPL Fraud.
    Signals: Multiple new accounts sharing device/IP, disposable emails, applying for BNPL limits.
    """
    events = []
    user_ids = []
    
    current_time = start_time
    
    # Generate 5 synthetic identities sharing the same device and IP
    for i in range(5):
        synth_user_id = f"usr_synth_{uuid.uuid4().hex[:6]}"
        user_ids.append(synth_user_id)
        current_time += timedelta(hours=random.randint(1, 4))
        
        # BNPL Application
        events.append({
            "event_id": str(uuid.uuid4()),
            "timestamp": current_time.isoformat(),
            "user_id": synth_user_id,
            "event_type": "BNPL_APPLICATION",
            "device_id": device_id,
            "ip_address": ip_address,
            "amount": 1000.0, # Requesting limit
            "merchant": "",
            "status": "PENDING" # Will be scored
        })
        
    return events, user_ids

def generate_velocity_abuse_events(user, device_id, ip_address, start_time):
    """
    Simulates Transaction Velocity/Amount Abuse.
    Signals: Many small authorisations then one large purchase, bursts of transactions.
    """
    events = []
    current_time = start_time
    
    # Card testing (small amounts)
    for i in range(5):
        current_time += timedelta(minutes=random.randint(1, 2))
        events.append({
            "event_id": str(uuid.uuid4()),
            "timestamp": current_time.isoformat(),
            "user_id": user["user_id"],
            "event_type": "TRANSACTION",
            "device_id": device_id,
            "ip_address": ip_address,
            "amount": round(random.uniform(0.5, 2.5), 2),
            "merchant": "Digital Goods Store",
            "status": "SUCCESS"
        })
        
    # Large transaction
    current_time += timedelta(minutes=5)
    events.append({
        "event_id": str(uuid.uuid4()),
        "timestamp": current_time.isoformat(),
        "user_id": user["user_id"],
        "event_type": "TRANSACTION",
        "device_id": device_id,
        "ip_address": ip_address,
        "amount": round(random.uniform(800, 2000), 2),
        "merchant": "High-Value Retailer",
        "status": "SUCCESS"
    })
    
    return events

def generate_refund_abuse_events(user, device_id, ip_address, start_time):
    """
    Simulates Refund / Chargeback Abuse.
    Signals: High refund ratio, consistent disputes on specific merchants.
    """
    events = []
    current_time = start_time
    
    # 3 purchases followed by 3 refunds
    for i in range(3):
        current_time += timedelta(days=random.randint(1, 3))
        amount = round(random.uniform(100, 300), 2)
        txn_id = str(uuid.uuid4())
        
        events.append({
            "event_id": txn_id,
            "timestamp": current_time.isoformat(),
            "user_id": user["user_id"],
            "event_type": "TRANSACTION",
            "device_id": device_id,
            "ip_address": ip_address,
            "amount": amount,
            "merchant": "Fashion Retailer",
            "status": "SUCCESS"
        })
        
        # Refund event a few days later
        current_time += timedelta(days=random.randint(2, 5))
        events.append({
            "event_id": str(uuid.uuid4()),
            "timestamp": current_time.isoformat(),
            "user_id": user["user_id"],
            "event_type": "REFUND",
            "device_id": device_id,
            "ip_address": ip_address,
            "amount": amount, # Full refund
            "merchant": "Fashion Retailer",
            "status": "SUCCESS",
            "linked_txn_id": txn_id
        })
        
    return events

def generate_money_laundering_loop_events(users, device_id, ip_address, start_time):
    """
    Simulates Money Laundering via Wallet Looping.
    Signals: Circular flows between wallets, fast movement from BNPL to wallet.
    """
    events = []
    current_time = start_time
    
    # Suppose users[0] funds via BNPL, then transfers to users[1], then users[2], then cashes out
    u1, u2, u3 = users[0], users[1], users[2]
    
    # 1. u1 gets BNPL loan
    events.append({
        "event_id": str(uuid.uuid4()),
        "timestamp": current_time.isoformat(),
        "user_id": u1["user_id"],
        "event_type": "BNPL_APPLICATION",
        "device_id": device_id,
        "ip_address": ip_address,
        "amount": 2000.0,
        "merchant": "",
        "status": "APPROVED"
    })
    
    current_time += timedelta(minutes=10)
    # 2. P2P u1 to u2
    events.append({
        "event_id": str(uuid.uuid4()),
        "timestamp": current_time.isoformat(),
        "user_id": u1["user_id"],
        "event_type": "P2P_TRANSFER",
        "device_id": device_id, # Same device ring
        "ip_address": ip_address,
        "amount": 1950.0,
        "beneficiary_id": u2["user_id"],
        "status": "SUCCESS"
    })
    
    current_time += timedelta(minutes=15)
    # 3. P2P u2 to u3
    events.append({
        "event_id": str(uuid.uuid4()),
        "timestamp": current_time.isoformat(),
        "user_id": u2["user_id"],
        "event_type": "P2P_TRANSFER",
        "device_id": device_id,
        "ip_address": ip_address,
        "amount": 1900.0,
        "beneficiary_id": u3["user_id"],
        "status": "SUCCESS"
    })
    
    current_time += timedelta(hours=1)
    # 4. u3 cashes out to crypto or high-risk PSP
    events.append({
        "event_id": str(uuid.uuid4()),
        "timestamp": current_time.isoformat(),
        "user_id": u3["user_id"],
        "event_type": "CASHOUT",
        "device_id": device_id,
        "ip_address": ip_address,
        "amount": 1850.0,
        "merchant": "Crypto Exchange X",
        "status": "SUCCESS"
    })
    
    return events
