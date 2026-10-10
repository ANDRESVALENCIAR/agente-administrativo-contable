"""Optimización: caché ligada a la base, índices y búsqueda de gastos en memoria."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import cfg  # noqa: E402
import database  # noqa: E402


def test_cache_se_refresca_cuando_cambia_la_base(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "DATABASE_PATH", str(tmp_path / "c.db"), raising=False)
    conn = database.get_conn()
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.commit()
    conn.close()
    llamadas = []

    @database.cache_bd
    def contar():
        llamadas.append(1)
        c = database.get_conn()
        n = c.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        c.close()
        return n

    assert contar() == 0 and contar() == 0 and len(llamadas) == 1  # segunda vez sale de memoria
    c = database.get_conn()
    c.execute("INSERT INTO t VALUES (1)")
    c.commit()
    c.close()
    assert contar() == 1 and len(llamadas) == 2  # la base cambió: se vuelve a leer


def test_indices_sin_duplicar(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "DATABASE_PATH", str(tmp_path / "i.db"), raising=False)
    c = database.get_conn()
    c.execute("CREATE TABLE IF NOT EXISTS cartera_cxc (id INTEGER PRIMARY KEY, cliente TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS log_ejecuciones_calendario (id INTEGER PRIMARY KEY, tarea_id INTEGER, "
              "fecha_ejecucion TEXT)")
    c.execute("CREATE INDEX IF NOT EXISTS ya_habia ON cartera_cxc(cliente)")
    c.commit()
    c.close()
    assert database.asegurar_indices() >= 2  # las dos de log_ejecuciones; cartera ya tenía índice
    assert database.asegurar_indices() == 0  # nunca duplica
    nombres = [r[1] for r in database.get_conn().execute("PRAGMA index_list('cartera_cxc')")]
    assert nombres == ["ya_habia"]
    assert database.get_conn().execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_lookup_gastos_en_memoria(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "DATABASE_PATH", str(tmp_path / "g.db"), raising=False)
    from modulos import catalogos_gastos as cg
    from utils import estandarizar_gastos as eg

    cg.inicializar_catalogos_gastos()
    c = database.get_conn()
    c.execute("CREATE TABLE IF NOT EXISTS gastos_maestro (id INTEGER PRIMARY KEY, detalle_original TEXT, "
              "detalle_limpio TEXT, categoria TEXT, periodicidad_std TEXT, requiere_revision INTEGER)")
    c.execute("INSERT INTO gastos_maestro (detalle_original, detalle_limpio, categoria, periodicidad_std, "
              "requiere_revision) VALUES ('x', 'ARRIENDO BODEGA CALLE 76', 'ARRIENDO', 'MENSUAL', 0)")
    c.commit()
    c.close()
    r = eg.lookup_gasto_por_detalle("  arriendo   bodega calle 76 ")
    assert r and r["categoria"] == "ARRIENDO" and r["periodicidad_std"] == "MENSUAL"
    assert eg.lookup_gasto_por_detalle("PAGO ARRIENDO BODEGA CALLE 76 OCTUBRE")["categoria"] == "ARRIENDO"  # parcial
    assert eg.lookup_gasto_por_detalle("ALGO QUE NO EXISTE") is None
