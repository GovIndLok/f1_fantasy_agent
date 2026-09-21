# agents/f1_analyst/schema.py
from pydantic import BaseModel


class ChatRequest(BaseModel):
    prompt: str


class ChatResponse(BaseModel):
    answer: str
    cost_log: dict

