"""Shared database dependency used by all routers."""
import os
from typing import Annotated

import duckdb
from fastapi import Depends

_PLAYERS_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'players.db')
_STATS_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'f1_stats.db')

def get_db():
    con = duckdb.connect(_PLAYERS_DB_PATH)
    con.execute(f"ATTACH '{_STATS_DB_PATH}' AS stats (READ_ONLY)")
    try:
        yield con
    finally:
        con.close()


DbDep = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]

