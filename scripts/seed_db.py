import os
import random
import time

import duckdb
import requests

BASE_URL = "https://api.jolpi.ca/ergast/f1"

def fetch_json(endpoint, params=None):
    url = f"{BASE_URL}/{endpoint}"
    all_data = []
    offset = 0
    limit = 100
    while True:
        paginated_params = {"limit": limit, "offset": offset}
        if params:
            paginated_params.update(params)
        response = requests.get(url, params=paginated_params)
        if response.status_code == 429:
            time.sleep(4)
            continue
        response.raise_for_status()
        data = response.json()
        mrdata = data.get("MRData", {})
        total = int(mrdata.get("total", "0"))

        table_key = next((k for k in mrdata if k.endswith("Table")), None)
        if not table_key:
            break
        data_list_key = next((k for k in mrdata[table_key] if isinstance(mrdata[table_key][k], list)), None)
        if not data_list_key:
            break

        items = mrdata[table_key][data_list_key]
        all_data.extend(items)

        if offset + limit >= total or not items:
            break
        offset += limit
        time.sleep(0.5)
    return all_data

def seed_database():
    season = "2024"
    print(f"Fetching drivers for {season}...")
    drivers = [
        {
            "driver_id": item.get("driverId"),
            "name": f"{item.get('givenName')} {item.get('familyName')}",
            "code": item.get("code", ""),
            "nationality": item.get("nationality", ""),
            "current_price": round(random.uniform(5.0, 30.0), 1),
        }
        for item in fetch_json(f"{season}/drivers")
    ]

    print(f"Fetching constructors for {season}...")
    constructors = [
        {
            "constructor_id": item.get("constructorId"),
            "name": item.get("name"),
            "nationality": item.get("nationality", ""),
            "current_price": round(random.uniform(10.0, 35.0), 1),
        }
        for item in fetch_json(f"{season}/constructors")
    ]

    print("Writing to DuckDB...")
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'f1_fantasy.db')
    con = duckdb.connect(db_path)

    # DuckDB reads Python lists of dicts directly — no pandas needed
    con.execute("CREATE OR REPLACE TABLE drivers AS SELECT * FROM drivers")
    con.execute("CREATE OR REPLACE TABLE constructors AS SELECT * FROM constructors")

    con.execute("""
        CREATE OR REPLACE TABLE players (
            player_id VARCHAR PRIMARY KEY,
            username VARCHAR,
            budget DECIMAL(5, 2)
        )
    """)
    con.execute("""
        CREATE OR REPLACE TABLE rosters (
            player_id VARCHAR,
            entity_id VARCHAR,
            entity_type VARCHAR
        )
    """)

    con.execute("INSERT INTO players VALUES ('user_1', 'f1_fanatic', 100.00)")
    con.executemany(
        "INSERT INTO rosters VALUES (?, ?, ?)",
        [("user_1", d["driver_id"], "driver") for d in drivers[:5]]
        + [("user_1", c["constructor_id"], "constructor") for c in constructors[:2]],
    )

    print("Database seeded successfully.")
    con.close()

if __name__ == "__main__":
    seed_database()
