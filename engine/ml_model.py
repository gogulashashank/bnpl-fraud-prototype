import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
import joblib
import os
import sqlite3
from engine.feature_store import FeatureStore

def prepare_training_data():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    transactions_file = os.path.join(base_dir, "transactions.csv")
    users_file = os.path.join(base_dir, "users.csv")
    db_path = os.path.join(base_dir, "feature_store_train.db")
    
    if os.path.exists(db_path):
        os.remove(db_path)
        
    events_df = pd.read_csv(transactions_file)
    users_df = pd.read_csv(users_file)
    
    events_df = events_df.merge(users_df[['user_id', 'email', 'kyc_status']], on='user_id', how='left')
    
    store = FeatureStore(db_path=db_path)
    
    features_list = []
    labels = []
    
    # Process events sequentially to simulate real-time feature generation
    for i, row in events_df.iterrows():
        event = row.to_dict()
        store.add_user(event["user_id"], event.get("kyc_status", "UNKNOWN"), event.get("email", ""))
        
        user_features = store.get_user_features(event["user_id"], event["timestamp"])
        device_features = store.get_device_features(event["device_id"], event["timestamp"])
        
        # Add to store AFTER getting features to simulate 'prior' state, 
        # but for simplicity we will just use the current state.
        # Wait, if we add it after, we get prior. If we add before, we include current event.
        # Let's add before to match `decision.py`.
        store.add_event(event)
        
        # Re-fetch with current event
        user_features = store.get_user_features(event["user_id"], event["timestamp"])
        device_features = store.get_device_features(event["device_id"], event["timestamp"])
        
        combined_features = {
            "tx_count_24h": user_features["tx_count_24h"],
            "tx_amount_24h": user_features["tx_amount_24h"],
            "tx_count_1h": user_features["tx_count_1h"],
            "distinct_devices_30d": user_features["distinct_devices_30d"],
            "distinct_users_on_device": device_features["distinct_users_on_device"],
            "is_disposable_email": 1 if user_features["is_disposable_email"] else 0,
            "amount": float(event["amount"])
        }
        
        features_list.append(combined_features)
        labels.append(event["is_fraud"])
        
    X = pd.DataFrame(features_list)
    y = pd.Series(labels)
    
    return X, y

def train_model():
    print("Preparing training data...")
    X, y = prepare_training_data()
    
    print(f"Dataset shape: {X.shape}, Fraud cases: {y.sum()}")
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    print("Training Random Forest...")
    clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    clf.fit(X_train, y_train)
    
    # Evaluate
    preds = clf.predict(X_test)
    probs = clf.predict_proba(X_test)[:, 1]
    
    auc = roc_auc_score(y_test, probs)
    print(f"ROC AUC Score: {auc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, preds))
    
    # Save model
    model_path = os.path.join(os.path.dirname(__file__), "rf_model.pkl")
    joblib.dump(clf, model_path)
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    train_model()
