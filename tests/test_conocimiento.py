"""Chat de Shaki: preguntas sobre personas, proveedores/clientes y cuentas (datos sintéticos)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

import config as cfg  # noqa: E402
from modulos import asistente  # noqa: E402
from modulos import conocimiento as co  # noqa: E402


@pytest.fixture(autouse=True)
def datos(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "DATABASE_PATH", str(tmp_path / "t.db"), raising=False)
    monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "", raising=False)
    emp = pd.DataFrame([
        {"nombre": "ANDRES FELIPE VALENCIA RAMIREZ", "activo": True, "vinculo": "Nómina", "cargo_n": "Gerente",
         "area": "Gerencia", "ingreso": pd.Timestamp(2017, 3, 1), "retiro": None, "antiguedad": 9.6, "edad": 50,
         "nacimiento": pd.Timestamp(1975, 11, 20), "contrato": "Indefinido", "eps": "Sanitas", "salario": 9_000_000},
        {"nombre": "LAURA GOMEZ", "activo": False, "vinculo": "Nómina", "cargo_n": "Auxiliar", "area": "Contabilidad",
         "ingreso": pd.Timestamp(2022, 1, 10), "retiro": pd.Timestamp(2024, 6, 30), "antiguedad": 2.47, "edad": None,
         "nacimiento": None, "contrato": "Fijo", "eps": "Sin dato", "salario": None},
    ])
    vac = pd.DataFrame([{"nombre": "ANDRES F VALENCIA RAMIREZ", "dias": 12.5}])
    monkeypatch.setattr(co, "_personal", lambda: {"empleados": emp, "vacaciones": vac, "contratos": pd.DataFrame()})

    f = pd.to_datetime
    mov = pd.DataFrame({
        "fecha": f(["2026-07-10", "2026-08-12", "2026-09-05"]), "clase": ["5", "5", "4"],
        "monto": [500_000.0, 700_000.0, 2_000_000.0], "tercero": ["CODIFER SAS", "CODIFER SAS", "CLIENTE MAYOR SA"],
        "nombre_cuenta4": ["Mantenimiento", "Mantenimiento", "Ventas"], "nombre_cuenta6": ["Reparaciones", "Reparaciones", "Ventas"],
    })
    terc = pd.DataFrame([
        # CODIFER: factura 1 pagada en dos abonos, factura 2 sin pagar, factura 3 con nota crédito
        {"fecha": f("2026-07-01"), "cuenta4": "2205", "tercero": "CODIFER SAS", "comprobante": "(EIF) CREM FAC 700",
         "detalle": "16001 FACT FAP-2548", "valor": -1_000_000.0},
        {"fecha": f("2026-07-20"), "cuenta4": "2205", "tercero": "CODIFER SAS", "comprobante": "CE 1",
         "detalle": "PAGO 16001 FACT FAP-2548 16001 FAC 700", "valor": 400_000.0},
        {"fecha": f("2026-08-20"), "cuenta4": "2205", "tercero": "CODIFER SAS", "comprobante": "CE 2",
         "detalle": "PAGO 16001 FACT FAP-2548 16001 FAC 700", "valor": 600_000.0},
        {"fecha": f("2026-09-30"), "cuenta4": "2205", "tercero": "CODIFER SAS", "comprobante": "(EIF) CREM FAC 860",
         "detalle": "16426 FACT FAV359226", "valor": -353_631.0},
        # cliente: factura devuelta y vuelta a emitir, con un abono
        {"fecha": f("2026-07-14"), "cuenta4": "1305", "tercero": "CLIENTE MAYOR SA", "comprobante": "FV 24954",
         "detalle": "Contrato 2 FV 24954", "valor": 610_000.0},
        {"fecha": f("2026-08-03"), "cuenta4": "1305", "tercero": "CLIENTE MAYOR SA", "comprobante": "DMC 622",
         "detalle": "DEVOLUCION FACTURA No 24954", "valor": -610_000.0},
        {"fecha": f("2026-08-03"), "cuenta4": "1305", "tercero": "CLIENTE MAYOR SA", "comprobante": "FV 25038",
         "detalle": "Contrato 2 FV 25038", "valor": 610_000.0},
        {"fecha": f("2026-08-31"), "cuenta4": "1305", "tercero": "CLIENTE MAYOR SA", "comprobante": "RC 1",
         "detalle": "PAGO Contrato 2 FV 25038", "valor": -10_000.0},
    ])
    monkeypatch.setattr(co, "_contable", lambda: {"mov": mov, "terceros": terc})


def test_claves_de_factura():
    assert co._num_factura("PAGO 16020 FACT FAM179816 16020 FAC 688") == ["FAM179816", "FAC688", "N688", "OC16020"]
    assert "N24954" in co._num_factura("DEVOLUCION FACTURA No 24954")
    assert co.candidatos_texto("¿Cuántos años lleva Andrés Valencia con nosotros?") == "andres valencia"


def test_antiguedad_persona_aunque_nombre_incompleto():
    r = asistente.responder("cuantos años lleva Andres Valencia con nosotros")
    assert "ANDRES FELIPE VALENCIA RAMIREZ" in r and "lleva" in r and "1 de marzo de 2017" in r


def test_vacaciones_y_retirado():
    assert "12 días" in asistente.responder("cuantas vacaciones tiene andres valencia")
    r = asistente.responder("cuantos años lleva laura gomez")
    assert "ya no está" in r and "30 de junio de 2024" in r


def test_cuanto_le_debemos_cruza_abonos():
    r = asistente.responder("¿Cuánto le debemos a Codifer?")
    assert "CODIFER SAS" in r and "1 por $353.631" in r and "FAV359226" in r
    assert "FAP2548" not in r  # pagada con dos abonos


def test_cuanto_nos_debe_cliente_con_devolucion():
    r = asistente.responder("cuanto nos debe cliente mayor")
    assert "le facturamos $610.000" in r and "$600.000" in r


def test_desconocidos_y_contabilidad():
    assert "No encontré a «pedro picapiedra»" in asistente.responder("cuantos años lleva pedro picapiedra")
    assert "No encontré a «ecopetrol»" in asistente.responder("cuanto nos debe ecopetrol")
    assert "$1.200.000" in asistente.responder("cuanto gastamos en reparaciones")
    assert "$2.000.000" in asistente.responder("cuanto vendimos en septiembre")


def test_nombre_con_errores_y_solo_el_nombre():
    r = asistente.responder("cuando entro andres valencia cuanto lleva con nostros?")
    assert "ANDRES FELIPE VALENCIA RAMIREZ" in r and "1 de marzo de 2017" in r
    assert "ANDRES FELIPE VALENCIA RAMIREZ" in asistente.responder("ANDRES VALENCIA")
    assert "ANDRES FELIPE VALENCIA RAMIREZ" in asistente.responder("cuantos años lleva andres valenvia")
    assert "CODIFER" in asistente.responder("cuanto le debemos a codifr")
