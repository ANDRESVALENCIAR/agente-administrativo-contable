"""
Radar tributario — obligaciones DIAN y SHD Bogotá del NIT de la empresa, con alerta 24 h
antes de la PRESENTACIÓN por correo y botón "Ya lo presenté".

- sincronizar(): carga/actualiza impuestos_obligaciones desde el calendario oficial
  (modulos.calendario_tributario_2026) según el perfil de obligaciones.
- enviar_alertas_24h(): un día antes del vencimiento envía correo (solo correo) a
  IMPUESTOS_ALERTA_EMAILS con botón; reclama/libera igual que el control de pagos.
- El botón abre el panel (?presentar=<token>) y marcar_presentado() lo deja al día.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import date, datetime, timedelta
from html import escape
from typing import Any

from config import cfg
from database import crear_alerta, get_conn, registrar_accion
from modulos import calendario_tributario_2026 as cal

logger = logging.getLogger(__name__)

ESTADOS = ("PENDIENTE", "PRESENTADO", "NO APLICA")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]
COLUMNAS = ["id", "clave", "grupo", "entidad", "impuesto", "periodo", "formulario", "tipo", "fecha_limite",
            "estado", "presentado_en", "presentado_por", "referencia", "alerta_24h_enviada", "fuente",
            "url_fuente", "nota"]


# ───────────────────────── BD ─────────────────────────

def inicializar_tablas() -> None:
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS impuestos_obligaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clave TEXT UNIQUE NOT NULL,
            grupo TEXT NOT NULL,
            entidad TEXT NOT NULL,
            impuesto TEXT NOT NULL,
            periodo TEXT,
            formulario TEXT,
            tipo TEXT,
            fecha_limite DATE NOT NULL,
            estado TEXT DEFAULT 'PENDIENTE',
            presentado_en TIMESTAMP,
            presentado_por TEXT,
            referencia TEXT,
            alerta_24h_enviada TIMESTAMP,
            fuente TEXT,
            url_fuente TEXT,
            nota TEXT,
            actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_impobl_fecha ON impuestos_obligaciones(fecha_limite);
        CREATE TABLE IF NOT EXISTS impuestos_obligaciones_alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            obligacion_id INTEGER,
            canal TEXT, destino TEXT, ok INTEGER,
            enviado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS impuestos_radar_meta (clave TEXT PRIMARY KEY, valor TEXT);
        """
    )
    conn.commit()
    conn.close()


def _meta(clave: str, valor: str | None = None) -> str | None:
    conn = get_conn()
    if valor is not None:
        conn.execute(
            "INSERT INTO impuestos_radar_meta(clave, valor) VALUES(?,?) "
            "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (clave, valor))
        conn.commit()
    row = conn.execute("SELECT valor FROM impuestos_radar_meta WHERE clave=?", (clave,)).fetchone()
    conn.close()
    return row[0] if row else None


# ───────────────────────── NIT y perfil ─────────────────────────

def nit_base() -> str:
    nit = (cfg.NIT_EMPRESA or "").replace(".", "").replace(" ", "")
    return nit.split("-")[0] if "-" in nit else nit[:-1]


def calendario_aplica() -> bool:
    b = nit_base()
    return b.endswith(cal.NIT_DOS_DIGITOS)


def perfil() -> dict[str, bool]:
    inicializar_tablas()
    raw = _meta("perfil")
    base = dict(cal.PERFIL_POR_DEFECTO)
    if raw:
        try:
            base.update(json.loads(raw))
        except ValueError:
            pass
    return base


def guardar_perfil(nuevo: dict[str, bool]) -> None:
    _meta("perfil", json.dumps(nuevo))
    sincronizar()


# ───────────────────────── Sincronización ─────────────────────────

def sincronizar() -> dict[str, int]:
    """Inserta/actualiza obligaciones del perfil; las que salen del perfil quedan 'NO APLICA'."""
    inicializar_tablas()
    if not calendario_aplica():
        logger.warning("Radar tributario: el NIT %s no termina en %s; calendario no aplicable",
                       cfg.NIT_EMPRESA, cal.NIT_DOS_DIGITOS)
        return {"nuevas": 0, "actualizadas": 0, "aplica": 0}
    p = perfil()
    hoy_iso = date.today().isoformat()
    conn = get_conn()
    nuevas = act = 0
    for o in cal.obligaciones():
        activo = p.get(o["grupo"], False)
        prev = conn.execute("SELECT id, estado FROM impuestos_obligaciones WHERE clave=?", (o["clave"],)).fetchone()
        if prev is None:
            # Cierre inicial: lo vencido antes de empezar a usar el radar se asume presentado (revisable)
            pasado = activo and o["fecha"] < hoy_iso
            conn.execute(
                """INSERT INTO impuestos_obligaciones (clave, grupo, entidad, impuesto, periodo, formulario, tipo,
                       fecha_limite, estado, presentado_por, nota, fuente, url_fuente)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (o["clave"], o["grupo"], o["entidad"], o["impuesto"], o["periodo"], o["formulario"], o["tipo"],
                 o["fecha"], "PRESENTADO" if pasado else ("PENDIENTE" if activo else "NO APLICA"),
                 "cierre inicial" if pasado else None,
                 f"Cierre inicial {hoy_iso}: se asume presentado, verifique" if pasado else None,
                 o["fuente"], o["url_fuente"]),
            )
            nuevas += 1
            continue
        estado = prev[1]
        if not activo and estado == "PENDIENTE":
            estado = "NO APLICA"
        elif activo and estado == "NO APLICA":
            estado = "PENDIENTE"
        conn.execute(
            """UPDATE impuestos_obligaciones SET grupo=?, entidad=?, impuesto=?, periodo=?, formulario=?, tipo=?,
                   fecha_limite=?, estado=?, fuente=?, url_fuente=?, actualizado_en=CURRENT_TIMESTAMP WHERE id=?""",
            (o["grupo"], o["entidad"], o["impuesto"], o["periodo"], o["formulario"], o["tipo"], o["fecha"],
             estado, o["fuente"], o["url_fuente"], prev[0]),
        )
        act += 1
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM impuestos_obligaciones WHERE estado!='NO APLICA'").fetchone()[0]
    conn.close()
    _meta("ultima_sync", datetime.now().isoformat(timespec="seconds"))
    return {"nuevas": nuevas, "actualizadas": act, "aplica": n}


def desactivar_recordatorios_viejos() -> int:
    """Apaga las tareas del módulo anterior (fechas SHD escritas a mano con errores)."""
    conn = get_conn()
    try:
        cur = conn.execute(
            """UPDATE calendario_maestro SET activa=0
               WHERE activa=1 AND funcion_callback IN
                 ('enviar_recordatorios_vencimientos','revisar_vencimientos','sincronizar_calendario_opendata')"""
        )
        conn.commit()
        return cur.rowcount
    except Exception:
        return 0
    finally:
        conn.close()


def inicializar_y_cargar() -> None:
    inicializar_tablas()
    sincronizar()
    desactivar_recordatorios_viejos()


# ───────────────────────── Consultas ─────────────────────────

def listar(desde: date | None = None, hasta: date | None = None, incluir_no_aplica: bool = False,
           estados: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    sql = f"SELECT {', '.join(COLUMNAS)} FROM impuestos_obligaciones WHERE 1=1"
    params: list[Any] = []
    if not incluir_no_aplica:
        sql += " AND estado!='NO APLICA'"
    if estados:
        sql += f" AND estado IN ({','.join('?' * len(estados))})"
        params += list(estados)
    if desde:
        sql += " AND fecha_limite >= ?"
        params.append(desde.isoformat())
    if hasta:
        sql += " AND fecha_limite <= ?"
        params.append(hasta.isoformat())
    sql += " ORDER BY fecha_limite, entidad, impuesto"
    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(zip(COLUMNAS, r)) for r in rows]


def obtener(oid: int) -> dict[str, Any] | None:
    conn = get_conn()
    r = conn.execute(f"SELECT {', '.join(COLUMNAS)} FROM impuestos_obligaciones WHERE id=?", (oid,)).fetchone()
    conn.close()
    return dict(zip(COLUMNAS, r)) if r else None


def semaforo(o: dict[str, Any], hoy: date | None = None) -> str:
    if o["estado"] == "PRESENTADO":
        return "PRESENTADO"
    if o["estado"] == "NO APLICA":
        return "NO APLICA"
    d = (date.fromisoformat(str(o["fecha_limite"])) - (hoy or date.today())).days
    if d < 0:
        return "VENCIDO"
    if d == 0:
        return "HOY"
    if d == 1:
        return "MAÑANA"
    if d <= 7:
        return "ESTA SEMANA"
    return "PROGRAMADO"


def proxima(hoy: date | None = None) -> dict[str, Any] | None:
    hoy = hoy or date.today()
    filas = listar(hoy, None, estados=("PENDIENTE",))
    return filas[0] if filas else None


def resumen(hoy: date | None = None) -> dict[str, Any]:
    hoy = hoy or date.today()
    todas = listar()
    pend = [o for o in todas if o["estado"] == "PENDIENTE"]
    venc = [o for o in pend if o["fecha_limite"] < hoy.isoformat()]
    prox30 = [o for o in pend if hoy.isoformat() <= o["fecha_limite"] <= (hoy + timedelta(days=30)).isoformat()]
    hasta_hoy = [o for o in todas if o["fecha_limite"] <= hoy.isoformat()]
    present = [o for o in hasta_hoy if o["estado"] == "PRESENTADO"]
    return {
        "total": len(todas), "pendientes": len(pend), "vencidas": len(venc), "prox30": len(prox30),
        "presentadas": len([o for o in todas if o["estado"] == "PRESENTADO"]),
        "cumplimiento": round(100 * len(present) / len(hasta_hoy)) if hasta_hoy else 100,
        "dian": len([o for o in pend if o["entidad"] == "DIAN"]),
        "shd": len([o for o in pend if o["entidad"] != "DIAN"]),
    }


# ───────────────────────── Estados ─────────────────────────

def marcar_presentado(oid: int, por: str = "dashboard", referencia: str | None = None) -> dict[str, Any]:
    o = obtener(oid)
    if not o:
        return {"ok": False}
    if o["estado"] == "PRESENTADO":
        return {"ok": True, "ya_estaba": True}
    conn = get_conn()
    conn.execute(
        """UPDATE impuestos_obligaciones SET estado='PRESENTADO', presentado_en=datetime('now','localtime'),
               presentado_por=?, referencia=COALESCE(?, referencia), actualizado_en=CURRENT_TIMESTAMP WHERE id=?""",
        (por, referencia, oid),
    )
    conn.commit()
    conn.close()
    registrar_accion("impuestos", "marcar_presentado", f"{o['impuesto']} {o['periodo']} ({por})", "EXITOSO")
    return {"ok": True, "ya_estaba": False}


def cambiar_estado(oid: int, estado: str) -> None:
    if estado not in ESTADOS:
        raise ValueError(estado)
    conn = get_conn()
    conn.execute(
        """UPDATE impuestos_obligaciones SET estado=?, presentado_en=CASE WHEN ?='PRESENTADO'
               THEN datetime('now','localtime') ELSE NULL END, actualizado_en=CURRENT_TIMESTAMP WHERE id=?""",
        (estado, estado, oid),
    )
    conn.commit()
    conn.close()


# ───────────────────────── Enlaces firmados ─────────────────────────

def _secreto() -> bytes:
    s = getattr(cfg, "PAGOS_LINK_SECRET", None)
    if s:
        return s.encode()
    from modulos import control_pagos as cp  # reutiliza el secreto generado y guardado en la BD

    return cp._secreto()


def generar_token(oid: int) -> str:
    return f"{oid}.{hmac.new(_secreto(), f'presentar:{oid}'.encode(), hashlib.sha256).hexdigest()[:32]}"


def verificar_token(token: str) -> int | None:
    try:
        a, b = str(token).split(".", 1)
        oid = int(a)
    except (ValueError, AttributeError):
        return None
    return oid if hmac.compare_digest(generar_token(oid).split(".", 1)[1], b) else None


def enlace(oid: int) -> str:
    return f"{getattr(cfg, 'APP_PUBLIC_URL', 'http://localhost:8501')}/?presentar={generar_token(oid)}"


# ───────────────────────── Alerta 24 h (solo correo) ─────────────────────────

def destinos() -> list[str]:
    raw = getattr(cfg, "IMPUESTOS_ALERTA_EMAILS", None) or "directorfenix@viaindustrial.com,gerenciafenix@viaindustrial.com"
    return [e.strip() for e in raw.replace(";", ",").split(",") if e.strip()]


def _fecha_humana(d: date) -> str:
    return f"{DIAS[d.weekday()].capitalize()} {d.day} de {MESES[d.month - 1]}"


def _cuando(o: dict[str, Any], hoy: date | None = None) -> str:
    d = (date.fromisoformat(str(o["fecha_limite"])) - (hoy or date.today())).days
    return "VENCE HOY" if d <= 0 else "VENCE MAÑANA" if d == 1 else f"VENCE EN {d} DÍAS"


def html_correo(obls: list[dict[str, Any]], hoy: date | None = None) -> str:
    bloques = []
    for o in obls:
        f = date.fromisoformat(str(o["fecha_limite"]))
        bloques.append(f"""
        <tr><td style="padding:0 0 16px 0">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#FFFFFF"
                 style="border:1px solid #E4E4E7;border-radius:12px;background:#FFFFFF">
            <tr><td style="padding:18px 20px;font-family:Arial,Helvetica,sans-serif;color:#18181B">
              <div style="font-size:11px;letter-spacing:.08em;color:#4338CA;font-weight:bold">
                PENDIENTE DE PRESENTACIÓN · {_cuando(o, hoy)} · {escape(o['entidad'])}</div>
              <div style="font-size:18px;font-weight:bold;margin:6px 0 4px 0">{escape(o['impuesto'])}</div>
              <div style="font-size:14px;color:#52525B;line-height:1.55">
                Periodo: <b>{escape(o['periodo'] or '')}</b> · Formulario: <b>{escape(o['formulario'] or '')}</b><br>
                Vence: <b>{_fecha_humana(f)}</b> · NIT {escape(cfg.NIT_EMPRESA)}<br>
                <span style="font-size:12px;color:#A1A1AA">{escape(o['fuente'] or '')}</span>
              </div>
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:14px"><tr>
                <td style="background:#18181B;border-radius:999px" bgcolor="#18181B">
                  <a href="{escape(enlace(o['id']))}" style="display:inline-block;padding:12px 22px;
                     font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;color:#FFFFFF;
                     text-decoration:none">✓ Ya lo presenté</a></td></tr></table>
            </td></tr></table>
        </td></tr>""")
    return f"""<!doctype html><html><body style="margin:0;background:#F4F4F5">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F4F5">
      <tr><td align="center" style="padding:24px 12px">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%">
          <tr><td style="padding:0 0 18px 0;font-family:Arial,Helvetica,sans-serif">
            <div style="font-size:20px;font-weight:bold;color:#18181B">Shaki · Radar tributario</div>
            <div style="font-size:14px;color:#52525B;margin-top:4px">{escape(cfg.NOMBRE_EMPRESA)} tiene
              {len(obls)} declaración(es) pendiente(s) de presentar. Cuando la presentes, toca el botón y el
              agente la deja al día.</div></td></tr>
          {''.join(bloques)}
          <tr><td style="font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#A1A1AA;padding-top:6px">
            Mensaje automático del agente administrativo. Verifique siempre en el portal de la entidad.</td></tr>
        </table></td></tr></table></body></html>"""


def texto_plano(obls: list[dict[str, Any]], hoy: date | None = None) -> str:
    return "\n\n".join(
        f"PENDIENTE DE PRESENTACIÓN · {_cuando(o, hoy)}\n{o['impuesto']} — {o['periodo']} ({o['entidad']})\n"
        f"Vence: {_fecha_humana(date.fromisoformat(str(o['fecha_limite'])))}\nYa lo presenté: {enlace(o['id'])}"
        for o in obls
    )


def para_alerta(hoy: date | None = None) -> list[dict[str, Any]]:
    hoy = hoy or date.today()
    conn = get_conn()
    rows = conn.execute(
        f"""SELECT {', '.join(COLUMNAS)} FROM impuestos_obligaciones
            WHERE estado='PENDIENTE' AND fecha_limite IN (?, ?) AND alerta_24h_enviada IS NULL
            ORDER BY fecha_limite, entidad""",
        (hoy.isoformat(), (hoy + timedelta(days=1)).isoformat()),
    ).fetchall()
    conn.close()
    return [dict(zip(COLUMNAS, r)) for r in rows]


def enviar_alerta(obls: list[dict[str, Any]], marcar: bool = True, hoy: date | None = None) -> dict[str, Any]:
    from conexiones.notificador import enviar_email

    vacio = {"obligaciones": 0, "correos": 0, "sin_canal": False, "pendientes": 0}
    if not obls:
        return vacio
    if marcar:
        conn = get_conn()
        tomadas = []
        for o in obls:
            cur = conn.execute(
                "UPDATE impuestos_obligaciones SET alerta_24h_enviada=datetime('now','localtime') "
                "WHERE id=? AND alerta_24h_enviada IS NULL", (o["id"],))
            if cur.rowcount == 1:
                tomadas.append(o)
        conn.commit()
        conn.close()
        obls = tomadas
        if not obls:
            return vacio
    asunto = (f"Pendiente de presentación: {obls[0]['impuesto']} {obls[0]['periodo']} · {_cuando(obls[0], hoy).lower()}"
              if len(obls) == 1 else f"{len(obls)} declaraciones pendientes de presentar")
    html, plano = html_correo(obls, hoy), texto_plano(obls, hoy)
    correos, ok_alguno, sin_canal = 0, False, True
    for dest in destinos():
        r = enviar_email(dest, asunto, html, plano)
        if r is None:
            continue
        sin_canal = False
        correos += bool(r)
        ok_alguno = ok_alguno or bool(r)
        conn = get_conn()
        conn.executemany(
            "INSERT INTO impuestos_obligaciones_alertas(obligacion_id, canal, destino, ok) VALUES (?,?,?,?)",
            [(o["id"], "correo", dest, int(bool(r))) for o in obls])
        conn.commit()
        conn.close()
    if marcar and not ok_alguno:
        conn = get_conn()
        conn.executemany("UPDATE impuestos_obligaciones SET alerta_24h_enviada=NULL WHERE id=?",
                         [(o["id"],) for o in obls])
        conn.commit()
        conn.close()
    return {"obligaciones": len(obls) if ok_alguno else 0, "correos": correos, "sin_canal": sin_canal,
            "pendientes": 0 if ok_alguno else len(obls)}


def enviar_alertas_24h(hoy: date | None = None) -> dict[str, Any]:
    """Tarea programada: alerta 24 h antes de la presentación (y recuperación del mismo día)."""
    inicializar_tablas()
    sincronizar()
    obls = para_alerta(hoy)
    res = enviar_alerta(obls, hoy=hoy)
    if obls and res["sin_canal"]:
        crear_alerta("URGENTE", "impuestos", "Alerta de impuestos SIN ENVIAR: falta configurar el correo",
                     f"{len(obls)} declaración(es) por avisar. Configure SMTP_* en .env.")
    elif res["obligaciones"]:
        crear_alerta("AVISO", "impuestos", f"Alerta enviada: {res['obligaciones']} declaración(es) por vencer",
                     "; ".join(f"{o['impuesto']} {o['periodo']}" for o in obls)[:400])
    registrar_accion("impuestos", "alertas_24h_presentacion", str(res),
                     "EXITOSO" if not res.get("pendientes") else "ERROR")
    return res
