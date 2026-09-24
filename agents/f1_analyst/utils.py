from google.genai.types import AutomaticFunctionCallingConfig
from langchain_google_genai import ChatGoogleGenerativeAI

LLM_MODEL = "gemini-3.5-flash-lite"


def get_llm():
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        model_kwargs={
            "automatic_function_calling": AutomaticFunctionCallingConfig(disable=True)
        },
    )


def content_to_text(content) -> str:
    if isinstance(content, list):
        return " ".join(
            part.get("text", "").strip()
            if isinstance(part, dict)
            else str(part).strip()
            for part in content
        ).strip()
    return str(content or "")
