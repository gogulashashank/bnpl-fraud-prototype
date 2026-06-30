import streamlit as st
import pandas as pd
import json
import os
import sys
import altair as alt
from streamlit_agraph import agraph, Node, Edge, Config
from datetime import datetime
import plotly.graph_objects as go

# Ensure the root directory is in sys.path so we can import 'engine'
base_dir = os.path.dirname(os.path.dirname(__file__))
if base_dir not in sys.path:
    sys.path.append(base_dir)

from engine.decision import score_event

st.set_page_config(page_title="Fraud Investigator Workbench", layout="wide", initial_sidebar_state="expanded")

# Minimalist UI Overrides
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&display=swap');
    
    * {
        font-family: 'IBM Plex Mono', monospace !important;
    }

    /* Clean up clutter */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Intel Cards for Metrics */
    div[data-testid="metric-container"] {
        background-color: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(255, 75, 75, 0.2);
        border-top: 3px solid #ff4b4b;
        padding: 1.5rem;
        border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5), inset 0 0 20px rgba(255, 75, 75, 0.05);
        transition: all 0.3s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(255, 75, 75, 0.2), inset 0 0 20px rgba(255, 75, 75, 0.1);
        border-color: rgba(255, 75, 75, 0.5);
    }
    
    /* Gradient Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #ff4b4b 0%, #990000 100%) !important;
        border: 1px solid #ff4b4b !important;
        color: white !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.3) !important;
        transition: transform 0.1s, box-shadow 0.2s !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px !important;
    }
    .stButton > button:hover {
        box-shadow: 0 0 10px rgba(255, 75, 75, 0.5) !important;
        border-color: #ffaaaa !important;
        color: white !important;
    }
    .stButton > button:active {
        transform: scale(0.98) !important;
    }
    
    /* Expander styling - Dark cards with red hover */
    [data-testid="stExpander"] {
        background-color: #0f172a !important;
        border: 1px solid #1e293b !important;
        border-radius: 8px !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
        overflow: hidden;
    }
    [data-testid="stExpander"]:hover {
        border-color: #ff4b4b !important;
        box-shadow: 0 0 8px rgba(255, 75, 75, 0.3) !important;
    }
    
    /* Adjust top padding */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }
    
    /* Live Pulse Animation for Critical Entities */
    @keyframes pulse-red {
        0% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0.7); border: 1px solid rgba(255, 75, 75, 1); }
        70% { box-shadow: 0 0 0 10px rgba(255, 75, 75, 0); border: 1px solid rgba(255, 75, 75, 0.3); }
        100% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0); border: 1px solid rgba(255, 75, 75, 1); }
    }
    
    .critical-pulse {
        animation: pulse-red 2s infinite;
        background-color: rgba(255, 75, 75, 0.05);
        padding: 10px;
        border-radius: 8px;
    }
    
    /* Evidence Wall Timeline CSS */
    .timeline-event {
        border-left: 2px solid #ff4b4b;
        padding-left: 15px;
        margin-bottom: 20px;
        position: relative;
    }
    .timeline-event::before {
        content: '';
        position: absolute;
        left: -6px;
        top: 0;
        width: 10px;
        height: 10px;
        background-color: inherit;
        border-radius: 50%;
    }
    .timeline-date {
        font-size: 0.8rem;
        color: #888;
        margin-bottom: 4px;
    }
</style>
""", unsafe_allow_html=True)

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
        
        # Risk Band Logic
        risk_score = latest_event['risk_score']
        if risk_score >= 80:
            band_color = "🔴"
            band_text = "CRITICAL"
            pulse_class = "critical-pulse"
        elif risk_score >= 40:
            band_color = "🟡"
            band_text = "ELEVATED"
            pulse_class = ""
        else:
            band_color = "🟢"
            band_text = "LOW RISK"
            pulse_class = ""

        # --- HEADER BAR ---
        col_hdr, col_actions = st.columns([4, 1])
        with col_hdr:
            tags = "🚨 SYNTHETIC" if "SYNTHETIC" in latest_event['triggered_rules'] else ""
            kyc_badge = f"🛡️ {user_info['kyc_status']}"
            st.markdown(f"<div class='{pulse_class}'><h3 style='margin-bottom:0;'>{selected_user_id} &nbsp; <span style='font-size: 0.5em; background: rgba(255,255,255,0.1); padding: 4px 8px; border-radius: 4px; vertical-align: middle;'>{kyc_badge}</span> &nbsp; <span style='font-size: 0.5em; color: #ff4b4b; vertical-align: middle;'>{tags}</span></h3></div>", unsafe_allow_html=True)
            
        with col_actions:
            with st.popover("⚡ Action Menu", use_container_width=True):
                if st.button("🚫 Block Device", use_container_width=True):
                    st.success(f"Device {latest_event['device_id']} blocked.")
                    note_key = f"notes_{selected_user_id}"
                    if note_key not in st.session_state: st.session_state[note_key] = []
                    st.session_state[note_key].append({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "text": f"[SYSTEM] Analyst blocked device {latest_event['device_id']}"})
                if st.button("📋 Generate SAR", use_container_width=True):
                    st.info("SAR PDF generated and queued.")
                if st.button("⬆️ Escalate", use_container_width=True):
                    st.warning("Escalated to Team Lead.")
                if st.button("✅ Mark Legit", use_container_width=True):
                    st.balloons()
        
        st.markdown("<br>", unsafe_allow_html=True)
            
        # Animated Plotly Gauge and secondary metrics
        col_gauge, col_m1, col_m2 = st.columns([2, 1, 1])
        
        with col_gauge:
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = risk_score,
                number = {'font': {'size': 40, 'color': 'white'}},
                title = {'text': "Blended Risk Score", 'font': {'size': 16, 'color': '#aaa'}},
                gauge = {
                    'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
                    'bar': {'color': "#ff4b4b" if risk_score >= 80 else "#ffa421" if risk_score >= 40 else "#00cc96"},
                    'bgcolor': "rgba(0,0,0,0)",
                    'borderwidth': 0,
                    'steps': [
                        {'range': [0, 40], 'color': "rgba(0, 204, 150, 0.15)"},
                        {'range': [40, 80], 'color': "rgba(255, 164, 33, 0.15)"},
                        {'range': [80, 100], 'color': "rgba(255, 75, 75, 0.15)"}],
                }
            ))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"}, height=150, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)
            
        with col_m1:
            st.metric("ML Score (RF)", f"{latest_event['ml_score']} / 100")
        with col_m2:
            st.metric("Risk Band", f"{band_color} {band_text}")
        
        st.markdown("---")
        
        # Core Focal Point: Network Graph
        st.subheader("🕸️ Link Analysis Graph")
        st.markdown("Visualizing shared devices and IP addresses across the network. **Click a User node to pivot the investigation, or an Attribute node to see its usage.**")
            
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
                user_kyc = users_df[users_df['user_id'] == uid].iloc[0]['kyc_status'] if uid in users_df['user_id'].values else "UNKNOWN"
                color = "#00ffcc" if uid == selected_user_id else "#ff00ff"
                
                # Highlight anchor node
                if uid == selected_user_id:
                    nodes.append(Node(id=uid, label=f"★ {uid}", size=40, color=color, shape="star", title=f"Risk: {user_max_risk} | KYC: {user_kyc}"))
                else:
                    nodes.append(Node(id=uid, label=uid, size=25, color=color, shape="dot", title=f"Risk: {user_max_risk} | KYC: {user_kyc}"))
                added_nodes.add(uid)
                
        # Add devices and ips and calculate edge weights
        edge_counts = {}
        for idx, row in linked_events.iterrows():
            dev_id = row['device_id']
            ip = row['ip_address']
            uid = row['user_id']
            
            if dev_id not in added_nodes:
                nodes.append(Node(id=dev_id, label=dev_id, size=15, color="#5c6bc0", shape="square", title="Device"))
                added_nodes.add(dev_id)
            if ip not in added_nodes:
                nodes.append(Node(id=ip, label=ip, size=15, color="#ab47bc", shape="triangle", title="IP Address"))
                added_nodes.add(ip)
                
            dev_edge_key = (uid, dev_id)
            ip_edge_key = (uid, ip)
            edge_counts[dev_edge_key] = edge_counts.get(dev_edge_key, 0) + 1
            edge_counts[ip_edge_key] = edge_counts.get(ip_edge_key, 0) + 1
            
        for (src, tgt), count in edge_counts.items():
            edge_label = f"used {count}x" if count > 1 else ""
            # Dark web glowing edges
            edges.append(Edge(source=src, target=tgt, label=edge_label, width=min(count, 5), color="#334455"))
            
        config = Config(width="100%", height=600, directed=True, physics=True, nodeHighlightBehavior=True, highlightColor="#ffffff",
                        collapsible=False, node={'labelProperty': 'label'}, link={'labelProperty': 'label', 'renderLabel': True},
                        backgroundColor="#020617")
        
        clicked_node = agraph(nodes=nodes, edges=edges, config=config)
        
        if clicked_node:
            # If it's a user and NOT the currently selected user, navigate to them
            if clicked_node in users_df['user_id'].values and clicked_node != selected_user_id:
                st.session_state['entity_selectbox'] = clicked_node
                st.rerun()
            # If it's an attribute (device/ip), show related transactions
            elif clicked_node != selected_user_id:
                st.markdown(f"### Activity for Attribute: `{clicked_node}`")
                attr_events = results_df[(results_df['device_id'] == clicked_node) | (results_df['ip_address'] == clicked_node)]
                st.dataframe(attr_events[['timestamp', 'user_id', 'amount', 'decision', 'risk_score', 'event_type']], use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Secondary Information Expanders
        with st.expander("📊 Entity Metadata & Features", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Name:** {user_info['name']}")
                st.write(f"**Email:** {user_info['email']}")
                st.write(f"**Phone:** {user_info['phone']}")
            with col2:
                st.write(f"**Total Volume:** £{entity_events['amount'].sum():.2f}")
                st.write(f"**Transaction Count:** {len(entity_events)}")
                features = latest_event['features']
                if type(features) == str: features = json.loads(features)
                st.write(f"**Distinct Devices (30d):** {features.get('distinct_devices_30d', 1)}")
                st.write(f"**Distinct IPs (30d):** {features.get('distinct_ips_30d', 1)}")

        with st.expander("⚠️ Transaction History & Alerts", expanded=False):
            display_df = entity_events[['timestamp', 'event_id', 'event_type', 'amount', 'decision', 'risk_score', 'triggered_rules', 'interventions']].copy()
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
        with st.expander("📈 Case Timeline (Evidence Wall)", expanded=False):
            st.markdown("<div style='background-color: #020617; padding: 25px; border-radius: 10px; border: 1px solid #1e293b; box-shadow: inset 0 0 20px rgba(0,0,0,0.5);'>", unsafe_allow_html=True)
            for idx, row in entity_events.iterrows():
                color = "#ff4b4b" if row['decision'] == 'DECLINE' else "#ffa421" if row['decision'] == 'REVIEW' else "#00cc96"
                st.markdown(f"""
                <div class="timeline-event" style="border-left-color: {color};">
                    <style>.timeline-event:nth-child({idx+1})::before {{ background-color: {color}; }}</style>
                    <div class="timeline-date">{row['timestamp']}</div>
                    <div style="font-weight: 600; color: #fff; font-size: 1.1em; letter-spacing: 0.5px;">{row['event_type']} - £{row['amount']}</div>
                    <div style="font-size: 0.9em; color: {color}; margin-top: 4px;">[ {row['decision']} ] &nbsp; <span style="color: #888;">Score: {row['risk_score']}</span></div>
                    <div style="font-size: 0.85em; color: #aaa; margin-top: 4px; font-family: monospace;">Rules: {row['triggered_rules'] or 'None'}</div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("📝 Analyst Notes", expanded=False):
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
