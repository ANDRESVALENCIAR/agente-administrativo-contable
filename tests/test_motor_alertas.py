"""Motor de alertas: crea, actualiza, cierra solo, no duplica, respeta lo resuelto a mano."""
import os
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "alertas.db")

from config import cfg  # noqa: E402

cfg.DATABASE_PATH = os.environ["DATABASE_PATH"]

import pytest  # noqa: E402

from database import crear_alerta, get_conn, inicializar_db  # noqa: E402
from modulos import motor_alertas as ma  # noqa: E402


@pytest.fixture(autouse=True)
def _bd_limpia(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "DATABASE_PATH", str(tmp_path / "alertas.db"))


def _cxp(fecha):
    conn = get_conn()
    cur = conn.execute("INSERT INTO cxp_programados (proveedor, concepto, monto, fecha_pago, estado) "
                       "VALUES ('Prov Z','Servicio',900000,?, 'PROGRAMADO')", (fecha.isoformat(),))
    conn.commit()
    i = cur.lastrowid
    conn.close()
    return i


def test_ciclo_completo():
    inicializar_db()
    for _ in range(3):
        crear_alerta("CRITICO", "pagos", "2904 pago(s) VENCIDO(S) sin pagar", "PAGOS")
    crear_alerta("AVISO", "juridico", "Revisar poder", "x")
    crear_alerta("AVISO", "JURIDICO", "Revisar poder", "x")
    ma.inicializar()
    viejas = [a for a in ma.listar() if a.get("origen") != "MOTOR"]
    assert len(viejas) == 1 and viejas[0]["titulo"] == "Revisar poder"     # migración: obsoletas y duplicadas fuera

    cid = _cxp(date.today())
    r1 = ma.escanear(notificar=False)
    assert r1["nuevas"] >= 1
    r2 = ma.escanear(notificar=False)
    assert r2["nuevas"] == 0                                                   # no duplica
    a = next(x for x in ma.listar() if x["clave"] == f"cxp:{cid}")
    assert a["nivel"] == "URGENTE" and a["veces"] >= 2

    conn = get_conn()
    conn.execute("UPDATE cxp_programados SET estado='PAGADO' WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    r3 = ma.escanear(notificar=False)
    assert r3["resueltas"] >= 1
    assert not any(x["clave"] == f"cxp:{cid}" for x in ma.listar())           # se cerró sola


def test_resuelta_a_mano_no_vuelve_y_posponer():
    inicializar_db()
    cid = _cxp(date.today() + timedelta(days=1))
    ma.escanear(notificar=False)
    a = next(x for x in ma.listar() if x["clave"] == f"cxp:{cid}")
    ma.posponer(a["id"], 24)
    assert not any(x["id"] == a["id"] for x in ma.listar())
    assert any(x["id"] == a["id"] for x in ma.listar("POSPUESTAS"))
    ma.reactivar(a["id"])
    ma.resolver(a["id"], por="usuario")
    ma.escanear(notificar=False)
    assert not any(x["clave"] == f"cxp:{cid}" for x in ma.listar())


def test_salud():
    assert ma.salud([]) == 100
    assert ma.salud([{"nivel": "CRITICO"}] * 4) < 40
