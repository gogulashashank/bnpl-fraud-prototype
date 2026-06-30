import pytest
from engine.rules import evaluate_rules

def test_ato_rule():
    user_features = {
        "distinct_devices_30d": 3,
        "tx_count_1h": 1,
        "tx_amount_24h": 100,
        "is_disposable_email": False
    }
    device_features = {"distinct_users_on_device": 1}
    current_event = {"amount": 600}
    
    rules, score, interventions = evaluate_rules(user_features, device_features, current_event)
    
    assert "ATO_SUSPICION_HIGH_VALUE_NEW_DEVICE" in rules
    assert score >= 40
    assert "MFA Request (Step-up Auth)" in interventions

def test_synthetic_identity_rule():
    user_features = {
        "distinct_devices_30d": 1,
        "tx_count_1h": 1,
        "tx_amount_24h": 50,
        "is_disposable_email": True
    }
    device_features = {"distinct_users_on_device": 4} # Trigger threshold is >= 3
    current_event = {"amount": 100}
    
    rules, score, interventions = evaluate_rules(user_features, device_features, current_event)
    
    assert "DEVICE_MULTI_ACCOUNTING" in rules
    assert "DISPOSABLE_EMAIL_DOMAIN" in rules
    assert score >= 80 # 60 + 20
    assert "Device Fingerprinting Block" in interventions
    assert "Step-Up KYC Required" in interventions

def test_velocity_abuse_rule():
    user_features = {
        "distinct_devices_30d": 1,
        "tx_count_1h": 6, # Trigger threshold is > 4
        "tx_amount_24h": 4000, # Trigger threshold is > 3000
        "is_disposable_email": False
    }
    device_features = {"distinct_users_on_device": 1}
    current_event = {"amount": 100}
    
    rules, score, interventions = evaluate_rules(user_features, device_features, current_event)
    
    assert "HIGH_VELOCITY_1H" in rules
    assert "HIGH_VALUE_24H" in rules
    assert score == 50 # 30 + 20
    assert "Velocity Limit Enforcement" in interventions

def test_clean_transaction():
    user_features = {
        "distinct_devices_30d": 1,
        "tx_count_1h": 1,
        "tx_amount_24h": 100,
        "is_disposable_email": False
    }
    device_features = {"distinct_users_on_device": 1}
    current_event = {"amount": 50}
    
    rules, score, interventions = evaluate_rules(user_features, device_features, current_event)
    
    assert len(rules) == 0
    assert score == 0
    assert len(interventions) == 0
