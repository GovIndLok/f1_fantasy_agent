import duckdb
from pydantic import BaseModel, Field

from agents.f1_analyst.utils import content_to_text, get_llm
from app import database

MAX_RETRIES = 2
MAX_ROWS = 20


class VerificationResult(BaseModel):
    is_safe: bool = Field(
        description=(
            "True if the query only uses SELECT and targets allowed tables. "
            "Must be False if it contains DROP, DELETE, INSERT, UPDATE, or PRAGMA."
        )
    )
    reason: str = Field(
        description="Explanation of why the query is safe or rejected."
    )


def _schema_context(db: duckdb.DuckDBPyConnection) -> str:
    tables = [
        row[0]
        for row in db.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
    ]
    lines = []
    for table in tables:
        schema = db.execute(f"DESCRIBE {table}").fetchall()
        lines.append(
            f"Table '{table}': "
            + ", ".join(f"{row[0]} ({row[1]})" for row in schema)
        )
        samples = db.execute(f"SELECT * FROM {table} LIMIT 2").fetchall()
        lines.append(f"  Sample data: {samples}")
    return "\n".join(lines)


def _generate_sql(generator, question: str, schema: str, last_error: str) -> str:
    error_hint = ""
    if last_error:
        error_hint = (
            "\n\nThe previous query attempt failed with this error:\n"
            f"{last_error}\n"
            "Please fix the query so it does not produce that error."
        )
    prompt = (
        "You are a DuckDB SQL expert. Write a query to answer the following question.\n\n"
        f"Schema and Samples:\n{schema}\n\n"
        f"Question: {question}{error_hint}\n\n"
        "Return ONLY the raw SQL query. Do not wrap in markdown tags like ```sql. "
        "Ensure you handle joins correctly. "
        "Do not try to attach databases; just query the tables directly."
    )
    raw = generator.invoke([("user", prompt)]).content
    return content_to_text(raw).replace("```sql", "").replace("```", "").strip()


def _is_read_only_select(sql: str) -> bool:
    return sql.lstrip().upper().startswith(("SELECT", "WITH"))


def _bounded_sql(sql: str) -> str:
    return (
        f"SELECT * FROM ({sql.rstrip('; \t\r\n')}) AS bounded_result "
        f"LIMIT {MAX_ROWS + 1}"
    )


def _format_result(
    rows: list[tuple], columns: list[str]
) -> str:
    if not rows:
        return "Query executed successfully but returned no results."

    lines = [f"Columns: {', '.join(columns)}"]
    lines.extend(str(row) for row in rows[:MAX_ROWS])
    if len(rows) > MAX_ROWS:
        lines.append(f"... and {len(rows) - MAX_ROWS} more rows.")
    return "\n".join(lines)


def run_sql_query(question: str) -> str:
    if not database.STATS_DB_PATH.exists():
        return "Database not found. Please run the seed script first."

    with database.connect_stats(read_only=True) as db:
        db.execute("SET enable_external_access = false")
        schema = _schema_context(db)
        generator = get_llm()
        verifier = generator.with_structured_output(VerificationResult)
        last_error = ""

        for attempt in range(MAX_RETRIES + 1):
            sql = _generate_sql(generator, question, schema, last_error)
            verification = verifier.invoke(
                [
                    (
                        "user",
                        f"Review this DuckDB SQL query:\n{sql}\n\n"
                        "Is it a safe, read-only SELECT query? "
                        "Reject anything that modifies data, drops tables, or alters settings.",
                    )
                ]
            )
            if not verification.is_safe:
                return f"Query rejected by Verifier Agent: {verification.reason}"
            if not _is_read_only_select(sql):
                return (
                    "Query rejected by Verifier Agent: Only SELECT or WITH queries "
                    "are allowed."
                )

            try:
                rows = db.execute(_bounded_sql(sql)).fetchall()
                columns = [description[0] for description in db.description]
            except Exception as exc:
                last_error = str(exc)
                if attempt == MAX_RETRIES:
                    return (
                        f"SQL agent failed after {attempt + 1} attempt(s). "
                        f"Last error: {last_error}"
                    )
                continue

            return _format_result(rows, columns)
