"""
LangChain tools for the F1 analyst agent.

Each @tool is a pure DB query. No agent logic lives here —
swap tools in/out without touching agent.py.
"""
import duckdb
from langchain_core.tools import tool


def build_tools(player_id: str, db: duckdb.DuckDBPyConnection) -> list:
    """Return a list of bound LangChain tools for the given player session."""

    @tool
    def get_my_team() -> str:
        """Returns the names of the drivers and constructors currently on the user's F1 Fantasy roster."""
        res = db.execute(
            "SELECT d.name FROM rosters r "
            "JOIN drivers d ON r.entity_id = d.driver_id "
            "WHERE r.player_id = ? AND r.entity_type = 'driver'",
            [player_id],
        ).fetchall()
        c_res = db.execute(
            "SELECT c.name FROM rosters r "
            "JOIN constructors c ON r.entity_id = c.constructor_id "
            "WHERE r.player_id = ? AND r.entity_type = 'constructor'",
            [player_id],
        ).fetchall()
        
        player_res = db.execute(
            "SELECT player_id FROM players WHERE player_id = ?", [player_id]
        ).fetchone()
        if not player_res:
            db.execute("INSERT INTO players VALUES (?, 'new_manager')", [player_id])

        lines = ["Drivers:"]
        lines += [f"- {r[0]}" for r in res]
        lines += ["Constructors:"] + [f"- {r[0]}" for r in c_res]
        return "\n".join(lines)

    @tool
    def query_f1_database(question: str) -> str:
        """Use this tool to answer ANY analytical or historical question about F1. 
        It writes and executes SQL against our F1 statistics database containing races, circuits, drivers, constructors, and results.
        Example questions: 'How did Max do in Bahrain?', 'Which constructor has the most points in 2024?', 'Who started on pole at Monza?'"""
        from agents.f1_analyst.sql_agent import run_sql_query
        return run_sql_query(question)

    return [get_my_team, query_f1_database]

