def evaluate_rules(user_features, device_features, current_event):
    """
    Evaluates risk features against heuristic rules.
    Returns a list of triggered rule names, risk score (0-100), and recommended interventions.
    """
    triggered_rules = []
    interventions = set()
    risk_score = 0
    
    # 1. ATO Rule
    if user_features["distinct_devices_30d"] > 2 and current_event.get("amount", 0) > 500:
        triggered_rules.append("ATO_SUSPICION_HIGH_VALUE_NEW_DEVICE")
        interventions.add("MFA Request (Step-up Auth)")
        risk_score += 40
        
    # 2. Synthetic Identity / Ring Rule
    if device_features["distinct_users_on_device"] >= 3:
        triggered_rules.append("DEVICE_MULTI_ACCOUNTING")
        interventions.add("Device Fingerprinting Block")
        interventions.add("Link Analysis Review")
        risk_score += 60
        
    if user_features["is_disposable_email"]:
        triggered_rules.append("DISPOSABLE_EMAIL_DOMAIN")
        interventions.add("Step-Up KYC Required")
        risk_score += 20
        
    # 3. Transaction Velocity Abuse Rule
    if user_features["tx_count_1h"] > 4:
        triggered_rules.append("HIGH_VELOCITY_1H")
        interventions.add("Velocity Limit Enforcement")
        risk_score += 30
        
    if user_features["tx_amount_24h"] > 3000:
        triggered_rules.append("HIGH_VALUE_24H")
        interventions.add("Velocity Limit Enforcement")
        risk_score += 20
        
    # Cap score at 100
    risk_score = min(risk_score, 100)
    
    return triggered_rules, risk_score, list(interventions)
