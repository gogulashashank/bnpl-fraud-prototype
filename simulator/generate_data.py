import json
import uuid
import random
from datetime import datetime, timedelta
from faker import Faker
import pandas as pd
from typologies import (
    generate_ato_events,
    generate_synthetic_identity_events,
    generate_velocity_abuse_events,
    generate_refund_abuse_events,
    generate_money_laundering_loop_events
)

fake = Faker()

def generate_base_user():
    return {
        "user_id": f"usr_{uuid.uuid4().hex[:10]}",
        "name": fake.name(),
        "email": fake.email(),
        "phone": fake.phone_number(),
        "dob": fake.date_of_birth(minimum_age=18, maximum_age=80).isoformat(),
        "address": fake.address().replace('\n', ', '),
        "kyc_status": "VERIFIED"
    }

def generate_clean_events(user, device_id, ip_address, start_time):
    events = []
    current_time = start_time
    
    # 1. Login
    events.append({
        "event_id": str(uuid.uuid4()),
        "timestamp": current_time.isoformat(),
        "user_id": user["user_id"],
        "event_type": "LOGIN",
        "device_id": device_id,
        "ip_address": ip_address,
        "amount": 0.0,
        "merchant": "",
        "status": "SUCCESS"
    })
    
    # 2. Few normal transactions
    for i in range(random.randint(1, 4)):
        current_time += timedelta(days=random.randint(1, 5), hours=random.randint(1, 12))
        events.append({
            "event_id": str(uuid.uuid4()),
            "timestamp": current_time.isoformat(),
            "user_id": user["user_id"],
            "event_type": "TRANSACTION",
            "device_id": device_id,
            "ip_address": ip_address,
            "amount": round(random.uniform(10, 150), 2),
            "merchant": fake.company(),
            "status": "SUCCESS"
        })
        
    return events

def main():
    print("Generating synthetic fraud data...")
    num_users = 100
    start_date = datetime(2023, 1, 1)
    
    users = []
    all_events = []
    
    # Generate clean users
    for _ in range(num_users):
        u = generate_base_user()
        users.append(u)
        
        device_id = f"dev_{uuid.uuid4().hex[:8]}"
        ip_address = fake.ipv4()
        
        # Determine if this user becomes a fraud victim or actor
        fraud_type = random.choices(
            ["CLEAN", "ATO", "VELOCITY", "REFUND", "ML_LOOP"], 
            weights=[80, 5, 5, 5, 5], 
            k=1
        )[0]
        
        user_start_time = start_date + timedelta(days=random.randint(0, 30))
        
        if fraud_type == "CLEAN":
            events = generate_clean_events(u, device_id, ip_address, user_start_time)
            for e in events: e["is_fraud"] = 0
            all_events.extend(events)
        elif fraud_type == "ATO":
            # Some clean events first, then ATO
            events = generate_clean_events(u, device_id, ip_address, user_start_time)
            for e in events: e["is_fraud"] = 0
            all_events.extend(events)
            
            ato_time = datetime.fromisoformat(events[-1]["timestamp"]) + timedelta(days=2)
            ato_events = generate_ato_events(u, None, None, ato_time)
            for e in ato_events: e["is_fraud"] = 1
            all_events.extend(ato_events)
        elif fraud_type == "VELOCITY":
            events = generate_velocity_abuse_events(u, device_id, ip_address, user_start_time)
            for e in events: e["is_fraud"] = 1
            all_events.extend(events)
        elif fraud_type == "REFUND":
            events = generate_refund_abuse_events(u, device_id, ip_address, user_start_time)
            for e in events: e["is_fraud"] = 1
            all_events.extend(events)
        elif fraud_type == "ML_LOOP":
            # Need 3 users for loop, we will just generate 2 extra synthetic ones here for simplicity
            u2, u3 = generate_base_user(), generate_base_user()
            users.extend([u2, u3])
            events = generate_money_laundering_loop_events([u, u2, u3], device_id, ip_address, user_start_time)
            for e in events: e["is_fraud"] = 1
            all_events.extend(events)

    # Generate Synthetic Identity Ring
    synth_device = f"dev_{uuid.uuid4().hex[:8]}"
    synth_ip = fake.ipv4()
    synth_start = start_date + timedelta(days=15)
    synth_events, synth_user_ids = generate_synthetic_identity_events(synth_device, synth_ip, synth_start)
    for e in synth_events: e["is_fraud"] = 1
    all_events.extend(synth_events)
    
    for uid in synth_user_ids:
        u = generate_base_user()
        u["user_id"] = uid
        u["email"] = f"{fake.word()}@disposable.com"
        users.append(u)
        
    # Sort events by timestamp
    all_events.sort(key=lambda x: x["timestamp"])
    
    # Save to CSV
    events_df = pd.DataFrame(all_events)
    users_df = pd.DataFrame(users)
    
    events_df.to_csv("transactions.csv", index=False)
    users_df.to_csv("users.csv", index=False)
    
    print(f"Generated {len(users)} users and {len(all_events)} events.")
    print("Saved to transactions.csv and users.csv")

if __name__ == "__main__":
    main()
