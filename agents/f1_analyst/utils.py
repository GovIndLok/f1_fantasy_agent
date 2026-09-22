"""
LLM and Agent utilities.

Single authoritative place to define and swap the LLM provider and model.
To change the model, update the string below.
"""
from langchain_google_genai import ChatGoogleGenerativeAI

LLM_MODEL = "gemini-3.5-flash-lite"


def get_llm():
    """Return configured Chat model instance."""
    return ChatGoogleGenerativeAI(model=LLM_MODEL)
