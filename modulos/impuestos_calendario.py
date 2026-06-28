"""
Calendario tributario open data + recordatorios 48h (email) y 24h (WhatsApp).
"""
import logging
import sqlite3
from datetime import date, datetime, timedelta

from config import cfg
from conexiones.gmail_client import enviar_correo
from conexiones.opendata_impuestos import obtener_todos_vencimientos_opendata
from conexiones.whatsapp_client import enviar_whatsapp
from database import crear_alerta, registrar_accion

logger = logging.getLogger(__name__)


def _conn():
    return sqlite3.connect(cfg.DATABASE_PATH)


def inicializar_tablas_calendario() -> None:
    """Crea tablas de calendario y recordatorios si no existen."""
    conn = _conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS calendario_tributario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entidad TEXT NOT NULL,
        impuesto TEXT NOT NULL,
        periodo TEXT,
        fecha_vencimiento DATE NOT NULL,
        formulario TEXT,
        categoria TEXT,
        observaciones TEXT,
        fuente TEXT DEFAULT 'opendata',
        UNIQUE(entidad, impuesto, periodo, fecha_vencimiento)
    );
    CREATE TABLE IF NOT EXISTS recordatorios_impuestos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        calendario_id INTEGER,
        tipo TEXT CHECK(tipo IN ('EMAIL_48H','WHATSAPP_24H')),
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        destinos TEXT,
        UNIQUE(calendario_id, tipo)
    );
    """)
    conn.commit()
    conn.close()


def sincronizar_calendario_opendata(anio: int | None = None) -> int:
    """
    Importa vencimientos DIAN + SHD Bogotá a SQLite e impuestos_maestro.

    Returns:
        Registros insertados/actualizados.
    """
    inicializar_tablas_calendario()
    items = obtener_todos_vencimientos_opendata(anio)
    conn = _conn()
    c = conn.cursor()
    n = 0
    for item in items:
        fv = item.get("fecha")
        if not fv:
            continue
        entidad = item.get("entidad", "DIAN")
        imp = item.get("impuesto", "")
        per = item.get("periodo", "")
        c.execute(
            """INSERT INTO calendario_tributario
            (entidad, impuesto, periodo, fecha_vencimiento, formulario, categoria, observaciones, fuente)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(entidad, impuesto, periodo, fecha_vencimiento) DO UPDATE SET
            formulario=excluded.formulario, categoria=excluded.categoria, observaciones=excluded.observaciones""",
            (
                entidad,
                imp,
                per,
                fv,
                item.get("formulario", ""),
                item.get("categoria", ""),
                item.get("observaciones", ""),
                "opendata",
            ),
        )
        c.execute(
            """INSERT INTO impuestos_maestro (impuesto, periodo, fecha_vencimiento, estado, formulario, observaciones)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(impuesto, periodo) DO UPDATE SET
            fecha_vencimiento=excluded.fecha_vencimiento, formulario=excluded.formulario,
            observaciones=excluded.observaciones""",
            (f"[{entidad}] {imp}", per, fv, "PENDIENTE", item.get("formulario", ""), item.get("observaciones", "")),
        )
        n += 1
    conn.commit()
    conn.close()
    registrar_accion("impuestos", "sincronizar_calendario_opendata", f"{n} vencimientos", "EXITOSO")
    return n


def _destinatarios_email_recordatorio() -> list[str]:
    """Contador, revisoría fiscal y equipo tributario."""
    raw = [
        cfg.EMAIL_CONTADOR,
        cfg.EMAIL_REVISORIA_FISCAL,
        cfg.EMAIL_CONTABILIDAD,
        cfg.EMAIL_GERENCIA,
    ]
    vistos: set[str] = set()
    out = []
    for e in raw:
        if e and e not in vistos:
            vistos.add(e)
            out.append(e)
    return out


def _ya_enviado(calendario_id: int, tipo: str) -> bool:
    conn = _conn()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM recordatorios_impuestos WHERE calendario_id=? AND tipo=?",
        (calendario_id, tipo),
    )
    ok = c.fetchone() is not None
    conn.close()
    return ok


def _marcar_enviado(calendario_id: int, tipo: str, destinos: str) -> None:
    conn = _conn()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO recordatorios_impuestos (calendario_id, tipo, destinos) VALUES (?,?,?)",
        (calendario_id, tipo, destinos),
    )
    conn.commit()
    conn.close()


def enviar_recordatorios_vencimientos() -> dict[str, int]:
    """
    - 48 horas antes: correo a contador, revisoría fiscal y equipo.
    - 24 horas antes: WhatsApp a todos los destinatarios configurados.

    Returns:
        dict con conteos email_48h y whatsapp_24h.
    """
    inicializar_tablas_calendario()
    ahora = datetime.now()
    conn = _conn()
    c = conn.cursor()
    c.execute(
        """SELECT id, entidad, impuesto, periodo, fecha_vencimiento, formulario
           FROM calendario_tributario WHERE fecha_vencimiento >= date('now')
           ORDER BY fecha_vencimiento"""
    )
    filas = c.fetchall()
    conn.close()

    stats = {"email_48h": 0, "whatsapp_24h": 0}
    destinos_email = _destinatarios_email_recordatorio()

    for row in filas:
        cid, entidad, impuesto, periodo, fv, formulario = row
        venc = datetime.combine(date.fromisoformat(str(fv)), datetime.max.time().replace(microsecond=0))
        horas = (venc - ahora).total_seconds() / 3600

        if 47 <= horas <= 49 and not _ya_enviado(cid, "EMAIL_48H"):
            html = f"""
            <h2>⏰ Recordatorio impuestos — 48 horas</h2>
            <p><strong>{cfg.NOMBRE_EMPRESA}</strong> (NIT {cfg.NIT_EMPRESA})</p>
            <ul>
              <li><strong>Entidad:</strong> {entidad}</li>
              <li><strong>Obligación:</strong> {impuesto}</li>
              <li><strong>Periodo:</strong> {periodo}</li>
              <li><strong>Vencimiento:</strong> {fv}</li>
              <li><strong>Formulario:</strong> {formulario or 'N/A'}</li>
            </ul>
            <p>Generado por AGENTE ADMIN SHAKI.</p>
            """
            for dest in destinos_email:
                enviar_correo(
                    dest,
                    f"[48h] Vencimiento tributario — {impuesto} ({entidad})",
                    html,
                )
            _marcar_enviado(cid, "EMAIL_48H", ",".join(destinos_email))
            crear_alerta("URGENTE", "impuestos", f"48h: {impuesto}", f"Vence {fv} — {entidad}")
            stats["email_48h"] += 1

        if 23 <= horas <= 25 and not _ya_enviado(cid, "WHATSAPP_24H"):
            msg = (
                f"🔔 AGENTE ADMIN SHAKI — {cfg.NOMBRE_EMPRESA}\n"
                f"Vencimiento en 24h:\n{impuesto} ({entidad})\n"
                f"Periodo: {periodo}\nFecha: {fv}\nFormulario: {formulario or 'N/A'}"
            )
            n = enviar_whatsapp(msg)
            if n:
                _marcar_enviado(cid, "WHATSAPP_24H", cfg.WHATSAPP_DESTINATARIOS or "demo")
                crear_alerta("CRITICO", "impuestos", f"24h WhatsApp: {impuesto}", f"Vence mañana — {fv}")
                stats["whatsapp_24h"] += 1

    registrar_accion(
        "impuestos",
        "enviar_recordatorios_vencimientos",
        f"Email 48h: {stats['email_48h']}, WhatsApp 24h: {stats['whatsapp_24h']}",
        "EXITOSO",
    )
    return stats


def listar_proximos_vencimientos(dias: int = 60) -> list[tuple]:
    """Vencimientos en los próximos N días."""
    inicializar_tablas_calendario()
    conn = _conn()
    c = conn.cursor()
    limite = (date.today() + timedelta(days=dias)).isoformat()
    c.execute(
        """SELECT entidad, impuesto, periodo, fecha_vencimiento, formulario
           FROM calendario_tributario
           WHERE fecha_vencimiento BETWEEN date('now') AND ?
           ORDER BY fecha_vencimiento""",
        (limite,),
    )
    rows = c.fetchall()
    conn.close()
    return rows
