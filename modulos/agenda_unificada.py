"""
Agenda unificada — junta en una sola línea de tiempo todo lo que tiene fecha en Shaki:

  PAGOS       control de pagos (pagos_calendario)            → botón "Ya lo pagué"
  IMPUESTOS   radar tributario DIAN/SHD (impuestos_obligaciones) → botón "Presentado"
  REVISION    revisar el borrador 3 días hábiles antes del vencimiento (si aún no hay revisión)
  AGENTE      tareas automáticas del calendario maestro (próxima ejecución) → "Ejecutar ahora"
  PERSONAL    contratos que vencen / preavisos, exámenes médicos, regreso de vacaciones,
              fin de incapacidades, cumpleaños
  CXP         pagos programados a proveedores (cxp_programados)
  FESTIVO     festivos de Colombia

Cada fuente se lee por separado: si una tabla no existe o falla, las demás siguen.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from database import get_conn

logger = logging.getLogger(__name__)

FUENTES = {
    "PAGOS": {"nombre": "Pagos", "color": "#4ADE80"},
    "IMPUESTOS": {"nombre": "Impuestos", "color": "#7DD3FC"},
    "REVISION": {"nombre": "Revisión impuestos", "color": "#C4B5FD"},
    "PERSONAL": {"nombre": "Personal", "color": "#F5C542"},
    "CXP": {"nombre": "Proveedores", "color": "#FB923C"},
    "AGENTE": {"nombre": "Automatizaciones", "color": "#A1A1AA"},
    "FESTIVO": {"nombre": "Festivos", "color": "#F472B6"},
}
ORDEN_NIVEL = {"VENCIDO": 0, "HOY": 1, "MAÑANA": 2, "PRONTO": 3, "PROGRAMADO": 4, "HECHO": 5}


def _d(v: Any) -> date | None:
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(str(v)[:10], fmt).date()
            except ValueError:
                pass
    return None


def nivel(fecha: date, hecho: bool = False, hoy: date | None = None) -> str:
    if hecho:
        return "HECHO"
    hoy = hoy or date.today()
    d = (fecha - hoy).days
    return "VENCIDO" if d < 0 else "HOY" if d == 0 else "MAÑANA" if d == 1 else "PRONTO" if d <= 3 else "PROGRAMADO"


def _ev(fuente: str, uid: str, fecha: date, titulo: str, sub: str = "", hecho: bool = False, valor: float | None = None,
        hora: str | None = None, accion: tuple[str, int] | None = None, hoy: date | None = None,
        prioridad: str | None = None) -> dict[str, Any]:
    return {"fuente": fuente, "uid": uid, "fecha": fecha, "hora": hora, "titulo": titulo, "sub": sub,
            "hecho": hecho, "valor": valor, "accion": accion, "nivel": nivel(fecha, hecho, hoy),
            "prioridad": prioridad}


def _filas(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()


# ───────────────────────── Fuentes ─────────────────────────

def _pagos(desde: date, hasta: date, hoy: date) -> list[dict]:
    out = []
    for p in _filas(
        "SELECT id, fecha_sugerida, fecha_limite, detalle, proveedor, valor, estado, prioridad, tipo "
        "FROM pagos_calendario WHERE estado!='ANULADO' AND ((fecha_sugerida BETWEEN ? AND ?) OR "
        "(fecha_sugerida < ? AND estado IN ('PENDIENTE','EN PROCESO')))",
        (desde.isoformat(), hasta.isoformat(), hoy.isoformat()),
    ):
        f = _d(p["fecha_sugerida"])
        if not f:
            continue
        hecho = p["estado"] == "PAGADO"
        sub = " · ".join(x for x in [p.get("proveedor"), p.get("tipo")] if x)
        out.append(_ev("PAGOS", f"pago-{p['id']}", f, p.get("detalle") or p.get("proveedor") or "Pago", sub, hecho,
                       p.get("valor"), accion=None if hecho else ("pagar", p["id"]), hoy=hoy,
                       prioridad=p.get("prioridad")))
    return out


def _impuestos(desde: date, hasta: date, hoy: date) -> list[dict]:
    out = []
    for o in _filas(
        "SELECT id, clave, entidad, impuesto, periodo, formulario, tipo, fecha_limite, estado "
        "FROM impuestos_obligaciones WHERE estado!='NO APLICA' AND ((fecha_limite BETWEEN ? AND ?) OR "
        "(fecha_limite < ? AND estado='PENDIENTE'))",
        (desde.isoformat(), hasta.isoformat(), hoy.isoformat()),
    ):
        f = _d(o["fecha_limite"])
        hecho = o["estado"] == "PRESENTADO"
        out.append(_ev("IMPUESTOS", f"imp-{o['id']}", f, f"{o['impuesto']} · {o['periodo'] or ''}".strip(" ·"),
                       f"{o['entidad']} · formulario {o['formulario'] or '—'} · {o['tipo'] or ''}", hecho,
                       accion=None if hecho else ("presentar", o["id"]), hoy=hoy))
        out[-1]["clave"] = o["clave"]
    return out


def clave_a_revision(clave: str) -> tuple[str, str] | None:
    """DIAN-RET-2026-09 → ('RET','2026-09'); DIAN-IVAB-2026-5 → ('IVA','2026-B5')…"""
    p = clave.split("-")
    try:
        if clave.startswith("DIAN-RET-"):
            return "RET", f"{p[2]}-{p[3]}"
        if clave.startswith("DIAN-IVAB-"):
            return "IVA", f"{p[2]}-B{p[3]}"
        if clave.startswith("SHD-ICAB-"):
            return "ICA", f"{p[2]}-B{p[3]}"
        if clave.startswith("SHD-RETEICA-"):
            return "RETEICA", f"{p[2]}-B{p[3]}"
    except IndexError:
        return None
    return None


def _menos_habiles(f: date, n: int) -> date:
    try:
        from utils.calendario_maestro import es_dia_habil
    except Exception:
        es_dia_habil = lambda d: d.weekday() < 5  # noqa: E731
    d = f
    while n > 0:
        d -= timedelta(days=1)
        if es_dia_habil(d):
            n -= 1
    return d


def _revisiones(impuestos: list[dict], desde: date, hasta: date, hoy: date) -> list[dict]:
    try:
        from modulos import revision_impuestos as ri
        hechas = {(r["impuesto"], r["periodo"]): r for r in ri.listar()}
        etiqueta = ri.etiqueta_periodo
    except Exception:
        return []
    out = []
    for o in impuestos:
        par = clave_a_revision(o.get("clave") or "")
        if not par or o["hecho"]:
            continue
        f = _menos_habiles(o["fecha"], 3)
        if not (desde <= f <= hasta) and not (f < hoy and o["fecha"] >= hoy):
            continue
        r = hechas.get(par)
        titulo = f"Revisar borrador · {etiqueta(*par)}"
        sub = (f"Revisado: {r['veredicto'].lower()}" if r else
               f"Subir borrador y liquidación en Impuestos → Revisión · vence {o['fecha']:%d/%m}")
        out.append(_ev("REVISION", f"rev-{par[0]}-{par[1]}", max(f, hoy) if not r and f < hoy else f, titulo, sub,
                       hecho=bool(r), hoy=hoy))
    return out


def _agente(desde: date, hasta: date, hoy: date) -> list[dict]:
    out = []
    for t in _filas(
        "SELECT id, titulo, modulo, prioridad, recurrencia, fecha_proxima_ejecucion, funcion_callback "
        "FROM calendario_maestro WHERE activa=1 AND fecha_proxima_ejecucion IS NOT NULL"
    ):
        dt = str(t["fecha_proxima_ejecucion"])
        f = _d(dt)
        if not f or f > hasta:
            continue
        hora = dt[11:16] if len(dt) >= 16 else None
        rec = (t.get("recurrencia") or "única vez").lower().replace("_", " ")
        ev = _ev("AGENTE", f"tarea-{t['id']}", max(f, desde) if f < desde else f, t["titulo"],
                 f"{t['modulo']} · {rec}", False, hora=hora,
                 accion=("ejecutar", t["id"]) if t.get("funcion_callback") else None, hoy=hoy,
                 prioridad=t.get("prioridad"))
        if f < hoy:
            ev["nivel"] = "VENCIDO"
        out.append(ev)
    return out


def _personal(desde: date, hasta: date, hoy: date) -> list[dict]:
    out: list[dict] = []
    consultas = [
        ("SELECT id, nombre_completo n, cargo, vencimiento_contrato f FROM contratos_fijos_fenix",
         "Vence contrato · {n}", "{cargo}", "cfijo"),
        ("SELECT id, nombre_completo n, cargo, fecha_preaviso f FROM contratos_fijos_fenix",
         "Preaviso de contrato · {n}", "Último día para avisar la no renovación (30 días)", "cprev"),
        ("SELECT id, nombre_completo n, cargo, fecha_fin f FROM contratos_activos WHERE COALESCE(estado,'ACTIVO')='ACTIVO'",
         "Fin de contrato · {n}", "{cargo}", "cact"),
        ("SELECT id, empleado n, tipo cargo, fecha_fin f FROM contratos_rrhh WHERE COALESCE(estado,'VIGENTE')='VIGENTE'",
         "Fin de contrato · {n}", "{cargo}", "crrhh"),
        ("SELECT id, empleado n, tipo cargo, fecha_vencimiento f FROM examenes_medicos",
         "Vence examen médico · {n}", "{cargo}", "exam"),
        ("SELECT id, nombre_completo n, observaciones cargo, fecha_regreso f FROM vacaciones_fenix",
         "Regresa de vacaciones · {n}", "", "vac"),
    ]
    vistos: set[tuple[str, date]] = set()
    for sql, tit, sub, pref in consultas:
        try:
            filas = _filas(sql)
        except Exception:
            continue
        for r in filas:
            f = _d(r.get("f"))
            if not f or not (desde <= f <= hasta):
                continue
            t = tit.format(n=r.get("n") or "—")
            if (t, f) in vistos:
                continue
            vistos.add((t, f))
            out.append(_ev("PERSONAL", f"{pref}-{r['id']}", f, t, sub.format(cargo=r.get("cargo") or "").strip(),
                           hecho=f < hoy, hoy=hoy))
    try:
        for r in _filas("SELECT id, empleado, fecha_inicio, dias FROM incapacidades"):
            fi = _d(r["fecha_inicio"])
            if fi and r.get("dias"):
                f = fi + timedelta(days=int(r["dias"]) - 1)
                if desde <= f <= hasta:
                    out.append(_ev("PERSONAL", f"inc-{r['id']}", f, f"Termina incapacidad · {r['empleado']}",
                                   f"{r['dias']} días", hecho=f < hoy, hoy=hoy))
    except Exception:
        pass
    try:
        meses = {m: i for i, m in enumerate(["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct",
                                              "nov", "dic"], start=1)}
        for r in _filas("SELECT id, nombre, dia, mes FROM cumpleanos_fenix"):
            try:
                dia = int(str(r["dia"]).strip())
                m = str(r["mes"]).strip().lower()
                mes = int(m) if m.isdigit() else meses.get(m[:3])
                for anio in {desde.year, hasta.year}:
                    f = date(anio, mes, dia)
                    if desde <= f <= hasta:
                        out.append(_ev("PERSONAL", f"cumple-{r['id']}-{anio}", f, f"Cumpleaños · {r['nombre']}",
                                       "Felicitar", hoy=hoy))
                        out[-1]["nivel"] = "PROGRAMADO" if f != hoy else "HOY"
            except (TypeError, ValueError):
                continue
    except Exception:
        pass
    return out


def _cxp(desde: date, hasta: date, hoy: date) -> list[dict]:
    out = []
    for r in _filas("SELECT id, proveedor, concepto, monto, fecha_pago, estado FROM cxp_programados "
                    "WHERE fecha_pago BETWEEN ? AND ?", (desde.isoformat(), hasta.isoformat())):
        f = _d(r["fecha_pago"])
        if f:
            out.append(_ev("CXP", f"cxp-{r['id']}", f, r.get("proveedor") or "Proveedor", r.get("concepto") or "",
                           hecho=str(r.get("estado") or "").upper() in ("PAGADO", "PAGO"), valor=r.get("monto"),
                           hoy=hoy))
    return out


def _festivos(desde: date, hasta: date, hoy: date) -> list[dict]:
    try:
        from utils.calendario_maestro import get_festivos_colombia
    except Exception:
        return []
    out = []
    for anio in {desde.year, hasta.year}:
        for f in get_festivos_colombia(anio):
            if desde <= f <= hasta:
                ev = _ev("FESTIVO", f"fest-{f}", f, "Festivo en Colombia", "No hay bancos ni DIAN", hoy=hoy)
                ev["nivel"] = "PROGRAMADO"
                out.append(ev)
    return out


# ───────────────────────── API ─────────────────────────

def eventos(desde: date, hasta: date, fuentes: tuple[str, ...] | None = None, hoy: date | None = None,
            incluir_hechos: bool = True) -> list[dict[str, Any]]:
    """Eventos de todas las fuentes entre desde y hasta (más lo vencido pendiente)."""
    hoy = hoy or date.today()
    todo: list[dict] = []
    imps: list[dict] = []
    for nombre, fn in [("PAGOS", _pagos), ("IMPUESTOS", _impuestos), ("AGENTE", _agente),
                       ("PERSONAL", _personal), ("CXP", _cxp), ("FESTIVO", _festivos)]:
        try:
            evs = fn(desde, hasta, hoy)
        except Exception as e:  # tabla inexistente o datos raros: no tumbar la agenda
            logger.debug("Agenda: fuente %s no disponible: %s", nombre, e)
            evs = []
        if nombre == "IMPUESTOS":
            imps = evs
        todo += evs
    try:
        todo += _revisiones(imps, desde, hasta, hoy)
    except Exception as e:
        logger.debug("Agenda: revisiones no disponibles: %s", e)
    if fuentes:
        todo = [e for e in todo if e["fuente"] in fuentes]
    if not incluir_hechos:
        todo = [e for e in todo if not e["hecho"]]
    todo.sort(key=lambda e: (e["fecha"], ORDEN_NIVEL.get(e["nivel"], 9), e["hora"] or "99", e["titulo"]))
    return todo


def resumen(hoy: date | None = None) -> dict[str, Any]:
    hoy = hoy or date.today()
    evs = eventos(hoy - timedelta(days=60), hoy + timedelta(days=30), hoy=hoy)
    abiertos = [e for e in evs if not e["hecho"] and e["fuente"] not in ("FESTIVO",)]
    semana = [e for e in abiertos if hoy <= e["fecha"] <= hoy + timedelta(days=7) and e["fuente"] != "AGENTE"]
    r = {
        "vencidos": sum(1 for e in abiertos if e["nivel"] == "VENCIDO" and e["fuente"] != "AGENTE"),
        "hoy": sum(1 for e in abiertos if e["fecha"] == hoy and e["fuente"] != "AGENTE"),
        "semana": len(semana),
        "valor_semana": sum(e["valor"] or 0 for e in semana if e["fuente"] in ("PAGOS", "CXP")),
        "impuestos_30": sum(1 for e in abiertos if e["fuente"] == "IMPUESTOS" and e["fecha"] <= hoy + timedelta(days=30)),
        "revisiones_pend": sum(1 for e in abiertos if e["fuente"] == "REVISION"),
        "automatizaciones_hoy": sum(1 for e in evs if e["fuente"] == "AGENTE" and e["fecha"] == hoy),
        "por_fuente": {f: sum(1 for e in abiertos if e["fuente"] == f) for f in FUENTES},
    }
    try:
        fallas = _filas("SELECT COUNT(*) n FROM log_ejecuciones_calendario WHERE estado='ERROR' "
                        "AND fecha_ejecucion >= ?", ((hoy - timedelta(days=1)).isoformat(),))
        r["fallas_24h"] = fallas[0]["n"] if fallas else 0
    except Exception:
        r["fallas_24h"] = 0
    return r


def ejecutar_accion(accion: tuple[str, int], por: str = "agenda") -> dict[str, Any]:
    tipo, oid = accion
    if tipo == "pagar":
        from modulos import control_pagos as cp
        return cp.marcar_pagado(oid, por=por)
    if tipo == "presentar":
        from modulos import radar_tributario as rt
        return rt.marcar_presentado(oid, por=por)
    if tipo == "ejecutar":
        from utils.calendario_maestro import ejecutar_tarea_por_id
        ejecutar_tarea_por_id(oid)
        return {"ok": True}
    return {"ok": False, "error": "acción desconocida"}
