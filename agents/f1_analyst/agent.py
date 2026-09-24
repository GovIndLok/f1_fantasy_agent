import duckdb
from langchain.agents import create_agent

from agents.f1_analyst.tools import build_tools
from agents.f1_analyst.utils import content_to_text, get_llm

_SYSTEM_PROMPT = (
    "You are a strict F1 Fantasy Analyst. "
    "You discuss Formula 1 racing, race statistics, and Fantasy transfers. "
    "If a user asks about non-Formula 1 topics, politely refuse to answer. "
    "You do not have access to live news, real-time upgrade packages, or live fantasy price changes. "
    "You must rely purely on historical performance data and whatever context the user provides in their prompt "
    "to make your predictions and roster suggestions. "
    "Keep in mind that a valid F1 Fantasy roster MUST strictly consist of exactly 5 drivers and 2 constructors. "
    "You have access to a tool to check the user's current roster, but pricing/budget context must be provided by the user."
)


def run_f1_agent(prompt: str, player_id: str, db: duckdb.DuckDBPyConnection) -> dict:
    tools = build_tools(player_id, db)
    agent = create_agent(get_llm(), tools, system_prompt=_SYSTEM_PROMPT)

    try:
        response = agent.invoke({"messages": [("user", prompt)]})
        answer = content_to_text(response["messages"][-1].content)
        return {
            "answer": answer,
            "cost_log": {"total_tokens": len(prompt.split()) + len(answer.split())},
        }
    except Exception as exc:
        return {"answer": f"Error: {exc}", "cost_log": {"total_tokens": 0}}
