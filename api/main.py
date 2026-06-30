from fastapi import FastAPI
from .schemas import TransactionEvent, EventResponse
from engine.decision import score_event
import uvicorn

app = FastAPI(title="Fintech Fraud Detection API", description="Scores transactions and BNPL applications in real-time.")

@app.post("/evaluate", response_model=EventResponse)
def evaluate_event(event: TransactionEvent):
    # Convert pydantic model to dict
    event_dict = event.model_dump()
    
    # Run through the engine
    result = score_event(event_dict)
    
    return result

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
