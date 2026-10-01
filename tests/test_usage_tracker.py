import sqlite3

import pytest

from agents.f1_analyst import usage_tracker


def test_log_llm_call_writes_row(tmp_path, monkeypatch):
    monkeypatch.setattr(usage_tracker, "DATA_DIR", tmp_path)
    monkeypatch.setattr(usage_tracker, "USAGE_DB_PATH", tmp_path / "llm_usage.db")

    usage_tracker.log_llm_call(
        user_id="user-abc",
        request_id="req-123",
        agent_name="main_agent",
        model="gemini-3.5-flash-lite",
        usage_metadata={
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
            "output_token_details": {"reasoning": 5},
        },
    )

    con = sqlite3.connect(tmp_path / "llm_usage.db")
    row = con.execute("SELECT * FROM llm_calls").fetchone()
    con.close()

    assert row is not None
    _call_id, user_id, request_id, agent_name, model, input_t, output_t, total_t, reasoning_t, ts = row
    assert user_id == "user-abc"
    assert request_id == "req-123"
    assert agent_name == "main_agent"
    assert model == "gemini-3.5-flash-lite"
    assert input_t == 10
    assert output_t == 20
    assert total_t == 30
    assert reasoning_t == 5
    assert ts  # non-empty ISO timestamp


def test_log_llm_call_stores_null_when_metadata_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(usage_tracker, "DATA_DIR", tmp_path)
    monkeypatch.setattr(usage_tracker, "USAGE_DB_PATH", tmp_path / "llm_usage.db")

    usage_tracker.log_llm_call(
        user_id="u",
        request_id="r",
        agent_name="sql_generator",
        model="m",
        usage_metadata=None,
    )

    con = sqlite3.connect(tmp_path / "llm_usage.db")
    row = con.execute("SELECT input_tokens, output_tokens, total_tokens, reasoning_tokens FROM llm_calls").fetchone()
    con.close()

    assert row == (None, None, None, None)


def test_log_llm_call_swallows_write_error(monkeypatch):
    def bad_connect(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(usage_tracker.sqlite3, "connect", bad_connect)

    # Must not raise
    usage_tracker.log_llm_call(
        user_id="u",
        request_id="r",
        agent_name="main_agent",
        model="m",
        usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )
