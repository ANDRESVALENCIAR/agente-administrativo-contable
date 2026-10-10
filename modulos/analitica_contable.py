"""
Analítica contable — estado de resultados, balance, caja, cartera/proveedores e indicadores a partir del libro
del contador (hojas Auxiliar y Prueba). Usa los mismos datos ya cacheados por analitica_gastos.

PUC colombiano: 1 activo · 2 pasivo · 3 patrimonio · 4 ingresos · 5 gastos · 6 costos de venta · 7 producción.
El balance de prueba trae los saldos en positivo (cada cuenta en su naturaleza).
"""
from __future__ import annotations

from typing import Any

import pandas as pd

ACTIVO_CORRIENTE = ("11", "12", "13", "14")
PASIVO_CORRIENTE = ("21", "22", "23", "24", "25", "26", "28")


def _s(pr: dict, cuenta: str) -> float:
    return float((pr.get(cuenta) or {}).get("nuevo_saldo") or 0.0)


def _nombre(pr: dict, cuenta: str, defecto: str = "") -> str:
    n = str((pr.get(cuenta) or {}).get("nombre") or defecto).strip()
    return n.capitalize() if n.isupper() else n


def corte(datos: dict) -> pd.Timestamp | None:
    fechas = [datos["mov"]["fecha"].max()]
    if datos.get("caja") is not None and not datos["caja"].empty:
        fechas.append(datos["caja"]["fecha"].max())
    fechas = [f for f in fechas if pd.notna(f)]
    return max(fechas) if fechas else None


# ───────────────────────── Balance ─────────────────────────

def balance(pr: dict) -> dict[str, Any]:
    activo, pasivo, patrimonio = _s(pr, "1"), _s(pr, "2"), _s(pr, "3")
    resultado = _s(pr, "4") - _s(pr, "5") - _s(pr, "6") - _s(pr, "7")
    ac = sum(_s(pr, c) for c in ACTIVO_CORRIENTE)
    pc = sum(_s(pr, c) for c in PASIVO_CORRIENTE)
    inventario = _s(pr, "14")

    def grupos(clase: str) -> list[dict]:
        return sorted(({"cuenta": k, "nombre": _nombre(pr, k), "saldo": _s(pr, k),
                        "anterior": float(pr[k].get("saldo_anterior") or 0)}
                       for k in pr if len(k) == 2 and k.startswith(clase) and _s(pr, k)),
                      key=lambda g: -g["saldo"])

    return {
        "activo": activo, "pasivo": pasivo, "patrimonio": patrimonio, "resultado": resultado,
        "patrimonio_total": patrimonio + resultado,
        "cuadra": abs(activo - (pasivo + patrimonio + resultado)) < max(1000.0, activo * 1e-6),
        "activo_corriente": ac, "pasivo_corriente": pc, "inventario": inventario,
        "disponible": _s(pr, "11"), "clientes": _s(pr, "1305"), "deudores": _s(pr, "13"),
        "proveedores": _s(pr, "22"), "bancos_deuda": _s(pr, "21"), "impuestos": _s(pr, "24"),
        "laborales": _s(pr, "25"), "otros_pasivos": _s(pr, "28"),
        "grupos_activo": grupos("1"), "grupos_pasivo": grupos("2"), "grupos_patrimonio": grupos("3"),
    }


def cuentas_disponible(pr: dict) -> list[dict]:
    """Saldo por caja y por cuenta bancaria (cuentas 11 de mayor detalle con saldo)."""
    hojas = [k for k in pr if k.startswith("11") and len(k) >= 6]
    finales = [k for k in hojas if not any(o != k and o.startswith(k) for o in hojas)]
    return sorted(({"cuenta": k, "nombre": _nombre(pr, k), "grupo": _nombre(pr, k[:4]), "saldo": _s(pr, k)}
                   for k in finales if abs(_s(pr, k)) >= 1), key=lambda r: -r["saldo"])


# ───────────────────────── Estado de resultados ─────────────────────────

def estado_resultados(mov: pd.DataFrame) -> dict[str, float]:
    """Con los movimientos del auxiliar (filtrables por periodo). Ingresos en positivo, gastos y costos en positivo."""
    g = mov.groupby("grupo")["monto"].sum()

    def v(*gr: str) -> float:
        return float(sum(g.get(x, 0.0) for x in gr))

    ing_op, ing_no = v("41"), v("42")
    costo = float(mov[mov["clase"].isin(["6", "7"])]["monto"].sum())
    adm, ven, no_op, renta = v("51"), v("52"), v("53"), v("54")
    bruta = ing_op - costo
    operacional = bruta - adm - ven
    antes_imp = operacional + ing_no - no_op
    neta = antes_imp - renta
    return {"ingresos": ing_op, "costo": costo, "bruta": bruta, "admin": adm, "ventas": ven,
            "operacional": operacional, "otros_ingresos": ing_no, "otros_gastos": no_op,
            "antes_impuestos": antes_imp, "renta": renta, "neta": neta,
            "margen_bruto": bruta / ing_op if ing_op else None,
            "margen_operacional": operacional / ing_op if ing_op else None,
            "margen_neto": neta / (ing_op + ing_no) if (ing_op + ing_no) else None}


def resultados_mensuales(mov: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for mes, sub in mov.groupby("mes"):
        e = estado_resultados(sub)
        filas.append({"mes": mes, "ingresos": e["ingresos"] + e["otros_ingresos"], "costo": e["costo"],
                      "gastos": e["admin"] + e["ventas"] + e["otros_gastos"] + e["renta"], "utilidad": e["neta"],
                      "margen_bruto": e["margen_bruto"]})
    return pd.DataFrame(filas).sort_values("mes") if filas else pd.DataFrame()


# ───────────────────────── Caja ─────────────────────────

def flujo_caja(caja: pd.DataFrame, saldo_final: float) -> pd.DataFrame:
    """Entradas, salidas y saldo al cierre de cada mes. El saldo inicial se deduce del saldo final de la
    prueba menos los movimientos del año."""
    if caja is None or caja.empty:
        return pd.DataFrame()
    m = caja.groupby("mes")["valor"].agg(entradas=lambda s: s[s > 0].sum(), salidas=lambda s: -s[s < 0].sum(),
                                         neto="sum").sort_index()
    inicial = saldo_final - m["neto"].sum()
    m["saldo"] = inicial + m["neto"].cumsum()
    m.attrs["inicial"] = inicial
    return m.reset_index()


def mayores_movimientos_caja(caja: pd.DataFrame, n: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Terceros que más plata trajeron y que más se llevaron (sin traslados entre cuentas propias)."""
    if caja is None or caja.empty:
        return pd.DataFrame(), pd.DataFrame()
    c = caja[~caja["detalle"].fillna("").str.upper().str.contains("TRASLADO|TRANSFERENCIA ENTRE")]
    t = c.groupby("tercero")["valor"].agg(entradas=lambda s: s[s > 0].sum(), salidas=lambda s: -s[s < 0].sum())
    return (t.sort_values("entradas", ascending=False).head(n).reset_index(),
            t.sort_values("salidas", ascending=False).head(n).reset_index())


# ───────────────────────── Cartera y proveedores ─────────────────────────

def abiertas(terc: pd.DataFrame, cuentas: tuple[str, ...], deuda_nuestra: bool, corte_: pd.Timestamp) -> pd.DataFrame:
    """Facturas sin pago registrado por tercero, con su edad (días desde la factura al corte)."""
    from modulos.conocimiento import _cruce

    if terc is None or terc.empty:
        return pd.DataFrame()
    t = terc[terc["cuenta4"].isin(cuentas)]
    filas = []
    for nombre, g in t.groupby("tercero"):
        for a in _cruce(g, deuda_nuestra).get("abiertas", []):
            dias = (corte_ - pd.Timestamp(a["fecha"])).days if pd.notna(a["fecha"]) else None
            filas.append({"tercero": nombre, "fecha": a["fecha"], "factura": a["factura"] or a["detalle"][:30],
                          "valor": a["valor"], "dias": dias, "abono": a["abono"]})
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["edad"] = pd.cut(df["dias"].fillna(0), [-1, 30, 60, 90, 180, 10_000],
                        labels=["0–30 días", "31–60", "61–90", "91–180", "Más de 180"])
    return df.sort_values("valor", ascending=False)


# ───────────────────────── Indicadores ─────────────────────────

def indicadores(b: dict, e: dict, dias_periodo: int) -> list[dict]:
    """Razones financieras con su lectura en lenguaje sencillo. semaforo: bien / ojo / mal."""
    ventas_dia = e["ingresos"] / dias_periodo if dias_periodo and e["ingresos"] else None
    costo_dia = e["costo"] / dias_periodo if dias_periodo and e["costo"] else None
    pc = b["pasivo_corriente"]

    def ind(nombre, valor, fmt, bien, ojo, que, menor_mejor=False):
        if valor is None:
            sem = "nd"
        elif menor_mejor:
            sem = "bien" if valor <= bien else "ojo" if valor <= ojo else "mal"
        else:
            sem = "bien" if valor >= bien else "ojo" if valor >= ojo else "mal"
        return {"nombre": nombre, "valor": valor, "fmt": fmt, "semaforo": sem, "que": que}

    return [
        ind("Liquidez", b["activo_corriente"] / pc if pc else None, "x", 1.5, 1.0,
            "Por cada $1 que se debe a corto plazo, cuánto hay en caja, cartera e inventario."),
        ind("Prueba ácida", (b["activo_corriente"] - b["inventario"]) / pc if pc else None, "x", 1.0, 0.7,
            "Lo mismo sin contar el inventario: ¿se pagan las deudas sin vender mercancía?"),
        ind("Endeudamiento", b["pasivo"] / b["activo"] if b["activo"] else None, "%", 0.6, 0.75,
            "Qué parte de lo que tiene la empresa está financiada con deuda.", menor_mejor=True),
        ind("Margen bruto", e["margen_bruto"], "%", 0.35, 0.2, "Lo que queda de cada venta después del costo."),
        ind("Margen operacional", e["margen_operacional"], "%", 0.08, 0.0,
            "Lo que queda después de pagar la operación (administración y ventas)."),
        ind("Margen neto", e["margen_neto"], "%", 0.05, 0.0, "La utilidad final por cada peso vendido."),
        ind("Días de cartera", b["clientes"] / ventas_dia if ventas_dia else None, "d", 60, 90,
            "En cuántos días, en promedio, pagan los clientes.", menor_mejor=True),
        ind("Días de proveedores", b["proveedores"] / costo_dia if costo_dia else None, "d", 30, 60,
            "En cuántos días, en promedio, se les paga a los proveedores."),
        ind("Días de inventario", b["inventario"] / costo_dia if costo_dia else None, "d", 90, 180,
            "Cuántos días de ventas hay guardados en bodega.", menor_mejor=True),
        ind("Capital de trabajo", b["activo_corriente"] - pc, "$", 0, -1e12,
            "Activo corriente menos pasivo corriente: el colchón para operar."),
    ]
