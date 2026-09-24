from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

import duckdb
from fastapi import Depends

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PLAYERS_DB_PATH = DATA_DIR / "players.db"
STATS_DB_PATH = DATA_DIR / "f1_stats.db"


def create_players_schema(db: duckdb.DuckDBPyConnection) -> None:
    db.execute("BEGIN TRANSACTION")
    try:
        tables = {
            row[0]
            for row in db.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main'"
            ).fetchall()
        }
        player_rows = (
            db.execute("SELECT player_id, username FROM players").fetchall()
            if "players" in tables
            else []
        )
        roster_rows = (
            db.execute(
                "SELECT player_id, entity_id, entity_type FROM rosters"
            ).fetchall()
            if "rosters" in tables
            else []
        )
        if "rosters" in tables:
            db.execute("DROP TABLE rosters")
        if "players" in tables:
            db.execute("DROP TABLE players")
        db.execute(
            """
            CREATE TABLE players (
                player_id VARCHAR PRIMARY KEY,
                username VARCHAR NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE rosters (
                player_id VARCHAR NOT NULL,
                entity_id VARCHAR NOT NULL,
                entity_type VARCHAR NOT NULL
                    CHECK (entity_type IN ('driver', 'constructor')),
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
            """
        )
        db.execute(
            """
            CREATE UNIQUE INDEX rosters_player_entity_unique
            ON rosters(player_id, entity_id)
            """
        )
        for row in player_rows:
            db.execute(
                "INSERT INTO players (player_id, username) VALUES (?, ?)",
                list(row),
            )
        for row in roster_rows:
            db.execute(
                "INSERT INTO rosters (player_id, entity_id, entity_type) "
                "VALUES (?, ?, ?)",
                list(row),
            )
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise


def create_stats_schema(db: duckdb.DuckDBPyConnection) -> None:
    statements = (
        """
        CREATE TABLE IF NOT EXISTS drivers (
            driver_id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            code VARCHAR NOT NULL,
            nationality VARCHAR NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS constructors (
            constructor_id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            nationality VARCHAR NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS circuits (
            circuit_id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            locality VARCHAR NOT NULL,
            country VARCHAR NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS races (
            race_id VARCHAR PRIMARY KEY,
            season INTEGER NOT NULL,
            round INTEGER NOT NULL,
            race_name VARCHAR NOT NULL,
            circuit_id VARCHAR NOT NULL,
            date VARCHAR NOT NULL,
            UNIQUE (season, round),
            FOREIGN KEY (circuit_id) REFERENCES circuits(circuit_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS results (
            race_id VARCHAR NOT NULL,
            driver_id VARCHAR NOT NULL,
            constructor_id VARCHAR NOT NULL,
            is_sprint BOOLEAN NOT NULL,
            grid_position INTEGER NOT NULL,
            finish_position INTEGER NOT NULL,
            points DOUBLE NOT NULL,
            PRIMARY KEY (race_id, driver_id, is_sprint),
            FOREIGN KEY (race_id) REFERENCES races(race_id),
            FOREIGN KEY (driver_id) REFERENCES drivers(driver_id),
            FOREIGN KEY (constructor_id) REFERENCES constructors(constructor_id)
        )
        """,
    )
    for statement in statements:
        db.execute(statement)


def connect_players() -> duckdb.DuckDBPyConnection:
    PLAYERS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(PLAYERS_DB_PATH))


def connect_stats(*, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    if not read_only:
        STATS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(STATS_DB_PATH), read_only=read_only)


def get_db() -> Iterator[duckdb.DuckDBPyConnection]:
    db = connect_players()
    try:
        db.execute(
            f"ATTACH IF NOT EXISTS '{STATS_DB_PATH}' AS stats (READ_ONLY)"
        )
        yield db
    finally:
        db.close()


DbDep = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]
