import duckdb
import pytest

from app.database import create_app_schema, create_stats_schema


def test_app_schema_enforces_roster_constraints():
    """rosters must enforce the entity_type check and the uniqueness index."""
    db = duckdb.connect(":memory:")
    create_app_schema(db)

    # Valid insert — no players table needed
    db.execute("INSERT INTO rosters VALUES ('player', 'max_verstappen', 'driver')")

    # Duplicate (player_id, entity_id) must be rejected
    with pytest.raises(duckdb.ConstraintException):
        db.execute(
            "INSERT INTO rosters VALUES ('player', 'max_verstappen', 'driver')"
        )

    # Invalid entity_type must be rejected
    with pytest.raises(duckdb.ConstraintException):
        db.execute("INSERT INTO rosters VALUES ('player', 'bad', 'invalid')")

    db.close()


def test_app_schema_migrates_legacy_players_table():
    """create_app_schema on an old DB (players + rosters with FK) must:
    - drop the players table
    - preserve all existing roster rows
    - re-apply the entity_type check and uniqueness constraints
    """
    db = duckdb.connect(":memory:")
    # Simulate the old schema
    db.execute("CREATE TABLE players (player_id VARCHAR PRIMARY KEY, username VARCHAR NOT NULL)")
    db.execute(
        "CREATE TABLE rosters (player_id VARCHAR, entity_id VARCHAR, entity_type VARCHAR)"
    )
    db.execute("INSERT INTO players VALUES ('player', 'name')")
    db.execute("INSERT INTO rosters VALUES ('player', 'max_verstappen', 'driver')")

    create_app_schema(db)

    # Roster row preserved
    assert db.execute("SELECT * FROM rosters").fetchall() == [
        ("player", "max_verstappen", "driver")
    ]
    # players table gone
    tables = {
        row[0]
        for row in db.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main'"
        ).fetchall()
    }
    assert "players" not in tables

    # Constraints re-applied
    with pytest.raises(duckdb.ConstraintException):
        db.execute("INSERT INTO rosters VALUES ('player', 'bad', 'invalid')")
    with pytest.raises(duckdb.ConstraintException):
        db.execute(
            "INSERT INTO rosters VALUES ('player', 'max_verstappen', 'driver')"
        )
    db.close()


def test_stats_schema_has_stable_keys():
    db = duckdb.connect(":memory:")
    create_stats_schema(db)
    db.execute("INSERT INTO drivers VALUES ('driver', 'Driver', 'DRI', 'Country')")
    db.execute(
        "INSERT INTO constructors VALUES ('constructor', 'Constructor', 'Country')"
    )
    db.execute("INSERT INTO circuits VALUES ('circuit', 'Circuit', 'City', 'Country')")
    db.execute(
        "INSERT INTO races VALUES ('2025_1', 2025, 1, 'Race', 'circuit', '2025-03-16')"
    )
    db.execute(
        "INSERT INTO results VALUES "
        "('2025_1', 'driver', 'constructor', false, 1, 1, 25.0)"
    )

    with pytest.raises(duckdb.ConstraintException):
        db.execute(
            "INSERT INTO races VALUES "
            "('2025_1', 2025, 1, 'Duplicate', 'circuit', '2025-03-16')"
        )

    db.close()
