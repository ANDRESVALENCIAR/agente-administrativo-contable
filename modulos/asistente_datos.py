"""
Herramientas de datos del chat de Shaki — finanzas, caja, cartera/proveedores, gastos, personal y SQL de solo
lectura. Las usan los dos motores:

- Sin clave de IA: el intérprete local las llama y arma la respuesta con `texto_*`.
- Con clave: Claude las elige solo (tool use) y razona con los resultados.

Todas son de SOLO LECTURA.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date
from typing import Any

import pandas as pd

from config import cfg

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def _p(v: Any, corto: bool = False) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    v = float(v)
    if corto and abs(v) >= 1e6:
        return ("−" if v < 0 else "") + f"${abs(v) / 1e6:,.1f} M".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if v < 0 else "") + "$" + f"{abs(v):,.0f}".replace(",", ".")


def _pct(v: Any) -> str:
    return "—" if v is None or pd.isna(v) else f"{v * 100:.1f}%".replace(".", ",")


def _f(ts: Any) -> str:
    if ts is None or pd.isna(ts):
        return "—"
    ts = pd.Timestamp(ts)
    return f"{ts.day} de {MESES[ts.month - 1]} de {ts.year}"


def _contable() -> dict | None:
    from modulos import analitica_gastos as ag
    d = ag.cargar()
    return d if d and "prueba" in d else None


SIN_CONTABILIDAD = {"error": "No hay contabilidad cargada. Suba el libro del contador (hojas Auxiliar y Prueba) en "
                             "Contabilidad o Gastos → «Fuente de datos»."}


def _mes_num(texto: str | None) -> int | None:
    if not texto:
        return None
    t = str(texto).lower()
    if t.isdigit() and 1 <= int(t) <= 12:
        return int(t)
    m = re.match(r"\d{4}-(\d{2})", t)
    if m:
        return int(m.group(1))
    import unicodedata
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return next((i + 1 for i, n in enumerate(MESES) if n.startswith(t[:3])), None)


def _filtrar_meses(mov: pd.DataFrame, desde_mes: str | None, hasta_mes: str | None) -> pd.DataFrame:
    d, h = _mes_num(desde_mes), _mes_num(hasta_mes)
    if d:
        mov = mov[mov["fecha"].dt.month >= d]
    if h:
        mov = mov[mov["fecha"].dt.month <= h]
    return mov


# ───────────────────────── Finanzas ─────────────────────────

def h_finanzas(desde_mes: str | None = None, hasta_mes: str | None = None) -> dict[str, Any]:
    """Estado de la empresa según el libro del contador: estado de resultados (ventas, costo, gastos, utilidad y
    márgenes) del periodo, balance general al corte (activo, pasivo, patrimonio, caja, cartera, proveedores, deuda
    bancaria, impuestos) e indicadores financieros con semáforo. desde_mes/hasta_mes: nombre o número de mes."""
    from modulos import analitica_contable as ac
    d = _contable()
    if not d:
        return SIN_CONTABILIDAD
    m = _filtrar_meses(d["mov"], desde_mes, hasta_mes)
    if m.empty:
        return {"error": "No hay movimientos en esos meses."}
    e = ac.estado_resultados(m)
    b = ac.balance(d["prueba"])
    dias = max(1, (m["fecha"].max() - m["fecha"].min()).days + 1)
    mm = ac.resultados_mensuales(m)
    return {
        "periodo": f"{_f(m['fecha'].min())} – {_f(m['fecha'].max())}", "corte_balance": _f(ac.corte(d)),
        "estado_resultados": {k: round(v, 4) if isinstance(v, float) and abs(v) < 10 else v for k, v in e.items()},
        "balance": {k: v for k, v in b.items() if not k.startswith("grupos")},
        "grupos_balance": {"activo": b["grupos_activo"], "pasivo": b["grupos_pasivo"], "patrimonio": b["grupos_patrimonio"]},
        "por_mes": [{"mes": r["mes"].strftime("%Y-%m"), "ingresos": r["ingresos"], "costo": r["costo"],
                     "gastos": r["gastos"], "utilidad": r["utilidad"]} for _, r in mm.iterrows()],
        "indicadores": [{k: i[k] for k in ("nombre", "valor", "semaforo", "que")} for i in ac.indicadores(b, e, dias)],
    }


def texto_finanzas(r: dict, enfoque: str = "general") -> str:
    if "error" in r:
        return r["error"]
    e, b = r["estado_resultados"], r["balance"]
    neta = e["neta"]
    if enfoque == "indicadores":
        sem = {"bien": "🟢", "ojo": "🟡", "mal": "🔴", "nd": "⚪"}
        lineas = [f"**Indicadores** (balance al {r['corte_balance']}):"]
        for i in r["indicadores"]:
            v = i["valor"]
            val = ("—" if v is None else _pct(v) if i["nombre"] in ("Endeudamiento", "Margen bruto", "Margen operacional",
                                                                    "Margen neto")
                   else f"{v:.0f} días" if i["nombre"].startswith("Días") else _p(v, True) if "Capital" in i["nombre"]
                   else f"{v:.2f}".replace(".", ","))
            lineas.append(f"{sem[i['semaforo']]} **{i['nombre']}: {val}** — {i['que']}")
        return "\n".join(lineas)
    if enfoque == "deuda":
        return (f"**Deudas al {r['corte_balance']}:** total pasivo **{_p(b['pasivo'])}** "
                f"({_pct(b['pasivo'] / b['activo'] if b['activo'] else None)} del activo)\n"
                f"• Bancos (obligaciones financieras): **{_p(b['bancos_deuda'])}**\n"
                f"• Proveedores: {_p(b['proveedores'])}\n• Impuestos por pagar: {_p(b['impuestos'])}\n"
                f"• Laborales: {_p(b['laborales'])}\n• Otros pasivos: {_p(b['otros_pasivos'])}")
    lineas = [f"**{'Utilidad' if neta >= 0 else 'Pérdida'} del periodo ({r['periodo']}): {_p(neta)}** · margen neto "
              f"{_pct(e['margen_neto'])}",
              f"• Ventas {_p(e['ingresos'])} − costo {_p(e['costo'])} = utilidad bruta {_p(e['bruta'])} "
              f"({_pct(e['margen_bruto'])})",
              f"• Gastos de administración {_p(e['admin'])} y de ventas {_p(e['ventas'])} → utilidad operacional "
              f"{_p(e['operacional'])} ({_pct(e['margen_operacional'])})",
              f"• Otros ingresos {_p(e['otros_ingresos'])} − gastos no operacionales {_p(e['otros_gastos'])}",
              f"\n**Balance al {r['corte_balance']}:** activo {_p(b['activo'], True)} · pasivo {_p(b['pasivo'], True)} · "
              f"patrimonio {_p(b['patrimonio_total'], True)} · caja y bancos {_p(b['disponible'], True)}"]
    malos = [i for i in r["indicadores"] if i["semaforo"] == "mal"]
    if malos:
        lineas.append("\n🔴 **Para atender:** " + " · ".join(i["nombre"] for i in malos))
    if r["por_mes"]:
        pm = r["por_mes"]
        mejor = max(pm, key=lambda x: x["utilidad"])
        peor = min(pm, key=lambda x: x["utilidad"])
        lineas.append(f"Mejor mes: {mejor['mes']} ({_p(mejor['utilidad'], True)}) · peor: {peor['mes']} "
                      f"({_p(peor['utilidad'], True)})")
    return "\n".join(lineas)


# ───────────────────────── Caja ─────────────────────────

def h_caja() -> dict[str, Any]:
    """Caja y bancos: saldo de cada cuenta bancaria y caja al corte, entradas/salidas/saldo de cada mes del año y
    los terceros que más plata trajeron o se llevaron."""
    from modulos import analitica_contable as ac
    d = _contable()
    if not d:
        return SIN_CONTABILIDAD
    b = ac.balance(d["prueba"])
    f = ac.flujo_caja(d.get("caja"), b["disponible"])
    ent, sal = ac.mayores_movimientos_caja(d.get("caja"), 8)
    return {"corte": _f(ac.corte(d)), "total": b["disponible"], "cuentas": ac.cuentas_disponible(d["prueba"]),
            "saldo_inicio_anio": float(f.attrs.get("inicial", 0)) if not f.empty else None,
            "por_mes": [{"mes": r["mes"].strftime("%Y-%m"), "entradas": r["entradas"], "salidas": r["salidas"],
                         "saldo": r["saldo"]} for _, r in f.iterrows()],
            "mas_entradas": ent.to_dict("records"), "mas_salidas": sal.to_dict("records")}


def texto_caja(r: dict) -> str:
    if "error" in r:
        return r["error"]
    lineas = [f"**Caja y bancos al {r['corte']}: {_p(r['total'])}**"]
    for c in r["cuentas"][:8]:
        lineas.append(f"• {c['nombre']}: {_p(c['saldo'])}")
    if r["por_mes"]:
        u = r["por_mes"][-1]
        lineas.append(f"\nÚltimo mes ({u['mes']}): entró {_p(u['entradas'], True)}, salió {_p(u['salidas'], True)}.")
    return "\n".join(lineas)


# ───────────────────────── Cartera y proveedores ─────────────────────────

def h_cuentas_por_cobrar_pagar(tipo: str = "clientes", min_dias: int = 0) -> dict[str, Any]:
    """Facturas abiertas por antigüedad. tipo: «clientes» (lo que nos deben, 1305) o «proveedores» (lo que
    debemos, 2205). min_dias filtra facturas con al menos esos días. Incluye saldo contable, totales por edad,
    top terceros y las facturas."""
    from modulos import analitica_contable as ac
    d = _contable()
    if not d:
        return SIN_CONTABILIDAD
    prov = str(tipo).lower().startswith("prov")
    b = ac.balance(d["prueba"])
    ab = ac.abiertas(d["terceros"], ("2205",) if prov else ("1305",), prov, ac.corte(d))
    if not ab.empty and min_dias:
        ab = ab[ab["dias"] >= int(min_dias)]
    por_edad = ab.groupby("edad", observed=False)["valor"].sum().to_dict() if not ab.empty else {}
    top = ab.groupby("tercero")["valor"].sum().sort_values(ascending=False).head(12) if not ab.empty else pd.Series()
    return {"tipo": "proveedores" if prov else "clientes", "corte": _f(ac.corte(d)),
            "saldo_contable": b["proveedores"] if prov else b["clientes"],
            "total_facturas_abiertas": float(ab["valor"].sum()) if not ab.empty else 0.0,
            "por_edad": {str(k): float(v) for k, v in por_edad.items()},
            "top_terceros": [{"tercero": k, "valor": float(v)} for k, v in top.items()],
            "facturas": [{"tercero": r["tercero"], "fecha": _f(r["fecha"]), "factura": r["factura"], "valor": r["valor"],
                          "dias": r["dias"]} for _, r in ab.head(40).iterrows()]}


def texto_cxc_cxp(r: dict) -> str:
    if "error" in r:
        return r["error"]
    quien = "Los clientes nos deben" if r["tipo"] == "clientes" else "Les debemos a proveedores"
    lineas = [f"**{quien} {_p(r['saldo_contable'])}** (saldo contable al {r['corte']})"]
    if r["por_edad"]:
        lineas.append("Por antigüedad: " + " · ".join(f"{k}: {_p(v, True)}" for k, v in r["por_edad"].items() if v))
    for t in r["top_terceros"][:8]:
        lineas.append(f"• {t['tercero']}: {_p(t['valor'])}")
    return "\n".join(lineas)


# ───────────────────────── Gastos y ventas ─────────────────────────

def h_gastos(agrupar: str = "cuenta", mes: str | None = None, buscar: str | None = None, top: int = 10,
             tipo: str = "gastos") -> dict[str, Any]:
    """Gastos (o ventas) del auxiliar del contador agrupados. agrupar: cuenta | tercero | mes. mes: filtra un mes.
    buscar: texto en el nombre de la cuenta o del tercero. tipo: gastos (cuentas 5, 6, 7) o ventas (cuenta 4)."""
    d = _contable()
    if not d:
        return SIN_CONTABILIDAD
    mov = d["mov"]
    m = mov[mov["clase"] == "4"] if str(tipo).startswith("vent") else mov[mov["clase"].isin(["5", "6", "7"])]
    n = _mes_num(mes)
    if n:
        m = m[m["fecha"].dt.month == n]
    if buscar:
        q = str(buscar).upper()
        m = m[m["nombre_cuenta6"].str.upper().str.contains(q, regex=False) |
              m["nombre_cuenta4"].str.upper().str.contains(q, regex=False) |
              m["tercero"].str.upper().str.contains(q, regex=False)]
    if agrupar == "tercero":  # sin los movimientos internos de la propia empresa (costo de ventas, cierres)
        m = m[~m["nit"].astype(str).str.replace(r"\D", "", regex=True).str.startswith("901146454")]
    col = {"cuenta": "nombre_cuenta4", "subcuenta": "nombre_cuenta6", "tercero": "tercero"}.get(agrupar)
    if agrupar == "mes":
        g = m.groupby(m["fecha"].dt.strftime("%Y-%m"))["monto"].sum().sort_index()
    else:
        g = m.groupby(col or "nombre_cuenta4")["monto"].sum().sort_values(ascending=False).head(int(top or 10))
    return {"tipo": tipo, "mes": MESES[n - 1] if n else "todo el periodo", "total": float(m["monto"].sum()),
            "agrupado_por": agrupar, "filas": [{"nombre": k, "valor": float(v)} for k, v in g.items()]}


def texto_gastos(r: dict) -> str:
    if "error" in r:
        return r["error"]
    que = "Ventas" if str(r["tipo"]).startswith("vent") else "Gastos y costos"
    por = {"cuenta": "por cuenta", "tercero": "por tercero", "mes": "por mes", "subcuenta": "por subcuenta"}
    lineas = [f"**{que} ({r['mes']}): {_p(r['total'])}** — {por.get(r['agrupado_por'], '')}"]
    for f in r["filas"]:
        lineas.append(f"• {str(f['nombre'])[:48]}: {_p(f['valor'])}")
    return "\n".join(lineas)


# ───────────────────────── Personal ─────────────────────────

def h_personal(consulta: str = "resumen") -> dict[str, Any]:
    """Personal / RR. HH. consulta: resumen (cuántos, antigüedad y edad promedio, rotación) · cumpleanos (del mes
    y próximos) · vacaciones (saldo por persona) · contratos (vencimientos y preavisos) · lista (activos con cargo,
    área, ingreso y antigüedad) · examenes (exámenes médicos y dotación pendiente)."""
    from modulos import analitica_personal as ap
    d = ap.cargar()
    e = d.get("empleados")
    if e is None or e.empty:
        return {"error": "No hay datos de personal. Cárguelos en Personal → Archivo General."}
    hoy = pd.Timestamp(d["hoy"])
    act = e[e["activo"]]
    c = str(consulta).lower()
    if c.startswith("cumple"):
        cu = d.get("cumpleanos")
        filas = []
        for _, r in act.iterrows():
            if pd.notna(r["nacimiento"]):
                n = pd.Timestamp(r["nacimiento"])
                filas.append({"nombre": r["nombre"], "dia": n.day, "mes": n.month})
        if cu is not None and not cu.empty:
            for _, r in cu.iterrows():
                nom = str(r["nombre"]).title()
                if pd.notna(r["dia"]) and pd.notna(r["mes"]) and not any(ap.parecido(nom, f["nombre"]) >= 90 for f in filas):
                    filas.append({"nombre": nom, "dia": int(r["dia"]), "mes": int(r["mes"])})

        def faltan(f):
            try:
                prox = date(hoy.year, f["mes"], f["dia"])
            except ValueError:
                return 999
            if prox < hoy.date():
                prox = date(hoy.year + 1, f["mes"], f["dia"])
            return (prox - hoy.date()).days
        filas = sorted(({**f, "faltan_dias": faltan(f)} for f in filas), key=lambda f: f["faltan_dias"])
        return {"consulta": "cumpleanos", "mes_actual": MESES[hoy.month - 1],
                "este_mes": [f for f in filas if f["mes"] == hoy.month], "proximos": filas[:10]}
    if c.startswith("vaca"):
        v = d.get("vacaciones")
        filas = [] if v is None else v.sort_values("dias", ascending=False).to_dict("records")
        return {"consulta": "vacaciones", "total_dias": float(sum(f["dias"] for f in filas)), "personas": filas}
    if c.startswith("contra"):
        co = d.get("contratos")
        filas = [] if co is None or co.empty else [
            {"nombre": r["nombre"], "vence": _f(r["prox"]), "preaviso": _f(r["preaviso"]),
             "dias": int((r["prox"] - hoy).days) if pd.notna(r["prox"]) else None}
            for _, r in co.sort_values("prox").iterrows()]
        return {"consulta": "contratos", "contratos": filas}
    if c.startswith("exam") or c.startswith("dota"):
        nv = d.get("novedades")
        filas = [] if nv is None or nv.empty else [
            {"nombre": r["nombre"], "proximo_examen": _f(r["prox_examen"]), "dotacion_pendiente": bool(r["dotacion_pend"]),
             "vencido": bool(pd.notna(r["prox_examen"]) and pd.Timestamp(r["prox_examen"]) < hoy),
             "_orden": pd.Timestamp(r["prox_examen"]) if pd.notna(r["prox_examen"]) else pd.Timestamp.max}
            for _, r in nv.iterrows()]
        filas.sort(key=lambda f: f.pop("_orden"))
        return {"consulta": "examenes", "personas": filas}
    if c.startswith("lista"):
        return {"consulta": "lista", "activos": [
            {"nombre": r["nombre"], "cargo": r["cargo_n"], "area": r["area"], "vinculo": r["vinculo"],
             "ingreso": _f(r["ingreso"]), "antiguedad_anios": None if pd.isna(r["antiguedad"]) else round(r["antiguedad"], 1),
             "edad": None if pd.isna(r["edad"]) else int(r["edad"])} for _, r in act.sort_values("nombre").iterrows()]}
    return {"consulta": "resumen", **{k: v for k, v in ap.kpis(d).items()},
            "por_area": act["area"].value_counts().to_dict(), "por_vinculo": act["vinculo"].value_counts().to_dict()}


def texto_personal(r: dict) -> str:
    if "error" in r:
        return r["error"]
    c = r["consulta"]
    if c == "cumpleanos":
        lineas = [f"**Cumpleaños de {r['mes_actual']}:** " + (", ".join(f"{f['nombre']} ({f['dia']})" for f in r["este_mes"])
                                                            or "nadie este mes")]
        lineas.append("**Próximos:**")
        lineas += [f"• {f['nombre']} — {f['dia']} de {MESES[f['mes'] - 1]}"
                   + (" (¡hoy! 🎂)" if f["faltan_dias"] == 0 else f" (en {f['faltan_dias']} días)") for f in r["proximos"][:6]]
        return "\n".join(lineas)
    if c == "vacaciones":
        lineas = [f"**Vacaciones pendientes: {r['total_dias']:.0f} días en total**"]
        lineas += [f"• {f['nombre']}: {f['dias']:.0f} días" + (" ⚠️" if f["dias"] >= 15 else "") for f in r["personas"][:12]]
        return "\n".join(lineas)
    if c == "contratos":
        if not r["contratos"]:
            return "No hay contratos a término fijo registrados (o todos son indefinidos)."
        return "**Contratos a término fijo:**\n" + "\n".join(
            f"• {f['nombre']}: vence el {f['vence']} (preaviso a más tardar el {f['preaviso']})" for f in r["contratos"])
    if c == "examenes":
        pend = [f["nombre"] for f in r["personas"] if f["dotacion_pendiente"]]
        venc = [f for f in r["personas"] if f["vencido"]]
        prox = [f for f in r["personas"] if not f["vencido"] and f["proximo_examen"] != "—"]
        lineas = [f"**Dotación pendiente ({len(pend)}):** {', '.join(pend) or 'nadie'}"]
        if venc:
            lineas.append(f"🔴 **Exámenes médicos vencidos ({len(venc)}):**")
            lineas += [f"• {f['nombre']}: debía hacerse el {f['proximo_examen']}" for f in venc[:12]]
        if prox:
            lineas.append("**Próximos exámenes:**")
            lineas += [f"• {f['nombre']}: {f['proximo_examen']}" for f in prox[:8]]
        return "\n".join(lineas)
    if c == "lista":
        return f"**{len(r['activos'])} personas activas:**\n" + "\n".join(
            f"• {f['nombre']} · {f['cargo']} · {f['vinculo']}" + (f" · {f['antiguedad_anios']} años" if f["antiguedad_anios"] else "")
            for f in r["activos"])
    lineas = [f"**Equipo: {r.get('activos', 0)} personas activas** ({r.get('nomina', 0)} en nómina, "
              f"{r.get('prestacion', 0)} por prestación de servicios)"]
    if r.get("antiguedad"):
        lineas.append(f"• Antigüedad promedio: {r['antiguedad']:.1f} años".replace(".", ","))
    if r.get("edad"):
        lineas.append(f"• Edad promedio: {r['edad']:.0f} años")
    if r.get("por_area"):
        lineas.append("• Por área: " + ", ".join(f"{'sin área registrada' if k == 'Sin dato' else k} {v}"
                                                 for k, v in r["por_area"].items()))
    lineas.append(f"• Retiros últimos 12 meses: {r.get('retiros_12m', 0)}")
    lineas.append(f"• Vacaciones pendientes: {r.get('vac_dias', 0):.0f} días · cumpleaños este mes: {r.get('cumple_mes', 0)}")
    return "\n".join(lineas)


# ───────────────────────── ¿Alcanza la plata? ─────────────────────────

def h_alcanza(dias: int = 30) -> dict[str, Any]:
    """¿Alcanza la caja? Compara la plata en caja y bancos con lo que hay que pagar: pagos programados de los
    próximos `dias`, pagos vencidos sin marcar, proveedores vencidos (más de 30 días) e impuestos pendientes."""
    from datetime import timedelta
    from modulos import control_pagos as cp
    hoy = date.today()
    caja = h_caja()
    if "error" in caja:
        return caja
    try:
        cp.inicializar_tablas()
        prox = [p for p in cp.listar(desde=hoy, hasta=hoy + timedelta(days=int(dias))) if p["estado"] in ("PENDIENTE", "EN PROCESO")]
        venc = [p for p in cp.listar(hasta=hoy - timedelta(days=1), estados=("PENDIENTE", "EN PROCESO"))]
    except Exception:
        prox, venc = [], []
    prov = h_cuentas_por_cobrar_pagar("proveedores", 31)
    cli = h_cuentas_por_cobrar_pagar("clientes")
    v_prox = sum(p["valor"] or 0 for p in prox)
    v_venc = sum(p["valor"] or 0 for p in venc)
    v_prov = prov.get("total_facturas_abiertas", 0.0)
    comprometido = v_prox + v_venc + v_prov
    return {"caja_y_bancos": caja["total"], "corte_caja": caja["corte"], "dias": int(dias),
            "pagos_programados": v_prox, "n_pagos_programados": len(prox),
            "pagos_sin_valor": [p["detalle"] or p["proveedor"] for p in prox + venc if not p["valor"]],
            "pagos_vencidos_sin_marcar": v_venc,
            "n_pagos_vencidos": len(venc), "proveedores_vencidos_mas_30_dias": v_prov,
            "total_comprometido": comprometido, "diferencia": caja["total"] - comprometido,
            "clientes_por_cobrar": cli.get("saldo_contable"), "cartera_0_60_dias":
                sum(v for k, v in (cli.get("por_edad") or {}).items() if k in ("0–30 días", "31–60"))}


def texto_alcanza(r: dict) -> str:
    if "error" in r:
        return r["error"]
    ok = r["diferencia"] >= 0
    veredicto = ("🔴 **No alcanza**" if not ok else "🟡 **Alcanza para lo que tiene valor registrado**"
                 if r.get("pagos_sin_valor") else "✅ **Sí alcanza**")
    lineas = [f"{veredicto} con la caja de hoy para lo comprometido en los "
              f"próximos {r['dias']} días ({'sobran' if ok else 'faltan'} **{_p(abs(r['diferencia']))}**).",
              f"• Caja y bancos (al {r['corte_caja']}): {_p(r['caja_y_bancos'])}",
              f"• Pagos programados próximos {r['dias']} días: {_p(r['pagos_programados'])} ({r['n_pagos_programados']})",
              f"• Pagos vencidos sin marcar como pagados: {_p(r['pagos_vencidos_sin_marcar'])} ({r['n_pagos_vencidos']})",
              f"• Proveedores con facturas de más de 30 días: {_p(r['proveedores_vencidos_mas_30_dias'])}"]
    if r.get("pagos_sin_valor"):
        sv = r["pagos_sin_valor"]
        lineas.append(f"⚠️ {len(sv)} pagos programados no tienen valor en el control de pagos (ej. "
                      f"{', '.join(str(x) for x in sv[:3])}), así que no están sumados: el total real comprometido es "
                      "mayor. Complete los valores en Pagos → Control de pagos.")
    if not ok and r.get("cartera_0_60_dias"):
        lineas.append(f"Para cubrir la diferencia, la cartera reciente por cobrar es {_p(r['cartera_0_60_dias'])}: "
                      "conviene gestionar esos cobros primero.")
    lineas.append("_La caja es la del corte del contador; si ya hubo movimientos después, revise el saldo en el banco._")
    return "\n".join(lineas)


# ───────────────────────── SQL de solo lectura (para la IA) ─────────────────────────

def _conn_ro() -> sqlite3.Connection:
    ruta = cfg.DATABASE_PATH
    conn = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def h_esquema(tabla: str | None = None) -> dict[str, Any]:
    """Tablas de la base de Shaki con sus columnas y número de filas (para luego consultar con «sql»). Si se pasa
    `tabla`, devuelve sus columnas y 3 filas de ejemplo."""
    conn = _conn_ro()
    try:
        tablas = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                                             "ORDER BY name")]
        if tabla:
            if tabla not in tablas:
                return {"error": f"No existe la tabla {tabla}", "tablas": tablas}
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{tabla}")')]
            ej = [dict(r) for r in conn.execute(f'SELECT * FROM "{tabla}" LIMIT 3')]
            return {"tabla": tabla, "columnas": cols, "ejemplo": ej}
        out = []
        for t in tablas:
            n = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            if n:
                out.append({"tabla": t, "filas": n, "columnas": [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')][:25]})
        return {"tablas": out}
    finally:
        conn.close()


_SQL_PROHIBIDO = re.compile(r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex)\b", re.I)


def h_sql(consulta: str) -> dict[str, Any]:
    """Consulta SQL de SOLO LECTURA (SELECT / WITH) sobre la base SQLite de Shaki. Máximo 200 filas. Úsela para
    preguntas que las otras herramientas no cubren; revise antes las tablas con «esquema»."""
    q = (consulta or "").strip().rstrip(";")
    if not re.match(r"^(select|with)\b", q, re.I) or ";" in q or _SQL_PROHIBIDO.search(q):
        return {"error": "Solo se permiten consultas SELECT de una sola sentencia."}
    conn = _conn_ro()
    try:
        cur = conn.execute(q)
        filas = cur.fetchmany(201)
        return {"columnas": [c[0] for c in cur.description or []], "filas": [dict(r) for r in filas[:200]],
                "truncado": len(filas) > 200}
    except sqlite3.Error as e:
        return {"error": str(e)}
    finally:
        conn.close()
