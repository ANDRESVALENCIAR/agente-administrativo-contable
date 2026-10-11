"""Revisión contable con reglas fijas: cada regla con un balance de prueba sintético."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from modulos import auditoria_contable as au  # noqa: E402
from modulos import auditoria_informe as ai  # noqa: E402


def c(nombre, final, anterior=None, deb=0.0, cre=0.0):
    return {"nombre": nombre, "saldo_anterior": final if anterior is None else anterior, "debitos": deb,
            "creditos": cre, "nuevo_saldo": final}


def balance_sano():
    pr = {
        "1": c("ACTIVO", 1000.0e6, 1000.0e6, 60e6, 60e6), "11": c("DISPONIBLE", 200e6, 200e6, 60e6, 60e6),
        "1110": c("BANCOS", 200e6, 200e6, 60e6, 60e6), "111005": c("MONEDA NACIONAL", 200e6, 200e6, 60e6, 60e6),
        "14": c("INVENTARIOS", 800e6), "1435": c("MERCANCIAS", 800e6), "143595": c("EQUIPOS", 800e6),
        "2": c("PASIVO", 600e6), "22": c("PROVEEDORES", 600e6), "2205": c("NACIONALES", 600e6),
        "220501": c("PROVEEDORES NACIONALES", 600e6),
        "3": c("PATRIMONIO", 300e6), "31": c("CAPITAL SOCIAL", 300e6), "3105": c("CAPITAL", 300e6),
        "310505": c("CAPITAL AUTORIZADO", 300e6),
        "4": c("INGRESOS", 300e6), "41": c("OPERACIONALES", 300e6), "4135": c("COMERCIO", 300e6),
        "413501": c("VENTAS", 300e6),
        "5": c("GASTOS", 200e6), "51": c("ADMINISTRACION", 200e6), "5195": c("DIVERSOS", 200e6),
        "519595": c("OTROS", 200e6),
    }
    return pr


def codigos(r):
    return {h["codigo"]: h["nivel"] for h in r["hallazgos"]}


def test_balance_sano_es_confiable():
    r = au.revisar(balance_sano(), corte=date(2026, 8, 31), empresa="Prueba")
    cod = codigos(r)
    assert cod["A1"] == cod["A2"] == cod["A3"] == "OK"
    assert r["veredicto"] == "Confiable" and r["puntaje"] == 100


def test_ecuacion_y_sumas_descuadradas():
    pr = balance_sano()
    pr["1"]["nuevo_saldo"] += 5e6
    pr["1"]["debitos"] += 5e6
    pr["1"]["saldo_anterior"] = pr["1"]["nuevo_saldo"] - 5e6  # aritmética de la cuenta sigue bien
    r = au.revisar(pr)
    assert codigos(r)["A1"] == "CRITICO" and codigos(r)["A2"] == "CRITICO"
    assert r["veredicto"] == "Requiere ajustes antes de usarse"


def test_inventario_negativo_y_cuenta_mayor():
    pr = balance_sano()
    pr["14359501"] = c("COMPRA Y VENTA", -50e6)
    pr["143595"]["nuevo_saldo"] = pr["143595"]["saldo_anterior"] = 800e6  # la mayor no cuadra con su subcuenta
    r = au.revisar(pr)
    b1 = [h for h in r["hallazgos"] if h["codigo"] == "B1"][0]
    assert b1["nivel"] == "ALTO" and "Inventario negativo" in b1["detalle"]
    assert codigos(r)["A4"] == "MEDIO"


def test_retencion_iva_y_prestaciones_vencidas():
    pr = balance_sano()
    pr["2365"] = c("RETENCION EN LA FUENTE", 30e6, 26e6, 0, 4e6)        # 26 M de meses anteriores
    pr["2408"] = c("IVA POR PAGAR", 100e6)
    pr["240899"] = c("IVA POR PAGAR", 100e6)
    pr["2510"] = c("CESANTIAS CONSOLIDADAS", 32e6)
    r = au.revisar(pr, corte=date(2026, 8, 31))
    tit = {h["codigo"]: h for h in r["hallazgos"]}
    assert tit["D1"]["valor"] == 26e6 and tit["D2"]["valor"] == 100e6 and tit["E3"]["nivel"] == "ALTO"
    assert r["riesgos_total"] == 26e6 + 100e6 + 32e6
    assert all(tit[k]["tipo"] == "riesgo" for k in ("D1", "D2", "E3"))   # no bajan la nota de confiabilidad


def test_nomina_con_porcentajes_de_ley():
    pr = balance_sano()
    pr.update({"510506": c("SUELDOS", 10e6, 0, 10e6), "510527": c("AUXILIO DE TRANSPORTE", 0.4e6, 0, 0.4e6),
               "510530": c("CESANTIAS", 0.866e6, 0, 0.866e6), "510533": c("INTERESES SOBRE CESANTIAS", 0.104e6, 0, 0.104e6),
               "510536": c("PRIMA DE SERVICIOS", 0.866e6, 0, 0.866e6), "510539": c("VACACIONES", 0.417e6, 0, 0.417e6),
               "510570": c("APORTES A FONDOS DE PENSIONES Y/0 CESANTIAS", 1.2e6, 0, 1.2e6),
               "510572": c("APORTES CAJAS DE COMPENSACION FAMILIAR", 0.4e6, 0, 0.4e6)})
    assert codigos(au.revisar(pr))["E1"] == "OK"
    pr["510536"] = c("PRIMA DE SERVICIOS", 0.0)
    r = au.revisar(pr)
    assert any(h["codigo"] == "E1" and h["nivel"] == "ALTO" and "prima" in h["titulo"].lower() for h in r["hallazgos"])


def test_auxiliar_descuadrado_duplicado_y_factura_repetida():
    aux = pd.DataFrame([
        {"cuenta": "519595", "fecha": "2026-08-03", "nit": 1, "nombre": "A", "comprobante": "CC 1", "detalle": "x", "valor": 500000},
        {"cuenta": "220501", "fecha": "2026-08-03", "nit": 1, "nombre": "A", "comprobante": "CC 1", "detalle": "x", "valor": -400000},
        {"cuenta": "111005", "fecha": "2026-08-04", "nit": 2, "nombre": "B", "comprobante": "CE 7", "detalle": "PAGO NOMINA", "valor": -3e6},
        {"cuenta": "111005", "fecha": "2026-08-04", "nit": 2, "nombre": "B", "comprobante": "CE 8", "detalle": "PAGO NOMINA", "valor": -3e6},
        {"cuenta": "220501", "fecha": "2026-08-05", "nit": 9, "nombre": "P", "comprobante": "(EIF) CREM FAC 1", "detalle": "FACT FAM123456", "valor": -2e6},
        {"cuenta": "220501", "fecha": "2026-08-20", "nit": 9, "nombre": "P", "comprobante": "(EIF) CREM FAC 9", "detalle": "FACT FAM123456", "valor": -2e6},
        {"cuenta": "413501", "fecha": "2026-08-05", "nit": 3, "nombre": "C", "comprobante": "FV 1", "detalle": "venta", "valor": 0.0},
        {"cuenta": "310505", "fecha": "2026-08-05", "nit": 3, "nombre": "C", "comprobante": "FV 1", "detalle": "x", "valor": 0.0},
    ])
    r = au.revisar(balance_sano(), aux, date(2026, 8, 31))
    cod = codigos(r)
    assert cod["G1"] == "CRITICO"          # CC 1, CE 7, CE 8 y las causaciones no cuadran
    assert cod["G3"] == "MEDIO" and cod["G4"] == "ALTO"


def test_terceros_y_continuidad():
    pr = balance_sano()
    ter = pd.DataFrame([{"cuenta": "220501", "nit": 1, "tercero": "P1", "saldo": 650e6},
                        {"cuenta": "220501", "nit": 2, "tercero": "P2", "saldo": -50e6 + 5e6}])
    sig = balance_sano()
    sig["1"]["saldo_anterior"] += 286000
    r = au.revisar(pr, terceros=ter, siguiente=(pr, sig, "agosto", "septiembre"))
    cod = codigos(r)
    assert cod["T1"] == "ALTO"   # 650 − 45 = 605 ≠ 600
    assert cod["J1"] == "ALTO"


def test_lectura_de_numeros_y_informe():
    assert au._num("(1.234.567)") == -1234567 and au._num("1,234,567.5") == 1234567.5 and au._num("abc") is None
    r = au.revisar(balance_sano(), corte=date(2026, 8, 31), empresa="EIF SAS")
    html = ai.generar_html(r)
    assert "EIF SAS" in html and "31 de agosto de 2026" in html and "Revisión contable" in html
