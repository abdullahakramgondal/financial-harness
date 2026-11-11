"""FH-19: shared data schemas. Har module (agent, sandbox, dashboard) yehi use karega."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class Holding(BaseModel):
    symbol: str
    quantity: float
    buy_price: float


class Goal(BaseModel):
    horizon: Literal["10_months", "20_months", "10_years"]
    target_value: float
    risk: Literal["low", "medium", "high"] = "medium"


class Portfolio(BaseModel):
    cash: float = 0.0
    holdings: list[Holding]
    goals: list[Goal] = []


class Suggestion(BaseModel):
    symbol: str
    action: Literal["HOLD", "ACCUMULATE", "BUY", "SELL"]
    horizon: Literal["long_term", "short_term"]
    quantity: float = 0.0
    reason: str
    confidence: float = Field(0.5, ge=0, le=1)
    risk_note: Optional[str] = None
    data_timestamp: Optional[str] = None  # kis waqt ka data use hua
