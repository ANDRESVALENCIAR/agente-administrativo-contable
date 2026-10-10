"""
Motor de alertas de Shaki — alertas VIVAS, sin duplicados y que se cierran solas.

Cómo funciona
-------------
1. Cada REGLA mira los datos reales (control de pagos, radar tributario, revisiones de impuestos,
   calendario maestro, personal, cartera, canales de envío…) y devuelve las condiciones que hoy
   requieren atención, cada una con una CLAVE estable (p. ej. "pago:123", "imp:DIAN-RET-2026-09").
2. escanear() sincroniza con la tabla `alertas`:
     · clave nueva          → crea la alerta (y si es CRÍTICA, avisa por correo de inmediato)
     · clave que sigue viva → actualiza nivel/texto y "última vez"
     · clave que desaparece → se RESUELVE SOLA ("auto: la condición ya no existe")
3. Posponer (1 día / 1 semana) la oculta hasta esa fecha; si la condición sigue, vuelve sola.
4. Resumen diario por correo (07:00) con todo lo abierto, ordenado por gravedad.

Las alertas que crean otros módulos con crear_alerta() siguen funcionando (origen MODULO);
las manuales quedan con origen MANUAL. Las alertas viejas duplicadas u obsoletas del sistema
anterior se limpian una sola vez (migración).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from html import escape
from typing import Any, Callable

from config import cfg
from database import get_conn

logger = logging.getLogger(__name__)

NIVELES = ("CRITICO", "URGENTE", "AVISO", "INFO")
PESO = {"CRITICO": 25, "URGENTE": 10, "AVISO": 3, "INFO": 0}
COLOR = {"CRITICO": "#E5484D", "URGENTE": "#FF6A3D", "AVISO": "#F5C542", "INFO": "#8B8B93"}
NOMBRE_NIVEL = {"CRITICO": "Crítica", "URGENTE": "Urgente", "AVISO": "Aviso", "INFO": "Info"}
MODULOS = {"pagos": "Pagos", "impuestos": "Impuestos", "revision": "Revisión impuestos", "agente": "Agente",
           "personal": "Personal", "creditos": "Cartera", "sistema": "Sistema", "juridico": "Jurídico",
           "manual": "Manual"}


def _p(v: Any) -> str:
    try:
        return "$" + f"{float(v):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


def _d(v: Any) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _filas(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()


def A(clave: str, nivel: str, modulo: str, titulo: str, detalle: str = "", valor: float | None = None,
      accion: tuple[str, int] | None = None, ir_a: str | None = None, fecha: date | None = None) -> dict[str, Any]:
    return {"clave": clave, "nivel": nivel, "modulo": modulo, "titulo": titulo, "detalle": detalle, "valor": valor,
            "accion": list(accion) if accion else None, "ir_a": ir_a, "fecha": fecha.isoformat() if fecha else None}


# ───────────────────────── Esquema ─────────────────────────

_COLS_NUEVAS = {
    "clave": "TEXT", "origen": "TEXT DEFAULT 'MODULO'", "valor": "REAL", "accion": "TEXT", "ir_a": "TEXT",
    "fecha_objetivo": "DATE", "ultima_vez": "DATETIME", "veces": "INTEGER DEFAULT 1", "pospuesta_hasta": "DATETIME",
    "notificada_en": "DATETIME", "resuelta_por": "TEXT",
}


def inicializar() -> None:
    conn = get_conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(alertas)").fetchall()}
    if not cols:
        conn.close()
        from database import inicializar_db
        inicializar_db()
        conn = get_conn()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(alertas)").fetchall()}
    for c, t in _COLS_NUEVAS.items():
        if c not in cols:
            conn.execute(f"ALTER TABLE alertas ADD COLUMN {c} {t}")
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_alertas_clave ON alertas(clave, resuelto);
        CREATE TABLE IF NOT EXISTS alertas_meta (clave TEXT PRIMARY KEY, valor TEXT);
        CREATE TABLE IF NOT EXISTS alertas_envios (
            id INTEGER PRIMARY KEY AUTOINCREMENT, enviado_en DATETIME DEFAULT (datetime('now','localtime')),
            tipo TEXT, destino TEXT, n_alertas INTEGER, ok INTEGER);
        """
    )
    conn.commit()
    conn.close()
    _migrar_una_vez()


def meta(clave: str, valor: str | None = None) -> str | None:
    conn = get_conn()
    if valor is None:
        r = conn.execute("SELECT valor FROM alertas_meta WHERE clave=?", (clave,)).fetchone()
        conn.close()
        return r[0] if r else None
    conn.execute("INSERT INTO alertas_meta(clave, valor) VALUES(?,?) ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
                 (clave, valor))
    conn.commit()
    conn.close()
    return valor


LEGADO = ("revisar_pagos_pendientes", "alerta_pagos_manana", "alerta_nomina_semanal", "alerta_vencimiento_impuesto")


def _apagar_generadores_viejos() -> int:
    """Las tareas viejas creaban una alerta NUEVA en cada corrida (miles de duplicadas); el motor las reemplaza."""
    try:
        conn = get_conn()
        n = conn.execute(f"UPDATE calendario_maestro SET activa=0 WHERE activa=1 AND funcion_callback IN "
                         f"({','.join('?' * len(LEGADO))})", LEGADO).rowcount
        conn.commit()
        conn.close()
        return n
    except Exception:
        return 0


def _migrar_una_vez() -> None:
    """Cierra las alertas automáticas del sistema viejo (conteos sin detalle, duplicadas por mayúsculas)."""
    if meta("migracion_v2"):
        return
    _apagar_generadores_viejos()
    conn = get_conn()
    ahora = datetime.now().isoformat(sep=" ", timespec="seconds")
    patrones = ["%pago(s) VENCIDO(S)%", "%pago(s) vencen HOY%", "%impuesto(s) vencen en%", "%APROBADO(S) por ejecutar%",
                "Impuesto % vence pronto", "Contrato vence:%", "Examen médico:%", "Pago programado:%", "Mora crítica:%",
                "Dotación pendiente:%", "Dotación próxima:%", "Vacaciones pendientes:%"]
    n = 0
    for p in patrones:
        n += conn.execute(
            "UPDATE alertas SET resuelto=1, fecha_resolucion=?, resuelta_por='migración: reemplazada por el motor nuevo' "
            "WHERE resuelto=0 AND clave IS NULL AND titulo LIKE ?", (ahora, p)).rowcount
    # duplicadas: mismo título y módulo (sin importar mayúsculas) → deja la más antigua
    n += conn.execute(
        """UPDATE alertas SET resuelto=1, fecha_resolucion=?, resuelta_por='migración: duplicada'
           WHERE resuelto=0 AND clave IS NULL AND id NOT IN (
             SELECT MIN(id) FROM alertas WHERE resuelto=0 AND clave IS NULL GROUP BY LOWER(modulo), LOWER(titulo))""",
        (ahora,)).rowcount
    conn.execute("UPDATE alertas SET origen='MANUAL' WHERE origen IS NULL AND LOWER(modulo)='manual'")
    conn.execute("UPDATE alertas SET origen='MODULO' WHERE origen IS NULL")
    conn.commit()
    conn.close()
    meta("migracion_v2", f"{datetime.now():%Y-%m-%d %H:%M} · {n} alertas viejas cerradas")


# ───────────────────────── Reglas ─────────────────────────

def r_pagos(hoy: date) -> list[dict]:
    out = []
    try:
        filas = _filas("SELECT id, detalle, proveedor, valor, fecha_sugerida, fecha_limite, estado FROM pagos_calendario "
                       "WHERE estado IN ('PENDIENTE','EN PROCESO') AND fecha_sugerida <= ?",
                       ((hoy + timedelta(days=1)).isoformat(),))
    except Exception:
        return out
    viejos = []
    for p in filas:
        fs, fl = _d(p["fecha_sugerida"]), _d(p["fecha_limite"]) or _d(p["fecha_sugerida"])
        nombre = p["detalle"] or p["proveedor"] or "Pago"
        if fl and (hoy - fl).days > 45:
            viejos.append(p)
            continue
        if fl and fl < hoy:
            nivel, cuando = "CRITICO", f"venció hace {(hoy - fl).days} día(s) ({fl:%d/%m})"
        elif fs and fs < hoy:
            nivel, cuando = "URGENTE", f"fecha sugerida {fs:%d/%m} pasada · límite {fl:%d/%m}"
        elif fs == hoy:
            nivel, cuando = "URGENTE", "se paga HOY"
        else:
            nivel, cuando = "AVISO", "se paga mañana"
        out.append(A(f"pago:{p['id']}", nivel, "pagos", nombre,
                     " · ".join(x for x in [p.get("proveedor"), cuando] if x), p.get("valor"),
                     accion=("pagar", p["id"]), ir_a="Pagos", fecha=fl))
    if viejos:
        total = sum(p.get("valor") or 0 for p in viejos)
        out.append(A("pagos:viejos", "AVISO", "pagos", f"{len(viejos)} pagos con más de 45 días sin marcar",
                     "Probablemente ya se pagaron y no se marcaron. Revíselos en Pagos → Control de pagos y márquelos "
                     "como pagados o anulados: " + "; ".join((p["detalle"] or "")[:40] for p in viejos[:5])
                     + ("…" if len(viejos) > 5 else ""), total or None, ir_a="Pagos"))
    try:
        n = _filas("SELECT COUNT(*) n FROM pagos_calendario WHERE excel_pendiente=1")[0]["n"]
        if n:
            out.append(A("pagos:excel", "AVISO", "pagos", f"{n} pago(s) marcados no se han escrito en el Excel",
                         "El archivo de control de pagos estaba abierto. Ciérrelo y Shaki lo actualiza en la próxima "
                         "lectura (7:30 a. m.) o desde Pagos → Control de pagos.", ir_a="Pagos"))
    except Exception:
        pass
    return out


def r_impuestos(hoy: date) -> list[dict]:
    out = []
    try:
        filas = _filas("SELECT id, clave, entidad, impuesto, periodo, formulario, fecha_limite FROM impuestos_obligaciones "
                       "WHERE estado='PENDIENTE' AND fecha_limite <= ?", ((hoy + timedelta(days=7)).isoformat(),))
    except Exception:
        return out
    for o in filas:
        f = _d(o["fecha_limite"])
        d = (f - hoy).days
        if d < 0:
            nivel, cuando = "CRITICO", f"VENCIÓ hace {-d} día(s): se causan sanción e intereses"
        elif d <= 1:
            nivel, cuando = "CRITICO", "vence HOY" if d == 0 else "vence MAÑANA"
        elif d <= 3:
            nivel, cuando = "URGENTE", f"vence en {d} días ({f:%d/%m})"
        else:
            nivel, cuando = "AVISO", f"vence en {d} días ({f:%d/%m})"
        out.append(A(f"imp:{o['clave']}", nivel, "impuestos", f"{o['impuesto']} · {o['periodo']}",
                     f"{o['entidad']} · formulario {o['formulario'] or '—'} · {cuando}",
                     accion=("presentar", o["id"]), ir_a="Impuestos", fecha=f))
    return out


def r_revisiones(hoy: date) -> list[dict]:
    out: list[dict] = []
    try:
        from modulos import agenda_unificada as ag
        from modulos import revision_impuestos as ri
        hechas = {}
        for r in ri.listar():
            hechas.setdefault((r["impuesto"], r["periodo"]), r)
        obls = _filas("SELECT clave, impuesto, periodo, fecha_limite FROM impuestos_obligaciones "
                      "WHERE estado='PENDIENTE' AND fecha_limite BETWEEN ? AND ?",
                      (hoy.isoformat(), (hoy + timedelta(days=5)).isoformat()))
    except Exception:
        return out
    for o in obls:
        par = ag.clave_a_revision(o["clave"])
        if par and par not in hechas:
            f = _d(o["fecha_limite"])
            out.append(A(f"rev:{par[0]}:{par[1]}", "URGENTE", "revision",
                         f"Falta revisar el borrador de {o['impuesto']} {o['periodo']}",
                         f"Vence el {f:%d/%m}. Suba el borrador y la liquidación del contador en Impuestos → Revisión "
                         "de impuestos antes de presentar.", ir_a="Impuestos", fecha=f))
    # hallazgos críticos de la última revisión de cada periodo (últimos 75 días)
    desde = (hoy - timedelta(days=75)).isoformat()
    for (imp, per), r in hechas.items():
        if str(r["creado_en"])[:10] < desde:
            continue
        try:
            res = json.loads(r.get("resultado_json") or "{}")
        except ValueError:
            continue
        etq = ri.etiqueta_periodo(imp, per)
        for f in (res.get("tablas", {}).get("pagos_retencion") or []):
            if f.get("pagado") in (None, "None") and f.get("estado") == "CRITICO" and f.get("vence"):
                venc = _d(f["vence"])
                if venc and venc < hoy:
                    lim = venc + timedelta(days=61)
                    out.append(A(f"retsinpago:{f['periodo']}", "CRITICO", "revision",
                                 f"Retención de {f['periodo']} sin pagar",
                                 f"Venció el {venc:%d/%m/%Y}. "
                                 + (f"Pagar a más tardar el {lim:%d/%m/%Y} para que la declaración no quede sin efecto "
                                    "(art. 580-1 ET)." if hoy <= lim else
                                    "Ya pasaron 2 meses: la declaración presentada sin pago no tiene efecto (art. 580-1 ET).")
                                 + f" Detectado en la revisión de {etq}.", f.get("valor"), ir_a="Impuestos", fecha=venc))
        for h in res.get("hallazgos", []):
            if h.get("nivel") == "CRITICO" and h.get("area") != "Pagos":
                out.append(A(f"hallazgo:{imp}:{per}:{h['titulo'][:60]}", "CRITICO", "revision",
                             f"{etq}: {h['titulo']}", h.get("accion") or h.get("detalle") or "", h.get("valor"),
                             ir_a="Impuestos"))
            elif h.get("titulo", "").startswith("La obligación de ReteICA no está activa"):
                try:
                    from modulos import radar_tributario as rt
                    if not rt.perfil().get("RETEICA"):
                        out.append(A("perfil:reteica", "URGENTE", "impuestos",
                                     "ReteICA no está activo en el radar tributario",
                                     "La contabilidad muestra que EIF retiene ICA: actívelo en Impuestos → Radar → "
                                     "Obligaciones y alertas para recibir los avisos de cada bimestre.", ir_a="Impuestos"))
                except Exception:
                    pass
    return out


def r_agente(hoy: date) -> list[dict]:
    out = []
    try:
        errores = _filas("SELECT tarea_id, titulo, COUNT(*) n, MAX(fecha_ejecucion) ultima, MAX(error) error "
                         "FROM log_ejecuciones_calendario WHERE estado='ERROR' AND fecha_ejecucion >= ? "
                         "GROUP BY tarea_id, titulo", ((datetime.now() - timedelta(hours=24)).isoformat(sep=" "),))
        for e in errores:
            out.append(A(f"tareaerr:{e['tarea_id']}", "URGENTE", "agente", f"Falla en la tarea automática: {e['titulo']}",
                         f"{e['n']} error(es) en 24 h. Último: {str(e['error'] or '')[:180]}",
                         accion=("ejecutar", e["tarea_id"]), ir_a="Calendario"))
        limite = (datetime.now() - timedelta(hours=3)).isoformat(sep="T", timespec="seconds")
        atrasadas = _filas("SELECT id, titulo FROM calendario_maestro WHERE activa=1 AND funcion_callback IS NOT NULL "
                           "AND fecha_proxima_ejecucion < ?", (limite,))
        if atrasadas:
            out.append(A("agente:atrasado", "URGENTE", "agente",
                         f"El agente tiene {len(atrasadas)} tarea(s) automáticas atrasadas",
                         "Puede que Shaki haya estado apagado. Tareas: " + ", ".join(a["titulo"] for a in atrasadas[:4])
                         + ". Deje Shaki abierto (o active el arranque 24/7) para que las alertas salgan solas.",
                         ir_a="Calendario"))
    except Exception:
        pass
    return out


def r_canales(hoy: date) -> list[dict]:
    out = []
    try:
        from conexiones.notificador import canal_correo
        if not canal_correo():
            out.append(A("canal:correo", "URGENTE", "sistema", "Las alertas por correo no se están enviando",
                         "No hay cuenta de correo configurada en este computador. Ejecute scripts\\configurar_correo.ps1.",
                         ir_a="Pagos"))
    except Exception:
        pass
    return out


def r_personal(hoy: date) -> list[dict]:
    out = []
    consultas = [
        ("SELECT id, nombre_completo n, fecha_preaviso f FROM contratos_fijos_fenix", "preaviso", 15,
         "Preaviso de contrato: {n}", "Último día para avisar si no se renueva el contrato: {f}.", "URGENTE"),
        ("SELECT id, nombre_completo n, vencimiento_contrato f FROM contratos_fijos_fenix", "contrato", 30,
         "Vence contrato: {n}", "Fecha de vencimiento: {f}.", "AVISO"),
        ("SELECT id, empleado n, fecha_fin f FROM contratos_rrhh WHERE estado='VIGENTE'", "contratorrhh", 30,
         "Vence contrato: {n}", "Fin del contrato: {f}.", "AVISO"),
        ("SELECT id, empleado n, fecha_vencimiento f FROM examenes_medicos", "examen", 30,
         "Examen médico por vencer: {n}", "Vence: {f}.", "AVISO"),
        ("SELECT id, empleado n, proxima_entrega f FROM dotacion WHERE proxima_entrega IS NOT NULL", "dotacion", 15,
         "Entrega de dotación: {n}", "Próxima entrega: {f}.", "AVISO"),
    ]
    for sql, pref, dias, tit, det, nivel in consultas:
        try:
            filas = _filas(sql)
        except Exception:
            continue
        for r in filas:
            f = _d(r.get("f"))
            if not f or f > hoy + timedelta(days=dias) or f < hoy - timedelta(days=60):
                continue
            niv = "URGENTE" if f <= hoy + timedelta(days=3) and nivel == "AVISO" else nivel
            out.append(A(f"{pref}:{r['id']}", niv, "personal", tit.format(n=r.get("n") or "—"),
                         det.format(f=f.strftime("%d/%m/%Y")) + (" (ya pasó)" if f < hoy else ""), ir_a="Personal",
                         fecha=f))
    try:
        for r in _filas("SELECT id, empleado, fecha_inicio FROM novedades_rrhh WHERE estado='PENDIENTE' AND tipo='Vacaciones'"):
            out.append(A(f"vac:{r['id']}", "AVISO", "personal", f"Vacaciones por aprobar: {r['empleado']}",
                         f"Desde {r['fecha_inicio']}.", ir_a="Personal"))
    except Exception:
        pass
    return out


def r_cartera_cxp(hoy: date) -> list[dict]:
    out = []
    try:
        for r in _filas("SELECT id, cliente, dias_mora, saldo FROM cartera_cxc WHERE dias_mora > 30"):
            out.append(A(f"mora:{r['id']}", "CRITICO" if r["dias_mora"] > 60 else "AVISO", "creditos",
                         f"Mora de {r['dias_mora']} días: {r['cliente']}", "Cartera vencida por cobrar.", r.get("saldo"),
                         ir_a="Créditos"))
    except Exception:
        pass
    try:
        for r in _filas("SELECT id, proveedor, concepto, monto, fecha_pago FROM cxp_programados "
                        "WHERE estado='PROGRAMADO' AND fecha_pago <= ?", ((hoy + timedelta(days=1)).isoformat(),)):
            f = _d(r["fecha_pago"])
            out.append(A(f"cxp:{r['id']}", "CRITICO" if f and f < hoy else "URGENTE", "pagos",
                         f"Pago a proveedor: {r['proveedor']}", f"{r.get('concepto') or ''} · {f:%d/%m}" if f else "",
                         r.get("monto"), ir_a="CXP / CXC", fecha=f))
    except Exception:
        pass
    return out


REGLAS: dict[str, dict[str, Any]] = {
    "pagos": {"nombre": "Pagos del control de pagos", "fn": r_pagos,
              "desc": "Vencidos (crítica), fecha sugerida pasada u hoy (urgente), mañana (aviso), pagos viejos sin marcar y Excel sin actualizar."},
    "impuestos": {"nombre": "Declaraciones DIAN y SHD", "fn": r_impuestos,
                  "desc": "Vencida o vence hoy/mañana (crítica), ≤3 días (urgente), ≤7 días (aviso)."},
    "revision": {"nombre": "Revisión de impuestos", "fn": r_revisiones,
                 "desc": "Borrador sin revisar a 5 días del vencimiento, hallazgos críticos y retenciones sin pagar detectadas."},
    "agente": {"nombre": "Salud del agente", "fn": r_agente,
               "desc": "Tareas automáticas con error en 24 h o atrasadas más de 3 horas."},
    "canales": {"nombre": "Canales de aviso", "fn": r_canales, "desc": "Correo de alertas sin configurar."},
    "personal": {"nombre": "Personal", "fn": r_personal,
                 "desc": "Preavisos y vencimientos de contrato, exámenes médicos, dotación y vacaciones por aprobar."},
    "cartera": {"nombre": "Cartera y proveedores", "fn": r_cartera_cxp,
                "desc": "Clientes con más de 30/60 días de mora y pagos programados a proveedores."},
}


def reglas_activas() -> dict[str, bool]:
    try:
        guardado = json.loads(meta("reglas") or "{}")
    except ValueError:
        guardado = {}
    return {k: bool(guardado.get(k, True)) for k in REGLAS}


def guardar_reglas(estado: dict[str, bool]) -> None:
    meta("reglas", json.dumps(estado))


def evaluar(hoy: date | None = None) -> list[dict]:
    hoy = hoy or date.today()
    out: list[dict] = []
    activas = reglas_activas()
    for k, r in REGLAS.items():
        if not activas.get(k):
            continue
        try:
            for a in r["fn"](hoy):
                a["regla"] = k
                out.append(a)
        except Exception as e:  # una regla rota no tumba las demás
            logger.warning("Regla de alertas %s falló: %s", k, e)
    vistas: dict[str, dict] = {}
    for a in out:
        vistas.setdefault(a["clave"], a)
    return list(vistas.values())


# ───────────────────────── Sincronización ─────────────────────────

def escanear(hoy: date | None = None, notificar: bool = True) -> dict[str, int]:
    """Evalúa reglas y sincroniza con la tabla alertas. Devuelve {nuevas, actualizadas, resueltas, notificadas}."""
    inicializar()
    ahora = datetime.now().isoformat(sep=" ", timespec="seconds")
    actuales = {a["clave"]: a for a in evaluar(hoy)}
    conn = get_conn()
    abiertas = {r[1]: r[0] for r in conn.execute(
        "SELECT id, clave FROM alertas WHERE resuelto=0 AND origen='MOTOR' AND clave IS NOT NULL").fetchall()}
    # lo que el usuario resolvió a mano no se reabre en 7 días, salvo que empeore de nivel
    rango = {n: i for i, n in enumerate(NIVELES)}
    silenciadas = {r[0]: r[1] for r in conn.execute(
        "SELECT clave, nivel FROM alertas WHERE resuelto=1 AND origen='MOTOR' AND resuelta_por='usuario' "
        "AND fecha_resolucion >= ?", ((datetime.now() - timedelta(days=7)).isoformat(sep=" "),)).fetchall()}
    nuevas, act, res = [], 0, 0
    for clave, a in actuales.items():
        if clave not in abiertas and clave in silenciadas and rango[a["nivel"]] >= rango.get(silenciadas[clave], 9):
            continue
        campos = (a["nivel"], a["modulo"], a["titulo"][:250], a["detalle"][:1500],
                  a["valor"], json.dumps(a["accion"]) if a["accion"] else None, a["ir_a"], a["fecha"])
        if clave in abiertas:
            conn.execute("UPDATE alertas SET nivel=?, modulo=?, titulo=?, descripcion=?, valor=?, accion=?, ir_a=?, "
                         "fecha_objetivo=?, ultima_vez=?, veces=COALESCE(veces,1)+1 WHERE id=?",
                         (*campos, ahora, abiertas[clave]))
            act += 1
        else:
            cur = conn.execute("INSERT INTO alertas (nivel, modulo, titulo, descripcion, valor, accion, ir_a, fecha_objetivo, "
                               "clave, origen, timestamp, ultima_vez, veces) VALUES (?,?,?,?,?,?,?,?,?,'MOTOR',?,?,1)",
                               (*campos, clave, ahora, ahora))
            nuevas.append({**a, "id": cur.lastrowid})
    for clave, aid in abiertas.items():
        if clave not in actuales:
            conn.execute("UPDATE alertas SET resuelto=1, fecha_resolucion=?, resuelta_por='auto: la condición ya no existe' "
                         "WHERE id=?", (ahora, aid))
            res += 1
    conn.commit()
    conn.close()
    meta("ultimo_escaneo", ahora)
    if not meta("primer_escaneo"):          # el primer escaneo carga lo existente sin mandar correos
        meta("primer_escaneo", ahora)
        notificar = False
    notificadas = 0
    if notificar:
        criticas = [a for a in nuevas if a["nivel"] == "CRITICO"]
        if criticas:
            notificadas = _enviar(criticas, inmediato=True)
    return {"nuevas": len(nuevas), "actualizadas": act, "resueltas": res, "notificadas": notificadas,
            "vivas": len(actuales)}


def escanear_si_toca(minutos: int = 5) -> dict[str, int] | None:
    """Para la carga del dashboard: escanea como máximo cada `minutos`."""
    try:
        inicializar()
        u = meta("ultimo_escaneo")
        if u and datetime.now() - datetime.fromisoformat(u) < timedelta(minutes=minutos):
            return None
        return escanear()
    except Exception as e:
        logger.warning("Motor de alertas: %s", e)
        return None


# ───────────────────────── Consultas y acciones ─────────────────────────

def listar(estado: str = "ACTIVAS", dias_historial: int = 30) -> list[dict[str, Any]]:
    inicializar()
    ahora = datetime.now().isoformat(sep=" ", timespec="seconds")
    orden = ("ORDER BY CASE nivel WHEN 'CRITICO' THEN 1 WHEN 'URGENTE' THEN 2 WHEN 'AVISO' THEN 3 ELSE 4 END, "
             "COALESCE(fecha_objetivo,'9999'), timestamp DESC")
    if estado == "ACTIVAS":
        sql = f"SELECT * FROM alertas WHERE resuelto=0 AND (pospuesta_hasta IS NULL OR pospuesta_hasta <= ?) {orden}"
        params: tuple = (ahora,)
    elif estado == "POSPUESTAS":
        sql = f"SELECT * FROM alertas WHERE resuelto=0 AND pospuesta_hasta > ? {orden}"
        params = (ahora,)
    else:
        sql = "SELECT * FROM alertas WHERE resuelto=1 AND fecha_resolucion >= ? ORDER BY fecha_resolucion DESC LIMIT 300"
        params = ((datetime.now() - timedelta(days=dias_historial)).isoformat(sep=" "),)
    filas = _filas(sql, params)
    for f in filas:
        try:
            f["accion"] = json.loads(f["accion"]) if f.get("accion") else None
        except ValueError:
            f["accion"] = None
    return filas


def resolver(aid: int, por: str = "usuario") -> None:
    conn = get_conn()
    conn.execute("UPDATE alertas SET resuelto=1, fecha_resolucion=?, resuelta_por=? WHERE id=?",
                 (datetime.now().isoformat(sep=" ", timespec="seconds"), por, aid))
    conn.commit()
    conn.close()


def posponer(aid: int, horas: int) -> None:
    hasta = (datetime.now() + timedelta(hours=horas)).isoformat(sep=" ", timespec="seconds")
    conn = get_conn()
    conn.execute("UPDATE alertas SET pospuesta_hasta=?, visto=1 WHERE id=?", (hasta, aid))
    conn.commit()
    conn.close()


def reactivar(aid: int) -> None:
    conn = get_conn()
    conn.execute("UPDATE alertas SET pospuesta_hasta=NULL WHERE id=?", (aid,))
    conn.commit()
    conn.close()


def ejecutar_accion(alerta: dict[str, Any]) -> dict[str, Any]:
    """Pagué / Presenté / Ejecutar desde la alerta; luego re-escanea para que se cierre sola."""
    from modulos import agenda_unificada as ag
    acc = alerta.get("accion")
    if not acc:
        return {"ok": False}
    r = ag.ejecutar_accion((acc[0], int(acc[1])), por="centro de alertas")
    escanear(notificar=False)
    return r if isinstance(r, dict) else {"ok": True}


def salud(alertas: list[dict] | None = None) -> int:
    """0–100: 100 = nada pendiente."""
    alertas = listar() if alertas is None else alertas
    carga = sum(PESO.get(a["nivel"], 0) for a in alertas)
    return round(100 / (1 + carga / 40))


# ───────────────────────── Notificaciones ─────────────────────────

def destinos() -> list[str]:
    raw = getattr(cfg, "ALERTAS_EMAILS", None) or getattr(cfg, "IMPUESTOS_ALERTA_EMAILS", "") or ""
    return [d.strip() for d in str(raw).replace(";", ",").split(",") if d.strip()]


def html_resumen(alertas: list[dict], titulo: str, intro: str) -> str:
    filas = []
    for a in alertas[:40]:
        c = COLOR.get(a["nivel"], "#8B8B93")
        filas.append(
            f'<tr><td style="padding:10px 0;border-bottom:1px solid #eee;vertical-align:top;width:86px">'
            f'<span style="display:inline-block;border:1px solid {c};color:{c};border-radius:999px;padding:1px 8px;'
            f'font-size:11px;font-weight:700">{NOMBRE_NIVEL.get(a["nivel"], a["nivel"])}</span></td>'
            f'<td style="padding:10px 0 10px 8px;border-bottom:1px solid #eee"><b style="color:#111">{escape(a["titulo"])}</b>'
            f'<div style="color:#555;font-size:13px;margin-top:2px">{escape(a.get("detalle") or a.get("descripcion") or "")}</div></td>'
            f'<td style="padding:10px 0;border-bottom:1px solid #eee;text-align:right;white-space:nowrap;color:#111">'
            f'{_p(a["valor"]) if a.get("valor") else ""}</td></tr>')
    url = getattr(cfg, "APP_PUBLIC_URL", "http://localhost:8501") or "http://localhost:8501"
    return (f'<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:640px;margin:auto">'
            f'<div style="background:#0B0B0E;color:#fff;border-radius:16px;padding:22px 24px">'
            f'<div style="font-size:11px;letter-spacing:.14em;color:#A1A1AA">SHAKI · CENTRO DE ALERTAS</div>'
            f'<div style="font-size:22px;font-weight:700;margin-top:6px">{escape(titulo)}</div>'
            f'<div style="color:#C4C4CC;margin-top:4px">{escape(intro)}</div></div>'
            f'<table style="width:100%;border-collapse:collapse;margin-top:10px">{"".join(filas)}</table>'
            f'<p style="margin-top:18px"><a href="{escape(url)}" style="background:#111;color:#fff;padding:10px 16px;'
            f'border-radius:10px;text-decoration:none">Abrir Shaki</a></p>'
            f'<p style="color:#999;font-size:12px">Equipos Industriales Fénix S.A.S. · aviso automático de Shaki</p></div>')


def _enviar(alertas: list[dict], inmediato: bool) -> int:
    from conexiones.notificador import enviar_email
    if not alertas:
        return 0
    if inmediato:
        asunto = (f"⚠ Alerta crítica: {alertas[0]['titulo']}" if len(alertas) == 1
                  else f"⚠ {len(alertas)} alertas críticas nuevas en Shaki")
        html = html_resumen(alertas, "Alerta crítica" if len(alertas) == 1 else f"{len(alertas)} alertas críticas",
                            "Esto requiere atención hoy.")
    else:
        n_c = sum(1 for a in alertas if a["nivel"] == "CRITICO")
        asunto = f"Resumen de alertas · {len(alertas)} abiertas" + (f" · {n_c} críticas" if n_c else "")
        html = html_resumen(alertas, f"Buenos días: {len(alertas)} alertas abiertas",
                            f"{n_c} críticas · {sum(1 for a in alertas if a['nivel'] == 'URGENTE')} urgentes · "
                            f"{datetime.now():%d/%m/%Y}")
    texto = "\n".join(f"[{a['nivel']}] {a['titulo']} — {a.get('detalle') or a.get('descripcion') or ''}" for a in alertas)
    enviados = 0
    for dest in destinos():
        r = enviar_email(dest, asunto, html, texto)
        conn = get_conn()
        conn.execute("INSERT INTO alertas_envios(tipo, destino, n_alertas, ok) VALUES (?,?,?,?)",
                     ("inmediata" if inmediato else "resumen", dest, len(alertas), None if r is None else int(bool(r))))
        if r and inmediato:
            conn.executemany("UPDATE alertas SET notificada_en=datetime('now','localtime') WHERE id=?",
                             [(a["id"],) for a in alertas if a.get("id")])
        conn.commit()
        conn.close()
        enviados += bool(r)
    return enviados


def enviar_resumen_diario() -> dict[str, Any]:
    """Tarea programada 07:00: escanea y manda el resumen de lo abierto (no envía si no hay nada)."""
    escanear(notificar=True)
    abiertas = [a for a in listar() if a["nivel"] in ("CRITICO", "URGENTE", "AVISO")]
    if not abiertas:
        return {"alertas": 0, "correos": 0}
    for a in abiertas:
        a.setdefault("detalle", a.get("descripcion"))
    return {"alertas": len(abiertas), "correos": _enviar(abiertas, inmediato=False)}


def escanear_programado() -> dict[str, int]:
    return escanear(notificar=True)
