from types import SimpleNamespace

from agents.f1_analyst import agent as agent_module


def test_agent_initializes_model_per_invocation(monkeypatch):
    calls = []

    class FakeAgent:
        def invoke(self, messages):
            calls.append(messages)
            return {
                "messages": [
                    SimpleNamespace(content=[{"text": "Historical"}, " answer"])
                ]
            }

    monkeypatch.setattr(agent_module, "build_tools", lambda player_id, db: ["tool"])
    monkeypatch.setattr(agent_module, "get_llm", lambda: "model")
    monkeypatch.setattr(
        agent_module,
        "create_agent",
        lambda model, tools, system_prompt: FakeAgent(),
    )

    result = agent_module.run_f1_agent("How did it go?", "user_1", "db")

    assert result == {
        "answer": "Historical answer",
        "cost_log": {"total_tokens": 6},
    }
    assert calls == [{"messages": [("user", "How did it go?")]}]
