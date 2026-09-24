import duckdb
import pytest

from app.database import create_players_schema, create_stats_schema


def test_player_schema_enforces_roster_integrity():
    db = duckdb.connect(":memory:")
    create_players_schema(db)
    db.execute("INSERT INTO players VALUES ('player', 'name')")
    db.execute("INSERT INTO rosters VALUES ('player', 'max_verstappen', 'driver')")

    with pytest.raises(duckdb.ConstraintException):
        db.execute(
            "INSERT INTO rosters VALUES ('player', 'max_verstappen', 'driver')"
        )

    with pytest.raises(duckdb.ConstraintException):
        db.execute("INSERT INTO rosters VALUES ('player', 'bad', 'invalid')")

    db.close()


def test_player_schema_upgrades_legacy_rosters():
    db = duckdb.connect(":memory:")
    db.execute("CREATE TABLE players (player_id VARCHAR, username VARCHAR)")
    db.execute(
        "CREATE TABLE rosters (player_id VARCHAR, entity_id VARCHAR, entity_type VARCHAR)"
    )
    db.execute("INSERT INTO players VALUES ('player', 'name')")
    db.execute("INSERT INTO rosters VALUES ('player', 'max_verstappen', 'driver')")

    create_players_schema(db)

    assert db.execute("SELECT * FROM rosters").fetchall() == [
        ("player", "max_verstappen", "driver")
    ]
    with pytest.raises(duckdb.ConstraintException):
        db.execute("INSERT INTO rosters VALUES ('player', 'bad', 'invalid')")
    with pytest.raises(duckdb.ConstraintException):
        db.execute("INSERT INTO players VALUES ('player', 'duplicate')")
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
