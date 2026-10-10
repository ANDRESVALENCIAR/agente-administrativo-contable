"""Analítica de personal y gastos: limpieza de datos importados y cálculos clave."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from modulos import analitica_gastos as ag  # noqa: E402
from modulos import analitica_personal as ap  # noqa: E402


def test_fechas_y_retiro():
    assert ap._fecha("2024-07-15") == pd.Timestamp(2024, 7, 15)
    assert ap._fecha("FIJO INFERIOR A UN AÑO") is None
    assert ap._fecha("NaT") is None
    assert ap._fecha("45444") == pd.Timestamp(2024, 6, 1)
    assert ap._retiro("RETIRO 31 JULIO DE 2025") == pd.Timestamp(2025, 7, 31)
    assert ap._retiro("Fecha retiro 15 Agosto 2021") == pd.Timestamp(2021, 8, 15)
    assert ap._retiro("RETIRO EL 23 DE DICIEMBRE") is None


def test_textos_y_dinero():
    assert ap._texto("COMPENSAR", ap.NO_CIUDAD) == "Sin dato"
    assert ap._texto("MEDELLIN") == "Medellin"
    assert ap._texto("2025-01-01") == "Sin dato"
    assert ap._dinero("1.750.905") == 1750905
    assert ap._dinero("COMISIONES") is None
    assert ap._termino_meses("6 meses") == 6 and ap._termino_meses("1 AÑO") == 12
    assert ap._termino_meses("INDEFINIDO") is None


def test_renovacion_automatica():
    hoy = date(2026, 10, 10)
    # 3 meses desde 2026-01-01: renueva cada 3 meses (3 veces) y luego por 1 año (art. 46 CST)
    v = ap.proximo_vencimiento(pd.Timestamp(2026, 1, 1), pd.Timestamp(2026, 3, 31), 3, hoy)
    assert v == pd.Timestamp(2026, 12, 31)
    v = ap.proximo_vencimiento(None, pd.Timestamp(2025, 3, 31), 3, hoy)  # 3 renovaciones cortas y luego 1 año
    assert v == pd.Timestamp(2026, 12, 31)
    v = ap.proximo_vencimiento(None, pd.Timestamp(2025, 12, 31), 12, hoy)
    assert v == pd.Timestamp(2026, 12, 31)
    assert ap.proximo_vencimiento(None, None, None, hoy) is None


def test_medidas_gastos():
    mov = pd.DataFrame({
        "mes": pd.to_datetime(["2026-01-01", "2026-01-01", "2026-02-01", "2026-02-01", "2026-03-01", "2026-03-01"]),
        "clase": ["4", "5", "4", "5", "4", "5"], "monto": [100.0, 60.0, 100.0, 80.0, 100.0, 2_000_000.0],
        "nombre_cuenta4": ["Ventas", "Servicios", "Ventas", "Servicios", "Ventas", "Servicios"],
        "tercero": ["A", "B", "A", "B", "A", "C"], "fecha": pd.to_datetime(["2026-01-05"] * 6),
    })
    m = ag.mensual(mov)
    assert list(m["resultado"].round()) == [40, 20, -1_999_900]
    k = ag.kpis(mov)
    assert k["gasto_total"] == 2_000_140 and k["terceros"] == 2
