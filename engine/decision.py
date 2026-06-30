from .feature_store import FeatureStore
from .rules import evaluate_rules
import os
import joblib
import pandas as pd

# Initialize a global feature store for the application
db_path = os.path.join(os.path.dirname(__file__), "..", "feature_store.db")
store = FeatureStore(db_path=db_path)

# Load ML Model (if exists)
model_path = os.path.join(os.path.dirname(__file__), "rf_model.pkl")
ml_model = None
if os.path.exists(model_path):
    ml_model = joblib.load(model_path)

def score_event(event):
    """
    Ingests an event, updates features, and returns a decision.
    """
    # 1. Add user and event to store
    store.add_user(event["user_id"], event.get("kyc_status", "UNKNOWN"), event.get("email", ""))
    store.add_event(event)
    
    # 2. Extract features
    user_features = store.get_user_features(event["user_id"], event["timestamp"])
    device_features = store.get_device_features(event["device_id"], event["timestamp"])
    
    # 3. Evaluate rules
    triggered_rules, rules_score, interventions = evaluate_rules(user_features, device_features, event)
    
    # 4. Evaluate ML Model
    ml_score = 0
    if ml_model:
        ml_features = pd.DataFrame([{
            "tx_count_24h": user_features["tx_count_24h"],
            "tx_amount_24h": user_features["tx_amount_24h"],
            "tx_count_1h": user_features["tx_count_1h"],
            "distinct_devices_30d": user_features["distinct_devices_30d"],
            "distinct_users_on_device": device_features["distinct_users_on_device"],
            "is_disposable_email": 1 if user_features["is_disposable_email"] else 0,
            "amount": float(event.get("amount", 0.0))
        }])
        ml_prob = ml_model.predict_proba(ml_features)[0][1] # Probability of fraud
        ml_score = int(ml_prob * 100)
        
    # 5. Make decision based on Blended Score (60% Rules, 40% ML)
    if ml_model:
        final_risk_score = int(0.6 * rules_score + 0.4 * ml_score)
    else:
        final_risk_score = rules_score
        
    decision = "APPROVE"
    if final_risk_score >= 80:
        decision = "DECLINE"
    elif final_risk_score >= 40:
        decision = "REVIEW"
        
    return {
        "event_id": event["event_id"],
        "decision": decision,
        "risk_score": final_risk_score,
        "rules_score": rules_score,
        "ml_score": ml_score,
        "triggered_rules": triggered_rules,
        "interventions": interventions,
        "features": {**user_features, **device_features}
    }
