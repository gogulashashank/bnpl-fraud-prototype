# Fintech Fraud Detection & Prevention Prototype

This project is a production-grade, end-to-end prototype for fraud detection targeting Consumer Wallets and Buy-Now-Pay-Later (BNPL) products at a Payment Service Provider (PSP).

## 🚀 Architecture: BigQuery ML Design Pattern

This architecture mirrors enterprise patterns used by leading fintechs (e.g., Google’s BigQuery ML Fraud Detection architecture):
1. **Event Ingestion (API)**: A FastAPI layer serving as the entry point for evaluating transactions and BNPL applications in real-time.
2. **Feature Store (SQLite/PostgreSQL)**: State is managed using a feature store approach. Locally, we use SQLite for demonstration, but the schema and queries are designed to be a drop-in replacement for **PostgreSQL** or a distributed cache (like Redis) in production.
3. **Dual-Scoring Engine**:
   - **Rules Engine (60% Weight)**: Drives governance and compliance. These heuristics encode strict policy, regulatory boundaries, and explainable thresholds (e.g., "KYC mismatch + device change").
   - **ML Model (40% Weight)**: A `scikit-learn` Random Forest model acting as a pattern detector and alert ranker. It catches nuanced, non-linear fraud patterns but is *not* the sole decision-maker to maintain model explainability.
   - **Risk Bands**: The blended score determines the final action:
     - **Low Risk (0-39)**: `APPROVE` - Transaction proceeds with no friction.
     - **Medium Risk (40-79)**: `REVIEW` - Sent to the investigator queue, often paired with "Step-Up Auth" or "MFA" interventions.
     - **High Risk (80-100)**: `DECLINE` - Hard block due to severe policy violations.

## 📚 Translating Research into Product Features

This prototype implements interventions and risk indicators derived directly from industry research on payments and BNPL fraud.

### Source 1: Payments Fraud & Account Takeover (ATO)
*Based on general patterns of card testing and ATO in PSPs.*
- **Risk Indicators**: Sudden changes in IP/Device velocity, high-value transactions following password resets.
- **Interventions Implemented**:
  - **Velocity Limit Enforcement**: Hard declines or alerts if transaction counts exceed thresholds over 1h/24h.
  - **MFA Request (Step-up Auth)**: Triggered when high-value transactions originate from an unseen device.

### Source 2: BNPL Risk & Synthetic Identities
*Based on modern threat landscapes surrounding "thin-file" credit and BNPL abuse.*
- **Risk Indicators**: Rapid multi-account creation on a single device, use of disposable email domains, and mismatched KYC records.
- **Interventions Implemented**:
  - **Device Fingerprinting Block**: Alerts triggered when >=3 distinct identities share a device fingerprint.
  - **Step-Up KYC Required**: Automatically recommended when disposable domains or mismatched data is detected.
  - **Link Analysis Review**: Investigator UI presents the shared identity ring for manual review.

## ⚖️ Regulatory Expectations & Compliance Alignment

A robust fraud system must satisfy risk management and Anti-Money Laundering (AML) obligations:
1. **Customer Identification Program (CIP) & KYC**: The system flags synthetic identities, ensuring we don't bypass KYC regulations by onboarding fictitious users. When suspicious signals are detected, the system outputs a `Step-Up KYC Required` intervention.
2. **Transaction Monitoring (TM)**: We enforce velocity and volume limits, which are critical for detecting structuring or rapid movement of funds (e.g., Money Laundering Loop typology) and generating Suspicious Activity Reports (SARs).
3. **Ongoing Screening & Risk Profiling**: The feature store tracks user behavior continuously, ensuring risk profiles are dynamically updated post-onboarding, aligning with continuous due diligence requirements.

## 🛠️ How to Run Locally

### 1. Generate Synthetic Data & Train ML Model
```bash
# Generate the dataset (simulates the 5 typologies)
python simulator/generate_data.py

# Train the Random Forest ML Model
PYTHONPATH=. python engine/ml_model.py
```

### 2. Run the Investigator Dashboard (Streamlit UI)
```bash
streamlit run ui/app.py
```
In the sidebar, click **"Run Batch Evaluation"**. The dashboard will:
- Load historical simulated transactions/loans.
- Compute Rules Score, ML Score, and Blended Risk Score.
- Display interventions like `Step‑Up KYC` and `Link Analysis` when specific fraud patterns are detected (ATO, synthetic rings, velocity abuse, refund abuse, laundering loops).

### 3. Run the API (Optional)
```bash
uvicorn api.main:app --reload
```
