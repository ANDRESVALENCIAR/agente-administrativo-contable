"""
Auditoría contable de Shaki — revisa el balance de prueba (y, si los hay, el auxiliar, los estados financieros
NIIF y la conciliación bancaria) con REGLAS FIJAS, sin IA: cada hallazgo trae la cifra, la cuenta y la regla que lo
produjo, así el informe se puede verificar a mano.

Bloques de revisión:
  A. Integridad: sumas iguales, ecuación patrimonial, aritmética de cada cuenta, cuentas padre = suma de hijas.
  B. Naturaleza: saldos contrarios (inventario o bancos negativos, proveedores con saldo débito…).
  C. Cuentas transitorias o por legalizar con saldo; anticipos que crecen sin legalizar.
  D. Impuestos: retenciones e IVA de periodos anteriores sin pagar.
  E. Nómina: prestaciones y aportes contra los porcentajes de ley; gasto causado = pasivo provisionado;
     cesantías, intereses y prima consolidados que ya debían estar pagados.
  F. Activos fijos: depreciación del mes.
  G. Auxiliar (si existe): comprobantes descuadrados, auxiliar vs balance, duplicados, facturas de proveedor
     registradas dos veces, terceros faltantes, domingos/festivos, montos redondos, ley de Benford.
  H. Estados financieros vs balance de prueba (si se suben).
  I. Conciliación bancaria (si se sube).

PUC colombiano (Decreto 2650/93, usado por World Office). Los saldos del balance vienen con signo según la
naturaleza de la cuenta: un saldo contrario aparece negativo.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import date
from typing import Any

import pandas as pd

NIVELES = ["CRITICO", "ALTO", "MEDIO", "BAJO", "OK"]
# Cada hallazgo resta un porcentaje de lo que queda (así muchos detalles menores no llevan la nota a cero)
PESO = {"CRITICO": 0.20, "ALTO": 0.08, "MEDIO": 0.03, "BAJO": 0.01, "OK": 0.0}
# Hallazgos que no son errores de registro sino riesgos de cumplimiento o de caja (no bajan la confiabilidad)
RIESGO = {"D1", "D2", "E3", "C2", "F2", "T3"}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
AREAS = {"A": "Integridad del balance", "B": "Naturaleza de los saldos", "C": "Cuentas transitorias y anticipos",
         "D": "Impuestos", "E": "Nómina y prestaciones", "F": "Activos fijos", "G": "Auxiliar contable",
         "H": "Estados financieros", "I": "Conciliación bancaria", "T": "Saldos por tercero",
         "J": "Continuidad entre periodos"}

# Cuentas que por definición tienen saldo contrario a su clase (no son error)
CONTRARIAS = ("1592", "1597", "1598", "1399", "1499", "1299", "1699", "1798", "1899", "1999", "240802", "240810",
              "3605", "3610", "3710", "3715", "4175", "4275", "6135", "6235", "5305")


def _p(v: float | None) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return ("−" if v < 0 else "") + "$" + f"{abs(v):,.0f}".replace(",", ".")


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.1f}%".replace(".", ",")


class Revision:
    def __init__(self) -> None:
        self.hallazgos: list[dict[str, Any]] = []

    def add(self, area: str, codigo: str, titulo: str, nivel: str, detalle: str, valor: float | None = None,
            evidencia: list[dict] | None = None, recomendacion: str = "") -> None:
        self.hallazgos.append({"area": area, "codigo": codigo, "titulo": titulo, "nivel": nivel, "detalle": detalle,
                               "valor": valor, "evidencia": evidencia or [], "recomendacion": recomendacion})

    def ok(self, area: str, codigo: str, titulo: str, detalle: str = "") -> None:
        self.add(area, codigo, titulo, "OK", detalle)


# ───────────────────────── utilidades del balance ─────────────────────────

def _hojas(pr: dict) -> list[str]:
    """Cuentas sin hijas (las de mayor detalle)."""
    cuentas = sorted(pr)
    return [c for i, c in enumerate(cuentas) if not (i + 1 < len(cuentas) and cuentas[i + 1].startswith(c))]


def _s(pr: dict, c: str, campo: str = "nuevo_saldo") -> float:
    return float((pr.get(c) or {}).get(campo) or 0.0)


def _mov(pr: dict, c: str) -> float:
    """Movimiento del periodo según la naturaleza (positivo = aumenta el saldo)."""
    d = pr.get(c) or {}
    nat = 1 if c[:1] in "15679" else -1
    return nat * (float(d.get("debitos") or 0) - float(d.get("creditos") or 0))


def _nombre(pr: dict, c: str) -> str:
    return str((pr.get(c) or {}).get("nombre") or "").strip()


def _buscar(pr: dict, prefijo: str, *palabras: str) -> list[str]:
    """Cuentas de 6 dígitos bajo `prefijo` cuyo nombre contiene alguna de las palabras."""
    out = []
    for c in pr:
        if c.startswith(prefijo) and len(c) == 6:
            n = _nombre(pr, c).upper()
            if any(p in n for p in palabras):
                out.append(c)
    return out


# ───────────────────────── A. Integridad ─────────────────────────

def _integridad(r: Revision, pr: dict) -> None:
    clases = [c for c in pr if len(c) == 1]
    deb = sum(float(pr[c]["debitos"]) for c in clases)
    cre = sum(float(pr[c]["creditos"]) for c in clases)
    if abs(deb - cre) > 1:
        r.add("A", "A1", "Débitos y créditos del periodo no suman igual", "CRITICO",
              f"Débitos {_p(deb)} vs. créditos {_p(cre)}: diferencia {_p(deb - cre)}. Un balance de prueba siempre "
              "debe tener sumas iguales; hay asientos descuadrados o el archivo está incompleto.", deb - cre,
              recomendacion="Pedir al contador el listado de comprobantes descuadrados del periodo.")
    else:
        r.ok("A", "A1", "Sumas iguales: débitos = créditos", f"{_p(deb)} en ambos lados.")

    act, pas, pat = _s(pr, "1"), _s(pr, "2"), _s(pr, "3")
    res = _s(pr, "4") - _s(pr, "5") - _s(pr, "6") - _s(pr, "7")
    dif = act - (pas + pat + res)
    if abs(dif) > max(1000.0, abs(act) * 1e-6):
        r.add("A", "A2", "La ecuación patrimonial no cuadra", "CRITICO",
              f"Activo {_p(act)} ≠ pasivo {_p(pas)} + patrimonio {_p(pat)} + resultado del periodo {_p(res)}. "
              f"Diferencia: {_p(dif)}.", dif, recomendacion="Revisar cuentas de orden mal clasificadas o el cierre.")
    else:
        r.ok("A", "A2", "Ecuación patrimonial cuadra",
             f"Activo {_p(act)} = pasivo {_p(pas)} + patrimonio {_p(pat)} + resultado {_p(res)}.")

    malas = []
    for c, d in pr.items():
        nat = 1 if c[:1] in "15679" else -1
        calc = float(d["saldo_anterior"]) + nat * (float(d["debitos"]) - float(d["creditos"]))
        if abs(calc - float(d["nuevo_saldo"])) > 1:
            malas.append({"cuenta": c, "nombre": _nombre(pr, c), "calculado": calc, "reportado": d["nuevo_saldo"]})
    if malas:
        r.add("A", "A3", f"{len(malas)} cuentas con saldo final mal calculado", "ALTO",
              "Saldo anterior ± movimientos no da el saldo final reportado.", None, malas[:30],
              "Volver a generar el balance desde el programa contable.")
    else:
        r.ok("A", "A3", "Saldo final de cada cuenta = saldo anterior ± movimientos", f"{len(pr)} cuentas verificadas.")

    jer = []
    cuentas = sorted(pr)
    for c in cuentas:
        hijas = [h for h in cuentas if h != c and h.startswith(c)]
        if not hijas:
            continue
        nivel = min(len(h) for h in hijas)
        directas = [h for h in hijas if len(h) == nivel]
        suma = sum(_s(pr, h) for h in directas)
        if abs(suma - _s(pr, c)) > 1:
            jer.append({"cuenta": c, "nombre": _nombre(pr, c), "saldo": _s(pr, c), "suma_subcuentas": suma})
    if jer:
        for j in jer:
            j["registrado_directo_en_la_mayor"] = j["saldo"] - j["suma_subcuentas"]
        r.add("A", "A4", f"{len(jer)} cuentas con movimientos registrados en la cuenta mayor", "MEDIO",
              "Estas cuentas tienen subcuentas, pero parte de su saldo se contabilizó directamente en la cuenta mayor "
              "(no en una subcuenta). El total es correcto, pero los informes por subcuenta quedan incompletos.",
              sum(abs(j["registrado_directo_en_la_mayor"]) for j in jer), jer[:30],
              "Reclasificar esos movimientos a la subcuenta que corresponde y bloquear la cuenta mayor para registros.")
    else:
        r.ok("A", "A4", "Cada cuenta mayor = suma de sus subcuentas")


# ───────────────────────── B. Naturaleza ─────────────────────────

def _naturaleza(r: Revision, pr: dict) -> None:
    contrarios = []
    for c in _hojas(pr):
        v = _s(pr, c)
        if v >= -1000 or c.startswith(CONTRARIAS):
            continue
        if c.startswith("3"):  # pérdidas acumuladas o del ejercicio
            continue
        contrarios.append({"cuenta": c, "nombre": _nombre(pr, c), "saldo": v})
    if not contrarios:
        r.ok("B", "B1", "Ninguna cuenta con saldo contrario a su naturaleza")
        return
    for x in sorted(contrarios, key=lambda x: x["saldo"]):
        c, v = x["cuenta"], x["saldo"]
        if c.startswith("11"):
            nivel, porque = "ALTO", "Caja o bancos en negativo: o hay un sobregiro no registrado como deuda o faltan consignaciones."
        elif c.startswith("14"):
            nivel, porque = "ALTO", ("Inventario negativo: salieron (se vendieron) más unidades de las que entraron. "
                                     "Suele ser una compra sin registrar o un costo de ventas mal calculado.")
        elif c.startswith("13"):
            nivel, porque = "MEDIO", "Deudores con saldo crédito: pagos o anticipos de clientes sin cruzar con su factura."
        elif c.startswith("22") or c.startswith("23"):
            nivel, porque = "MEDIO", "Proveedor o cuenta por pagar con saldo débito: pago de más o factura sin registrar."
        elif c.startswith("21"):
            nivel, porque = "MEDIO", "Obligación financiera o tarjeta con saldo débito: pago de más o cuota mal aplicada."
        else:
            nivel, porque = "BAJO", "Saldo contrario a la naturaleza de la cuenta."
        if abs(v) < 100_000:
            nivel = "BAJO"
        r.add("B", "B1", f"Saldo contrario: {c} {x['nombre'].title()[:45]}", nivel, porque, v, [x],
              "Revisar el auxiliar de la cuenta y hacer el ajuste o la reclasificación.")


# ───────────────────────── C. Transitorias y anticipos ─────────────────────────

PALABRAS_TRANSITORIAS = ("PENDIENTE", "POR LEGALIZAR", "LEGALIZAR", "POR IDENTIFICAR", "TRANSITORI", "PUENTE",
                         "SIN SOPORTE", "POR CLASIFICAR", "POR APLICAR", "SIN IDENTIFICAR", "CRUCE")


def _transitorias(r: Revision, pr: dict) -> None:
    filas = [{"cuenta": c, "nombre": _nombre(pr, c), "saldo": _s(pr, c)} for c in _hojas(pr)
             if any(p in _nombre(pr, c).upper() for p in PALABRAS_TRANSITORIAS) and abs(_s(pr, c)) >= 1000]
    if filas:
        total = sum(abs(f["saldo"]) for f in filas)
        r.add("C", "C1", f"{len(filas)} cuentas transitorias o «por legalizar» con saldo", "MEDIO" if total > 1e6 else "BAJO",
              "Son cuentas de paso que deberían quedar en cero al cierre del mes.", total, filas,
              "Legalizar con los soportes o reclasificar a la cuenta definitiva.")
    else:
        r.ok("C", "C1", "Cuentas transitorias en cero")
    for pref, nombre in (("1330", "Anticipos y avances"), ("1466", "Anticipos de importaciones")):
        if pref not in pr:
            continue
        ant, fin = _s(pr, pref, "saldo_anterior"), _s(pr, pref)
        if fin > 1e6 and ant > 0 and fin > ant * 1.5:
            r.add("C", "C2", f"{nombre} crecieron {_pct(fin / ant - 1)} en el mes", "MEDIO",
                  f"Pasaron de {_p(ant)} a {_p(fin)}. Los anticipos deben cruzarse con la factura cuando llega la "
                  "mercancía o el servicio; si no, el gasto/costo y el IVA descontable quedan sin registrar.", fin,
                  recomendacion="Pedir el detalle por tercero y legalizar los que ya tienen factura.")
        elif fin > 1e6:
            r.add("C", "C2", f"{nombre}: {_p(fin)} por legalizar", "BAJO",
                  "Saldo de anticipos entregados pendientes de cruzar con factura.", fin)


# ───────────────────────── D. Impuestos ─────────────────────────

def _impuestos(r: Revision, pr: dict, mes: int | None) -> None:
    for pref, nombre, meses_ok in (("2365", "Retención en la fuente", 1), ("2367", "IVA retenido", 1),
                                   ("2368", "ICA retenido (Bogotá, bimestral)", 2)):
        if pref not in pr:
            continue
        saldo = _s(pr, pref)
        del_mes = float(pr[pref]["creditos"])
        viejo = saldo - del_mes * meses_ok
        if viejo > 10_000:
            r.add("D", "D1", f"{nombre}: {_p(viejo)} de periodos anteriores sin pagar", "ALTO",
                  f"El saldo de la cuenta {pref} es {_p(saldo)} y lo retenido en el mes es {_p(del_mes)}. Lo que excede "
                  "corresponde a declaraciones anteriores no pagadas (generan intereses de mora y, en retención, la "
                  "declaración sin pago se tiene por no presentada — art. 580-1 E.T.).", viejo,
                  [{"cuenta": c, "nombre": _nombre(pr, c), "saldo": _s(pr, c)} for c in pr
                   if c.startswith(pref) and len(c) == 6 and abs(_s(pr, c)) > 1000],
                  "Pagar con los intereses de mora y conciliar la cuenta con los recibos 490.")
        else:
            r.ok("D", "D1", f"{nombre}: solo queda lo del periodo", _p(saldo))
    if "2408" in pr:
        por_pagar = sum(_s(pr, c) for c in _buscar(pr, "2408", "POR PAGAR"))
        if por_pagar > 10_000:
            r.add("D", "D2", f"IVA de periodos anteriores por pagar: {_p(por_pagar)}", "ALTO",
                  "La subcuenta de IVA por pagar (saldo ya declarado) tiene saldo. El IVA de un bimestre declarado se "
                  "paga con la declaración; si sigue aquí, hay declaraciones de IVA sin pagar.", por_pagar,
                  [{"cuenta": c, "nombre": _nombre(pr, c), "saldo_anterior": _s(pr, c, "saldo_anterior"),
                    "pagos_del_mes": float(pr[c]["debitos"]), "saldo": _s(pr, c)} for c in _buscar(pr, "2408", "POR PAGAR")],
                  "Confirmar con el contador si hay acuerdo de pago con la DIAN; si no, pagar con intereses.")
        gen = sum(float(pr[c]["creditos"]) for c in _buscar(pr, "2408", "GENERADO"))
        # ventas brutas facturadas en el mes (sin devoluciones, que reversan su propio IVA)
        ventas = float(sum(pr[c]["creditos"] for c in pr if c.startswith("41") and len(c) == 4 and not c.startswith("4175")))
        if gen and ventas > 0:
            tasa = gen / ventas
            if tasa > 0.20 or tasa < 0.12:
                r.add("D", "D3", f"IVA generado del mes = {_pct(tasa)} de las ventas facturadas", "MEDIO",
                      f"IVA generado {_p(gen)} sobre ventas facturadas {_p(ventas)}. Con ventas gravadas al 19 % debería rondar el "
                      "19 % (menos si hay ventas exentas o excluidas). Una tasa muy distinta indica facturas sin IVA o IVA "
                      "registrado en otro mes.", tasa)
            else:
                r.ok("D", "D3", "IVA generado coherente con las ventas del mes", f"{_pct(tasa)} de {_p(ventas)}")


# ───────────────────────── E. Nómina ─────────────────────────

def _causado(pr: dict, c: str) -> float:
    """Gasto causado en el mes = débitos (los créditos son reversiones o reclasificaciones)."""
    return float((pr.get(c) or {}).get("debitos") or 0)


def _nomina(r: Revision, pr: dict, mes: int | None) -> None:
    def mes_de(*palabras: str, sin: tuple[str, ...] = ()) -> float:
        return sum(_causado(pr, c) for c in _buscar(pr, "5105", *palabras) + _buscar(pr, "5205", *palabras)
                   if not any(x in _nombre(pr, c).upper() for x in sin))

    sueldos = mes_de("SUELDOS", "SALARIO", "JORNALES", sin=("INTEGRAL",))
    if sueldos <= 0:
        return
    aux_t = mes_de("AUXILIO DE TRANSPORTE")
    extras = mes_de("HORAS EXTRAS", "COMISIONES", "RECARGOS")
    base_prest = sueldos + aux_t + extras
    ibc = sueldos + extras
    reglas = [
        ("CESANTIAS", ("CESANTIAS",), base_prest, 0.0833, "8,33 % de salario + auxilio de transporte"),
        ("PRIMA DE SERVICIOS", ("PRIMA DE SERVICIOS",), base_prest, 0.0833, "8,33 % de salario + auxilio de transporte"),
        ("VACACIONES", ("VACACIONES",), sueldos, 0.0417, "4,17 % del salario básico"),
        ("PENSIONES", ("PENSION",), ibc, 0.12, "12 % del salario (aporte del empleador)"),
        ("CAJA DE COMPENSACIÓN", ("CAJAS DE COMPENSACION", "CAJA DE COMPENSACION"), ibc, 0.04, "4 % del salario"),
    ]
    evid, problemas = [], []
    for nombre, palabras, base, tasa, ley in reglas:
        if nombre == "CESANTIAS":
            valor = mes_de("CESANTIAS", sin=("INTERES", "APORTE", "PENSION", "FONDO"))
        elif nombre == "PENSIONES":
            valor = mes_de("PENSION")
        else:
            valor = mes_de(*palabras)
        real = valor / base if base else 0
        evid.append({"concepto": nombre.title(), "causado_mes": valor, "base": base, "porcentaje": _pct(real),
                     "ley": _pct(tasa)})
        if valor <= 0:
            problemas.append(("ALTO", f"No se causó {nombre.lower()} en el mes",
                              f"Hay sueldos por {_p(sueldos)} pero no hay gasto de {nombre.lower()} ({ley}). El pasivo "
                              "laboral queda subestimado.", base * tasa))
        elif abs(real / tasa - 1) > 0.15:
            problemas.append(("MEDIO", f"{nombre.title()} causada al {_pct(real)} (ley: {_pct(tasa)})",
                              f"Gasto del mes {_p(valor)} sobre una base de {_p(base)}; lo esperado es {_p(base * tasa)} "
                              f"({ley}). Puede haber salario integral, incapacidades o un error de causación.",
                              valor - base * tasa))
    ces = mes_de("CESANTIAS", sin=("INTERES", "APORTE", "PENSION", "FONDO"))
    intereses = mes_de("INTERESES SOBRE CESANTIAS")
    if ces > 0:
        real = intereses / ces
        evid.append({"concepto": "Intereses sobre cesantías", "causado_mes": intereses, "base": ces,
                     "porcentaje": _pct(real), "ley": "12,0%"})
        if abs(real / 0.12 - 1) > 0.2:
            problemas.append(("MEDIO", f"Intereses sobre cesantías al {_pct(real)} de las cesantías (ley: 12 %)",
                              f"Causado {_p(intereses)} frente a {_p(ces * 0.12)} esperado (Ley 52 de 1975).",
                              intereses - ces * 0.12))
    if problemas:
        for i, (nivel, titulo, detalle, valor) in enumerate(problemas):
            r.add("E", "E1", titulo, nivel, detalle, valor, evid if i == 0 else None,
                  "Revisar la liquidación de nómina y causar la diferencia.")
    else:
        r.ok("E", "E1", "Prestaciones y aportes del mes según los porcentajes de ley",
             f"Base: sueldos {_p(sueldos)} + auxilio de transporte {_p(aux_t)}.")
        r.hallazgos[-1]["evidencia"] = evid

    # gasto causado = pasivo provisionado (2610)
    pares = [("CESANTIAS", "CESANTIAS"), ("PRIMA", "PRIMA"), ("VACACIONES", "VACACIONES"), ("INTERESES", "INTERESES")]
    difs = []
    for g, p in pares:
        gasto = sum(_causado(pr, c) for c in _buscar(pr, "5105", g)
                    if (g == "INTERESES") == ("INTERES" in _nombre(pr, c).upper())
                    and not any(x in _nombre(pr, c).upper() for x in ("APORTE", "PENSION", "FONDO")))
        pas = sum(float(pr[c]["creditos"]) for c in _buscar(pr, "2610", p)
                  if (p == "INTERESES") == ("INTERES" in _nombre(pr, c).upper()))
        if gasto and pas and abs(gasto - pas) > 1000:
            difs.append({"concepto": g.title(), "gasto_del_mes": gasto, "provision_del_mes": pas, "diferencia": gasto - pas})
    if difs:
        r.add("E", "E2", "Gasto de prestaciones distinto a la provisión del pasivo", "MEDIO",
              "Lo causado en el gasto (5105) debería ser igual a lo que aumentó la provisión (2610).", None, difs)
    elif _buscar(pr, "2610", "CESANTIAS"):
        r.ok("E", "E2", "Gasto de prestaciones = provisión del pasivo laboral")



def _consolidados(r: Revision, pr: dict, mes: int | None) -> None:
    """Cesantías, intereses y prima ya liquidados que a esta fecha debían estar pagados."""
    if mes:
        pendientes = []
        for pref, nombre, vence, desde_mes in (("2510", "Cesantías consolidadas", "14 de febrero (fondo de cesantías)", 3),
                                               ("2515", "Intereses sobre cesantías", "31 de enero (al trabajador)", 2),
                                               ("2520", "Prima de servicios", "30 de junio y 20 de diciembre", 7)):
            v = _s(pr, pref)
            if v > 100_000 and mes >= desde_mes:
                pendientes.append({"cuenta": pref, "concepto": nombre, "saldo": v, "debia_pagarse": vence})
        if pendientes:
            total = sum(p["saldo"] for p in pendientes)
            r.add("E", "E3", f"Prestaciones consolidadas que ya debían estar pagadas: {_p(total)}", "ALTO",
                  "Estas cuentas guardan lo ya liquidado a los trabajadores; a esta fecha deberían estar en cero. Si se "
                  "pagaron, falta registrar el pago; si no, hay sanción moratoria (art. 99 Ley 50/90: un día de salario "
                  "por cada día de retraso en cesantías).", total, pendientes,
              "Verificar con la planilla de pago al fondo y los comprobantes de pago; registrar o pagar.")
        else:
            r.ok("E", "E3", "Prestaciones consolidadas sin saldos vencidos")




# ───────────────────────── F. Activos fijos ─────────────────────────

def _activos(r: Revision, pr: dict) -> None:
    no_dep = ("1504", "1508", "1512", "1592", "1597", "1598", "1599")
    depreciables = sum(_s(pr, c) for c in pr if c.startswith("15") and len(c) == 4 and not c.startswith(no_dep))
    dep_mes = float((pr.get("1592") or {}).get("creditos") or 0)
    gasto_dep = sum(_mov(pr, c) for c in pr if c.startswith(("5160", "5260", "7360")) and len(c) == 4)
    if depreciables > 0 and dep_mes == 0 and gasto_dep == 0:
        r.add("F", "F1", "No se registró la depreciación del mes", "MEDIO",
              f"Hay activos depreciables por {_p(depreciables)} y la depreciación acumulada (1592) no se movió.",
              depreciables, recomendacion="Causar la depreciación mensual (débito 5160, crédito 1592).")
    elif depreciables > 0:
        r.ok("F", "F1", "Depreciación del mes registrada", _p(dep_mes))
    montaje = _s(pr, "1512") + _s(pr, "1508")
    if montaje > 1e6:
        r.add("F", "F2", f"Activos «en montaje / en curso» por {_p(montaje)} sin depreciar", "BAJO",
              "Mientras un activo está en montaje no se deprecia; si ya está en uso (por ejemplo equipo de oficina), "
              "debe trasladarse a su cuenta definitiva y empezar a depreciarse.", montaje,
              [{"cuenta": c, "nombre": _nombre(pr, c), "saldo": _s(pr, c)} for c in pr
               if c.startswith(("1512", "1508")) and len(c) == 6])


# ───────────────────────── G. Auxiliar ─────────────────────────

def _benford(valores: pd.Series) -> tuple[float, pd.DataFrame]:
    """Desviación media absoluta (MAD) del primer dígito frente a la ley de Benford (umbrales de Nigrini)."""
    d = valores.abs()
    d = d[d >= 10].astype(int).astype(str).str[0].astype(int)
    n = len(d)
    obs = d.value_counts(normalize=True).reindex(range(1, 10), fill_value=0)
    esp = pd.Series({k: math.log10(1 + 1 / k) for k in range(1, 10)})
    mad = float((obs - esp).abs().mean())
    tabla = pd.DataFrame({"digito": range(1, 10), "observado": obs.values, "esperado": esp.values, "n": n})
    return mad, tabla


def _auxiliar(r: Revision, aux: pd.DataFrame, pr: dict) -> None:
    aux = aux.copy()
    aux["fecha"] = pd.to_datetime(aux["fecha"], errors="coerce")
    aux["cuenta"] = aux["cuenta"].astype(str)
    aux["detalle"] = aux["detalle"].fillna("").astype(str)
    aux["comprobante"] = aux["comprobante"].fillna("").astype(str)

    # G1 comprobantes descuadrados (solo si el auxiliar trae todas las cuentas)
    if aux["cuenta"].str[0].nunique() >= 4:
        g = aux.groupby("comprobante")["valor"].sum()
        malos = g[g.abs() > 1]
        if len(malos):
            r.add("G", "G1", f"{len(malos)} comprobantes descuadrados", "CRITICO",
                  "La suma de débitos y créditos de cada comprobante debe dar cero.", float(malos.abs().sum()),
                  [{"comprobante": k, "diferencia": v} for k, v in malos.head(30).items()])
        else:
            r.ok("G", "G1", f"Los {len(g):,} comprobantes del auxiliar están cuadrados".replace(",", "."))

    # G2 auxiliar vs balance en cuentas de resultado (acumulado del año), por cuenta de 4 dígitos
    if pr:
        res = aux[aux["cuenta"].str[0].isin(list("4567"))]
        suma = res.groupby(res["cuenta"].str[:4])["valor"].sum()
        difs = []
        for c, v in suma.items():
            if c in pr:
                esperado = v if c[0] in "567" else -v
                if abs(esperado - _s(pr, c)) > 1000:
                    difs.append({"cuenta": c, "nombre": _nombre(pr, c), "auxiliar": esperado, "balance": _s(pr, c),
                                 "diferencia": esperado - _s(pr, c)})
        if difs:
            r.add("G", "G2", f"{len(difs)} cuentas de resultado no cuadran entre auxiliar y balance", "ALTO",
                  "El acumulado del auxiliar debería ser igual al saldo del balance de prueba (mismo corte).", None,
                  difs[:30], "Revisar que ambos archivos sean del mismo corte y que no haya comprobantes anulados a medias.")
        elif len(suma):
            r.ok("G", "G2", "Auxiliar y balance coinciden en todas las cuentas de resultado", f"{len(suma)} cuentas.")

    # G3 duplicados exactos
    base = aux[aux["valor"].abs() >= 100_000].copy()
    base["quien"] = (base["nit"] if base["nit"].notna().any() else base.get("nombre", base["nit"])).astype(str)
    dup = base[base.duplicated(["cuenta", "quien", "fecha", "valor", "detalle"], keep=False)]
    grupos = dup.groupby(["cuenta", "quien", "fecha", "valor", "detalle"])["comprobante"].apply(lambda s: sorted(set(s)))
    grupos = grupos[grupos.map(len) > 1]
    pares: dict[tuple, dict] = {}
    for k, v in grupos.items():  # un mismo par de comprobantes cuenta una vez (no por cada línea del asiento)
        clave = tuple(v)
        if clave not in pares or abs(k[3]) > abs(pares[clave]["valor"]):
            pares[clave] = {"fecha": str(k[2])[:10], "cuenta": k[0], "tercero": k[1] if k[1] not in ("None", "nan") else "",
                            "valor": abs(k[3]), "detalle": k[4][:60], "comprobantes": ", ".join(v)}
    if pares:
        ev = sorted(pares.values(), key=lambda x: -x["valor"])
        r.add("G", "G3", f"{len(pares)} posibles asientos duplicados", "MEDIO",
              "Mismo tercero, cuenta, fecha, valor y detalle en comprobantes distintos (muchas veces consecutivos).",
              float(sum(x["valor"] for x in ev)), ev[:30],
              "Confirmar con los soportes; si es un duplicado, anular uno de los comprobantes.")
    else:
        r.ok("G", "G3", "Sin registros duplicados (≥ $100.000)")

    # G4 facturas de proveedor registradas dos veces
    from modulos.conocimiento import _num_factura
    prov = aux[aux["cuenta"].str.startswith("2205") & (aux["valor"] < 0)]

    def tipo_doc(comp: str) -> str:
        t = re.sub(r"^\([^)]*\)\s*", "", comp).split()
        return t[0].upper() if t else ""
    vistos: dict[tuple, list] = defaultdict(list)
    for _, f in prov.iterrows():
        td = tipo_doc(f["comprobante"])
        if td in ("NC", "ND", "CE", "RC", "NCE", "AJ", "CI"):  # notas, egresos, recibos y ajustes no son causación
            continue
        for k in _num_factura(f"{f['detalle']}"):
            if not k.startswith(("OC", "FAC", "N")):  # número de la factura del proveedor
                quien = str(f["nit"]) if pd.notna(f["nit"]) and str(f["nit"]).strip() else str(f.get("nombre", ""))
                vistos[(quien, k, td)].append((f["comprobante"], f["valor"], str(f["fecha"])[:10]))
    dobles = [{"tercero": k[0], "factura": k[1], "registros": "; ".join(f"{c} {_p(-v)} ({d})" for c, v, d in v)}
              for k, v in vistos.items() if len({c for c, _, _ in v}) > 1]
    if dobles:
        r.add("G", "G4", f"{len(dobles)} facturas de proveedor causadas más de una vez", "ALTO",
              "El mismo número de factura del mismo proveedor aparece en comprobantes de causación distintos: se "
              "estaría pagando o descontando IVA dos veces.", None, dobles[:30],
              "Revisar cada caso; anular la causación repetida o, si es una nota, registrarla como tal.")
    elif len(prov):
        r.ok("G", "G4", "Ninguna factura de proveedor causada dos veces")

    # G5 terceros faltantes donde son obligatorios
    ident = aux["nit"] if aux["nit"].notna().any() else aux.get("nombre", aux["nit"])
    sin = aux[aux["cuenta"].str.startswith(("13", "22", "23", "2365")) &
              (ident.isna() | ident.astype(str).str.strip().isin(["", "0", "None", "nan"]))]
    if len(sin):
        r.add("G", "G5", f"{len(sin)} movimientos sin tercero en cuentas que lo exigen", "MEDIO",
              "Cartera, proveedores, cuentas por pagar y retenciones deben llevar NIT (lo pide la exógena y el "
              "certificado de retenciones).", float(sin["valor"].abs().sum()),
              sin.head(20)[["cuenta", "fecha", "comprobante", "detalle", "valor"]].assign(
                  fecha=lambda d: d["fecha"].astype(str).str[:10]).to_dict("records"))
    else:
        r.ok("G", "G5", "Todos los movimientos de cartera, proveedores y retenciones tienen tercero")

    # G6 domingos y festivos (gastos y costos)
    try:
        from core.calendario_col import es_festivo_colombia
    except Exception:  # noqa: BLE001
        es_festivo_colombia = None  # type: ignore
    gastos = aux[aux["cuenta"].str[0].isin(["5", "6", "7"]) & (aux["valor"] > 0)].dropna(subset=["fecha"])
    if len(gastos):
        fest = gastos[gastos["fecha"].map(lambda f: f.weekday() == 6 or bool(es_festivo_colombia and
                                                                               es_festivo_colombia(f.date())))]
        fest = fest[fest["valor"] >= 500_000]
        if len(fest) > 0:
            r.add("G", "G6", f"{len(fest)} gastos registrados en domingo o festivo", "BAJO",
                  "No es un error por sí mismo (puede ser la fecha de la factura), pero conviene revisar los soportes.",
                  float(fest["valor"].sum()),
                  fest.sort_values("valor", ascending=False).head(15)[["fecha", "cuenta", "comprobante", "detalle", "valor"]]
                  .assign(fecha=lambda d: d["fecha"].dt.strftime("%Y-%m-%d")).to_dict("records"))

        # G7 montos redondos altos
        red = gastos[(gastos["valor"] >= 5_000_000) & (gastos["valor"] % 1_000_000 == 0)]
        if len(red):
            r.add("G", "G7", f"{len(red)} gastos por montos exactos en millones (≥ $5 M)", "BAJO",
                  "Los montos redondos grandes son típicos de estimaciones o cuentas de cobro sin factura: verificar soporte.",
                  float(red["valor"].sum()),
                  red.sort_values("valor", ascending=False).head(15)[["fecha", "cuenta", "comprobante", "detalle", "valor"]]
                  .assign(fecha=lambda d: d["fecha"].dt.strftime("%Y-%m-%d")).to_dict("records"))

        # G8 Benford
        if len(gastos) >= 300:
            mad, tabla = _benford(gastos["valor"])
            if mad > 0.015:
                r.add("G", "G8", f"Los montos de gastos no siguen la ley de Benford (MAD {mad:.4f})", "MEDIO",
                      "En contabilidades reales la frecuencia del primer dígito sigue la ley de Benford. Una desviación "
                      "alta (MAD > 0,015, criterio de Nigrini) señala montos repetidos, estimados o digitados: no prueba un "
                      "error, indica dónde mirar.", mad, tabla.round(4).to_dict("records"))
            else:
                r.ok("G", "G8", f"Montos de gastos conformes con la ley de Benford (MAD {mad:.4f})",
                     f"{int(tabla['n'].iloc[0]):,} registros analizados.".replace(",", "."))


# ───────────────────────── I. Conciliación bancaria ─────────────────────────

def _conciliacion(r: Revision, pr: dict, conc: dict, corte: date | None) -> None:
    """conc: {'saldo_extracto', 'saldo_libros', 'partidas': [{'fecha','concepto','valor','tipo'}], 'cuenta'}."""
    ext, lib = conc.get("saldo_extracto"), conc.get("saldo_libros")
    partidas = conc.get("partidas") or []
    if ext is None or lib is None:
        r.add("I", "I0", "No se encontraron los saldos de extracto y libros en la conciliación", "MEDIO",
              "Se buscan rótulos como «Saldo según extracto» y «Saldo según libros».")
        return
    neto = sum(p["valor"] for p in partidas)
    dif = ext + neto - lib
    if abs(dif) > 1:
        r.add("I", "I1", f"La conciliación no cierra: diferencia de {_p(dif)}", "CRITICO",
              f"Extracto {_p(ext)} + partidas conciliatorias {_p(neto)} ≠ libros {_p(lib)}.", dif,
              recomendacion="Identificar la partida faltante antes de cerrar el mes.")
    else:
        r.ok("I", "I1", "La conciliación cierra", f"Extracto {_p(ext)} + partidas {_p(neto)} = libros {_p(lib)}")
    # libros de la conciliación vs balance
    cands = [c for c in pr if c.startswith(("1110", "1120")) and len(c) >= 6]
    if cands:
        iguales = [c for c in cands if abs(_s(pr, c) - lib) <= 1]
        if iguales:
            r.ok("I", "I2", "El saldo en libros de la conciliación = saldo de la cuenta en el balance",
                 f"{iguales[0]} {_nombre(pr, iguales[0]).title()}")
        else:
            r.add("I", "I2", "El saldo en libros de la conciliación no aparece en el balance de prueba", "ALTO",
                  f"Saldo en libros según la conciliación: {_p(lib)}. Ninguna cuenta de bancos del balance tiene ese "
                  "saldo: la conciliación o el balance no son del mismo corte, o hay ajustes sin registrar.", lib,
                  [{"cuenta": c, "nombre": _nombre(pr, c), "saldo": _s(pr, c)} for c in cands if abs(_s(pr, c)) > 1])
    if corte and partidas:
        viejas = [p for p in partidas if p.get("fecha") and (corte - p["fecha"]).days > 60]
        if viejas:
            r.add("I", "I3", f"{len(viejas)} partidas conciliatorias con más de 60 días", "MEDIO",
                  "Cheques sin cobrar, consignaciones o notas del banco viejas deben ajustarse en libros (cheques "
                  "> 6 meses se reversan; notas bancarias se registran).", float(sum(abs(p["valor"]) for p in viejas)),
                  [{**p, "fecha": str(p["fecha"])} for p in sorted(viejas, key=lambda x: x["fecha"])[:30]])
        else:
            r.ok("I", "I3", "Sin partidas conciliatorias viejas (> 60 días)")



# ───────────────────────── Lectores World Office ─────────────────────────

def leer_auxiliar_wo(libro) -> pd.DataFrame | None:
    """«Libro Auxiliar» exportado de World Office: Cuenta (código + nombre) · Tercero · Fecha · Nota · Doc Num ·
    Débitos · Créditos."""
    from modulos.revision_lectores import norm
    for hoja in libro.hojas:
        filas = libro.hoja(hoja) or []
        for i, f in enumerate(filas[:15]):
            cab = [norm(x) for x in f]
            if "cuenta" in cab and "fecha" in cab and any(c.startswith("debito") for c in cab) and \
                    any(c.startswith("credito") for c in cab) and "tercero" in cab:
                ic = {k: cab.index(k) for k in ("cuenta", "tercero", "fecha")}
                ide = next(j for j, c in enumerate(cab) if c.startswith("debito"))
                icr = next(j for j, c in enumerate(cab) if c.startswith("credito"))
                inota = next((j for j, c in enumerate(cab) if c in ("nota", "detalle", "concepto")), None)
                idoc = next((j for j, c in enumerate(cab) if c in ("doc num", "documento", "comprobante")), None)
                out = []
                for g in filas[i + 1:]:
                    m = re.match(r"\s*(\d{1,10})", str(g[ic["cuenta"]] or ""))
                    if not m:
                        continue
                    d = g[ide] if isinstance(g[ide], (int, float)) else 0
                    c = g[icr] if isinstance(g[icr], (int, float)) else 0
                    out.append({"cuenta": m.group(1), "fecha": g[ic["fecha"]], "nit": None,
                                "nombre": str(g[ic["tercero"]] or "").strip(),
                                "comprobante": str(g[idoc] or "") if idoc is not None else "",
                                "detalle": str(g[inota] or "") if inota is not None else "", "valor": float(d) - float(c)})
                if out:
                    return pd.DataFrame(out)
    return None


def leer_terceros_wo(libro) -> pd.DataFrame | None:
    """Balance por tercero de World Office (CodCuentaNivel5 · TIPO · CC O NIT · Tercero · … · SaldoFinalDet)."""
    from modulos.revision_lectores import norm
    mejor = None
    for hoja in libro.hojas:
        filas = libro.hoja(hoja) or []
        for i, f in enumerate(filas[:6]):
            cab = [norm(x).replace(" ", "") for x in f]
            if any(c.startswith("codcuenta") for c in cab) and any(c.startswith("saldofinal") for c in cab):
                icu = next(j for j, c in enumerate(cab) if c.startswith("codcuenta"))
                ifi = next(j for j, c in enumerate(cab) if c.startswith("saldofinal"))
                inom = next((j for j, c in enumerate(cab) if "tercero" in c), None)
                init = next((j for j, c in enumerate(cab) if c in ("cconit", "nit", "ccnit")), None)
                out = []
                for g in filas[i + 1:]:
                    m = re.match(r"\s*(\d{4,10})", str(g[icu] or ""))
                    if m and isinstance(g[ifi], (int, float)):
                        out.append({"cuenta": m.group(1), "nit": g[init] if init is not None else None,
                                    "tercero": str(g[inom] or "").strip() if inom is not None else "",
                                    "saldo": float(g[ifi])})
                df = pd.DataFrame(out)
                if not df.empty and (mejor is None or (init is not None and mejor["nit"].isna().all())):
                    mejor = df
                break
    return mejor


# ───────────────────────── T. Terceros ─────────────────────────

def _terceros(r: Revision, pr: dict, ter: pd.DataFrame) -> None:
    suma = ter.groupby("cuenta")["saldo"].sum()
    hojas = set(_hojas(pr))
    difs = [{"cuenta": c, "nombre": _nombre(pr, c), "balance": _s(pr, c), "suma_terceros": v, "diferencia": v - _s(pr, c)}
            for c, v in suma.items() if c in hojas and abs(v - _s(pr, c)) > 1000]
    if difs:
        r.add("T", "T1", f"{len(difs)} cuentas donde la suma por tercero no da el saldo del balance", "ALTO",
              "El auxiliar por terceros debe sumar exactamente el saldo de la cuenta.", None, difs[:30],
              "Revisar movimientos sin tercero o el corte de los dos reportes.")
    else:
        r.ok("T", "T1", "La suma por tercero = saldo de cada cuenta", f"{len(suma)} cuentas verificadas.")
    reglas = [("1305", "Clientes con saldo a favor (crédito)", lambda v: v < -1000,
               "Pagos o anticipos de clientes sin cruzar con su factura, o facturas sin registrar."),
              ("2205", "Proveedores con saldo a nuestro favor (débito)", lambda v: v > 1000,
               "Pagos de más o facturas del proveedor sin causar."),
              ("2335", "Cuentas por pagar con saldo débito", lambda v: v > 1000, "Pagos sin la cuenta por pagar causada.")]
    for pref, titulo, cond, porque in reglas:
        sub = ter[ter["cuenta"].str.startswith(pref)]
        sub = sub.groupby(["tercero"], dropna=False)["saldo"].sum()
        malos = sub[sub.map(cond)].sort_values(key=abs, ascending=False)
        if len(malos):
            total = float(malos.abs().sum())
            r.add("T", "T2", f"{titulo}: {len(malos)} terceros", "MEDIO" if total > 1e6 else "BAJO", porque, total,
                  [{"tercero": k, "saldo": v} for k, v in malos.head(25).items()],
                  "Cruzar cada saldo con su factura o pago y depurar.")
    # saldos viejos de anticipos a proveedores por tercero
    ant = ter[ter["cuenta"].str.startswith("1330")].groupby("tercero")["saldo"].sum()
    ant = ant[ant > 1e6].sort_values(ascending=False)
    if len(ant):
        r.add("T", "T3", f"Anticipos a {len(ant)} terceros por {_p(float(ant.sum()))} pendientes de legalizar", "BAJO",
              "Saldos de anticipos por tercero al corte.", float(ant.sum()),
              [{"tercero": k, "saldo": v} for k, v in ant.head(20).items()])


# ───────────────────────── H. Estados financieros (lectura completa) ─────────────────────────

ERRORES_EXCEL = ("#REF!", "#DIV/0!", "#N/A", "#VALUE!", "#NAME?", "#NUM!", "#NULL!", "#¡REF!", "#¡VALOR!", "#N/D")


def _filas_codigos(filas: list[tuple]) -> list[dict]:
    """Filas de un estado financiero: códigos PUC a la izquierda del rótulo, rótulo y primer valor (periodo actual)."""
    out = []
    for f in filas:
        cel = list(f)
        idx_lab = next((i for i, x in enumerate(cel) if isinstance(x, str) and re.search(r"[A-Za-zÁÉÍÓÚáéíóú]{3}", x)), None)
        if idx_lab is None:
            continue
        cods = []
        for x in cel[:idx_lab]:
            t = str(int(x)) if isinstance(x, (int, float)) and float(x).is_integer() else str(x or "").strip()
            if re.fullmatch(r"\d{1,8}", t):
                cods.append(t)
        nums = [x for x in cel[idx_lab + 1:] if isinstance(x, (int, float)) and not isinstance(x, bool)]
        out.append({"codigos": cods, "rotulo": str(cel[idx_lab]).strip(), "valores": nums,
                    "errores": [str(x) for x in cel if isinstance(x, str) and x.strip().upper() in ERRORES_EXCEL]})
    return out


def _cruce_por_codigos(filas: list[dict], pr: dict) -> list[dict]:
    """Agrupa las filas que comparten códigos y compara el valor con el balance de prueba (descontando las
    subcuentas que el estado muestra en otra fila)."""
    filas = [f for f in filas if f["codigos"] and f["valores"]]
    padre = list(range(len(filas)))

    def raiz(i):
        while padre[i] != i:
            i = padre[i]
        return i
    dueno: dict[str, int] = {}
    for i, f in enumerate(filas):
        for c in f["codigos"]:
            if c in dueno:
                padre[raiz(i)] = raiz(dueno[c])
            else:
                dueno[c] = i
    grupos: dict[int, list[int]] = defaultdict(list)
    for i in range(len(filas)):
        grupos[raiz(i)].append(i)
    todos = set(dueno)
    out = []
    for idx in grupos.values():
        cods = sorted({c for i in idx for c in filas[i]["codigos"]})
        if not all(c in pr for c in cods):
            continue
        cods = [c for c in cods if not any(o != c and c.startswith(o) for o in cods)]  # sin repetir hijas
        esperado = sum(_s(pr, c) for c in cods)
        hijas_fuera = [o for o in todos - set(cods) if any(o != c and o.startswith(c) for c in cods) and o in pr]
        esperado -= sum(_s(pr, o) for o in hijas_fuera)
        valor = sum(filas[i]["valores"][0] for i in idx)
        out.append({"rubro": " + ".join(filas[i]["rotulo"][:45] for i in idx), "cuentas": ", ".join(cods)
                    + (f" (menos {', '.join(sorted(hijas_fuera))})" if hijas_fuera else ""),
                    "estados_financieros": valor, "balance_de_prueba": esperado, "diferencia": valor - esperado})
    return out


def _explicar(lineas: list[dict], filas: list[dict], pr: dict) -> None:
    """Intenta explicar cada diferencia con 1 a 3 cuentas mencionadas en el estado (agrupaciones del contador)."""
    from itertools import combinations
    cands = sorted({c for f in filas for c in f["codigos"] if len(c) >= 4 and c in pr and abs(_s(pr, c)) > 0})
    for x in lineas:
        d = x["diferencia"]
        if abs(d) <= 1000:
            continue
        for n in (1, 2, 3):
            hallado = next((combo for combo in combinations(cands, n)
                            if abs(sum(_s(pr, c) for c in combo) - abs(d)) <= 1), None)
            if hallado:
                signo = "incluye además" if d > 0 else "no incluye"
                x["explicacion"] = f"{signo} " + ", ".join(f"{c} {_nombre(pr, c).title()} ({_p(_s(pr, c))})" for c in hallado)
                break


def _total(filas: list[dict], *patrones: str) -> float | None:
    from modulos.revision_lectores import norm
    for f in filas:
        if f["valores"] and any(re.search(p, norm(f["rotulo"])) for p in patrones):
            return float(f["valores"][0])
    return None


def revisar_eeff_libro(r: Revision, libro, pr: dict, corte: date | None) -> None:
    from modulos.revision_lectores import norm

    def hoja(*pats):
        for h in libro.hojas:
            if any(re.search(p, norm(h)) for p in pats):
                return h, _filas_codigos(libro.hoja(h) or [])
        return None, []

    h_esf, esf = hoja(r"balance cte|situacion financiera|^esf$|balance general")
    h_er, er = hoja(r"^estado resultado|resultado integral|^e-?r$|estado de resultados")
    h_cp, cp = hoja(r"cambios")
    h_fl, fl = hoja(r"flujo")
    if not esf and not er:
        r.add("H", "H0", "No se encontraron el estado de situación financiera ni el de resultados", "MEDIO",
              f"Hojas del archivo: {', '.join(libro.hojas[:12])}.")
        return

    # H1 · cruce línea a línea con el balance de prueba
    lineas = _cruce_por_codigos(esf, pr) + _cruce_por_codigos(er, pr)
    _explicar(lineas, esf + er, pr)
    malas = [x for x in lineas if abs(x["diferencia"]) > 1000 and not x.get("explicacion")]
    reclas = [x for x in lineas if x.get("explicacion")]
    if reclas:
        r.add("H", "H1b", f"{len(reclas)} rubros agrupan cuentas distintas a las que indica el estado", "BAJO",
              "La diferencia se explica exactamente con otras cuentas del balance: es una agrupación del contador, no un "
              "error de cifras. Conviene dejarla documentada en la nota del rubro.", None,
              [{"rubro": x["rubro"], "diferencia": x["diferencia"], "explicacion": x["explicacion"]} for x in reclas])
    if malas:
        r.add("H", "H1", f"{len(malas)} rubros de los estados financieros no coinciden con el balance de prueba", "ALTO",
              "Cada rubro se recalculó sumando las cuentas PUC que el mismo estado indica al lado del rótulo.",
              float(sum(abs(x["diferencia"]) for x in malas)), malas,
              "Ajustar el rubro o la fórmula del estado financiero para que tome todas las cuentas del balance.")
    elif lineas:
        r.ok("H", "H1", "Cada rubro de los estados financieros = cuentas del balance de prueba",
             f"{len(lineas)} rubros verificados.")
        r.hallazgos[-1]["evidencia"] = lineas

    act = _total(esf, r"^activos? totales?$|^total (de )?activos?$")
    pas = _total(esf, r"^pasivos? totales?$|^total (de )?pasivos?$")
    pat = _total(esf, r"^patrimonio total$|^total (del )?patrimonio$")
    res_esf = _total(esf, r"^resultado del ejercicio|^(utilidad|perdida|ganancia).{0,20}ejercicio")
    res_er = _total(er, r"^ganancia \(perdida\) del periodo|^(utilidad|perdida|resultado).{0,15}(neta|del periodo|del ejercicio)")
    res_bal = _s(pr, "4") - _s(pr, "5") - _s(pr, "6") - _s(pr, "7")

    # H2 · totales y ecuación
    filas_tot = []
    for nombre, v, b in (("Activos totales", act, _s(pr, "1")), ("Pasivos totales", pas, _s(pr, "2")),
                         ("Patrimonio total", pat, _s(pr, "3") + res_bal), ("Resultado del periodo (ER)", res_er, res_bal)):
        if v is not None:
            filas_tot.append({"rubro": nombre, "estados_financieros": v, "balance_de_prueba": b, "diferencia": v - b})
    malas_t = [x for x in filas_tot if abs(x["diferencia"]) > 1000]
    if malas_t:
        r.add("H", "H2", "Los totales de los estados financieros no coinciden con el balance", "CRITICO",
              "Activo, pasivo, patrimonio y resultado deben ser idénticos a los del balance de prueba del mismo corte.",
              None, filas_tot)
    elif filas_tot:
        r.ok("H", "H2", "Totales de los estados financieros = balance de prueba")
        r.hallazgos[-1]["evidencia"] = filas_tot
    if act is not None and pas is not None and pat is not None and abs(act - pas - pat) > 1000:
        r.add("H", "H3", "El estado de situación financiera no cuadra", "CRITICO",
              f"Activos {_p(act)} ≠ pasivos {_p(pas)} + patrimonio {_p(pat)} (diferencia {_p(act - pas - pat)}).", act - pas - pat)
    elif act is not None and pas is not None and pat is not None:
        r.ok("H", "H3", "Estado de situación financiera cuadra", f"Activos {_p(act)} = pasivos + patrimonio.")
    if res_esf is not None and res_er is not None:
        if abs(res_esf - res_er) > 1000:
            r.add("H", "H4", "El resultado del estado de resultados no es el del estado de situación financiera", "CRITICO",
                  f"Estado de resultados {_p(res_er)} vs. resultado del ejercicio en el patrimonio {_p(res_esf)}.",
                  res_er - res_esf)
        else:
            r.ok("H", "H4", "Resultado del ejercicio igual en el estado de resultados y en el patrimonio", _p(res_er))

    # H5 · estado de cambios en el patrimonio
    if cp and pat is not None:
        finales = [f for f in cp if re.search(r"^saldo (a|al) ", norm(f["rotulo"])) and f["valores"]]
        if finales:
            fin = float(finales[-1]["valores"][-1])
            if abs(fin - pat) > 1000:
                r.add("H", "H5", "El estado de cambios en el patrimonio no termina en el patrimonio del balance", "CRITICO",
                      f"Saldo final del estado de cambios {_p(fin)} ≠ patrimonio total del estado de situación "
                      f"financiera {_p(pat)} (diferencia {_p(fin - pat)}). Suele pasar cuando se arrastra el estado de un "
                      "periodo anterior sin actualizar el saldo inicial.", fin - pat,
                      [{"rubro": f["rotulo"][:60], "valor": f["valores"][-1]} for f in cp if f["valores"]],
                      "Rehacer el estado de cambios partiendo del patrimonio al 31 de diciembre del año anterior.")
            else:
                r.ok("H", "H5", "Estado de cambios en el patrimonio = patrimonio del balance", _p(fin))

    # H6 · flujo de efectivo
    if fl:
        efe = _total(esf, r"^efectivo y equivalentes")
        cierre = [f for f in fl if re.search(r"efectivo y equivalentes al efectivo", norm(f["rotulo"])) and f["valores"]]
        if cierre and efe is not None:
            fin = float(cierre[-1]["valores"][-1])
            if abs(fin - efe) > 1000:
                r.add("H", "H6", "El flujo de efectivo no llega al efectivo del balance", "CRITICO",
                      f"Efectivo al final según el flujo {_p(fin)} ≠ efectivo en el estado de situación financiera "
                      f"{_p(efe)} (diferencia {_p(fin - efe)}).", fin - efe,
                      [{"rubro": f["rotulo"][:60], "valor": f["valores"][-1]} for f in cierre],
                      "Revisar las variaciones del flujo: deben salir del mismo balance comparativo.")
            else:
                r.ok("H", "H6", "El flujo de efectivo termina en el efectivo del balance", _p(efe))
        dep_fl = _total(fl, r"depreciacion")
        dep_bal = -(_s(pr, "1592") - _s(pr, "1592", "saldo_anterior")) if "1592" in pr else None
        mov_anual = sum(_causado(pr, c) for c in pr if c.startswith(("5160", "5260")) and len(c) == 4)
        if dep_fl and abs(dep_fl) > 1000 and (dep_bal or 0) == 0 and mov_anual == 0:
            r.add("H", "H7", f"El flujo suma una depreciación de {_p(dep_fl)} que no está en la contabilidad", "ALTO",
                  "La depreciación acumulada (1592) no cambió y no hay gasto de depreciación; el flujo de efectivo "
                  "incluye un ajuste que no existe en los libros.", dep_fl)

    # H8 · fechas de encabezado desactualizadas y errores de fórmula
    anio = (corte or date.today()).year
    viejos, errores = [], []
    for h in [x for x in (h_esf, h_er, h_cp, h_fl) if x]:
        for f in (libro.hoja(h) or [])[:12]:
            for x in f:
                if isinstance(x, str):
                    for a in re.findall(r"\b(20\d\d)\b", x):
                        if int(a) < anio - 1:
                            viejos.append({"hoja": h, "texto": x.strip()[:80]})
        for f in libro.hoja(h) or []:
            for x in f:
                if isinstance(x, str) and x.strip().upper() in ERRORES_EXCEL:
                    errores.append({"hoja": h, "error": x.strip(), "fila": next((str(y)[:50] for y in f if isinstance(y, str)
                                                                                  and y.strip().upper() not in ERRORES_EXCEL), "")})
    if viejos:
        r.add("H", "H8", f"Encabezados con fechas de años anteriores en {len({v['hoja'] for v in viejos})} estados", "MEDIO",
              f"Los estados son de {anio}, pero sus títulos dicen otras fechas: el lector puede creer que son de otro periodo.",
              None, viejos[:12], "Actualizar los títulos y fechas de cada estado.")
    if errores:
        r.add("H", "H9", f"{len(errores)} celdas con error de fórmula en los estados financieros", "MEDIO",
              "Una celda con #REF!, #DIV/0! u otro error indica una fórmula rota; la cifra que depende de ella no es confiable.",
              None, errores[:20], "Corregir las referencias de la fórmula.")

    # comparativo: pasivos negativos en el año anterior
    neg = [f for f in esf if f["codigos"] and f["codigos"][-1][:1] == "2" and len(f["valores"]) > 1 and f["valores"][1] < -1000]
    if neg:
        r.add("H", "H10", "Pasivos con valor negativo en la columna comparativa", "BAJO",
              "Un pasivo negativo en el año anterior indica una reclasificación pendiente en ese cierre.", None,
              [{"rubro": f["rotulo"][:60], "valor": f["valores"][1]} for f in neg])


def continuidad(r: Revision, pr_mes: dict, pr_siguiente: dict, etiqueta: str) -> None:
    """El saldo final de un mes debe ser el saldo inicial del mes siguiente."""
    difs = [{"cuenta": c, "nombre": _nombre(pr_mes, c), "saldo_final_mes": _s(pr_mes, c),
             "saldo_inicial_siguiente": _s(pr_siguiente, c, "saldo_anterior"),
             "diferencia": _s(pr_siguiente, c, "saldo_anterior") - _s(pr_mes, c)}
            for c in pr_mes if len(c) <= 4 and c in pr_siguiente
            and abs(_s(pr_siguiente, c, "saldo_anterior") - _s(pr_mes, c)) > 1]
    if difs:
        r.add("J", "J1", f"El saldo inicial de {etiqueta} no es el saldo final de este corte ({len(difs)} cuentas)", "ALTO",
              "Después de cerrar el mes se modificaron registros (o el archivo siguiente es de otra versión): los "
              "estados financieros entregados ya no coinciden con la contabilidad actual.", None, difs[:30],
              "Preguntar al contador qué ajustes hizo después del cierre y reexpedir los estados si cambian.")
    else:
        r.ok("J", "J1", f"El saldo inicial de {etiqueta} = saldo final de este corte")


# ───────────────────────── Orquestador ─────────────────────────

def revisar(prueba: dict, auxiliar: pd.DataFrame | None = None, corte: date | None = None,
            eeff_libro=None, conciliacion: dict | None = None, empresa: str = "", fuentes: list[str] | None = None,
            terceros: pd.DataFrame | None = None, siguiente: tuple[dict, str] | None = None) -> dict[str, Any]:
    r = Revision()
    mes = corte.month if corte else None
    if prueba:
        _integridad(r, prueba)
        _naturaleza(r, prueba)
        _transitorias(r, prueba)
        _impuestos(r, prueba, mes)
        _nomina(r, prueba, mes)
        _consolidados(r, prueba, mes)
        _activos(r, prueba)
    if terceros is not None and not terceros.empty and prueba:
        _terceros(r, prueba, terceros)
    if auxiliar is not None and not auxiliar.empty:
        _auxiliar(r, auxiliar, prueba or {})
    if eeff_libro is not None:
        revisar_eeff_libro(r, eeff_libro, prueba or {}, corte)
    if conciliacion:
        _conciliacion(r, prueba or {}, conciliacion, corte)
    if siguiente and prueba:
        continuidad(r, prueba, siguiente[0], siguiente[1])
    for h in r.hallazgos:
        h["tipo"] = "riesgo" if h["codigo"] in RIESGO else "registro"
    cuenta = Counter(h["nivel"] for h in r.hallazgos)
    registro = [h for h in r.hallazgos if h["tipo"] == "registro"]
    puntaje = round(100 * math.prod(1 - PESO[h["nivel"]] for h in registro))
    criticos = any(h["nivel"] == "CRITICO" for h in registro)
    veredicto = ("Confiable" if puntaje >= 85 and not criticos else
                 "Confiable con salvedades" if puntaje >= 65 and not criticos else "Requiere ajustes antes de usarse")
    riesgos = [h for h in r.hallazgos if h["tipo"] == "riesgo" and h["nivel"] != "OK"]
    orden = {n: i for i, n in enumerate(NIVELES)}
    r.hallazgos.sort(key=lambda h: (orden[h["nivel"]], h["area"], h["codigo"]))
    return {"empresa": empresa, "corte": corte, "fuentes": fuentes or [], "puntaje": puntaje, "veredicto": veredicto,
            "conteo": {n: cuenta.get(n, 0) for n in NIVELES}, "hallazgos": r.hallazgos,
            "riesgos_total": float(sum(h["valor"] or 0 for h in riesgos if h["codigo"] in ("D1", "D2", "E3"))),
            "reglas": len(r.hallazgos), "generado": date.today()}


# ───────────────────────── Lectura de archivos ─────────────────────────

def _mes_en(texto: str) -> int | None:
    from modulos.revision_lectores import norm
    t = norm(texto)
    for i, m in enumerate(MESES):
        if re.search(rf"\b{m}\b|\b{m[:3]}\b", t):
            return i + 1
    return None


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or "").strip().replace("$", "").replace(" ", "")
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-")
    s = s.strip("()-")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", s):
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s):
        s = s.replace(",", "")
    try:
        x = float(s)
    except ValueError:
        return None
    return -x if neg else x


def leer_conciliacion(libro) -> dict[str, Any]:
    from modulos.revision_lectores import norm
    out: dict[str, Any] = {"partidas": []}
    for hoja in libro.hojas:
        filas = libro.hoja(hoja) or []
        for f in filas:
            celdas = list(f)
            texto = " ".join(norm(x) for x in celdas if isinstance(x, str))
            nums = [_num(x) for x in celdas if not isinstance(x, str) and _num(x) is not None]
            if not nums:
                continue
            if "saldo_extracto" not in out and re.search(r"saldo (segun |en |del )?(el )?(extracto|banco)", texto):
                out["saldo_extracto"] = nums[-1]
            elif "saldo_libros" not in out and re.search(r"saldo (segun |en )?(los )?libros|saldo contable", texto):
                out["saldo_libros"] = nums[-1]
            else:
                fecha = next((x for x in celdas if hasattr(x, "year") and hasattr(x, "month")), None)
                if fecha is not None and texto:
                    v = nums[-1]
                    # cheques/notas débito restan; consignaciones/notas crédito suman al extracto
                    if re.search(r"cheque|nota debito|n\.?d\.?\b|gmf|4x1000|comision|cargo", texto):
                        v = -abs(v)
                    out["partidas"].append({"fecha": fecha.date() if hasattr(fecha, "date") else fecha,
                                            "concepto": texto[:80], "valor": v})
    return out


def _corte_de(libro, ruta) -> date | None:
    """Fecha de corte: «Balance de Prueba entre el 01/08/2026 y el 31/08/2026», o el mes del nombre del archivo."""
    import calendar
    for h in libro.hojas[:3]:
        for f in (libro.hoja(h) or [])[:6]:
            for x in f:
                if isinstance(x, str):
                    m = re.findall(r"(\d{1,2})/(\d{1,2})/(\d{4})", x)
                    if m:
                        d, mm, a = (int(v) for v in m[-1])
                        try:
                            return date(a, mm, d)
                        except ValueError:
                            pass
    m = _mes_en(ruta.stem)
    if m:
        hoy = date.today()
        anio = hoy.year if m <= hoy.month else hoy.year - 1
        return date(anio, m, calendar.monthrange(anio, m)[1])
    return None


def revisar_archivos(rutas: list, empresa: str = "EQUIPOS INDUSTRIALES FÉNIX S.A.S.", comparar_con_contador: bool = True
                     ) -> dict[str, Any]:
    """Detecta qué trae cada archivo (balance de prueba del mes, auxiliar, saldos por tercero, estados financieros,
    conciliación) y revisa todo junto."""
    from pathlib import Path

    from modulos.revision_lectores import Libro, norm
    prueba: dict = {}
    aux = ter = None
    eeff_libro = None
    conc: dict = {}
    corte = None
    fuentes = []
    abiertos = []
    for ruta in rutas:
        ruta = Path(ruta)
        nombre = norm(ruta.stem)
        libro = Libro(ruta)
        abiertos.append(libro)
        que = []
        if "concilia" in nombre:
            conc = leer_conciliacion(libro)
            que.append("conciliación bancaria")
        else:
            es_eeff = any(re.search(r"balance cte|situacion financiera|estado resultado|flujo", norm(h)) for h in libro.hojas)
            if es_eeff:
                eeff_libro = libro
                que.append("estados financieros")
            # balance del mes: hoja «B.Prueba <Mes>» o «Prueba»; si el archivo de balance trae varias, la del mes
            pr = {}
            for h in libro.hojas:
                nh = norm(h)
                if re.search(r"prueba", nh) and not re.search(r"\d{4}|ene|2025|acum", nh.replace("prueba", "")):
                    filas_h = libro.hoja(h)
                    if filas_h:
                        libro._cache["__prueba__"] = filas_h
                        pr = _prueba_de_filas(libro, h)
                        break
            pr = pr or libro.prueba()
            if pr and (not prueba or not es_eeff):  # el balance suelto manda sobre la copia dentro de los EEFF
                prueba = pr
                que.append("balance de prueba")
                corte = _corte_de(libro, ruta) or corte
            a = leer_auxiliar_wo(libro)
            if a is None and libro.hoja("Auxiliar"):
                a = pd.DataFrame(libro.auxiliar(("",)))
            if a is not None and not a.empty:
                aux = a
                que.append("auxiliar")
            t = leer_terceros_wo(libro)
            if t is not None and not t.empty:
                ter = t
                que.append("saldos por tercero")
        corte = corte or _corte_de(libro, ruta)
        fuentes.append(f"{ruta.name} ({', '.join(que) or 'sin datos reconocidos'})")
    if aux is not None and corte is not None:
        aux = aux[pd.to_datetime(aux["fecha"], errors="coerce") <= pd.Timestamp(corte)]
    # continuidad: si el libro del contador cargado en Shaki es del mes siguiente, su saldo inicial debe ser este cierre
    siguiente = None
    if comparar_con_contador and prueba and corte:
        try:
            from modulos import analitica_gastos as ag
            d = ag.cargar()
            if d and d.get("prueba") and d["mov"]["fecha"].max().month == (corte.month % 12) + 1:
                siguiente = (d["prueba"], f"{MESES[corte.month % 12]} (libro del contador cargado en Shaki)")
        except Exception:  # noqa: BLE001
            pass
    try:
        return revisar(prueba, aux, corte, eeff_libro, conc or None, empresa, fuentes, ter, siguiente)
    finally:
        for lb in abiertos:
            lb.cerrar()


def _prueba_de_filas(libro, hoja: str) -> dict:
    """Usa el lector de balance de prueba sobre una hoja concreta."""
    original = libro.hoja

    def solo(*nombres):
        return original(hoja) if any(norm_ in ("prueba",) for norm_ in nombres) else original(*nombres)
    libro.hoja = solo  # type: ignore[method-assign]
    try:
        return libro.prueba()
    finally:
        libro.hoja = original  # type: ignore[method-assign]
