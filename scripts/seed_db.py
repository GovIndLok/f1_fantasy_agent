import os
import time
import duckdb
import pandas as pd
import requests

BASE_URL = "https://api.jolpi.ca/ergast/f1"

def fetch_all(endpoint):
    """Paginates through an Ergast endpoint and returns all items in the innermost list."""
    all_data = []
    offset = 0
    limit = 100
    while True:
        url = f"{BASE_URL}/{endpoint}.json?limit={limit}&offset={offset}"
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(4)
            continue
        response.raise_for_status()
        data = response.json()["MRData"]
        
        total = int(data.get("total", 0))
        
        keys = list(data.keys())
        table_key = next((k for k in keys if k.endswith("Table")), None)
        if not table_key:
            break
            
        list_keys = [k for k in data[table_key].keys() if isinstance(data[table_key][k], list)]
        if not list_keys:
            break
            
        items = data[table_key][list_keys[0]]
        all_data.extend(items)
        
        if offset + limit >= total or not items:
            break
        offset += limit
        time.sleep(0.5)
    return all_data

def seed_database():
    seasons = ["2023", "2024"]
    
    drivers_dict = {}
    constructors_dict = {}
    circuits_dict = {}
    races_list = []
    results_list = []

    for season in seasons:
        print(f"Fetching {season} Grand Prix results...")
        races_data = fetch_all(f"{season}/results")
        
        for r in races_data:
            race_id = f"{season}_{r['round']}"
            circuit = r["Circuit"]
            
            circuits_dict[circuit["circuitId"]] = {
                "circuit_id": circuit["circuitId"],
                "name": circuit["circuitName"],
                "locality": circuit["Location"]["locality"],
                "country": circuit["Location"]["country"]
            }
            
            races_list.append({
                "race_id": race_id,
                "season": int(season),
                "round": int(r["round"]),
                "race_name": r["raceName"],
                "circuit_id": circuit["circuitId"],
                "date": r["date"]
            })
            
            for res in r["Results"]:
                driver = res["Driver"]
                constructor = res["Constructor"]
                
                drivers_dict[driver["driverId"]] = {
                    "driver_id": driver["driverId"],
                    "name": f"{driver.get('givenName')} {driver.get('familyName')}",
                    "code": driver.get("code", ""),
                    "nationality": driver.get("nationality", "")
                }
                
                constructors_dict[constructor["constructorId"]] = {
                    "constructor_id": constructor["constructorId"],
                    "name": constructor["name"],
                    "nationality": constructor["nationality"]
                }
                
                results_list.append({
                    "race_id": race_id,
                    "driver_id": driver["driverId"],
                    "constructor_id": constructor["constructorId"],
                    "is_sprint": False,
                    "grid_position": int(res["grid"]),
                    "finish_position": int(res["position"]),
                    "points": float(res["points"])
                })

        print(f"Fetching {season} Sprint results...")
        sprint_data = fetch_all(f"{season}/sprint")
        for r in sprint_data:
            race_id = f"{season}_{r['round']}"
            for res in r["SprintResults"]:
                results_list.append({
                    "race_id": race_id,
                    "driver_id": res["Driver"]["driverId"],
                    "constructor_id": res["Constructor"]["constructorId"],
                    "is_sprint": True,
                    "grid_position": int(res["grid"]),
                    "finish_position": int(res["position"]),
                    "points": float(res["points"])
                })

    df_drivers = pd.DataFrame(list(drivers_dict.values()))
    df_constructors = pd.DataFrame(list(constructors_dict.values()))
    df_circuits = pd.DataFrame(list(circuits_dict.values()))
    df_races = pd.DataFrame(races_list)
    df_results = pd.DataFrame(results_list)

    stats_db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'f1_stats.db')
    players_db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'players.db')
    
    # --- 1. Seed F1 Stats Database ---
    print(f"Seeding {stats_db_path}...")
    stats_con = duckdb.connect(stats_db_path)
    stats_con.execute("CREATE OR REPLACE TABLE drivers AS SELECT * FROM df_drivers")
    stats_con.execute("CREATE OR REPLACE TABLE constructors AS SELECT * FROM df_constructors")
    stats_con.execute("CREATE OR REPLACE TABLE circuits AS SELECT * FROM df_circuits")
    stats_con.execute("CREATE OR REPLACE TABLE races AS SELECT * FROM df_races")
    stats_con.execute("CREATE OR REPLACE TABLE results AS SELECT * FROM df_results")
    stats_con.close()

    # --- 2. Seed Players Database ---
    print(f"Seeding {players_db_path}...")
    players_con = duckdb.connect(players_db_path)
    players_con.execute("""
        CREATE OR REPLACE TABLE players (
            player_id VARCHAR PRIMARY KEY,
            username VARCHAR
        )
    """)
    players_con.execute("""
        CREATE OR REPLACE TABLE rosters (
            player_id VARCHAR,
            entity_id VARCHAR,
            entity_type VARCHAR
        )
    """)

    players_con.execute("INSERT INTO players VALUES ('user_1', 'f1_fanatic')")
    
    driver_ids = list(drivers_dict.keys())
    constructor_ids = list(constructors_dict.keys())
    players_con.executemany(
        "INSERT INTO rosters VALUES (?, ?, ?)",
        [("user_1", d_id, "driver") for d_id in driver_ids[:5]]
        + [("user_1", c_id, "constructor") for c_id in constructor_ids[:2]],
    )
    players_con.close()

    print("Databases seeded successfully with split architecture.")

if __name__ == "__main__":
    seed_database()
