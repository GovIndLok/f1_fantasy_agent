import duckdb
from langchain.tools import tool

from agents.f1_analyst.sql_agent import run_sql_query
from app.rosters.service import get_roster, transfer_roster_entities


def build_tools(player_id: str, db: duckdb.DuckDBPyConnection) -> list:
    @tool
    def get_my_team() -> str:
        """Returns the names of the drivers and constructors currently on the user's F1 Fantasy roster."""
        roster = get_roster(player_id, db)
        lines = ["Drivers:"]
        lines.extend(
            f"- {entity['name']}"
            for entity in roster
            if entity["entity_type"] == "driver"
        )
        lines.append("Constructors:")
        lines.extend(
            f"- {entity['name']}"
            for entity in roster
            if entity["entity_type"] == "constructor"
        )
        return "\n".join(lines)

    @tool
    def query_f1_database(question: str) -> str:
        """Use this tool for analytical or historical F1 questions.

        It queries the F1 statistics database containing races, circuits, drivers,
        constructors, and results. Example: 'How did Max do in Bahrain?' or
        'Which constructor scored the most points in 2024?'
        """
        return run_sql_query(question)

    @tool
    def transfer_roster(remove: list[str], add: list[str]) -> str:
        """Make a transfer in the user's F1 Fantasy roster.

        Use Ergast-format IDs to remove and add one or more entities. The resulting
        roster must contain exactly 5 drivers and 2 constructors.
        """
        try:
            result = transfer_roster_entities(player_id, remove, add, db)
            removed = ", ".join(result["transferred_out"]) or "none"
            added = ", ".join(result["transferred_in"]) or "none"
            return f"Transfer complete. Out: {removed}. In: {added}."
        except ValueError as exc:
            return f"Transfer failed: {exc}"

    return [get_my_team, query_f1_database, transfer_roster]
