"""Tablero de contabilidad: balance, estado de resultados, caja e indicadores con datos sintéticos."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from modulos import analitica_contable as ac  # noqa: E402


def _c(s):
    return {"nuevo_saldo": s, "saldo_anterior": s, "nombre": ""}


PR = {"1": _c(1000.0), "11": _c(100.0), "13": _c(400.0), "1305": _c(300.0), "14": _c(300.0), "15": _c(200.0),
      "2": _c(700.0), "21": _c(300.0), "22": _c(200.0), "24": _c(100.0), "28": _c(100.0),
      "3": _c(250.0), "4": _c(1000.0), "5": _c(500.0), "6": _c(450.0),
      "11100501": {"nuevo_saldo": 80.0, "nombre": "BANCOLOMBIA CTE"}, "11050501": {"nuevo_saldo": 20.0, "nombre": "CAJA"},
      "1110": {"nuevo_saldo": 80.0, "nombre": "BANCOS"}, "1105": {"nuevo_saldo": 20.0, "nombre": "CAJA"}}


def test_balance_cuadra_e_indicadores():
    b = ac.balance(PR)
    assert b["resultado"] == 50 and b["cuadra"]  # 1000 = 700 + 250 + 50
    assert b["activo_corriente"] == 800 and b["pasivo_corriente"] == 700
    inds = {i["nombre"]: i for i in ac.indicadores(b, ac.estado_resultados(_mov()), 90)}
    assert round(inds["Liquidez"]["valor"], 3) == round(800 / 700, 3)
    assert round(inds["Prueba ácida"]["valor"], 3) == round(500 / 700, 3)
    assert inds["Endeudamiento"]["semaforo"] == "ojo"  # 70 %
    assert [c["nombre"] for c in ac.cuentas_disponible(PR)] == ["Bancolombia cte", "Caja"]


def _mov():
    return pd.DataFrame({
        "mes": pd.to_datetime(["2026-01-01"] * 4 + ["2026-02-01"] * 2),
        "fecha": pd.to_datetime(["2026-01-15"] * 4 + ["2026-02-15"] * 2),
        "grupo": ["41", "61", "51", "53", "41", "52"], "clase": ["4", "6", "5", "5", "4", "5"],
        "monto": [600.0, 300.0, 100.0, 20.0, 400.0, 80.0]})


def test_estado_de_resultados():
    e = ac.estado_resultados(_mov())
    assert e["ingresos"] == 1000 and e["costo"] == 300 and e["bruta"] == 700
    assert e["operacional"] == 700 - 100 - 80 and e["neta"] == 520 - 20
    mm = ac.resultados_mensuales(_mov())
    assert list(mm["utilidad"]) == [180.0, 320.0]


def test_flujo_de_caja_parte_del_saldo_final():
    caja = pd.DataFrame({"mes": pd.to_datetime(["2026-01-01", "2026-01-01", "2026-02-01"]),
                         "valor": [500.0, -200.0, -100.0], "detalle": ["", "", ""], "tercero": ["A", "B", "B"]})
    f = ac.flujo_caja(caja, saldo_final=1000.0)
    assert f.attrs["inicial"] == 800 and list(f["saldo"]) == [1100.0, 1000.0]
    ent, sal = ac.mayores_movimientos_caja(caja)
    assert ent.iloc[0]["tercero"] == "A" and sal.iloc[0]["salidas"] == 300
