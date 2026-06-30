import streamlit as st
import pandas as pd
import json
import os
import sys
import altair as alt
from streamlit_agraph import agraph, Node, Edge, Config
from datetime import datetime

# Ensure the root directory is in sys.path so we can import 'engine'
base_dir = os.path.dirname(os.path.dirname(__file__))
if base_dir not in sys.path:
    sys.path.append(base_dir)

from engine.decision import score_event

st.set_page_config(page_title="Fraud Investigator Workbench", layout="wide", initial_sidebar_state="expanded")

# --- DATA LOADING ---
transactions_file = os.path.join(base_dir, "transactions.csv")
users_file = os.path.join(base_dir, "users.csv")

if not os.path.exists(transactions_file):
    st.warning("No synthetic data found. Please run the simulator first: `python simulator/generate_data.py`")
    st.stop()

@st.cache_data
def load_data():
    events_df = pd.read_csv(transactions_file)
    users_df = pd.read_csv(users_file)
    events_df = events_df.merge(users_df[['user_id', 'email', 'kyc_status', 'phone']], on='user_id', how='left')
    return events_df, users_df

events_df, users_df = load_data()

# --- BATCH EVALUATION ---
st.sidebar.header("1. Batch Evaluation")
if st.sidebar.button("Run Evaluation on Synthetic Data", type="primary"):
    # Safely clear the database by closing the connection first
    from engine.decision import store
    db_path = os.path.join(base_dir, "feature_store.db")
    try:
        store.conn.close()
    except Exception:
        pass
        
    if os.path.exists(db_path):
        os.remove(db_path)
        
    # Reinitialize the store with a fresh database
    store.__init__(db_path=db_path)
    
    results = []
    progress_bar = st.sidebar.progress(0)
    for i, row in events_df.iterrows():
        event_dict = row.to_dict()
        event_dict['amount'] = float(event_dict['amount'])
        if pd.isna(event_dict['merchant']):
            event_dict['merchant'] = ""
            
        res = score_event(event_dict)
        
        results.append({
            "event_id": event_dict["event_id"],
            "user_id": event_dict["user_id"],
            "device_id": event_dict["device_id"],
            "ip_address": event_dict["ip_address"],
            "timestamp": event_dict["timestamp"],
            "event_type": event_dict["event_type"],
            "amount": event_dict["amount"],
            "decision": res["decision"],
            "risk_score": res["risk_score"],
            "rules_score": res.get("rules_score", 0),
            "ml_score": res.get("ml_score", 0),
            "triggered_rules": ", ".join(res["triggered_rules"]),
            "interventions": ", ".join(res.get("interventions", [])),
            "features": res["features"], # Keep as dict for easier extraction
            "is_fraud": event_dict.get("is_fraud", 0) # For ground truth visualization
        })
        if i % 10 == 0:
            progress_bar.progress(min((i + 1) / len(events_df), 1.0))
            
    progress_bar.progress(1.0)
    st.session_state['evaluation_results'] = pd.DataFrame(results)
    st.sidebar.success("Evaluation complete!")

# --- UI REDESIGN ---
if 'evaluation_results' in st.session_state:
    results_df = st.session_state['evaluation_results']
    
    st.sidebar.header("2. Investigator Queue")
    
    # Get entities that have alerts
    alerted_users = results_df[results_df['decision'].isin(['REVIEW', 'DECLINE'])]['user_id'].unique()
    
    if len(alerted_users) == 0:
        st.success("No alerts found in the queue!")
        st.stop()
        
    if 'entity_selectbox' not in st.session_state:
        st.session_state['entity_selectbox'] = alerted_users[0]
        
    selected_user_id = st.sidebar.selectbox("Select Entity to Investigate", alerted_users, key="entity_selectbox")
    
    if selected_user_id:
        # Extract Entity Data
        entity_events = results_df[results_df['user_id'] == selected_user_id].sort_values(by='timestamp')
        latest_event = entity_events.iloc[-1]
        user_info = users_df[users_df['user_id'] == selected_user_id].iloc[0]
        
        # --- KEYBOARD NAVIGATION (j/k) ---
        import streamlit.components.v1 as components
        components.html("""
            <script>
            const doc = window.parent.document;
            if (!doc.getElementById('jk-listener')) {
                doc.addEventListener('keydown', function(e) {
                    if (e.target.tagName.toLowerCase() === 'input' || e.target.tagName.toLowerCase() === 'textarea') return;
                    if (e.key === 'j') {
                        const btns = Array.from(doc.querySelectorAll('button'));
                        const nextBtn = btns.find(b => b.innerText.includes('Next Case (j)'));
                        if (nextBtn) nextBtn.click();
                    }
                    if (e.key === 'k') {
                        const btns = Array.from(doc.querySelectorAll('button'));
                        const prevBtn = btns.find(b => b.innerText.includes('Prev Case (k)'));
                        if (prevBtn) prevBtn.click();
                    }
                });
                const marker = doc.createElement('div');
                marker.id = 'jk-listener';
                doc.body.appendChild(marker);
            }
            </script>
        """, height=0)

        # Handle Queue Navigation
        current_idx = list(alerted_users).index(selected_user_id)
        
        def prev_case():
            if current_idx > 0:
                st.session_state['entity_selectbox'] = alerted_users[current_idx - 1]
                
        def next_case():
            if current_idx < len(alerted_users) - 1:
                st.session_state['entity_selectbox'] = alerted_users[current_idx + 1]
                
        c_prev, c_next = st.sidebar.columns(2)
        c_prev.button("⬅️ Prev Case (k)", use_container_width=True, on_click=prev_case)
        c_next.button("Next Case (j) ➡️", use_container_width=True, on_click=next_case)
        
        # --- HEADER BAR ---
        st.markdown(f"### Entity Profile: `{selected_user_id}`")
        
        # Risk Band Logic
        risk_score = latest_event['risk_score']
        if risk_score >= 80:
            band_color = "🔴"
            band_text = "CRITICAL (DECLINE)"
        elif risk_score >= 40:
            band_color = "🟡"
            band_text = "ELEVATED (REVIEW)"
        else:
            band_color = "🟢"
            band_text = "LOW RISK (APPROVE)"
            
        # FIXED ML SCORE BUG: Don't use delta, it adds an Up Arrow that looks like a '1'
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Blended Risk Score", f"{risk_score} / 100")
        c2.metric("ML Score (RF)", f"{latest_event['ml_score']} / 100")
        c3.metric("Risk Band", f"{band_color} {band_text}")
        c4.metric("KYC Status", user_info['kyc_status'])
        c5.metric("Tags", "🚨 SYNTHETIC" if "SYNTHETIC" in latest_event['triggered_rules'] else "None")
        
        st.markdown("---")
        
        # --- TABS ---
        tab_overview, tab_alerts, tab_network, tab_timeline, tab_notes = st.tabs([
            "📊 Overview", "⚠️ Alerts", "🕸️ Network", "📈 Risk Timeline", "📝 Notes"
        ])
        
        with tab_overview:
            st.subheader("Entity Metadata")
            col1, col2 = st.columns([2, 1])
            with col1:
                st.write(f"**Name:** {user_info['name']}")
                st.write(f"**Email:** {user_info['email']}")
                st.write(f"**Phone:** {user_info['phone']}")
                st.write(f"**Total Volume:** £{entity_events['amount'].sum():.2f}")
                st.write(f"**Transaction Count:** {len(entity_events)}")
                
                features = latest_event['features']
                if type(features) == str:
                    features = json.loads(features)
                    
                st.write(f"**Distinct Devices (30d):** {features.get('distinct_devices_30d', 1)}")
                st.write(f"**Distinct IPs (30d):** {features.get('distinct_ips_30d', 1)}")
            
            with col2:
                st.markdown("**Quick Actions**")
                if st.button("🚫 Block Device", use_container_width=True):
                    st.success(f"Device {latest_event['device_id']} added to global blocklist.")
                    note_key = f"notes_{selected_user_id}"
                    if note_key not in st.session_state: st.session_state[note_key] = []
                    st.session_state[note_key].append({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "text": f"[SYSTEM] Analyst blocked device {latest_event['device_id']}"})
                    
                if st.button("📋 Generate SAR Pack", use_container_width=True):
                    st.info("SAR (Suspicious Activity Report) PDF generated and queued for compliance review.")
                    
                if st.button("⬆️ Escalate to TL", use_container_width=True):
                    st.warning("Entity escalated to Team Lead for secondary review.")
                    
                if st.button("✅ Mark Legit", use_container_width=True):
                    st.balloons()
                    st.success("User marked as False Positive. Rules score adjusted.")
                
        with tab_alerts:
            st.subheader("Transaction History & Alerts")
            # Format dataframe for display
            display_df = entity_events[['timestamp', 'event_id', 'event_type', 'amount', 'decision', 'risk_score', 'triggered_rules', 'interventions']].copy()
            st.dataframe(display_df, use_container_width=True)
            
        with tab_network:
            st.subheader("Link Analysis Graph")
            st.markdown("Visualizing shared devices and IP addresses across the network.")
            
            # Extract the devices and IPs used by this user
            devices = entity_events['device_id'].unique()
            ips = entity_events['ip_address'].unique()
            
            # Find all users who share these devices or IPs
            linked_events = results_df[results_df['device_id'].isin(devices) | results_df['ip_address'].isin(ips)]
            
            nodes = []
            edges = []
            added_nodes = set()
            
            # Add users
            for uid in linked_events['user_id'].unique():
                if uid not in added_nodes:
                    user_max_risk = linked_events[linked_events['user_id'] == uid]['risk_score'].max()
                    color = "#ff4b4b" if user_max_risk >= 80 else "#ffa421" if user_max_risk >= 40 else "#00cc96"
                    nodes.append(Node(id=uid, label=uid, size=25, color=color))
                    added_nodes.add(uid)
                    
            # Add devices and ips
            for idx, row in linked_events.iterrows():
                dev_id = row['device_id']
                ip = row['ip_address']
                uid = row['user_id']
                
                if dev_id not in added_nodes:
                    nodes.append(Node(id=dev_id, label=dev_id, size=15, color="#5c6bc0", shape="square"))
                    added_nodes.add(dev_id)
                if ip not in added_nodes:
                    nodes.append(Node(id=ip, label=ip, size=15, color="#ab47bc", shape="triangle"))
                    added_nodes.add(ip)
                    
                edges.append(Edge(source=uid, target=dev_id, label="used_device"))
                edges.append(Edge(source=uid, target=ip, label="used_ip"))
                
            config = Config(width=800, height=500, directed=False, nodeHighlightBehavior=True, highlightColor="#F7A7A6",
                            collapsible=False, node={'labelProperty': 'label'}, link={'labelProperty': 'label', 'renderLabel': True})
            
            agraph(nodes=nodes, edges=edges, config=config)
            
        with tab_timeline:
            st.subheader("Risk Score Timeline")
            # Prepare data for Altair
            timeline_df = entity_events[['timestamp', 'risk_score', 'amount', 'decision']].copy()
            timeline_df['timestamp'] = pd.to_datetime(timeline_df['timestamp'])
            
            line_chart = alt.Chart(timeline_df).mark_line(point=True).encode(
                x='timestamp:T',
                y=alt.Y('risk_score:Q', scale=alt.Scale(domain=[0, 100])),
                color=alt.Color('decision:N', scale=alt.Scale(domain=['APPROVE', 'REVIEW', 'DECLINE'], range=['green', 'orange', 'red'])),
                tooltip=['timestamp', 'risk_score', 'amount', 'decision']
            ).properties(height=400)
            
            st.altair_chart(line_chart, use_container_width=True)

        with tab_notes:
            st.subheader("Analyst Notes")
            note_key = f"notes_{selected_user_id}"
            if note_key not in st.session_state:
                st.session_state[note_key] = []
                
            for note in st.session_state[note_key]:
                st.info(f"**[{note['timestamp']}] @analyst:** {note['text']}")
                
            new_note = st.text_area("Add a new note...")
            if st.button("Save Note"):
                if new_note:
                    st.session_state[note_key].append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "text": new_note
                    })
                    st.rerun()
else:
    st.info("👈 Run the Batch Evaluation from the sidebar to populate the investigator queue.")
