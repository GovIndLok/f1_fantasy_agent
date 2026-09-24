import datetime

import duckdb
import pytest

from app import database
from app.f1_data import DEFAULT_SEASONS, seed_historical_data, sync_current_season


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def race_payload(season=2025):
    race = {
        "season": str(season),
        "round": "1",
        "raceName": "Test Grand Prix",
        "date": "2025-03-01",
        "Circuit": {
            "circuitId": "test_circuit",
            "circuitName": "Test Circuit",
            "Location": {"locality": "Test City", "country": "Test Country"},
        },
        "Results": [
            {
                "Driver": {
                    "driverId": f"driver_{position}",
                    "givenName": "Test",
                    "familyName": "Driver",
                    "code": "TST",
                    "nationality": "Test",
                },
                "Constructor": {
                    "constructorId": f"team_{position}",
                    "name": "Test Team",
                    "nationality": "Test",
                },
                "grid": str(position),
                "position": str(position),
                "points": str(25 - position),
            }
            for position in range(1, 21)
        ],
    }
    return {
        "MRData": {
            "RaceTable": {
                "Races": [race],
                "total": "1",
            }
        }
    }


def sprint_results(count=20):
    return [
        {
            "Driver": {
                "driverId": f"sprint_driver_{position}",
                "givenName": "Sprint",
                "familyName": f"Driver {position}",
                "code": "SPT",
                "nationality": "Test",
            },
            "Constructor": {
                "constructorId": f"sprint_team_{position}",
                "name": "Sprint Team",
                "nationality": "Test",
            },
            "grid": str(position),
            "position": str(position),
            "points": "1",
        }
        for position in range(1, count + 1)
    ]


def install_api(monkeypatch):
    calls = []

    def get(url, timeout):
        calls.append(url)
        assert timeout > 0
        if url.endswith("/results.json?limit=100"):
            return FakeResponse(race_payload())
        if url.endswith("/sprint.json?limit=100"):
            return FakeResponse({"MRData": {"RaceTable": {"Races": []}}})
        if url.endswith("/2025.json?limit=100"):
            schedule = race_payload()["MRData"]["RaceTable"]["Races"]
            return FakeResponse(
                {"MRData": {"RaceTable": {"Races": schedule, "total": "1"}}}
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("app.f1_data.requests.get", get)
    return calls


def use_temp_databases(tmp_path, monkeypatch):
    stats_path = tmp_path / "f1_stats.db"
    players_path = tmp_path / "players.db"
    monkeypatch.setattr(database, "STATS_DB_PATH", stats_path)
    monkeypatch.setattr(database, "PLAYERS_DB_PATH", players_path)
    return stats_path, players_path


def test_default_seed_seasons_are_stable():
    assert DEFAULT_SEASONS == (2023, 2024, 2025)


def test_sync_is_idempotent(tmp_path, monkeypatch):
    use_temp_databases(tmp_path, monkeypatch)
    calls = install_api(monkeypatch)
    db = database.connect_stats()
    database.create_stats_schema(db)
    db.close()

    assert sync_current_season(datetime.date(2025, 3, 4)) == 1
    assert sync_current_season(datetime.date(2025, 3, 4)) == 0

    db = duckdb.connect(str(tmp_path / "f1_stats.db"), read_only=True)
    assert db.execute("SELECT count(*) FROM races").fetchone() == (1,)
    assert db.execute("SELECT count(*) FROM results").fetchone() == (20,)
    db.close()
    assert len(calls) == 6


def test_sync_refreshes_existing_round(tmp_path, monkeypatch):
    use_temp_databases(tmp_path, monkeypatch)
    db = database.connect_stats()
    database.create_stats_schema(db)
    db.close()
    sprint_calls = 0
    calls = []

    def get(url, timeout):
        nonlocal sprint_calls
        calls.append(url)
        if url.endswith("/results.json?limit=100"):
            return FakeResponse(race_payload())
        if url.endswith("/sprint.json?limit=100"):
            sprint_calls += 1
            if sprint_calls == 2:
                results = sprint_results()
            elif sprint_calls == 3:
                results = sprint_results(1)
            else:
                results = []
            races = [{"SprintResults": results}] if results else []
            return FakeResponse({"MRData": {"RaceTable": {"Races": races}}})
        schedule = race_payload()["MRData"]["RaceTable"]["Races"]
        return FakeResponse(
            {"MRData": {"RaceTable": {"Races": schedule, "total": "1"}}}
        )

    monkeypatch.setattr("app.f1_data.requests.get", get)

    assert sync_current_season(datetime.date(2025, 3, 4)) == 1
    assert sync_current_season(datetime.date(2025, 3, 4)) == 0
    assert sync_current_season(datetime.date(2025, 3, 4)) == 0

    db = duckdb.connect(str(tmp_path / "f1_stats.db"), read_only=True)
    assert db.execute(
        "SELECT count(*) FROM results WHERE is_sprint"
    ).fetchone() == (20,)
    db.close()
    assert len(calls) == 9


def test_failed_seed_keeps_existing_stats(tmp_path, monkeypatch):
    stats_path, _ = use_temp_databases(tmp_path, monkeypatch)
    db = database.connect_stats()
    database.create_stats_schema(db)
    db.execute("INSERT INTO circuits VALUES ('old', 'Old', 'Old', 'Old')")
    db.execute(
        "INSERT INTO races VALUES ('2024_1', 2024, 1, 'Old Race', 'old', '2024-03-01')"
    )
    db.close()

    def fail(url, timeout):
        raise RuntimeError("network failed")

    monkeypatch.setattr("app.f1_data.requests.get", fail)

    with pytest.raises(RuntimeError, match="network failed"):
        seed_historical_data((2025,))

    db = duckdb.connect(str(stats_path), read_only=True)
    assert db.execute("SELECT race_id FROM races").fetchall() == [("2024_1",)]
    db.close()


def test_seed_does_not_replace_player_data(tmp_path, monkeypatch):
    _, players_path = use_temp_databases(tmp_path, monkeypatch)
    install_api(monkeypatch)
    players = duckdb.connect(str(players_path))
    database.create_players_schema(players)
    players.execute("INSERT INTO players VALUES ('player', 'name')")
    players.execute(
        "INSERT INTO rosters VALUES ('player', 'driver_a', 'driver')"
    )
    players.close()

    assert seed_historical_data((2025,)) == 1

    players = duckdb.connect(str(players_path), read_only=True)
    assert players.execute("SELECT * FROM players").fetchall() == [
        ("player", "name")
    ]
    assert players.execute("SELECT * FROM rosters").fetchall() == [
        ("player", "driver_a", "driver")
    ]
    players.close()
