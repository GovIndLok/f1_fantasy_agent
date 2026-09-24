from types import SimpleNamespace

import duckdb
import pytest

from agents.f1_analyst import sql_agent
from agents.f1_analyst.sql_agent import VerificationResult, run_sql_query
from app import database
from app.database import create_stats_schema


class FakeModel:
    def __init__(self, queries, is_safe, reason):
        self.queries = list(queries)
        self.calls = 0
        self.get_llm_calls = 0
        self.structured = False
        self.verification = VerificationResult(is_safe=is_safe, reason=reason)

    def with_structured_output(self, schema):
        assert schema is VerificationResult
        return FakeVerifier(self.verification)

    def invoke(self, messages):
        self.calls += 1
        return SimpleNamespace(content=self.queries.pop(0))


class FakeVerifier:
    def __init__(self, verification):
        self.verification = verification

    def invoke(self, messages):
        return self.verification


@pytest.fixture()
def stats_db(tmp_path, monkeypatch):
    path = tmp_path / "f1_stats.db"
    db = duckdb.connect(str(path))
    create_stats_schema(db)
    db.execute("INSERT INTO drivers VALUES ('hamilton', 'Lewis Hamilton', 'HAM', 'British')")
    db.execute("INSERT INTO constructors VALUES ('ferrari', 'Ferrari', 'Italian')")
    db.execute("INSERT INTO circuits VALUES ('bahrain', 'Bahrain Circuit', 'Sakhir', 'Bahrain')")
    db.execute(
        "INSERT INTO races VALUES ('2024_1', 2024, 1, 'Bahrain Grand Prix', 'bahrain', '2024-03-01')"
    )
    db.execute(
        "INSERT INTO results VALUES ('2024_1', 'hamilton', 'ferrari', false, 2, 1, 25.0)"
    )
    db.close()
    monkeypatch.setattr(database, "STATS_DB_PATH", path)
    return path


def install_models(monkeypatch, queries, *, is_safe=True, reason="safe"):
    model = FakeModel(queries, is_safe, reason)

    def get_llm():
        model.get_llm_calls += 1
        return model

    monkeypatch.setattr(sql_agent, "get_llm", get_llm)
    return model


def test_sql_query_returns_generated_result(stats_db, monkeypatch):
    model = install_models(monkeypatch, ["SELECT driver_id FROM drivers"])

    result = run_sql_query("Who won the race?")

    assert model.get_llm_calls == 1
    assert "Columns: driver_id" in result
    assert "hamilton" in result


def test_sql_query_retries_execution_failure(stats_db, monkeypatch):
    generator = install_models(
        monkeypatch,
        ["SELECT missing_column FROM drivers", "SELECT driver_id FROM drivers"],
    )

    result = run_sql_query("Who won the race?")

    assert generator.calls == 2
    assert "hamilton" in result


def test_sql_query_rejects_unsafe_query(stats_db, monkeypatch):
    install_models(
        monkeypatch,
        ["DROP TABLE drivers"],
        is_safe=False,
        reason="DROP is not allowed",
    )

    result = run_sql_query("Drop the drivers table")

    assert result == "Query rejected by Verifier Agent: DROP is not allowed"


def test_sql_query_rejects_non_select_even_if_verifier_approves(stats_db, monkeypatch):
    model = install_models(monkeypatch, ["DROP TABLE drivers"], is_safe=True)

    result = run_sql_query("Drop the drivers table")

    assert model.calls == 1
    assert result == (
        "Query rejected by Verifier Agent: Only SELECT or WITH queries are allowed."
    )


def test_sql_query_formats_at_most_twenty_rows(stats_db, monkeypatch):
    install_models(monkeypatch, ["SELECT * FROM range(21)"])

    result = run_sql_query("Return 21 rows")

    assert "(19,)" in result
    assert "(20,)" not in result
    assert "... and 1 more rows." in result


def test_sql_query_blocks_external_file_access(stats_db, tmp_path, monkeypatch):
    external_file = tmp_path / "external.csv"
    external_file.write_text("secret\nvalue\n")
    query = f"SELECT * FROM read_csv_auto('{external_file}')"
    generator = install_models(monkeypatch, [query, query, query])

    result = run_sql_query("Read an external file")

    assert generator.calls == 3
    assert "SQL agent failed after 3 attempt(s)" in result


def test_sql_query_reports_missing_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "STATS_DB_PATH", tmp_path / "missing.db")

    assert run_sql_query("Anything") == (
        "Database not found. Please run the seed script first."
    )
