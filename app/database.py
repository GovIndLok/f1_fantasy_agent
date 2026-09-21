"""Shared database dependency used by all routers."""
import os
from typing import Annotated

import duckdb
from fastapi import Depends

_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'f1_fantasy.db')


def get_db():
    con = duckdb.connect(_DB_PATH)
    try:
        yield con
    finally:
        con.close()


DbDep = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]

