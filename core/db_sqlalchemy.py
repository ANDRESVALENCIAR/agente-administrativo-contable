"""SQLAlchemy sobre SQLite — capa BD del agente."""
import logging
from typing import Any

import pandas as pd

from config import cfg

logger = logging.getLogger(__name__)

_engine = None

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine

    _HAS_SQLALCHEMY = True
except ImportError:
    _HAS_SQLALCHEMY = False
    Engine = Any  # type: ignore


def get_engine() -> Any | None:
    """Engine SQLAlchemy para cfg.DATABASE_PATH."""
    global _engine
    if not _HAS_SQLALCHEMY:
        return None
    if _engine is None:
        url = f"sqlite:///{cfg.DATABASE_PATH}"
        _engine = create_engine(url, connect_args={"check_same_thread": False})
        logger.info("SQLAlchemy engine activo: %s", cfg.DATABASE_PATH)
    return _engine


def query_df(sql: str, params: dict | tuple | None = None) -> pd.DataFrame:
    """SELECT vía SQLAlchemy (params nombrados) o sqlite3 (params posicionales)."""
    engine = get_engine()
    if engine is not None and isinstance(params, dict):
        from core.registro_libs import registrar_uso_libreria

        registrar_uso_libreria("dashboard", "sqlalchemy")
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params)
    import sqlite3

    conn = sqlite3.connect(cfg.DATABASE_PATH)
    df = pd.read_sql(sql, conn, params=params if params else ())
    conn.close()
    return df


def execute(sql: str, params: dict | tuple | None = None) -> None:
    """Ejecuta DML vía SQLAlchemy (dict) o sqlite3 (tupla)."""
    engine = get_engine()
    if engine is not None and isinstance(params, dict):
        with engine.begin() as conn:
            conn.execute(text(sql), params)
        return
    import sqlite3

    conn = sqlite3.connect(cfg.DATABASE_PATH)
    conn.execute(sql, params or ())
    conn.commit()
    conn.close()
