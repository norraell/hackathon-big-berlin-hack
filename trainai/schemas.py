"""
backend/schemas.py
Pydantic models for request / response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2_000, description="User message")
    session_id: Optional[str] = Field(None, description="Optional session identifier for conversation continuity")


class IntentResult(BaseModel):
    intent: str
    confidence: float


class ChatResponse(BaseModel):
    reply: str
    intent: IntentResult
    session_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    model: str
    intent_router_loaded: bool
