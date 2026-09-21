"""
F1 Analyst agent — entry point.

This file owns:
  - LLM initialisation (swap provider here)
  - Agent assembly (tools + system prompt)
  - Execution and response normalisation

It imports tools from tools.py and schemas from schema.py.
No DB query logic lives here.
"""
import duckdb
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.f1_analyst.tools import build_tools

_SYSTEM_PROMPT = (
    "You are a strict F1 Fantasy Analyst. "
    "You ONLY discuss Formula 1 and Fantasy transfers. "
    "If a user asks about anything else, politely refuse to answer. "
    "You do not have access to live news, real-time upgrade packages, or live fantasy price changes. "
    "You must rely purely on historical performance data and whatever context the user provides in their prompt "
    "to make your predictions and roster suggestions. "
    "Keep in mind that a valid F1 Fantasy roster MUST strictly consist of exactly 5 drivers and 2 constructors. "
    "You have access to a tool to check the user's current roster, but pricing/budget context must be provided by the user."
)


def run_f1_agent(prompt: str, player_id: str, db: duckdb.DuckDBPyConnection) -> dict:
    """Run the F1 analyst agent and return {"answer": str, "cost_log": dict}."""
    # Swap the LLM here — everything else stays the same
    llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)
    tools = build_tools(player_id, db)
    agent = create_agent(llm, tools, system_prompt=_SYSTEM_PROMPT)

    try:
        response = agent.invoke({"messages": [("user", prompt)]})
        content = response["messages"][-1].content
        answer = content if isinstance(content, str) else str(content)
        return {
            "answer": answer,
            "cost_log": {"total_tokens": len(prompt.split()) + len(answer.split())},
        }
    except Exception as e:
        return {"answer": f"Error: {e}", "cost_log": {"total_tokens": 0}}

