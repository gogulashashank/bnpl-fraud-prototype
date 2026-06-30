from pydantic import BaseModel, Field
from typing import Optional

class TransactionEvent(BaseModel):
    event_id: str
    user_id: str
    device_id: str
    ip_address: str
    event_type: str
    amount: float
    timestamp: str
    merchant: Optional[str] = ""
    email: Optional[str] = ""
    kyc_status: Optional[str] = "UNKNOWN"

class EventResponse(BaseModel):
    event_id: str
    decision: str
    risk_score: int
    triggered_rules: list[str]
    features: dict
