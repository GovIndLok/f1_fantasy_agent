import random
import time

import duckdb
import pandas as pd
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
        
        # dynamic table finding
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
    drivers_data = fetch_json(f"{season}/drivers")
    drivers = []
    for item in drivers_data:
        drivers.append({
            "driver_id": item.get("driverId"),
            "name": f"{item.get('givenName')} {item.get('familyName')}",
            "code": item.get("code", ""),
            "nationality": item.get("nationality", ""),
            # Synthetic price for fantasy (between $5M and $30M)
            "current_price": round(random.uniform(5.0, 30.0), 1)
        })
    drivers_df = pd.DataFrame(drivers)

    print(f"Fetching constructors for {season}...")
    constructors_data = fetch_json(f"{season}/constructors")
    constructors = []
    for item in constructors_data:
        constructors.append({
            "constructor_id": item.get("constructorId"),
            "name": item.get("name"),
            "nationality": item.get("nationality", ""),
            # Synthetic price for fantasy (between $10M and $35M)
            "current_price": round(random.uniform(10.0, 35.0), 1)
        })
    constructors_df = pd.DataFrame(constructors)

    print("Writing to DuckDB...")
    con = duckdb.connect('../data/f1_fantasy.db')
    
    # Create or replace tables from DataFrames
    con.execute("CREATE OR REPLACE TABLE drivers AS SELECT * FROM drivers_df")
    con.execute("CREATE OR REPLACE TABLE constructors AS SELECT * FROM constructors_df")
    
    # Also create a dummy players and rosters table for M2
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
            entity_type VARCHAR -- 'driver' or 'constructor'
        )
    """)
    
    # Seed a dummy user
    con.execute("INSERT INTO players VALUES ('user_1', 'f1_fanatic', 100.00)")
    # Seed dummy roster (5 drivers, 2 constructors)
    con.execute(f"INSERT INTO rosters VALUES ('user_1', '{drivers[0]['driver_id']}', 'driver')")
    con.execute(f"INSERT INTO rosters VALUES ('user_1', '{drivers[1]['driver_id']}', 'driver')")
    con.execute(f"INSERT INTO rosters VALUES ('user_1', '{drivers[2]['driver_id']}', 'driver')")
    con.execute(f"INSERT INTO rosters VALUES ('user_1', '{drivers[3]['driver_id']}', 'driver')")
    con.execute(f"INSERT INTO rosters VALUES ('user_1', '{drivers[4]['driver_id']}', 'driver')")
    con.execute(f"INSERT INTO rosters VALUES ('user_1', '{constructors[0]['constructor_id']}', 'constructor')")
    con.execute(f"INSERT INTO rosters VALUES ('user_1', '{constructors[1]['constructor_id']}', 'constructor')")

    print("Database seeded successfully in f1_fantasy.db")
    con.close()

if __name__ == "__main__":
    seed_database()

