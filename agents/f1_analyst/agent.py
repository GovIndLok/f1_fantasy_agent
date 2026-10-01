import uuid

import duckdb
from langchain.agents import create_agent

from agents.f1_analyst.tools import build_tools
from agents.f1_analyst.usage_tracker import log_llm_call
from agents.f1_analyst.utils import LLM_MODEL, content_to_text, get_llm

_SYSTEM_PROMPT = (
    "You are a strict F1 Fantasy Analyst. "
    "You discuss Formula 1 racing, race statistics, and Fantasy transfers. "
    "If a user asks about non-Formula 1 topics, politely refuse to answer. "
    "You do not have access to live news, real-time upgrade packages, or live fantasy price changes. "
    "You must rely purely on historical performance data and whatever context the user provides in their prompt "
    "to make your predictions and roster suggestions. "
    "Keep in mind that a valid F1 Fantasy roster MUST strictly consist of exactly 5 drivers and 2 constructors. "
    "You have access to a tool to check the user's current roster, but pricing/budget context must be provided by the user. "
    "The primary way a fantasy team succeeds is by accumulating points through driver and constructor performance in the championship. "
    "These points are calculated based mainly on their final results in both sprints and normal races over a weekend event. "
    "Ignore irrelevant details like pit stops; your main focus should always be on the points scored and final positions achieved by drivers and constructors."
)


def run_f1_agent(prompt: str, player_id: str, db: duckdb.DuckDBPyConnection) -> dict:
    request_id = str(uuid.uuid4())
    tools = build_tools(player_id, db, user_id=player_id, request_id=request_id)
    agent = create_agent(get_llm(), tools, system_prompt=_SYSTEM_PROMPT)

    try:
        response = agent.invoke({"messages": [("user", prompt)]})
        answer = content_to_text(response["messages"][-1].content)

        total_tokens = 0
        for msg in response["messages"]:
            if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                log_llm_call(
                    user_id=player_id,
                    request_id=request_id,
                    agent_name="main_agent",
                    model=LLM_MODEL,
                    usage_metadata=msg.usage_metadata,
                )
                total_tokens += msg.usage_metadata.get("total_tokens") or 0

        return {
            "answer": answer,
            "cost_log": {"total_tokens": total_tokens},
        }
    except Exception as exc:
        return {"answer": f"Error: {exc}", "cost_log": {"total_tokens": 0}}
