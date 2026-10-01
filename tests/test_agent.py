from types import SimpleNamespace

from agents.f1_analyst import agent as agent_module
from agents.f1_analyst import usage_tracker


def test_agent_initializes_model_per_invocation(monkeypatch):
    calls = []

    class FakeAIMessage:
        """Minimal stand-in for langchain_core.messages.AIMessage."""
        def __init__(self):
            self.content = [{"text": "Historical"}, " answer"]
            self.usage_metadata = {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8}

    class FakeAgent:
        def invoke(self, messages):
            calls.append(messages)
            return {"messages": [FakeAIMessage()]}

    monkeypatch.setattr(agent_module, "build_tools", lambda player_id, db, user_id, request_id: ["tool"])
    monkeypatch.setattr(agent_module, "get_llm", lambda: "model")
    monkeypatch.setattr(
        agent_module,
        "create_agent",
        lambda model, tools, system_prompt: FakeAgent(),
    )
    # Swallow tracker writes (no real DB in unit tests)
    monkeypatch.setattr(usage_tracker, "USAGE_DB_PATH", None)
    logged = []
    monkeypatch.setattr(agent_module, "log_llm_call", lambda **kw: logged.append(kw))

    result = agent_module.run_f1_agent("How did it go?", "user_1", "db")

    assert result["answer"] == "Historical answer"
    assert result["cost_log"] == {"total_tokens": 8}
    assert calls == [{"messages": [("user", "How did it go?")]}]
    assert len(logged) == 1
    assert logged[0]["agent_name"] == "main_agent"
    assert logged[0]["user_id"] == "user_1"
