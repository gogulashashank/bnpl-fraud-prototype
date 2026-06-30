import pytest
import os
from datetime import datetime, timedelta
from engine.feature_store import FeatureStore

@pytest.fixture
def store():
    db_path = "test_feature_store.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    store = FeatureStore(db_path=db_path)
    yield store
    if os.path.exists(db_path):
        os.remove(db_path)

def test_add_user_and_event(store):
    store.add_user("usr_123", "VERIFIED", "test@clean.com")
    
    event = {
        "event_id": "evt_1",
        "user_id": "usr_123",
        "device_id": "dev_1",
        "ip_address": "1.1.1.1",
        "event_type": "TRANSACTION",
        "amount": 100.0,
        "timestamp": datetime(2023, 1, 1, 12, 0).isoformat()
    }
    
    store.add_event(event)
    
    user_features = store.get_user_features("usr_123", datetime(2023, 1, 1, 12, 1).isoformat())
    
    assert user_features["tx_count_1h"] == 1
    assert user_features["tx_amount_24h"] == 100.0
    assert user_features["distinct_devices_30d"] == 1
    assert user_features["is_disposable_email"] == False

def test_device_features(store):
    store.add_user("usr_1", "VERIFIED", "u1@clean.com")
    store.add_user("usr_2", "VERIFIED", "u2@clean.com")
    
    ts = datetime(2023, 1, 1, 12, 0).isoformat()
    
    # Both users use the same device
    store.add_event({
        "event_id": "evt_1", "user_id": "usr_1", "device_id": "dev_bad",
        "ip_address": "1.1.1.1", "event_type": "LOGIN", "amount": 0, "timestamp": ts
    })
    store.add_event({
        "event_id": "evt_2", "user_id": "usr_2", "device_id": "dev_bad",
        "ip_address": "1.1.1.1", "event_type": "LOGIN", "amount": 0, "timestamp": ts
    })
    
    device_features = store.get_device_features("dev_bad", ts)
    assert device_features["distinct_users_on_device"] == 2
