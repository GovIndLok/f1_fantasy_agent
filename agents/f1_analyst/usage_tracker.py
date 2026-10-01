"""Persistent LLM usage tracking.

Writes one row per actual LLM call to data/llm_usage.db (SQLite).
All writes are fire-and-forget: any exception is printed to stderr so the
caller's request is never affected.
"""
import sqlite3
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
USAGE_DB_PATH = DATA_DIR / "llm_usage.db"

_DDL = """
CREATE TABLE IF NOT EXISTS llm_calls (
    call_id          TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL,
    request_id       TEXT NOT NULL,
    agent_name       TEXT NOT NULL,
    model            TEXT NOT NULL,
    input_tokens     INTEGER,
    output_tokens    INTEGER,
    total_tokens     INTEGER,
    reasoning_tokens INTEGER,
    timestamp        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_calls_request ON llm_calls(request_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_user    ON llm_calls(user_id);
"""


def _init_db(con: sqlite3.Connection) -> None:
    con.executescript(_DDL)


def log_llm_call(
    *,
    user_id: str,
    request_id: str,
    agent_name: str,
    model: str,
    usage_metadata: dict | None,
) -> None:
    """Write one LLM call record to llm_usage.db.

    Never raises; exceptions are printed to stderr so the caller is unaffected.
    usage_metadata is the AIMessage.usage_metadata dict (or None if unavailable).
    """
    try:
        meta = usage_metadata or {}
        reasoning: int | None = None
        details = meta.get("output_token_details")
        if isinstance(details, dict):
            reasoning = details.get("reasoning")

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(USAGE_DB_PATH) as con:
            _init_db(con)
            con.execute(
                """
                INSERT INTO llm_calls
                    (call_id, user_id, request_id, agent_name, model,
                     input_tokens, output_tokens, total_tokens, reasoning_tokens,
                     timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    user_id,
                    request_id,
                    agent_name,
                    model,
                    meta.get("input_tokens"),
                    meta.get("output_tokens"),
                    meta.get("total_tokens"),
                    reasoning,
                    datetime.now(UTC).isoformat(),
                ),
            )
    except Exception as exc:  # noqa: BLE001
        print(f"[usage_tracker] write failed: {exc}", file=sys.stderr)
