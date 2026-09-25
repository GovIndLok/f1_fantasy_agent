import duckdb

from agents.f1_analyst.tools import build_tools
from app.database import create_app_schema


def test_tools_keep_model_facing_interfaces():
    db = duckdb.connect(":memory:")
    create_app_schema(db)
    db.execute("ATTACH ':memory:' AS stats")
    db.execute("CREATE TABLE stats.drivers (driver_id VARCHAR, name VARCHAR)")
    db.execute("CREATE TABLE stats.constructors (constructor_id VARCHAR, name VARCHAR)")
    db.execute("INSERT INTO rosters VALUES ('user_1', 'driver_a', 'driver')")
    db.execute("INSERT INTO rosters VALUES ('user_1', 'driver_b', 'driver')")
    db.execute("INSERT INTO rosters VALUES ('user_1', 'driver_c', 'driver')")
    db.execute("INSERT INTO rosters VALUES ('user_1', 'driver_d', 'driver')")
    db.execute("INSERT INTO rosters VALUES ('user_1', 'driver_e', 'driver')")
    db.execute("INSERT INTO rosters VALUES ('user_1', 'team_a', 'constructor')")
    db.execute("INSERT INTO rosters VALUES ('user_1', 'team_b', 'constructor')")
    db.execute("INSERT INTO stats.drivers VALUES ('driver_a', 'Driver A')")
    db.execute("INSERT INTO stats.drivers VALUES ('driver_f', 'Driver F')")

    tools = build_tools("user_1", db)

    assert [item.name for item in tools] == [
        "get_my_team",
        "query_f1_database",
        "transfer_roster",
    ]
    assert tools[1].args == {"question": {"title": "Question", "type": "string"}}
    assert tools[2].args == {
        "remove": {
            "items": {"type": "string"},
            "title": "Remove",
            "type": "array",
        },
        "add": {
            "items": {"type": "string"},
            "title": "Add",
            "type": "array",
        },
    }
    assert "Driver A" in tools[0].invoke({})

    result = tools[2].invoke({"remove": ["driver_a"], "add": ["driver_f"]})
    assert result == "Transfer complete. Out: driver_a. In: driver_f."
    db.close()
