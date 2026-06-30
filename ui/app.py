import streamlit as st
import pandas as pd
import requests
import json
import os
import sys

# Ensure the root directory is in sys.path so we can import 'engine'
base_dir = os.path.dirname(os.path.dirname(__file__))
if base_dir not in sys.path:
    sys.path.append(base_dir)
st.set_page_config(page_title="Fraud Investigator Workbench", layout="wide")

st.title("🛡️ Fintech Fraud Investigator Workbench")
st.markdown("Review flagged transactions and BNPL applications.")

# Determine paths
base_dir = os.path.dirname(os.path.dirname(__file__))
transactions_file = os.path.join(base_dir, "transactions.csv")
users_file = os.path.join(base_dir, "users.csv")

if not os.path.exists(transactions_file):
    st.warning("No synthetic data found. Please run the simulator first: `python simulator/generate_data.py`")
    st.stop()

# Load Data
@st.cache_data
def load_data():
    events_df = pd.read_csv(transactions_file)
    users_df = pd.read_csv(users_file)
    # Merge email and KYC for the API request payload
    events_df = events_df.merge(users_df[['user_id', 'email', 'kyc_status']], on='user_id', how='left')
    return events_df

events_df = load_data()

st.sidebar.header("Controls")
if st.sidebar.button("Run Batch Evaluation"):
    # Clear feature store and re-evaluate
    db_path = os.path.join(base_dir, "feature_store.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # We will simulate calling the engine directly to avoid needing the API server running for this demo
    from engine.decision import score_event
    
    results = []
    progress_bar = st.progress(0)
    for i, row in events_df.iterrows():
        event_dict = row.to_dict()
        event_dict['amount'] = float(event_dict['amount'])
        if pd.isna(event_dict['merchant']):
            event_dict['merchant'] = ""
            
        res = score_event(event_dict)
        
        results.append({
            "event_id": event_dict["event_id"],
            "user_id": event_dict["user_id"],
            "timestamp": event_dict["timestamp"],
            "event_type": event_dict["event_type"],
            "amount": event_dict["amount"],
            "decision": res["decision"],
            "risk_score": res["risk_score"],
            "rules_score": res.get("rules_score", 0),
            "ml_score": res.get("ml_score", 0),
            "triggered_rules": ", ".join(res["triggered_rules"]),
            "interventions": ", ".join(res.get("interventions", [])),
            "features": json.dumps(res["features"])
        })
        if i % 10 == 0:
            progress_bar.progress(min((i + 1) / len(events_df), 1.0))
            
    progress_bar.progress(1.0)
    st.session_state['evaluation_results'] = pd.DataFrame(results)
    st.success("Evaluation complete!")

if 'evaluation_results' in st.session_state:
    results_df = st.session_state['evaluation_results']
    
    # Metrics
    total = len(results_df)
    declined = len(results_df[results_df['decision'] == 'DECLINE'])
    review = len(results_df[results_df['decision'] == 'REVIEW'])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Events", total)
    c2.metric("Requires Review", review)
    c3.metric("Auto Declined", declined)
    
    st.subheader("Alerts Queue (REVIEW & DECLINE)")
    alerts_df = results_df[results_df['decision'].isin(['REVIEW', 'DECLINE'])].sort_values(by='timestamp', ascending=False)
    st.dataframe(alerts_df[['timestamp', 'event_id', 'user_id', 'event_type', 'amount', 'decision', 'risk_score', 'rules_score', 'ml_score', 'interventions']])
    
    st.subheader("Deep Dive & Link Analysis")
    selected_event_id = st.selectbox("Select Event ID to investigate", alerts_df['event_id'].tolist() if not alerts_df.empty else [])
    
    if selected_event_id:
        event_details = alerts_df[alerts_df['event_id'] == selected_event_id].iloc[0]
        st.write(f"**Triggered Rules:** {event_details['triggered_rules']}")
        
        if event_details['interventions']:
            st.warning(f"**Recommended Interventions:** {event_details['interventions']}")
            
        c4, c5 = st.columns(2)
        with c4:
            st.markdown("### Risk Scores")
            st.write(f"**Blended Final Score:** {event_details['risk_score']}")
            st.write(f"**Rules Score (Heuristics):** {event_details['rules_score']}")
            st.write(f"**ML Score (Random Forest):** {event_details['ml_score']}")
            
        with c5:
            st.markdown("### Risk Features at Time of Event")
            features = json.loads(event_details['features'])
            st.json(features)
