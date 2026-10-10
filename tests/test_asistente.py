"""Asistente de Shaki: fechas en español y respuestas sin romperse con la base vacía."""
import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.mkdtemp(), "asis.db"))

import pytest  # noqa: E402

from config import cfg  # noqa: E402
from database import inicializar_db  # noqa: E402
from modulos import asistente as a  # noqa: E402


@pytest.fixture(autouse=True)
def _bd(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "DATABASE_PATH", str(tmp_path / "asis.db"))
    monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "")
    inicializar_db()


def test_rango():
    sab = date(2026, 10, 10)
    assert a.rango("pagos de mañana", sab)[:2] == (date(2026, 10, 11), date(2026, 10, 11))
    assert a.rango("qué tengo hoy", sab)[:2] == (sab, sab)
    assert a.rango("esta semana", sab)[1] == date(2026, 10, 18)              # sábado → hasta el domingo siguiente
    assert a.rango("esta semana", date(2026, 10, 7))[1] == date(2026, 10, 11)
    assert a.rango("impuestos de noviembre", sab)[:2] == (date(2026, 11, 1), date(2026, 11, 30))
    assert a.rango("próximos 15 días", sab)[1] == date(2026, 10, 25)


@pytest.mark.parametrize("q", ["¿Qué tengo hoy?", "pagos de esta semana", "pagos vencidos", "¿qué impuestos vienen?",
                               "alertas críticas", "correos importantes", "clientes en mora", "busca codifer",
                               "cómo quedó la revisión de retención", "hola", "ayuda", "asdfgh"])
def test_responde_sin_romperse(q):
    r = a.responder(q)
    assert isinstance(r, str) and len(r) > 5
    assert "problema leyendo" not in r


def test_impuestos_con_radar():
    from modulos import radar_tributario as rt
    rt.inicializar_y_cargar()
    r = a.responder("impuestos de noviembre")
    assert "Retención en la fuente" in r and "noviembre" in r
