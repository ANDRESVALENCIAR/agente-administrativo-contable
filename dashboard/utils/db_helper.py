"""Helpers SQL reutilizables para páginas Streamlit."""
import sqlite3
from typing import Any

import pandas as pd

from config import cfg


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Ejecuta SELECT y retorna DataFrame."""
    conn = sqlite3.connect(cfg.DATABASE_PATH)
    df = pd.read_sql(sql, conn, params=params)
    conn.close()
    return df


def execute(sql: str, params: tuple = ()) -> None:
    """Ejecuta INSERT/UPDATE/DELETE."""
    conn = sqlite3.connect(cfg.DATABASE_PATH)
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def insert_row(table: str, data: dict[str, Any]) -> None:
    """Inserta un registro en tabla."""
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" * len(data))
    execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", tuple(data.values()))
