"""Agenda unificada: junta pagos, impuestos, revisiones y tareas sin romperse si falta una tabla."""
import os
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "agenda.db")

from config import cfg  # noqa: E402

cfg.DATABASE_PATH = os.environ["DATABASE_PATH"]

from database import get_conn, inicializar_db  # noqa: E402
from modulos import agenda_unificada as ag  # noqa: E402
from modulos import radar_tributario as rt  # noqa: E402


def test_clave_a_revision():
    assert ag.clave_a_revision("DIAN-RET-2026-09") == ("RET", "2026-09")
    assert ag.clave_a_revision("DIAN-IVAB-2026-5") == ("IVA", "2026-B5")
    assert ag.clave_a_revision("SHD-RETEICA-2026-4") == ("RETEICA", "2026-B4")
    assert ag.clave_a_revision("DIAN-RENTA-2025-1") is None


def test_nivel():
    h = date(2026, 10, 10)
    assert ag.nivel(h - timedelta(days=1), hoy=h) == "VENCIDO"
    assert ag.nivel(h, hoy=h) == "HOY"
    assert ag.nivel(h + timedelta(days=1), hoy=h) == "MAÑANA"
    assert ag.nivel(h + timedelta(days=10), hoy=h) == "PROGRAMADO"
    assert ag.nivel(h, hecho=True, hoy=h) == "HECHO"


def test_eventos_integra_fuentes():
    inicializar_db()
    rt.inicializar_y_cargar()
    hoy = date(2026, 10, 10)
    conn = get_conn()
    conn.execute("INSERT INTO cxp_programados (proveedor, concepto, monto, fecha_pago) VALUES ('Prov X','Servicio',500000,?)",
                 (hoy.isoformat(),))
    conn.commit()
    conn.close()
    evs = ag.eventos(hoy - timedelta(days=5), hoy + timedelta(days=10), hoy=hoy)
    fuentes = {e["fuente"] for e in evs}
    assert "IMPUESTOS" in fuentes and "CXP" in fuentes and "FESTIVO" in fuentes
    ret = [e for e in evs if e.get("clave") == "DIAN-RET-2026-09"]
    assert ret and ret[0]["accion"] == ("presentar", ret[0]["accion"][1])
    assert any(e["fuente"] == "REVISION" and "Septiembre 2026" in e["titulo"] for e in evs)
    assert evs == sorted(evs, key=lambda e: (e["fecha"], ag.ORDEN_NIVEL[e["nivel"]], e["hora"] or "99", e["titulo"]))
    r = ag.resumen(hoy)
    assert r["hoy"] >= 1 and r["valor_semana"] >= 500000
