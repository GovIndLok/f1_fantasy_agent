"""
Unit tests for app/rosters/service.py — transfer_roster_entities().

These tests use an in-memory DuckDB that mimics the real split-DB setup
(app DB + stats attached READ_ONLY). No FastAPI, no HTTP, no mocking
of the LLM — pure business-logic coverage.
"""
import pytest
import duckdb

from app.database import create_app_schema
from app.rosters.service import get_roster, transfer_roster_entities

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db():
    """In-memory DuckDB with rosters + an attached in-memory stats DB."""
    con = duckdb.connect(":memory:")

    # Attach a second in-memory DB as 'stats' to mirror production layout
    con.execute("ATTACH ':memory:' AS stats")

    # Create stats tables
    con.execute("""
        CREATE TABLE stats.drivers (
            driver_id VARCHAR PRIMARY KEY,
            name      VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE stats.constructors (
            constructor_id VARCHAR PRIMARY KEY,
            name           VARCHAR
        )
    """)

    # Seed some drivers and constructors
    con.executemany(
        "INSERT INTO stats.drivers VALUES (?, ?)",
        [
            ["max_verstappen", "Max Verstappen"],
            ["perez",          "Sergio Perez"],
            ["hamilton",       "Lewis Hamilton"],
            ["russell",        "George Russell"],
            ["alonso",         "Fernando Alonso"],
            ["sainz",          "Carlos Sainz"],
        ],
    )
    con.executemany(
        "INSERT INTO stats.constructors VALUES (?, ?)",
        [
            ["red_bull", "Red Bull"],
            ["mercedes", "Mercedes"],
            ["ferrari",  "Ferrari"],
        ],
    )

    create_app_schema(con)

    # Seed user_1 with a valid 5-driver, 2-constructor roster.
    con.executemany(
        "INSERT INTO rosters VALUES (?, ?, ?)",
        [
            ["user_1", "max_verstappen", "driver"],
            ["user_1", "perez",          "driver"],
            ["user_1", "hamilton",       "driver"],
            ["user_1", "russell",        "driver"],
            ["user_1", "alonso",         "driver"],
            ["user_1", "red_bull",       "constructor"],
            ["user_1", "mercedes",       "constructor"],
        ],
    )

    yield con
    con.close()


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

def test_get_roster_returns_names_and_types(db):
    roster = get_roster("user_1", db)

    assert len(roster) == 7
    assert {
        "entity_id": "max_verstappen",
        "name": "Max Verstappen",
        "entity_type": "driver",
    } in roster
    assert {
        "entity_id": "red_bull",
        "name": "Red Bull",
        "entity_type": "constructor",
    } in roster


def test_valid_driver_swap(db):
    """Swap one driver out and bring a valid replacement in."""
    result = transfer_roster_entities(
        player_id="user_1",
        remove=["alonso"],
        add=["sainz"],
        db=db,
    )

    assert result["status"] == "ok"
    assert "alonso" in result["transferred_out"]
    assert "sainz" in result["transferred_in"]

    # Verify DB state
    rows = db.execute(
        "SELECT entity_id FROM rosters WHERE player_id = 'user_1' AND entity_type = 'driver'"
    ).fetchall()
    entity_ids = {r[0] for r in rows}
    assert "sainz" in entity_ids
    assert "alonso" not in entity_ids
    assert len(entity_ids) == 5  # still exactly 5 drivers


def test_valid_constructor_swap(db):
    """Swap one constructor."""
    result = transfer_roster_entities(
        player_id="user_1",
        remove=["mercedes"],
        add=["ferrari"],
        db=db,
    )

    assert result["status"] == "ok"
    rows = db.execute(
        "SELECT entity_id FROM rosters WHERE player_id = 'user_1' AND entity_type = 'constructor'"
    ).fetchall()
    ids = {r[0] for r in rows}
    assert "ferrari" in ids
    assert "mercedes" not in ids
    assert len(ids) == 2


def test_no_duplicate_rows_after_multiple_inserts(db):
    """Calling the service twice should not produce duplicate roster rows."""
    transfer_roster_entities(
        player_id="user_1",
        remove=["alonso"],
        add=["sainz"],
        db=db,
    )
    # Bring alonso back (sainz out)
    transfer_roster_entities(
        player_id="user_1",
        remove=["sainz"],
        add=["alonso"],
        db=db,
    )

    count = db.execute(
        "SELECT COUNT(*) FROM rosters WHERE player_id = 'user_1'"
    ).fetchone()[0]
    assert count == 7  # always exactly 7 rows


def test_get_roster_returns_empty_for_unknown_player(db):
    """An authenticated user with no roster entries gets an empty list.

    There is no longer a players table to insert into — the player_id is
    simply the Supabase user UUID and needs no local record.
    """
    roster = get_roster("brand_new_player_uuid", db)
    assert roster == []


# ---------------------------------------------------------------------------
# Business-rule violation tests
# ---------------------------------------------------------------------------

def test_transfer_rolls_back_when_persistence_fails(db):
    db.execute("CREATE TABLE roster_backup AS SELECT * FROM rosters")
    db.execute("DROP TABLE rosters")
    db.execute("""
        CREATE TABLE rosters (
            player_id VARCHAR,
            entity_id VARCHAR CHECK (entity_id <> 'sainz'),
            entity_type VARCHAR
        )
    """)
    db.execute("INSERT INTO rosters SELECT * FROM roster_backup")

    with pytest.raises(duckdb.ConstraintException):
        transfer_roster_entities(
            player_id="user_1",
            remove=["alonso"],
            add=["sainz"],
            db=db,
        )

    rows = db.execute(
        "SELECT entity_id FROM rosters WHERE player_id = 'user_1'"
    ).fetchall()
    assert len(rows) == 7
    assert ("alonso",) in rows
    assert ("sainz",) not in rows


def test_rejects_adding_entity_already_on_roster(db):
    with pytest.raises(ValueError, match="already on your roster"):
        transfer_roster_entities(
            player_id="user_1",
            remove=["alonso"],
            add=["hamilton"],
            db=db,
        )

    assert db.execute(
        "SELECT count(*) FROM rosters WHERE player_id = 'user_1'"
    ).fetchone() == (7,)


def test_rejects_duplicate_additions(db):
    with pytest.raises(ValueError, match="Duplicate entities in add"):
        transfer_roster_entities(
            player_id="user_1",
            remove=["alonso"],
            add=["sainz", "sainz"],
            db=db,
        )


def test_rejects_duplicate_removals(db):
    with pytest.raises(ValueError, match="Duplicate entities in remove"):
        transfer_roster_entities(
            player_id="user_1",
            remove=["alonso", "alonso"],
            add=["sainz"],
            db=db,
        )

    assert db.execute(
        "SELECT count(*) FROM rosters WHERE player_id = 'user_1'"
    ).fetchone() == (7,)


def test_raises_when_removing_entity_not_on_roster(db):
    """Trying to remove leclerc (not on roster) must raise ValueError."""
    with pytest.raises(ValueError, match="not on your roster"):
        transfer_roster_entities(
            player_id="user_1",
            remove=["leclerc"],   # not seeded on user_1
            add=["sainz"],
            db=db,
        )


def test_raises_on_unknown_add_entity(db):
    """Adding a completely unknown entity ID must raise ValueError."""
    with pytest.raises(ValueError, match="Unknown entity"):
        transfer_roster_entities(
            player_id="user_1",
            remove=["alonso"],
            add=["totally_fake_driver_9999"],
            db=db,
        )


def test_raises_when_roster_would_have_too_few_drivers(db):
    """Removing a driver without a driver replacement breaks the 5-driver rule."""
    with pytest.raises(ValueError, match="5 drivers"):
        transfer_roster_entities(
            player_id="user_1",
            remove=["alonso"],
            add=[],   # no replacement
            db=db,
        )


def test_raises_when_roster_would_have_too_many_constructors(db):
    """Adding a constructor without removing one breaks the 2-constructor rule.

    Scenario: swap two drivers for two drivers (roster stays at 5 drivers)
    then add a third constructor without removing one → 3 constructors total.
    We do this in one call: remove no constructors, add one constructor while
    also removing one driver and adding one driver so driver count stays at 5.
    Net result: 5 drivers, 3 constructors → ValueError.
    """
    with pytest.raises(ValueError, match="2 constructors"):
        transfer_roster_entities(
            player_id="user_1",
            remove=["alonso"],          # −1 driver
            add=["sainz", "ferrari"],   # +1 driver, +1 constructor → 5d, 3c
            db=db,
        )
