"""Helpers SQL — usa SQLAlchemy del core cuando está disponible."""
import sqlite3
from typing import Any

import pandas as pd

from config import cfg
from core.db_sqlalchemy import get_engine, query_df as core_query_df


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Ejecuta SELECT vía core (SQLAlchemy) o sqlite3."""
    if get_engine() is not None:
        return core_query_df(sql, params if params else None)
    conn = sqlite3.connect(cfg.DATABASE_PATH)
    df = pd.read_sql(sql, conn, params=params)
    conn.close()
    return df


def execute(sql: str, params: tuple = ()) -> None:
    """Ejecuta INSERT/UPDATE/DELETE (sqlite3 directo)."""
    conn = sqlite3.connect(cfg.DATABASE_PATH)
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def insert_row(table: str, data: dict[str, Any]) -> None:
    """Inserta un registro en tabla."""
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" * len(data))
    execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", tuple(data.values()))
