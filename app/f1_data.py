import argparse
import datetime
import time
from collections.abc import Iterable

import duckdb
import requests

from app import database

BASE_URL = "https://api.jolpi.ca/ergast/f1"
DEFAULT_SEASONS = (2023, 2024, 2025)
REQUEST_TIMEOUT = 10
RETRY_DELAY_SECONDS = 4
# ponytail: assumes 20 classified F1 results; split by season/classification if future formats differ.
F1_DRIVER_COUNT = 20


def _get_json(url: str):
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    if response.status_code == 429:
        time.sleep(RETRY_DELAY_SECONDS)
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _schedule(season: int) -> list[dict]:
    payload = _get_json(f"{BASE_URL}/{season}.json?limit=100")
    return payload["MRData"]["RaceTable"]["Races"]


def _round_data(season: int, round_number: int) -> tuple[dict, list[dict]] | None:
    results_url = f"{BASE_URL}/{season}/{round_number}/results.json?limit=100"
    races = _get_json(results_url)["MRData"]["RaceTable"]["Races"]
    if not races:
        return None

    sprint_url = f"{BASE_URL}/{season}/{round_number}/sprint.json?limit=100"
    sprint_races = _get_json(sprint_url)["MRData"]["RaceTable"]["Races"]
    sprint_results = (
        sprint_races[0].get("SprintResults", []) if sprint_races else []
    )
    return races[0], sprint_results


def _already_stored(db, season: int, round_number: int) -> bool:
    return (
        db.execute(
            "SELECT 1 FROM races WHERE season = ? AND round = ?",
            [season, round_number],
        ).fetchone()
        is not None
    )


def _insert_result(
    db,
    race_id: str,
    result: dict,
    is_sprint: bool,
) -> None:
    driver = result["Driver"]
    constructor = result["Constructor"]
    db.execute(
        """
        INSERT INTO drivers (driver_id, name, code, nationality)
        VALUES (?, ?, ?, ?)
        ON CONFLICT DO NOTHING
        """,
        [
            driver["driverId"],
            f"{driver.get('givenName')} {driver.get('familyName')}",
            driver.get("code", ""),
            driver.get("nationality", ""),
        ],
    )
    db.execute(
        """
        INSERT INTO constructors (constructor_id, name, nationality)
        VALUES (?, ?, ?)
        ON CONFLICT DO NOTHING
        """,
        [
            constructor["constructorId"],
            constructor["name"],
            constructor["nationality"],
        ],
    )
    db.execute(
        """
        INSERT INTO results (
            race_id,
            driver_id,
            constructor_id,
            is_sprint,
            grid_position,
            finish_position,
            points
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            race_id,
            driver["driverId"],
            constructor["constructorId"],
            is_sprint,
            int(result["grid"]),
            int(result["position"]),
            float(result["points"]),
        ],
    )


def _existing_sprint_results(db, race_id: str) -> list[tuple]:
    return db.execute(
        "SELECT race_id, driver_id, constructor_id, is_sprint, "
        "grid_position, finish_position, points FROM results "
        "WHERE race_id = ? AND is_sprint",
        [race_id],
    ).fetchall()


def _insert_circuit(db, circuit: dict) -> None:
    db.execute(
        """
        INSERT INTO circuits (circuit_id, name, locality, country)
        VALUES (?, ?, ?, ?)
        ON CONFLICT DO NOTHING
        """,
        [
            circuit["circuitId"],
            circuit["circuitName"],
            circuit["Location"]["locality"],
            circuit["Location"]["country"],
        ],
    )


def _insert_race(
    db,
    season: int,
    round_number: int,
    race: dict,
) -> None:
    db.execute(
        """
        INSERT INTO races (
            race_id, season, round, race_name, circuit_id, date
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            f"{season}_{round_number}",
            season,
            round_number,
            race["raceName"],
            race["Circuit"]["circuitId"],
            race["date"],
        ],
    )


def _write_round(
    db,
    *,
    season: int,
    round_number: int,
    was_stored: bool,
    race_id: str,
    race: dict,
    sprint_results: list[dict],
    preserved_sprint: list[tuple],
) -> None:
    results = [(result, False) for result in race["Results"]]
    results.extend((result, True) for result in sprint_results)
    db.execute("BEGIN TRANSACTION")
    try:
        if was_stored:
            db.execute("DELETE FROM results WHERE race_id = ?", [race_id])
        _insert_circuit(db, race["Circuit"])
        # ponytail: race metadata is immutable after publication; use a
        # maintenance replacement if upstream corrections appear.
        if not was_stored:
            _insert_race(db, season, round_number, race)
        for result, is_sprint in results:
            _insert_result(db, race_id, result, is_sprint)
        for result in preserved_sprint:
            db.execute(
                "INSERT INTO results VALUES (?, ?, ?, ?, ?, ?, ?)",
                result,
            )
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise


def _store_round(db, season: int, round_number: int) -> bool:
    was_stored = _already_stored(db, season, round_number)
    round_data = _round_data(season, round_number)
    if not round_data or len(round_data[0].get("Results", [])) != F1_DRIVER_COUNT:
        return False

    race, sprint_results = round_data
    if sprint_results and len(sprint_results) != F1_DRIVER_COUNT:
        sprint_results = []
    race_id = f"{season}_{round_number}"
    preserved_sprint = (
        _existing_sprint_results(db, race_id)
        if was_stored and not sprint_results
        else []
    )
    _write_round(
        db,
        season=season,
        round_number=round_number,
        was_stored=was_stored,
        race_id=race_id,
        race=race,
        sprint_results=sprint_results,
        preserved_sprint=preserved_sprint,
    )
    return not was_stored


def _sync_season(
    db,
    season: int,
    *,
    as_of: datetime.date | None = None,
) -> int:
    stored = 0
    for race in _schedule(season):
        race_date = datetime.date.fromisoformat(race["date"])
        if as_of is not None and as_of < race_date + datetime.timedelta(days=3):
            continue
        stored += _store_round(db, season, int(race["round"]))
    return stored


def sync_current_season(as_of: datetime.date | None = None) -> int:
    as_of = as_of or datetime.date.today()
    db = database.connect_stats()
    try:
        table = db.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_name = 'races'"
        ).fetchone()
        if table is None:
            raise RuntimeError(
                "F1 stats database is not initialized. Run the seed command."
            )
        return _sync_season(db, as_of.year, as_of=as_of)
    finally:
        db.close()


def seed_historical_data(
    seasons: Iterable[int] = DEFAULT_SEASONS,
) -> int:
    players = database.connect_players()
    try:
        database.create_players_schema(players)
    finally:
        players.close()

    temporary_path = database.STATS_DB_PATH.with_name("f1_stats.tmp.db")
    temporary_path.unlink(missing_ok=True)
    try:
        with duckdb.connect(str(temporary_path)) as db:
            database.create_stats_schema(db)
            count = sum(_sync_season(db, int(season)) for season in seasons)
        temporary_path.replace(database.STATS_DB_PATH)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("seed", "sync"))
    args = parser.parse_args()
    if args.command == "seed":
        count = seed_historical_data()
    else:
        count = sync_current_season()
    print(f"Stored {count} new F1 race(s).")


if __name__ == "__main__":
    main()
