"""
Conocimiento de Shaki sobre PERSONAS y TERCEROS — para responder preguntas concretas como
«¿cuántos años lleva Andrés Valencia con nosotros?» o «¿cuánto le debemos a Codifer?».

- Reconoce nombres aunque estén incompletos o mal escritos (rapidfuzz; si no está, difflib).
- Personas: empleados_fenix + otras tablas de personal (ingreso, antigüedad, edad, cargo, área,
  vacaciones, contrato, cumpleaños).
- Terceros: auxiliar del contador (proveedores 2205, costos y gastos por pagar 2335, clientes 1305,
  anticipos 1330) + control de pagos + cartera. La deuda se estima cruzando cada factura con su pago
  por número de factura; se aclara siempre que es con base en los movimientos del año en el auxiliar.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from modulos.analitica_personal import _n, _ok, parecido

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
PALABRAS_VACIAS = {"cuanto", "cuantos", "cuantas", "cual", "cuales", "que", "quien", "como", "cuando", "donde", "le",
                   "lo", "la", "el", "los", "las", "de", "del", "a", "al", "con", "en", "por", "para", "nos", "nosotros",
                   "hemos", "ha", "han", "tiene", "tenemos", "debemos", "debe", "pagado", "pagamos", "anos", "ano",
                   "lleva", "llevan", "empresa", "trabajando", "esta", "es", "y", "un", "una", "me", "dime", "sabes",
                   "saber", "favor", "hay", "edad", "cumple", "cumpleanos", "cargo", "area", "vacaciones", "dias",
                   "contrato", "vence", "facturas", "factura", "saldo", "deuda", "gastado", "gastamos", "compras",
                   "compramos", "vendido", "vendimos", "ventas", "cliente", "proveedor", "pendientes", "pendiente",
                   "debo", "plata", "dinero", "total", "mucho", "ingreso", "ingresar", "entro", "desde", "fecha", "hace",
                   "nuestra", "nuestro", "su", "sus", "ese", "esa", "este", "nomina", "salario", "gana", "sueldo",
                   "clientes", "proveedores", "mora", "cartera", "quien", "trabaja", "hemos", "cuesta", "hace", "pagos",
                   "semana", "mes", "hoy", "manana", "nos", "nostros", "alcanza", "alcanzar", "podemos", "nosotras", "facturo", "facturado", "facturamos", "vendio"}


def _p(v: float | None) -> str:
    return "—" if v is None else "$" + f"{abs(v):,.0f}".replace(",", ".")


def _f(d: Any) -> str:
    if not _ok(d):
        return "sin fecha"
    d = pd.Timestamp(d)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _anios(x: float | None) -> str:
    if x is None or pd.isna(x):
        return "—"
    a = int(x)
    m = int(round((x - a) * 12))
    if m == 12:
        a, m = a + 1, 0
    return f"{a} año{'s' if a != 1 else ''}" + (f" y {m} mes{'es' if m != 1 else ''}" if m else "")


# Siglas y nombres cortos con que se conoce a empresas grandes en Colombia
ALIAS = {"emcali": "empresas municipales de cali", "epm": "empresas publicas de medellin",
         "eaab": "empresa de acueducto y alcantarillado de bogota", "acueducto": "acueducto y alcantarillado",
         "etb": "empresa de telecomunicaciones de bogota", "codensa": "enel colombia", "enel": "enel colombia",
         "une": "une epm telecomunicaciones", "dian": "direccion de impuestos y aduanas nacionales",
         "shd": "secretaria distrital de hacienda", "colpensiones": "administradora colombiana de pensiones",
         "ecopetrol": "ecopetrol", "bavaria": "bavaria", "claro": "comunicacion celular comcel",
         "comcel": "comunicacion celular comcel", "movistar": "colombia telecomunicaciones",
         "tigo": "colombia movil", "davivienda": "banco davivienda", "bancolombia": "bancolombia"}


def candidatos_texto(pregunta: str) -> str:
    """Quita palabras de la pregunta para quedarse con el posible nombre (y expande siglas conocidas)."""
    pal = [w for w in re.findall(r"[a-z0-9&.]+", _n(pregunta).lower()) if w not in PALABRAS_VACIAS and len(w) > 1]
    return " ".join(ALIAS.get(w, w) for w in pal)


COMUNES = {"sas", "s.a.s", "ltda", "s.a", "sa", "cia", "y", "e.u", "eu", "esp", "de", "del", "la", "los"}


def _tok(t: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9&]+", _n(t).lower()) if len(w) >= 3 and w not in COMUNES]


def _parecida(a: str, b: str) -> bool:
    """Dos palabras son la misma aunque tengan un error de digitación (valenvia ≈ valencia)."""
    if a == b:
        return True
    if min(len(a), len(b)) < 4:
        return False
    if len(a) >= 4 and b.startswith(a):  # «codi» → «codifer», «andr» → «andres»
        return True
    try:
        from rapidfuzz import fuzz
        return fuzz.ratio(a, b) >= 85
    except ImportError:
        import difflib
        return difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def _mejor(nombre: str, opciones: list[str], minimo: float = 80) -> list[tuple[str, float]]:
    """Busca el nombre por palabras: las palabras de la pregunta que no aparecen en ningún nombre
    («nostros», «entro», «cuanto») se ignoran solas; luego gana quien tenga más palabras en común."""
    opciones = [o for o in dict.fromkeys(opciones) if o and str(o).strip()]
    q = list(dict.fromkeys(_tok(nombre)))
    if not q or not opciones:
        return []
    toks_op = {o: set(_tok(o)) for o in opciones}
    vocab = set().union(*toks_op.values())
    utiles = [w for w in q if w in vocab or any(_parecida(w, v) for v in vocab if v[:1] == w[:1])]
    if not utiles:
        return []
    puntajes = []
    for o, ts in toks_op.items():
        m = sum(1 for w in utiles if any(_parecida(w, v) for v in ts))
        if not m:
            continue
        cubre = 100 * m / len(utiles)
        if cubre < 60:
            continue
        final = 0.7 * cubre + 0.3 * parecido(" ".join(utiles), o)
        puntajes.append((o, round(final, 1)))
    puntajes.sort(key=lambda x: (-x[1], len(x[0])))
    return [p for p in puntajes if p[1] >= min(minimo, 75)][:5]


# ───────────────────────── Personas ─────────────────────────

def _personal() -> dict[str, Any]:
    from modulos import analitica_personal as ap
    return ap.cargar()


def buscar_persona(texto: str) -> dict[str, Any] | None:
    d = _personal()
    e = d.get("empleados")
    if e is None or e.empty:
        return None
    q = candidatos_texto(texto)
    hallados = _mejor(q, e["nombre"].tolist(), 78)
    if not hallados:
        return None
    empates = [h[0] for h in hallados if h[1] >= hallados[0][1] - 1]
    if len(empates) > 1:
        return {"ambiguo": empates}
    nombre = hallados[0][0]
    fila = e[e["nombre"] == nombre].sort_values("activo", ascending=False).iloc[0]
    info: dict[str, Any] = {"nombre": nombre, "activo": bool(fila["activo"]), "vinculo": fila["vinculo"],
                            "cargo": fila["cargo_n"], "area": fila["area"], "ingreso": fila["ingreso"],
                            "retiro": fila["retiro"], "antiguedad": fila["antiguedad"], "edad": fila["edad"],
                            "nacimiento": fila["nacimiento"], "contrato": fila["contrato"], "eps": fila["eps"],
                            "salario": fila["salario"], "otros": [h[0] for h in hallados[1:3] if h[1] >= 85]}
    vac = d.get("vacaciones")
    if vac is not None and not vac.empty:
        v = _mejor(nombre, vac["nombre"].tolist(), 88)
        if v:
            info["vacaciones"] = float(vac.loc[vac["nombre"] == v[0][0], "dias"].iloc[0])
    con = d.get("contratos")
    if con is not None and not con.empty:
        c = _mejor(nombre, con["nombre"].tolist(), 88)
        if c:
            r = con[con["nombre"] == c[0][0]].iloc[0]
            info["vence"] = r["prox"]
            info["preaviso"] = r["preaviso"]
    return info


def responder_persona(pregunta: str, info: dict[str, Any]) -> str:
    if info.get("ambiguo"):
        return ("Hay varias personas con ese nombre: " + ", ".join(f"**{x}**" for x in info["ambiguo"])
                + ". ¿Por cuál me pregunta? Escriba el nombre y un apellido.")
    t = _n(pregunta).lower()
    n = info["nombre"]
    lineas = []
    if not info["activo"]:
        lineas.append(f"**{n}** ya no está en la empresa" + (f" (retiro: {_f(info['retiro'])})." if _ok(info["retiro"]) else "."))
    pide_edad = bool(re.search(r"edad|anos tiene|nacio|cumple", t))
    if re.search(r"lleva|antiguedad|desde cuando|cuando (entro|ingreso)|hace cuanto|tiempo|trabaja", t) or \
            (re.search(r"anos", t) and not pide_edad):
        if _ok(info["ingreso"]):
            lineas.append(f"**{n}** lleva **{_anios(info['antiguedad'])}** con nosotros: ingresó el {_f(info['ingreso'])}"
                          + (f" y salió el {_f(info['retiro'])}." if not info["activo"] and _ok(info["retiro"]) else "."))
        else:
            lineas.append(f"No tengo la fecha de ingreso de **{n}**. Complétela en el Excel «Archivo General» "
                          "(columna FECHA INICIO DE CONTRATO) o en Personal → Contratos Activos.")
    if pide_edad:
        if _ok(info["nacimiento"]):
            nac = pd.Timestamp(info["nacimiento"])
            lineas.append(f"**{n}** tiene **{int(info['edad'])} años**; cumple el {nac.day} de {MESES[nac.month - 1]}.")
        else:
            lineas.append(f"No tengo la fecha de nacimiento de **{n}**.")
    if re.search(r"vacacion", t):
        lineas.append(f"**{n}** tiene **{info['vacaciones']:.0f} días** de vacaciones pendientes." if "vacaciones" in info
                      else f"No encontré saldo de vacaciones para **{n}**.")
    if re.search(r"contrato|vence|preaviso|renov", t):
        if _ok(info.get("vence")):
            lineas.append(f"El contrato de **{n}** vence el **{_f(info['vence'])}** (preaviso a más tardar el "
                          f"{_f(info.get('preaviso'))}). Tipo: {info['contrato']}.")
        else:
            lineas.append(f"Contrato de **{n}**: {info['contrato']}; no tengo fecha de vencimiento (puede ser indefinido).")
    if re.search(r"cargo|que hace|puesto|area|departamento", t):
        lineas.append(f"**{n}**: {info['cargo']} · área {info['area']} · {info['vinculo'].lower()}.")
    if re.search(r"salario|sueldo|gana|ibc", t):
        lineas.append(f"Salario/IBC registrado de **{n}**: {_p(info['salario'])}." if info["salario"] else
                      f"No hay salario registrado para **{n}**.")
    if not lineas or (len(lineas) == 1 and not info["activo"]):
        partes = [f"**{n}**"] + [x for x in (info["cargo"], info["area"], info["vinculo"]) if x and x != "Sin dato"]
        lineas.append(" · ".join(partes))
        if _ok(info["ingreso"]):
            lineas.append(f"• Ingresó el {_f(info['ingreso'])} · lleva {_anios(info['antiguedad'])}")
        if _ok(info["nacimiento"]):
            nac = pd.Timestamp(info["nacimiento"])
            lineas.append(f"• {int(info['edad'])} años · cumple el {nac.day} de {MESES[nac.month - 1]}")
        if "vacaciones" in info:
            lineas.append(f"• {info['vacaciones']:.0f} días de vacaciones pendientes")
        if _ok(info.get("vence")):
            lineas.append(f"• Contrato vence el {_f(info['vence'])}")
        if info.get("eps") and info["eps"] != "Sin dato":
            lineas.append(f"• EPS: {info['eps']}")
    if info.get("otros"):
        lineas.append(f"_(También hay nombres parecidos: {', '.join(info['otros'])}.)_")
    return "\n".join(lineas)


# ───────────────────────── Terceros ─────────────────────────

def _contable() -> dict[str, Any] | None:
    from modulos import analitica_gastos as ag
    return ag.cargar()


def _num_factura(det: str) -> list[str]:
    """Números que identifican una factura en el detalle o el comprobante: FAM184425, FAV-341492 → FAV341492,
    FAC 813 (consecutivo interno) → FAC813, y la orden de compra de 5 dígitos (16269) → OC16269."""
    s = str(det).upper()
    claves = [a + b for a, b in re.findall(r"\b(F[A-Z]{1,3})[\s.#:-]*(\d{2,10})\b", s)]
    claves += ["N" + n for n in re.findall(r"\b(?:FV|FE|FACTURA(?:\s+N[O°º.]*)?|FACT|FAC)[\s.#:-]*(\d{3,10})\b", s)]
    claves += ["OC" + n for n in re.findall(r"(?<![\d-])(1\d{4})(?!\d)", s)]
    return list(dict.fromkeys(claves))


def buscar_tercero(texto: str) -> dict[str, Any] | None:
    datos = _contable()
    q = candidatos_texto(texto)
    nombres: list[str] = []
    if datos:
        nombres += datos["mov"]["tercero"].dropna().tolist()
        if datos.get("terceros") is not None and not datos["terceros"].empty:
            nombres += datos["terceros"]["tercero"].dropna().tolist()
    from modulos.motor_alertas import _filas
    try:
        nombres += [r["n"] for r in _filas("SELECT DISTINCT proveedor n FROM pagos_calendario WHERE proveedor IS NOT NULL")]
        nombres += [r["n"] for r in _filas("SELECT DISTINCT cliente n FROM cartera_cxc")]
    except Exception:
        pass
    hallados = _mejor(q, [n for n in nombres if n and n != "Sin tercero"], 80)
    if not hallados:
        return None
    nombre = hallados[0][0]
    clave = [t for t in _n(nombre).split() if len(t) >= 4][:2]
    info: dict[str, Any] = {"nombre": nombre, "otros": [h[0] for h in hallados[1:3] if h[1] >= 88]}
    if datos:
        mov, terc = datos["mov"], datos.get("terceros")
        m = mov[mov["tercero"] == nombre]
        info["desde"] = mov["fecha"].min()
        info["hasta"] = mov["fecha"].max()
        info["gasto"] = float(m[m["clase"].isin(["5", "6", "7"])]["monto"].sum())
        info["ventas"] = float(m[m["clase"] == "4"]["monto"].sum())
        info["cuentas_gasto"] = m[m["clase"].isin(["5", "6", "7"])].groupby("nombre_cuenta4")["monto"].sum() \
            .sort_values(ascending=False).head(3).to_dict()
        if terc is not None and not terc.empty:
            t = terc[terc["tercero"] == nombre]
            info["pasivo"] = _cruce(t[t["cuenta4"].isin(["2205", "2335", "2380"])], deuda_nuestra=True)
            info["cartera"] = _cruce(t[t["cuenta4"].isin(["1305"])], deuda_nuestra=False)
            ant = t[t["cuenta4"] == "1330"]["valor"].sum()
            info["anticipos"] = float(ant) if ant else 0.0
    try:
        from modulos.motor_alertas import _filas
        like = f"%{clave[0]}%" if clave else f"%{nombre}%"
        info["programados"] = _filas("SELECT fecha_sugerida, detalle, valor, estado FROM pagos_calendario WHERE "
                                     "(proveedor LIKE ? OR detalle LIKE ?) AND estado IN ('PENDIENTE','EN PROCESO') "
                                     "ORDER BY fecha_sugerida LIMIT 5", (like, like))
        info["mora"] = _filas("SELECT saldo, dias_mora FROM cartera_cxc WHERE cliente LIKE ?", (like,))
    except Exception:
        pass
    return info


_RE_DEVOL = re.compile(r"DEVOLUC|NOTA CR|\bNC\b|\bDMC\b")


def _cruce(t: pd.DataFrame, deuda_nuestra: bool) -> dict[str, Any]:
    """Cruza facturas con pagos (y abonos parciales) por número de factura / consecutivo / orden de compra.
    Los movimientos que comparten algún número quedan en el mismo grupo; un grupo con saldo es una factura abierta.
    En Python puro (sin pandas por fila): se puede correr para cientos de terceros en un instante."""
    if t is None or t.empty:
        return {}
    filas = list(zip(t["fecha"], t["detalle"].fillna("").astype(str),
                     (t["comprobante"] if "comprobante" in t else pd.Series([""] * len(t))).fillna("").astype(str),
                     t["valor"].astype(float)))
    return cruce_filas(filas, deuda_nuestra)


def cruce_filas(filas: list[tuple], deuda_nuestra: bool) -> dict[str, Any]:
    """filas: (fecha, detalle, comprobante, valor). Ver _cruce."""
    signo = -1 if deuda_nuestra else 1  # pasivo: factura = crédito (valor < 0); cartera: al revés
    padre = list(range(len(filas)))

    def raiz(i: int) -> int:
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    dueno: dict[str, int] = {}
    for i, (_, det, comp, _v) in enumerate(filas):
        for k in _num_factura(f"{det} {comp}"):
            if k in dueno:
                padre[raiz(i)] = raiz(dueno[k])
            else:
                dueno[k] = i
    facturado = pagado = devoluciones = neto = 0.0
    grupos: dict[int, list[int]] = {}
    for i, (_, det, comp, v) in enumerate(filas):
        grupos.setdefault(raiz(i), []).append(i)
        neto += v
        sv = v * signo
        if sv > 0:
            facturado += abs(v)
        elif sv < 0:
            if _RE_DEVOL.search(f"{det} {comp}".upper()) and "PAGO" not in det.upper():
                devoluciones += abs(v)
            else:
                pagado += abs(v)
    abiertas = []
    for idx in grupos.values():
        saldo = sum(filas[i][3] * signo for i in idx)
        fact = [i for i in idx if filas[i][3] * signo > 0]
        if saldo > 1000 and fact:
            f0 = filas[fact[0]]
            total = abs(sum(filas[i][3] for i in fact))
            nums = [k for k in _num_factura(f0[1]) if not k.startswith("OC")] or _num_factura(f0[1])
            abiertas.append({"fecha": f0[0], "detalle": f0[1], "valor": float(saldo), "total": float(total),
                             "factura": nums[0] if nums else "", "abono": saldo < total - 1})
    abiertas.sort(key=lambda x: x["fecha"])
    if not deuda_nuestra:
        # Los clientes casi nunca citan la factura al pagar: lo abierto no puede superar lo que quedó debiendo
        # en el año. Los pagos sin número se aplican a las facturas más antiguas primero.
        sobra = sum(a["valor"] for a in abiertas) - max(neto, 0.0)
        while sobra > 1 and abiertas:
            a = abiertas[0]
            if a["valor"] <= sobra:
                sobra -= a["valor"]
                abiertas.pop(0)
            else:
                a["valor"] -= sobra
                a["abono"] = True
                sobra = 0
    return {"facturado": facturado - devoluciones, "pagado": pagado, "devoluciones": devoluciones,
            "neto": float(-neto if deuda_nuestra else neto),
            "abiertas": abiertas,
            "pendiente": float(sum(a["valor"] for a in abiertas))}


def responder_tercero(pregunta: str, info: dict[str, Any]) -> str:
    t = _n(pregunta).lower()
    n = info["nombre"]
    periodo = (f"{_f(info['desde'])} – {_f(info['hasta'])}" if _ok(info.get("desde")) else "el periodo cargado")
    lineas: list[str] = []
    quiere_deuda = re.search(r"debemos|debo|deuda|saldo|pendiente|por pagar|le debe", t)
    quiere_cartera = re.search(r"nos debe|cobrar|cartera|debe a nosotros", t)
    if quiere_cartera or (not quiere_deuda and info.get("cartera", {}).get("facturado")):
        c = info.get("cartera") or {}
        if c:
            lineas.append(f"**{n}** (cliente): le facturamos {_p(c['facturado'])} y nos pagó {_p(c['pagado'])} en {periodo}.")
            if c["abiertas"]:
                lineas.append(f"Facturas sin pago registrado: **{len(c['abiertas'])} por {_p(c['pendiente'])}** "
                              f"(la más antigua: {_f(c['abiertas'][0]['fecha'])}).")
        for mo in info.get("mora") or []:
            lineas.append(f"En cartera figura con saldo {_p(mo['saldo'])} y {mo['dias_mora']} días de mora.")
    if quiere_deuda or not lineas:
        p = info.get("pasivo") or {}
        if p:
            lineas.append(f"**{n}** (proveedor): en {periodo} nos facturó **{_p(p['facturado'])}** y le pagamos "
                          f"**{_p(p['pagado'])}**.")
            if p["abiertas"]:
                lineas.append(f"**Facturas sin pago registrado: {len(p['abiertas'])} por {_p(p['pendiente'])}**:")
                for a in p["abiertas"][:6]:
                    lineas.append(f"• {_f(a['fecha'])} · {a['factura'] or a['detalle'][:40]} · {_p(a['valor'])}"
                                  + (f" (abonado parcialmente; total {_p(a['total'])})" if a.get("abono") else ""))
                if len(p["abiertas"]) > 6:
                    lineas.append(f"…y {len(p['abiertas']) - 6} más.")
            else:
                lineas.append("Todas sus facturas del periodo tienen pago registrado ✓ "
                              + (f"(se pagó {_p(-p['neto'])} más de lo facturado: abonos a saldo del año anterior)."
                                 if p["neto"] < 0 else ""))
        elif quiere_deuda:
            lineas.append(f"No encontré facturas por pagar de **{n}** en la contabilidad cargada.")
    if re.search(r"gast|pagado|pagamos|compr|cuanto le hemos", t) or not lineas:
        if (info.get("gasto") or 0) > 1000:
            cuentas = ", ".join(f"{k} {_p(v)}" for k, v in (info.get("cuentas_gasto") or {}).items())
            lineas.append(f"Gasto/costo con **{n}** en {periodo}: **{_p(info['gasto'])}**" + (f" ({cuentas})." if cuentas else "."))
    if re.search(r"vend|venta|factur.*(a el|le)|nos compr", t) and info.get("ventas"):
        lineas.append(f"Ventas a **{n}** en {periodo}: **{_p(info['ventas'])}**.")
    for pr in info.get("programados") or []:
        lineas.append(f"Pago programado: {pr['detalle']} el {_f(pr['fecha_sugerida'])}" + (f" · {_p(pr['valor'])}" if pr["valor"] else ""))
    if info.get("anticipos"):
        lineas.append(f"Anticipos registrados: {_p(info['anticipos'])}.")
    lineas.append("_Cálculo con los movimientos del auxiliar del contador del periodo cargado; los saldos de años "
                  "anteriores no están en ese archivo._")
    if info.get("otros"):
        lineas.append(f"_(Nombres parecidos: {', '.join(info['otros'])}.)_")
    return "\n".join(lineas)


# ───────────────────────── Cuentas contables ─────────────────────────

def responder_contable(pregunta: str) -> str | None:
    """«¿Cuánto gastamos en arriendo?», «¿cuánto vendimos en septiembre?»"""
    datos = _contable()
    if not datos:
        return None
    t = _n(pregunta).lower()
    mov = datos["mov"]
    mes = next((i + 1 for i, m in enumerate(MESES) if re.search(rf"\b{_n(m).lower()}\b", t)), None)
    m = mov[mov["fecha"].dt.month == mes] if mes else mov
    etiqueta = f"en {MESES[mes - 1]}" if mes else f"de {MESES[mov['fecha'].min().month - 1]} a {MESES[mov['fecha'].max().month - 1]}"
    if re.search(r"vend|ventas|ingres|facturamos", t) and not re.search(r"gast", t):
        v = m[m["clase"] == "4"]["monto"].sum()
        return f"Ingresos {etiqueta}: **{_p(v)}** (cuentas 41 y 42 del auxiliar)."
    if re.search(r"gast|pagamos|cuesta|costo", t):
        q = " ".join(w for w in candidatos_texto(t).split() if w not in MESES and w not in ("mes", "ano", "2026", "2025"))
        cuentas = m["nombre_cuenta6"].dropna().unique().tolist() + m["nombre_cuenta4"].dropna().unique().tolist()
        hall = _mejor(q, cuentas, 75) if q else []
        if hall:
            c = hall[0][0]
            sel = m[(m["nombre_cuenta6"] == c) | (m["nombre_cuenta4"] == c)]
            por_mes = sel.groupby(sel["fecha"].dt.month)["monto"].sum()
            extra = "" if mes else " · por mes: " + ", ".join(f"{MESES[k - 1][:3]} {_p(v)}" for k, v in por_mes.items())
            return f"Gasto en **{c}** {etiqueta}: **{_p(sel['monto'].sum())}**{extra}."
        g = m[m["clase"].isin(["5", "6", "7"])]
        if not q:
            return f"Gastos y costos {etiqueta}: **{_p(g['monto'].sum())}**."
        if re.search(r"gast\w* (en|de)\b|cuesta", t):
            top = g.groupby("nombre_cuenta6")["monto"].sum().sort_values(ascending=False).head(5)
            return (f"No encontré una cuenta de gasto que se parezca a «{q}» {etiqueta}. Los gastos más grandes son: "
                    + ", ".join(f"{k} {_p(v)}" for k, v in top.items()) + ".")
    return None
