import duckdb


def _ensure_player(player_id: str, db: duckdb.DuckDBPyConnection) -> None:
    db.execute(
        "INSERT INTO players (player_id, username) VALUES (?, 'new_manager') "
        "ON CONFLICT DO NOTHING",
        [player_id],
    )


def _load_roster(
    player_id: str, db: duckdb.DuckDBPyConnection
) -> dict[str, str]:
    rows = db.execute(
        "SELECT entity_id, entity_type FROM rosters WHERE player_id = ?",
        [player_id],
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def _resolve_additions(
    add: list[str], db: duckdb.DuckDBPyConnection
) -> dict[str, str]:
    if not add:
        return {}

    placeholders = ", ".join("?" for _ in add)
    found_drivers = {
        row[0]
        for row in db.execute(
            f"SELECT driver_id FROM stats.drivers WHERE driver_id IN ({placeholders})",
            add,
        ).fetchall()
    }
    found_constructors = {
        row[0]
        for row in db.execute(
            f"SELECT constructor_id FROM stats.constructors "
            f"WHERE constructor_id IN ({placeholders})",
            add,
        ).fetchall()
    }
    unknown = [
        entity_id
        for entity_id in add
        if entity_id not in found_drivers and entity_id not in found_constructors
    ]
    if unknown:
        raise ValueError(
            f"Unknown entity IDs (not found in drivers or constructors): {unknown}"
        )
    return {
        entity_id: "driver" if entity_id in found_drivers else "constructor"
        for entity_id in add
    }


def _validate_composition(roster: dict[str, str]) -> None:
    drivers = sum(entity_type == "driver" for entity_type in roster.values())
    constructors = sum(
        entity_type == "constructor" for entity_type in roster.values()
    )
    if drivers != 5:
        raise ValueError(
            "Roster must have exactly 5 drivers, but the transfer results in "
            f"{drivers}."
        )
    if constructors != 2:
        raise ValueError(
            "Roster must have exactly 2 constructors, but the transfer results in "
            f"{constructors}."
        )


def _write_transfer(
    player_id: str,
    remove: list[str],
    add: dict[str, str],
    db: duckdb.DuckDBPyConnection,
) -> None:
    if remove:
        placeholders = ", ".join("?" for _ in remove)
        db.execute(
            f"DELETE FROM rosters WHERE player_id = ? "
            f"AND entity_id IN ({placeholders})",
            [player_id, *remove],
        )
    for entity_id, entity_type in add.items():
        db.execute(
            "INSERT INTO rosters (player_id, entity_id, entity_type) "
            "VALUES (?, ?, ?)",
            [player_id, entity_id, entity_type],
        )


def get_roster(
    player_id: str, db: duckdb.DuckDBPyConnection
) -> list[dict[str, str]]:
    _ensure_player(player_id, db)
    rows = db.execute(
        """
        SELECT r.entity_id, d.name, r.entity_type
        FROM rosters r
        JOIN stats.drivers d ON r.entity_id = d.driver_id
        WHERE r.player_id = ? AND r.entity_type = 'driver'
        UNION ALL
        SELECT r.entity_id, c.name, r.entity_type
        FROM rosters r
        JOIN stats.constructors c ON r.entity_id = c.constructor_id
        WHERE r.player_id = ? AND r.entity_type = 'constructor'
        """,
        [player_id, player_id],
    ).fetchall()
    return [
        {"entity_id": row[0], "name": row[1], "entity_type": row[2]}
        for row in rows
    ]


def transfer_roster_entities(
    player_id: str,
    remove: list[str],
    add: list[str],
    db: duckdb.DuckDBPyConnection,
) -> dict:
    db.execute("BEGIN TRANSACTION")
    try:
        _ensure_player(player_id, db)
        if len(remove) != len(set(remove)):
            raise ValueError(f"Duplicate entities in remove: {remove}")
        if len(add) != len(set(add)):
            raise ValueError(f"Duplicate entities in add: {add}")

        current = _load_roster(player_id, db)
        not_on_team = [
            entity_id for entity_id in remove if entity_id not in current
        ]
        if not_on_team:
            raise ValueError(
                f"Cannot remove entities not on your roster: {not_on_team}"
            )

        resolved_additions = _resolve_additions(add, db)
        updated = dict(current)
        for entity_id in remove:
            del updated[entity_id]
        for entity_id in resolved_additions:
            if entity_id in updated:
                raise ValueError(
                    f"Cannot add an entity already on your roster: {entity_id}"
                )
        updated.update(resolved_additions)
        _validate_composition(updated)
        _write_transfer(player_id, remove, resolved_additions, db)
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise

    return {
        "status": "ok",
        "transferred_out": list(remove),
        "transferred_in": list(resolved_additions),
        "roster": [
            {"entity_id": entity_id, "entity_type": entity_type}
            for entity_id, entity_type in updated.items()
        ],
    }
