"""
Motor de revisión de la declaración de RETENCIÓN EN LA FUENTE (formulario 350) — EIF SAS.

Cruza el borrador (PDF) contra la liquidación del contador (Excel) y la contabilidad que viene
dentro del mismo libro (Prueba, Auxiliar, RetenciónHT, AutorrentaHT, Formato 383…):

 1. Borrador vs. liquidación, renglón por renglón.
 2. Aritmética del formulario (130, 134, 136, 138) y redondeo a miles (art. 577 ET).
 3. Cuadre contable: cuentas 2365 / 2367 del mes vs. renglones del 350.
 4. Autorretención especial (Decreto 0572 de 2025): base = ingresos del mes, tarifa por CIIU.
 5. Art. 383 ET: recálculo de cada trabajador (depuración, topes 25 % / 40 % / 1.340 UVT).
 6. Retenciones línea por línea: tarifa vs. cuenta, PJ en cuentas de "no declarante",
    bases mínimas (10 UVT compras / 2 UVT servicios).
 7. ReteIVA: proveedores a los que se retuvo (art. 437-2 num. 9 → solo régimen SIMPLE).
 8. Pagos: cuenta 23658001 — cada periodo se cruza con su pago; mora y art. 580-1 ET
    (declaración sin pago total dentro de 2 meses = sin efecto).
 9. ReteICA por pagar (23680199) y vencimientos SHD.
10. Pago total (980) y sanciones (137) según la fecha de hoy.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from dateutil.relativedelta import relativedelta

from modulos import calendario_tributario_2026 as cal
from modulos.revision_lectores import Libro, norm

UVT = {2025: 49799, 2026: 52374}
TARIFA_AUTORRET = {"4659": 0.012}          # Decreto 0572/2025, desde 1-jun-2025
MESES_ABR = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]

# Renglones que suman al 130 (retenciones renta + autorretenciones)
R_130 = list(range(42, 59)) + list(range(68, 77)) + list(range(93, 113)) + list(range(121, 129))
CONCEPTOS = {
    "Rentas de trabajo (art. 383)": ("236505", [93]),
    "Honorarios": ("236515", [42, 95]),
    "Comisiones": ("236520", [43, 96]),
    "Servicios": ("236525", [44, 97]),
    "Arrendamientos": ("236530", [46, 99]),
    "Compras": ("236540", [49, 102]),
    "Autorretenciones": ("236575", [68, 69, 70, 71, 72, 73, 74, 75, 76, 121, 122, 123, 124, 125, 126, 127, 128]),
}


def pesos(v: float | int | None) -> str:
    if v is None:
        return "—"
    s = f"{abs(v):,.0f}".replace(",", ".")
    return f"-${s}" if v < 0 else f"${s}"


def _h(nivel: str, area: str, titulo: str, detalle: str = "", accion: str = "", valor: float | None = None,
       norma: str = "") -> dict[str, Any]:
    return {"nivel": nivel, "area": area, "titulo": titulo, "detalle": detalle, "accion": accion,
            "valor": valor, "norma": norma}


def _vencimiento_ret(anio: int, mes: int) -> date | None:
    clave = f"DIAN-RET-{anio}-{mes:02d}"
    for o in cal.obligaciones():
        if o["clave"] == clave:
            return date.fromisoformat(o["fecha"])
    return None


def _vencimiento_reteica(anio: int, bimestre: int) -> date | None:
    clave = f"SHD-RETEICA-{anio}-{bimestre}"
    for o in cal.obligaciones():
        if o["clave"] == clave:
            return date.fromisoformat(o["fecha"])
    return None


# ───────────────────────── 1-2. Formulario ─────────────────────────

def comparar_borrador(pdf: dict[int, float], xl: dict[int, float]) -> tuple[list[dict], list[dict]]:
    filas, hall = [], []
    claves = sorted(k for k in set(pdf) | set(xl) if k >= 26 and (pdf.get(k) or xl.get(k)))
    for k in claves:
        a, b = pdf.get(k, 0.0), xl.get(k, 0.0)
        ok = abs(a - b) < 1
        filas.append({"renglon": k, "borrador": a, "liquidacion": b, "diferencia": a - b, "ok": ok})
        if not ok:
            hall.append(_h("CRITICO", "Formulario", f"Renglón {k}: el borrador no coincide con la liquidación",
                           f"Borrador {pesos(a)} vs. liquidación {pesos(b)} (diferencia {pesos(a - b)}).",
                           "Corregir el borrador antes de firmar y presentar."))
    return filas, hall


def aritmetica(c: dict[int, float]) -> tuple[list[dict], list[dict]]:
    g = lambda k: c.get(k, 0.0)  # noqa: E731
    reglas = [
        (130, sum(g(k) for k in R_130) - g(129), "Suma de retenciones renta y autorretenciones (42…128) − 129"),
        (134, g(131) + g(132) - g(133), "131 + 132 − 133"),
        (136, g(130) + g(134) + g(135), "130 + 134 + 135"),
        (138, g(136) + g(137), "136 + 137"),
    ]
    ok, hall = [], []
    for r, esperado, formula in reglas:
        if abs(g(r) - esperado) < 1:
            ok.append({"titulo": f"Renglón {r} = {formula}", "detalle": pesos(esperado)})
        else:
            hall.append(_h("CRITICO", "Formulario", f"Renglón {r} mal sumado",
                           f"Declarado {pesos(g(r))}; según {formula} debe ser {pesos(esperado)}.",
                           f"Corregir renglón {r}."))
    no_mil = [k for k, v in c.items() if k >= 26 and k not in (27, 28) and v and abs(v) >= 1 and v % 1000]
    if no_mil:
        hall.append(_h("MEDIO", "Formulario", "Valores sin redondear a miles",
                       "Renglones: " + ", ".join(map(str, sorted(no_mil))),
                       "Redondear al múltiplo de mil más cercano.", norma="Art. 577 ET"))
    else:
        ok.append({"titulo": "Todos los valores redondeados a miles", "detalle": "Art. 577 ET"})
    return ok, hall


# ───────────────────────── 3. Contabilidad ─────────────────────────

def _neto_mes(pr: dict, cuenta: str) -> float:
    d = pr.get(cuenta)
    return (d["creditos"] - d["debitos"]) if d else 0.0


def cuadre_contable(pr: dict, c: dict[int, float]) -> tuple[list[dict], list[dict], list[dict]]:
    filas, ok, hall = [], [], []
    total = 0.0
    for nombre, (cta, renglones) in CONCEPTOS.items():
        neto = _neto_mes(pr, cta)
        decl = sum(c.get(r, 0.0) for r in renglones)
        total += neto
        if not neto and not decl:
            continue
        cuadra = abs(neto - decl) <= 1000
        filas.append({"concepto": nombre, "cuenta": cta, "contabilidad": neto, "declarado": decl,
                      "diferencia": decl - neto, "ok": cuadra})
        if not cuadra:
            hall.append(_h("ALTO", "Cuadre contable", f"{nombre}: lo declarado no cuadra con la cuenta {cta}",
                           f"Contabilidad {pesos(neto)} vs. declarado {pesos(decl)} (diferencia {pesos(decl - neto)}).",
                           "Revisar causaciones del mes o el renglón del formulario."))
    iva = _neto_mes(pr, "2367")
    if iva or c.get(134):
        filas.append({"concepto": "ReteIVA", "cuenta": "2367", "contabilidad": iva, "declarado": c.get(134, 0.0),
                      "diferencia": c.get(134, 0.0) - iva, "ok": abs(iva - c.get(134, 0.0)) <= 1000})
        if abs(iva - c.get(134, 0.0)) > 1000:
            hall.append(_h("ALTO", "Cuadre contable", "ReteIVA declarado no cuadra con la cuenta 2367",
                           f"Contabilidad {pesos(iva)} vs. renglón 134 {pesos(c.get(134))}."))
    if filas and not hall:
        ok.append({"titulo": "Cuentas 2365 y 2367 del mes cuadran con el formulario",
                   "detalle": f"Retención renta contable {pesos(total)} vs. renglón 130 {pesos(c.get(130))}"})
    return filas, ok, hall


def autorretencion(libro: Libro, pr: dict, c: dict[int, float], mes: int) -> tuple[dict, list, list]:
    ok, hall = [], []
    datos = libro.datos()
    ciiu = str(datos.get("actividad") or "").strip()
    tarifa = TARIFA_AUTORRET.get(ciiu)
    ingresos = _neto_mes(pr, "41") + _neto_mes(pr, "42")
    base, valor = c.get(59, 0.0), c.get(68, 0.0)
    info = {"ciiu": ciiu, "tarifa": tarifa, "ingresos_mes": ingresos, "base_59": base, "renglon_68": valor}
    if not base and not valor:
        return info, ok, hall
    if ingresos and abs(ingresos - base) > max(1000, base * 0.001):
        hall.append(_h("ALTO", "Autorretención", "Base de autorretención (59) distinta a los ingresos del mes",
                       f"Ingresos 41+42 del mes {pesos(ingresos)} vs. renglón 59 {pesos(base)}.",
                       "Verificar ingresos no sometidos o faltantes.", norma="DUR 1625/2016 arts. 1.2.6.6 y ss."))
    elif ingresos:
        ok.append({"titulo": "Base de autorretención = ingresos del mes (cuentas 41 + 42)",
                   "detalle": f"{pesos(ingresos)} ≈ renglón 59 {pesos(base)}"})
    if tarifa:
        esperado = base * tarifa
        if abs(esperado - valor) > 1000:
            hall.append(_h("ALTO", "Autorretención", "Autorretención no corresponde a la tarifa",
                           f"{pesos(base)} × {tarifa * 100:.2f}% = {pesos(esperado)} vs. renglón 68 {pesos(valor)}.",
                           norma="Decreto 0572 de 2025"))
        else:
            ok.append({"titulo": f"Autorretención especial al {tarifa * 100:.2f}% (CIIU {ciiu})",
                       "detalle": f"{pesos(base)} × {tarifa * 100:.2f}% = {pesos(esperado)} ✓ · Decreto 0572 de 2025"})
    for f in libro.tabla("AutorrentaHT", ("MES", "SALDO")):
        if norm(f.get("mes"))[:3] == MESES_ABR[mes - 1]:
            info["contable"] = -float(f.get("saldo") or 0)
    return info, ok, hall


# ───────────────────────── 5. Art. 383 ─────────────────────────

def _tabla_383(uvt_base: float) -> float:
    tramos = [(2300, 0.39, 770), (945, 0.37, 268), (640, 0.35, 162), (360, 0.33, 69), (150, 0.28, 10), (95, 0.19, 0)]
    for desde, t, mas in tramos:
        if uvt_base > desde:
            return (uvt_base - desde) * t + mas
    return 0.0


def _valor_rotulo(filas: list[tuple], *rotulos: str) -> float | None:
    rot = [norm(r) for r in rotulos]
    for f in filas:
        for j, x in enumerate(f):
            if isinstance(x, str) and any(norm(x).startswith(r) for r in rot):
                nums = [v for v in f[j + 1:] if isinstance(v, (int, float)) and not isinstance(v, bool)]
                if nums:
                    return float(nums[0])
    return None


def art_383(libro: Libro, anio: int, c: dict[int, float]) -> tuple[list[dict], list, list]:
    filas, ok, hall = [], [], []
    uvt = UVT.get(anio, UVT[2026])
    for hoja, datos in libro.hojas_que_empiezan("Formato").items():
        nombre = re.sub(r"^formato\s*\d{4}\s*", "", hoja, flags=re.I).strip() or hoja
        ingreso = _valor_rotulo(datos, "Totalidad de ingresos", "Ingresos laborales")
        base = _valor_rotulo(datos, "Ingreso Laboral Mensual Base")
        declarado = _valor_rotulo(datos, "RETENCION EN LA FUENTE POR ART 383")
        pension = _valor_rotulo(datos, "1. Aportes obligatorios a Pens")
        depend = _valor_rotulo(datos, "2. Deducción por dependientes")
        exenta25 = _valor_rotulo(datos, "Renta de Trabajo Exenta (25%)")
        ded_total = _valor_rotulo(datos, "Total deducciones y renta exentas")
        if base is None or declarado is None:
            continue
        uvts = base / uvt
        calculado = _tabla_383(uvts) * uvt
        redondeado = round(calculado / 1000) * 1000
        cuadra = abs(redondeado - declarado) <= 1000
        filas.append({"trabajador": nombre, "ingreso": ingreso, "base": base, "uvt": uvts,
                      "calculado": calculado, "declarado": declarado, "ok": cuadra})
        if not cuadra:
            hall.append(_h("ALTO", "Art. 383", f"{nombre}: retención mal calculada",
                           f"Base {pesos(base)} = {uvts:.2f} UVT → {pesos(redondeado)}; se retuvo {pesos(declarado)}.",
                           "Recalcular y ajustar en la próxima nómina.", norma="Art. 383 ET"))
        if ingreso and depend and depend > min(ingreso * 0.10, 32 * uvt) + 1:
            hall.append(_h("MEDIO", "Art. 383", f"{nombre}: deducción por dependientes supera el tope",
                           f"{pesos(depend)} > mínimo entre 10% del ingreso y 32 UVT.", norma="Art. 387 ET"))
        elif depend:
            hall.append(_h("INFO", "Art. 383", f"{nombre}: aplica deducción por dependientes ({pesos(depend)})",
                           "Debe existir certificado firmado del trabajador con los dependientes.",
                           "Archivar el certificado en la hoja de vida.", norma="DUR 1625 art. 1.2.4.1.18"))
        if exenta25 and exenta25 > 790 / 12 * uvt + 1:
            hall.append(_h("MEDIO", "Art. 383", f"{nombre}: renta exenta 25% supera 790 UVT/año",
                           f"{pesos(exenta25)} en el mes.", norma="Art. 206 num. 10 ET"))
        if ingreso and ded_total and ded_total > min(ingreso * 0.40, 1340 / 12 * uvt) + 1:
            hall.append(_h("MEDIO", "Art. 383", f"{nombre}: deducciones + exentas superan el límite 40% / 1.340 UVT",
                           f"{pesos(ded_total)}.", norma="Art. 336 ET"))
        if ingreso and pension and pension < ingreso * 0.039:
            hall.append(_h("INFO", "Art. 383", f"{nombre}: aportes a pensión bajos frente al ingreso",
                           f"Pensión {pesos(pension)} sobre ingreso {pesos(ingreso)} ({pension / ingreso * 100:.1f}%). "
                           "Si es independiente, solo se resta lo realmente pagado en PILA y el IBC mínimo es el 40% del ingreso.",
                           "Pedir la planilla PILA del mes como soporte.", norma="Seguridad social de independientes (IBC 40%)"))
    if filas:
        bases = sum(f["base"] for f in filas)
        rets = sum(f["declarado"] for f in filas)
        if all(f["ok"] for f in filas):
            ok.append({"titulo": f"Art. 383 recalculado para {len(filas)} personas — todo correcto",
                       "detalle": f"Retención total {pesos(rets)} · UVT {anio} {pesos(uvt)}"})
        if abs(bases - c.get(77, 0)) <= 1000 and abs(rets - c.get(93, 0)) <= 1000:
            ok.append({"titulo": "Renglones 77 y 93 = suma de las depuraciones 383",
                       "detalle": f"Base {pesos(bases)} · retención {pesos(rets)}"})
        elif c.get(93):
            hall.append(_h("MEDIO", "Art. 383", "Renglones 77/93 no coinciden con las hojas de depuración",
                           f"Hojas: base {pesos(bases)}, retención {pesos(rets)} · Formulario: 77 {pesos(c.get(77))}, "
                           f"93 {pesos(c.get(93))}.", "Puede haber pagos 383 a independientes sin hoja de depuración."))
    return filas, ok, hall


# ───────────────────────── 6-7. Línea por línea ─────────────────────────

def _pct_desc(desc: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", desc or "")
    return float(m.group(1).replace(",", ".")) / 100 if m else None


def lineas_retencion(libro: Libro, anio: int, mes: int) -> tuple[list[dict], list, list]:
    uvt = UVT.get(anio, UVT[2026])
    obs, ok, hall = [], [], []
    filas = [f for f in libro.tabla("RetenciónHT", ("MES", "TP", "CUENTA", "SALDO"))
             if norm(f.get("mes"))[:3] == MESES_ABR[mes - 1]]
    n = 0
    for f in filas:
        cuenta = str(f.get("cuenta") or "")
        desc = str(f.get("descripcion") or "")
        base = f.get("inv-cruc-base") or f.get("base verifica") or 0
        ret = -(f.get("saldo") or 0)
        if (not isinstance(base, (int, float)) or not base or not ret
                or cuenta.startswith(("236505", "2367", "2368"))):   # 383 y ReteIVA/ReteICA van aparte
            continue
        n += 1
        tp = str(f.get("tp") or "").upper()
        tarifa_cta = _pct_desc(desc)
        tasa = ret / base
        nombre = str(f.get("nombre") or "").split(" Nit:")[0]
        nd = "no declarante" in norm(desc)
        if tp == "PJ" and nd:
            correcta = 0.04 if cuenta.startswith("236525") else 0.11 if cuenta.startswith("236515") else None
            dif = (tasa - correcta) * base if correcta else None
            hall.append(_h("ALTO", "Retenciones", f"{nombre}: persona jurídica con tarifa de NO declarante",
                           f"NIT {f.get('nit')} · base {pesos(base)} · retenido {pesos(ret)} ({tasa * 100:.1f}%). "
                           f"Las personas jurídicas son declarantes: tarifa {correcta * 100:.0f}%"
                           + (f" → {'exceso' if dif > 0 else 'faltante'} de {pesos(abs(dif))}." if dif else ".")
                           if correcta else "Las personas jurídicas siempre son declarantes.",
                           "Confirmar el RUT; si es PJ, reintegrar el exceso (o corregir la cuenta) y ajustarlo en el "
                           "renglón 129 del periodo en que se reintegre.", valor=dif, norma="Art. 591 ET"))
            obs.append({**_lin(f, base, ret, tasa), "observacion": "PJ con tarifa de no declarante"})
        elif tarifa_cta and abs(tasa - tarifa_cta) * base > 1000:
            hall.append(_h("MEDIO", "Retenciones", f"{nombre}: tarifa aplicada distinta a la de la cuenta",
                           f"Cuenta {cuenta} ({tarifa_cta * 100:.2f}%) · aplicada {tasa * 100:.2f}% sobre {pesos(base)}."))
            obs.append({**_lin(f, base, ret, tasa), "observacion": "Tarifa distinta a la cuenta"})
        minimo = 10 * uvt if cuenta.startswith("236540") else (
            2 * uvt if cuenta.startswith("236525") and "sof" not in norm(desc) else 0)
        if minimo and base < minimo:
            hall.append(_h("MEDIO", "Retenciones", f"{nombre}: retención sobre una base menor a la mínima",
                           f"Base {pesos(base)} < {pesos(minimo)} ({'10' if minimo == 10 * uvt else '2'} UVT). "
                           "Solo procede si hay varios pagos al mismo tercero en el mes que juntos la superen.",
                           norma="Decreto 0572 de 2025"))
            obs.append({**_lin(f, base, ret, tasa), "observacion": "Base menor a la mínima"})
    if n:
        ok.append({"titulo": f"{n} retenciones del mes revisadas una por una",
                   "detalle": f"Tarifas vs. cuenta, tipo de tercero (PN/PJ) y bases mínimas con UVT {anio} {pesos(uvt)}"})
    return obs, ok, hall


def _lin(f: dict, base: float, ret: float, tasa: float) -> dict:
    return {"tercero": str(f.get("nombre") or "").split(" Nit:")[0], "nit": f.get("nit"), "tp": f.get("tp"),
            "cuenta": f.get("cuenta"), "base": base, "retencion": ret, "tasa": tasa,
            "detalle": str(f.get("detalle") or "")[:80]}


def reteiva(libro: Libro, mes: int, anio: int) -> tuple[list[dict], list, list]:
    movs = [m for m in libro.auxiliar(("2367",)) if m["fecha"] and m["fecha"].month == mes
            and m["fecha"].year == anio and m["valor"] < 0]
    por: dict[str, dict] = {}
    for m in movs:
        k = str(m["nit"])
        d = por.setdefault(k, {"nit": k, "tercero": str(m["nombre"] or "").split(" Nit:")[0], "valor": 0.0, "n": 0})
        d["valor"] += -m["valor"]
        d["n"] += 1
    filas = sorted(por.values(), key=lambda x: -x["valor"])
    hall = []
    if filas:
        hall.append(_h("MEDIO", "ReteIVA", f"ReteIVA practicado a {len(filas)} proveedor(es): confirmar régimen SIMPLE",
                       "Desde la Ley 2010 de 2019 solo se retiene IVA (15%) a responsables del régimen SIMPLE; "
                       "las cuentas aún dicen 'régimen simplificado'. Proveedores: "
                       + "; ".join(f"{d['tercero']} {pesos(d['valor'])}" for d in filas[:6]) + ".",
                       "Revisar el RUT de cada uno (responsabilidad 47 = SIMPLE). Si no es SIMPLE, no se debía retener.",
                       norma="Art. 437-2 num. 9 ET"))
    return filas, [], hall


# ───────────────────────── 8-9. Pagos ─────────────────────────

def _estado_pago(venc: date | None, pago: date | None, hoy: date) -> tuple[str, str]:
    if venc is None:
        return ("INFO", "Sin fecha de vencimiento en el calendario")
    limite = venc + relativedelta(months=2)
    if pago:
        dias = (pago - venc).days
        if dias <= 0:
            return ("OK", "Pagada a tiempo")
        if pago <= limite:
            return ("MEDIO", f"Pagada {dias} días tarde: intereses de mora")
        return ("CRITICO", f"Pagada {dias} días tarde (más de 2 meses)")
    if hoy <= venc:
        return ("INFO", "Aún no vence")
    if hoy <= limite:
        return ("CRITICO", f"SIN PAGO · vencida hace {(hoy - venc).days} días")
    return ("CRITICO", f"SIN PAGO · más de 2 meses vencida")


def pagos_retencion(libro: Libro, anio: int, mes: int, hoy: date) -> tuple[list[dict], list, list]:
    movs = sorted(libro.auxiliar(("23658001",)), key=lambda m: (m["fecha"] or date.min))
    cierres = [m for m in movs if m["valor"] < 0 and "cierre" in norm(m["detalle"])]
    pagos = [m for m in movs if m["valor"] > 0]
    usados: set[int] = set()
    filas, ok, hall = [], [], []
    # pagos de periodos del año anterior (detalle "AÑO 2025 PERIODO 12")
    for i, p in enumerate(pagos):
        m = re.search(r"a.o\s*(\d{4})\s*periodo\s*(\d{1,2})", norm(p["detalle"]))
        if m and int(m.group(1)) < anio:
            usados.add(i)
            a, per = int(m.group(1)), int(m.group(2))
            cota = (date(a, per, 1) + relativedelta(months=2)) - relativedelta(days=1)  # fin del mes siguiente
            tarde = p["fecha"] > cota + relativedelta(months=2)
            filas.append({"periodo": f"{MESES[per - 1].capitalize()} {a}", "valor": p["valor"], "vence": None,
                          "pagado": p["fecha"], "estado": "CRITICO" if tarde else "INFO",
                          "nota": "Pagada más de 2 meses después del vencimiento" if tarde else "Periodo del año anterior"})
    for c in cierres:
        per_mes = c["fecha"].month
        per_anio = c["fecha"].year
        valor = -c["valor"]
        venc = _vencimiento_ret(per_anio, per_mes)
        idx = next((i for i, p in enumerate(pagos) if i not in usados and abs(p["valor"] - valor) < 1
                    and p["fecha"] >= c["fecha"] - relativedelta(days=5)), None)
        pago = None
        nota_extra = ""
        if idx is not None:
            usados.add(idx)
            pago = pagos[idx]["fecha"]
            if "iva" in norm(pagos[idx]["detalle"]) and "retencion" not in norm(pagos[idx]["detalle"]):
                nota_extra = f" · el comprobante dice “{pagos[idx]['detalle']}”"
        nivel, nota = _estado_pago(venc, pago, hoy)
        filas.append({"periodo": f"{MESES[per_mes - 1].capitalize()} {per_anio}", "valor": valor, "vence": venc,
                      "pagado": pago, "estado": nivel, "nota": nota + nota_extra})
    # movimientos que no son cierre ni pago de una declaración
    for i, p in enumerate(pagos):
        if i not in usados:
            filas.append({"periodo": "¿?", "valor": p["valor"], "vence": None, "pagado": p["fecha"], "estado": "MEDIO",
                          "nota": f"Pago sin periodo identificado: {p['detalle']}"})
    raros = [m for m in movs if m["valor"] < 0 and "cierre" not in norm(m["detalle"])]
    for m in raros:
        hall.append(_h("MEDIO", "Pagos", "Movimiento ajeno en la cuenta Retefuente por pagar (23658001)",
                       f"{m['fecha']} · {m['comprobante']} · {m['detalle']} · {pesos(-m['valor'])}.",
                       "Reclasificar: esta cuenta solo debe recibir los cierres mensuales y los pagos a la DIAN."))
    # hallazgos por periodo
    sin_pago = [f for f in filas if f["pagado"] is None and f["estado"] == "CRITICO"]
    tarde = [f for f in filas if f["pagado"] is not None and f["estado"] == "CRITICO"]
    mora = [f for f in filas if f["pagado"] is not None and f["estado"] == "MEDIO" and f["vence"]]
    for f in sin_pago:
        limite = f["vence"] + relativedelta(months=2)
        dentro = hoy <= limite
        hall.append(_h("CRITICO", "Pagos", f"Retención de {f['periodo']} SIN PAGAR: {pesos(f['valor'])}",
                       f"Venció el {f['vence']:%d/%m/%Y}. "
                       + (f"Si la declaración se presentó sin pago, queda sin efecto si no se paga completa a más "
                          f"tardar el {limite:%d/%m/%Y}." if dentro else
                          "Pasaron más de 2 meses: si se presentó sin pago, la declaración no produce efecto legal."),
                       ("PAGAR YA con intereses de mora" + (f" (antes del {limite:%d/%m/%Y})" if dentro else
                        "; presentar de nuevo con sanción de extemporaneidad")
                        + ". Las retenciones son dinero de terceros: no consignarlas puede tener consecuencias penales."),
                       valor=f["valor"], norma="Art. 580-1 ET · art. 634 ET · art. 402 Código Penal"))
    if tarde:
        hall.append(_h("CRITICO", "Pagos", f"{len(tarde)} periodo(s) pagados más de 2 meses tarde",
                       "Periodos: " + ", ".join(f"{f['periodo']} (pagado {f['pagado']:%d/%m/%Y})" for f in tarde)
                       + ". Si esas declaraciones se presentaron sin pago, son ineficaces (no producen efecto) y "
                         "pueden ser emplazadas por no declarar.",
                       "Que el contador confirme con los recibos 490 la fecha real de pago; si es igual a la contable, "
                       "evaluar presentar de nuevo con sanción reducida (art. 640 ET) antes de que la DIAN lo detecte.",
                       norma="Art. 580-1 ET"))
    if mora:
        hall.append(_h("ALTO", "Pagos", f"{len(mora)} periodo(s) pagados tarde (menos de 2 meses)",
                       "Periodos: " + ", ".join(f"{f['periodo']} ({(f['pagado'] - f['vence']).days} días)" for f in mora)
                       + ". La declaración es válida, pero se causan intereses de mora.",
                       "Verificar que el recibo incluyó los intereses; si no, queda un saldo a cargo.",
                       norma="Art. 634 y 635 ET"))
    if filas and not (sin_pago or tarde or mora):
        ok.append({"titulo": "Todas las retenciones del año pagadas a tiempo", "detalle": "Cuenta 23658001"})
    return filas, ok, hall


def pagos_reteica(libro: Libro, anio: int, hoy: date, perfil_reteica: bool | None) -> tuple[list[dict], list, list]:
    movs = sorted(libro.auxiliar(("23680199",)), key=lambda m: (m["fecha"] or date.min))
    filas, ok, hall = [], [], []
    pagos = [m for m in movs if m["valor"] > 0]
    usados: set[int] = set()
    for c in [m for m in movs if m["valor"] < 0]:
        if c["fecha"].year != anio:
            continue
        bim = (c["fecha"].month + 1) // 2
        venc = _vencimiento_reteica(anio, bim)
        idx = next((i for i, p in enumerate(pagos) if i not in usados and abs(p["valor"] + c["valor"]) < 1
                    and p["fecha"] >= c["fecha"]), None)
        pago = pagos[idx]["fecha"] if idx is not None else None
        if idx is not None:
            usados.add(idx)
        nivel, nota = _estado_pago(venc, pago, hoy)
        if nivel == "CRITICO":
            nivel = "ALTO"
        filas.append({"periodo": f"Bimestre {bim} {anio}", "valor": -c["valor"], "vence": venc, "pagado": pago,
                      "estado": nivel, "nota": nota})
    pend = [f for f in filas if f["pagado"] is None and f["vence"] and f["vence"] < hoy]
    if pend:
        total = sum(f["valor"] for f in pend)
        hall.append(_h("ALTO", "ReteICA", f"ReteICA Bogotá sin pagar: {pesos(total)}",
                       "Bimestres: " + ", ".join(f"{f['periodo']} {pesos(f['valor'])} (venció {f['vence']:%d/%m/%Y})"
                                                for f in pend) + ". La empresa practica ReteICA cada mes (cuentas 2368).",
                       "Confirmar si se declararon; declarar y pagar con sanción de extemporaneidad e intereses.",
                       valor=total, norma="Plazos: Res. SDH-000195 de 2025"))
    if filas and perfil_reteica is False:
        hall.append(_h("ALTO", "ReteICA", "La obligación de ReteICA no está activa en el radar tributario",
                       "La contabilidad muestra retenciones de ICA (2368), así que EIF es agente retenedor de ICA en "
                       "Bogotá y debe declararlas cada bimestre.",
                       "Activar 'ReteICA Bogotá' en Impuestos → Radar → Obligaciones y alertas."))
    return filas, ok, hall


# ───────────────────────── 10. Periodo actual ─────────────────────────

def estado_periodo(pdf: dict[int, float], c: dict[int, float], anio: int, mes: int, hoy: date) -> tuple[dict, list, list]:
    ok, hall = [], []
    venc = _vencimiento_ret(anio, mes)
    total = c.get(138, 0.0)
    info = {"vence": venc, "total": total, "pago_980": pdf.get(980)}
    if total and not pdf.get(980):
        hall.append(_h("ALTO", "Presentación", "Campo 980 «Pago total» vacío en el borrador",
                       f"Debe quedar en {pesos(total)}. Una declaración de retención presentada sin pago total no "
                       "produce efecto legal.",
                       f"Presentar con pago de {pesos(total)} a más tardar el {venc:%d/%m/%Y}." if venc else "",
                       valor=total, norma="Art. 580-1 ET"))
    elif total and abs(pdf.get(980, 0) - total) >= 1:
        hall.append(_h("CRITICO", "Presentación", "Pago total (980) distinto al total a pagar (138)",
                       f"980 = {pesos(pdf.get(980))} vs. 138 = {pesos(total)}."))
    if venc:
        if hoy > venc and not c.get(137):
            uvt = UVT.get(hoy.year, UVT[2026])
            hall.append(_h("ALTO", "Presentación", "Ya venció y no se liquidó sanción (137)",
                           f"Venció el {venc:%d/%m/%Y}. La sanción por extemporaneidad es 5% por mes sobre la "
                           f"retención (mínimo 10 UVT = {pesos(10 * uvt)}), más intereses de mora.",
                           "Liquidar sanción en el 137 (reducible art. 640).", norma="Art. 641 ET"))
        elif hoy <= venc:
            ok.append({"titulo": f"En plazo: vence el {venc:%d/%m/%Y} ({(venc - hoy).days} días)",
                       "detalle": "Sin sanción si se presenta y paga a tiempo"})
    return info, ok, hall


# ───────────────────────── Orquestador ─────────────────────────

def revisar(pdf_campos: dict[int, float] | None, ruta_excel: str | None, anio: int, mes: int,
            hoy: date | None = None, perfil_reteica: bool | None = None) -> dict[str, Any]:
    hoy = hoy or date.today()
    pdf_campos = pdf_campos or {}
    res: dict[str, Any] = {"hallazgos": [], "verificaciones": [], "tablas": {}, "datos": {}}

    def add(o, h):
        res["verificaciones"] += o
        res["hallazgos"] += h

    libro = None
    xl_campos: dict[int, float] = {}
    if ruta_excel:
        from modulos.revision_lectores import leer_excel_formulario
        xl = leer_excel_formulario(ruta_excel, "350")
        xl_campos = xl["campos"]
        res["datos"]["hoja_formulario"] = xl["hoja"]
        try:
            libro = Libro(ruta_excel)
        except Exception as e:  # .xls u otro formato: solo comparación de renglones
            res["hallazgos"].append(_h("INFO", "Insumos", "No se pudo abrir el libro completo", str(e)))
    c = {**xl_campos, **{k: v for k, v in pdf_campos.items() if k >= 26}} if pdf_campos else xl_campos
    res["datos"]["campos"] = c

    if pdf_campos and xl_campos:
        filas, h = comparar_borrador(pdf_campos, xl_campos)
        res["tablas"]["borrador_vs_liquidacion"] = filas
        add([{"titulo": f"Borrador = liquidación en los {len(filas)} renglones con valor",
              "detalle": "PDF del borrador vs. hoja del formulario en el Excel"}] if not h else [], h)
    elif not pdf_campos:
        res["hallazgos"].append(_h("INFO", "Insumos", "No se subió el borrador en PDF",
                                   "Se revisó solo la liquidación en Excel."))
    if c:
        add(*aritmetica(c))
        info, o, h = estado_periodo(pdf_campos, c, anio, mes, hoy)
        res["datos"]["periodo"] = info
        add(o, h)

    if libro:
        try:
            pr = libro.prueba()
            if pr:
                filas, o, h = cuadre_contable(pr, c)
                res["tablas"]["cuadre_contable"] = filas
                add(o, h)
                info, o, h = autorretencion(libro, pr, c, mes)
                res["datos"]["autorretencion"] = info
                add(o, h)
            filas, o, h = art_383(libro, anio, c)
            res["tablas"]["art_383"] = filas
            add(o, h)
            filas, o, h = lineas_retencion(libro, anio, mes)
            res["tablas"]["lineas_observadas"] = filas
            add(o, h)
            filas, o, h = reteiva(libro, mes, anio)
            res["tablas"]["reteiva"] = filas
            add(o, h)
            filas, o, h = pagos_retencion(libro, anio, mes, hoy)
            res["tablas"]["pagos_retencion"] = filas
            add(o, h)
            filas, o, h = pagos_reteica(libro, anio, hoy, perfil_reteica)
            res["tablas"]["pagos_reteica"] = filas
            add(o, h)
            if pr:
                res["datos"]["reteica_mes"] = sum(d["creditos"] for k, d in pr.items()
                                                  if k.startswith("236801") and len(k) == 8 and k != "23680199")
        finally:
            libro.cerrar()
    return res
