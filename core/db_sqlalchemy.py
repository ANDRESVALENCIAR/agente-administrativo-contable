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
    """SELECT vía SQLAlchemy; fallback sqlite3 + pandas."""
    engine = get_engine()
    if engine is not None:
        from core.registro_libs import registrar_uso_libreria

        registrar_uso_libreria("dashboard", "sqlalchemy")
        with engine.connect() as conn:
            if isinstance(params, dict):
                return pd.read_sql(text(sql), conn, params=params)
            if isinstance(params, tuple):
                return pd.read_sql(sql, conn, params=list(params))
            return pd.read_sql(sql, conn)
    import sqlite3

    conn = sqlite3.connect(cfg.DATABASE_PATH)
    df = pd.read_sql(sql, conn, params=params if params else ())
    conn.close()
    return df


def execute(sql: str, params: dict | tuple | None = None) -> None:
    """Ejecuta DML vía SQLAlchemy o sqlite3."""
    engine = get_engine()
    if engine is not None:
        with engine.begin() as conn:
            if isinstance(params, dict):
                conn.execute(text(sql), params)
            elif isinstance(params, tuple):
                conn.execute(text(sql), list(params))
            else:
                conn.execute(text(sql))
        return
    import sqlite3

    conn = sqlite3.connect(cfg.DATABASE_PATH)
    conn.execute(sql, params or ())
    conn.commit()
    conn.close()
