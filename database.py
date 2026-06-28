"""
Base de datos SQLite local. Guarda todo el estado, logs y estadísticas del agente.
"""
import sqlite3
import logging
from datetime import datetime, date
from typing import Any

from config import cfg

logger = logging.getLogger(__name__)


def get_conn() -> sqlite3.Connection:
    """Retorna conexión a SQLite."""
    return sqlite3.connect(cfg.DATABASE_PATH, check_same_thread=False)


def inicializar_db() -> None:
    """Crea todas las tablas si no existen."""
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS log_acciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        modulo TEXT NOT NULL,
        funcion TEXT NOT NULL,
        descripcion TEXT,
        estado TEXT CHECK(estado IN ('EXITOSO','ERROR','PENDIENTE','CANCELADO')),
        detalle_error TEXT,
        tokens_input INTEGER DEFAULT 0,
        tokens_output INTEGER DEFAULT 0,
        costo_usd REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS alertas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        nivel TEXT CHECK(nivel IN ('CRITICO','URGENTE','AVISO','INFO')),
        modulo TEXT NOT NULL,
        titulo TEXT NOT NULL,
        descripcion TEXT,
        visto INTEGER DEFAULT 0,
        resuelto INTEGER DEFAULT 0,
        fecha_resolucion DATETIME
    );

    CREATE TABLE IF NOT EXISTS correos_procesados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        message_id TEXT UNIQUE,
        origen TEXT CHECK(origen IN ('GMAIL','OUTLOOK')),
        remitente TEXT,
        asunto TEXT,
        categoria TEXT,
        destino_reenvio TEXT,
        accion TEXT,
        tokens_usados INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS pagos_pendientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_identificacion DATETIME DEFAULT CURRENT_TIMESTAMP,
        proveedor TEXT NOT NULL,
        concepto TEXT,
        monto REAL NOT NULL,
        fecha_vencimiento DATE,
        dias_vencimiento INTEGER,
        prioridad TEXT CHECK(prioridad IN ('VENCIDO','HOY','URGENTE','PROXIMO','NORMAL')),
        cuenta_bancaria TEXT,
        tipo_pago TEXT,
        estado TEXT CHECK(estado IN ('PENDIENTE','APROBADO','RECHAZADO','PAGADO')) DEFAULT 'PENDIENTE',
        aprobado_por TEXT,
        fecha_decision DATETIME
    );

    CREATE TABLE IF NOT EXISTS creditos_analizados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        cliente TEXT NOT NULL,
        nit TEXT,
        cupo_solicitado REAL,
        cupo_aprobado REAL,
        decision TEXT CHECK(decision IN ('APROBADO','NEGADO','CONDICIONAL')),
        condiciones TEXT,
        justificacion TEXT,
        carta_path TEXT,
        observaciones_via TEXT,
        estado_habilitacion TEXT DEFAULT 'PENDIENTE'
    );

    CREATE TABLE IF NOT EXISTS estado_impuestos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        impuesto TEXT NOT NULL,
        periodo TEXT NOT NULL,
        fecha_vencimiento DATE,
        dias_restantes INTEGER,
        estado TEXT CHECK(estado IN ('PENDIENTE','PRESENTADO','PAGADO','VENCIDO')),
        ultima_alerta_enviada DATETIME,
        nivel_ultima_alerta TEXT,
        UNIQUE(impuesto, periodo)
    );

    CREATE TABLE IF NOT EXISTS documentos_generados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        tipo TEXT NOT NULL,
        nombre_archivo TEXT,
        path_local TEXT,
        modulo_origen TEXT,
        descripcion TEXT,
        descargado INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS uso_tokens_diario (
        fecha DATE PRIMARY KEY,
        tokens_input_haiku INTEGER DEFAULT 0,
        tokens_output_haiku INTEGER DEFAULT 0,
        tokens_input_sonnet INTEGER DEFAULT 0,
        tokens_output_sonnet INTEGER DEFAULT 0,
        costo_estimado_usd REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS historial_chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        rol TEXT CHECK(rol IN ('user','assistant')),
        contenido TEXT,
        tokens_usados INTEGER DEFAULT 0,
        modulo_referenciado TEXT
    );

    CREATE TABLE IF NOT EXISTS estadisticas_diarias (
        fecha DATE PRIMARY KEY,
        correos_procesados INTEGER DEFAULT 0,
        alertas_generadas INTEGER DEFAULT 0,
        pagos_procesados INTEGER DEFAULT 0,
        documentos_generados INTEGER DEFAULT 0,
        tareas_completadas INTEGER DEFAULT 0,
        tareas_con_error INTEGER DEFAULT 0,
        horas_ahorradas REAL DEFAULT 0
    );
    """)
    conn.commit()
    conn.close()
    from database_modulos import inicializar_tablas_modulos
    from modulos.impuestos_calendario import inicializar_tablas_calendario

    inicializar_tablas_modulos()
    inicializar_tablas_calendario()
    logger.info("Base de datos inicializada correctamente.")


def registrar_accion(
    modulo: str,
    funcion: str,
    descripcion: str,
    estado: str,
    detalle_error: str | None = None,
    tokens_input: int = 0,
    tokens_output: int = 0,
) -> int:
    """Registra una acción del agente en el log."""
    costo = (tokens_input * 3 + tokens_output * 15) / 1_000_000
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO log_acciones
        (modulo, funcion, descripcion, estado, detalle_error, tokens_input, tokens_output, costo_usd)
        VALUES (?,?,?,?,?,?,?,?)""",
        (modulo, funcion, descripcion, estado, detalle_error, tokens_input, tokens_output, costo),
    )
    conn.commit()
    last_id = c.lastrowid
    conn.close()
    return last_id or 0


def crear_alerta(nivel: str, modulo: str, titulo: str, descripcion: str) -> int:
    """Crea una alerta nueva en el sistema."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO alertas (nivel, modulo, titulo, descripcion) VALUES (?,?,?,?)",
        (nivel, modulo, titulo, descripcion),
    )
    conn.commit()
    last_id = c.lastrowid
    conn.close()
    logger.warning("[%s] %s: %s", nivel, titulo, descripcion)
    return last_id or 0


def obtener_alertas_activas() -> list[tuple[Any, ...]]:
    """Retorna todas las alertas no resueltas."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """SELECT * FROM alertas WHERE resuelto=0
                 ORDER BY CASE nivel
                   WHEN 'CRITICO' THEN 1 WHEN 'URGENTE' THEN 2
                   WHEN 'AVISO' THEN 3 ELSE 4 END, timestamp DESC"""
    )
    rows = c.fetchall()
    conn.close()
    return rows


def marcar_alerta_resuelta(alerta_id: int) -> None:
    """Marca una alerta como resuelta."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE alertas SET resuelto=1, fecha_resolucion=? WHERE id=?",
        (datetime.now(), alerta_id),
    )
    conn.commit()
    conn.close()


def obtener_pagos_pendientes() -> list[tuple[Any, ...]]:
    """Retorna pagos pendientes de aprobación ordenados por prioridad."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """SELECT * FROM pagos_pendientes WHERE estado='PENDIENTE'
                 ORDER BY CASE prioridad
                   WHEN 'VENCIDO' THEN 1 WHEN 'HOY' THEN 2
                   WHEN 'URGENTE' THEN 3 WHEN 'PROXIMO' THEN 4 ELSE 5 END"""
    )
    rows = c.fetchall()
    conn.close()
    return rows


def aprobar_pago(pago_id: int, aprobado_por: str = "Usuario") -> None:
    """Aprueba un pago pendiente."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """UPDATE pagos_pendientes SET estado='APROBADO',
                 aprobado_por=?, fecha_decision=? WHERE id=?""",
        (aprobado_por, datetime.now(), pago_id),
    )
    conn.commit()
    conn.close()


def rechazar_pago(pago_id: int, aprobado_por: str = "Usuario") -> None:
    """Rechaza un pago pendiente."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """UPDATE pagos_pendientes SET estado='RECHAZADO',
                 aprobado_por=?, fecha_decision=? WHERE id=?""",
        (aprobado_por, datetime.now(), pago_id),
    )
    conn.commit()
    conn.close()


def guardar_mensaje_chat(
    rol: str, contenido: str, tokens: int = 0, modulo: str | None = None
) -> None:
    """Guarda un mensaje del historial de chat."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO historial_chat (rol, contenido, tokens_usados, modulo_referenciado)
                 VALUES (?,?,?,?)""",
        (rol, contenido, tokens, modulo),
    )
    conn.commit()
    conn.close()


def obtener_historial_chat(limite: int = 20) -> list[tuple[Any, ...]]:
    """Retorna los últimos N mensajes del chat."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT rol, contenido, timestamp FROM historial_chat ORDER BY id DESC LIMIT ?",
        (limite,),
    )
    rows = c.fetchall()
    conn.close()
    return list(reversed(rows))


def obtener_estadisticas_hoy() -> dict[str, Any]:
    """Retorna estadísticas del día actual."""
    conn = get_conn()
    c = conn.cursor()
    hoy = date.today().isoformat()

    c.execute("SELECT COUNT(*) FROM correos_procesados WHERE DATE(timestamp)=?", (hoy,))
    correos = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM alertas WHERE DATE(timestamp)=?", (hoy,))
    alertas = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM alertas WHERE resuelto=0", ())
    alertas_activas = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM pagos_pendientes WHERE estado='PENDIENTE'", ())
    pagos_pendientes = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM documentos_generados WHERE DATE(timestamp)=?", (hoy,))
    documentos = c.fetchone()[0]

    c.execute("SELECT SUM(costo_usd) FROM log_acciones WHERE DATE(timestamp)=?", (hoy,))
    costo_hoy = c.fetchone()[0] or 0

    c.execute(
        "SELECT SUM(costo_usd) FROM log_acciones WHERE strftime('%Y-%m', timestamp)=strftime('%Y-%m', 'now')",
        (),
    )
    costo_mes = c.fetchone()[0] or 0

    c.execute(
        "SELECT COUNT(*) FROM log_acciones WHERE estado='EXITOSO' AND DATE(timestamp)=?",
        (hoy,),
    )
    tareas_ok = c.fetchone()[0]

    c.execute(
        """SELECT modulo, funcion, descripcion, estado, timestamp
                 FROM log_acciones ORDER BY id DESC LIMIT 10"""
    )
    ultimas_acciones = c.fetchall()

    conn.close()
    return {
        "correos_hoy": correos,
        "alertas_hoy": alertas,
        "alertas_activas": alertas_activas,
        "pagos_pendientes": pagos_pendientes,
        "documentos_hoy": documentos,
        "costo_hoy": round(costo_hoy, 2),
        "costo_mes": round(costo_mes, 2),
        "tareas_completadas_hoy": tareas_ok,
        "ultimas_acciones": ultimas_acciones,
    }


def obtener_correos_ultimos_dias(dias: int = 7) -> list[tuple[Any, ...]]:
    """Retorna conteo de correos por día de los últimos N días."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """SELECT DATE(timestamp) as fecha, COUNT(*) as total,
                 categoria FROM correos_procesados
                 WHERE timestamp >= datetime('now', ?)
                 GROUP BY fecha, categoria
                 ORDER BY fecha""",
        (f"-{dias} days",),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def registrar_documento(
    tipo: str,
    nombre_archivo: str,
    path_local: str,
    modulo_origen: str,
    descripcion: str,
) -> int:
    """Registra un documento generado en la base de datos."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO documentos_generados
        (tipo, nombre_archivo, path_local, modulo_origen, descripcion)
        VALUES (?,?,?,?,?)""",
        (tipo, nombre_archivo, path_local, modulo_origen, descripcion),
    )
    conn.commit()
    last_id = c.lastrowid
    conn.close()
    return last_id or 0


def cargar_datos_demo() -> None:
    """Inserta datos de ejemplo si la base está vacía (modo demo)."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM alertas")
    if c.fetchone()[0] > 0:
        conn.close()
        return

    crear_alerta("AVISO", "impuestos", "IVA próximo a vencer", "IVA febrero vence en 12 días")
    crear_alerta("URGENTE", "pagos", "Pago proveedor vencido", "Servicios XYZ — $2.500.000 vencido hace 3 días")

    c.execute(
        """INSERT INTO pagos_pendientes
        (proveedor, concepto, monto, fecha_vencimiento, dias_vencimiento, prioridad, estado)
        VALUES (?,?,?,?,?,?,?)""",
        ("Servicios XYZ S.A.S.", "Mantenimiento mensual", 2500000, "2026-06-20", -6, "VENCIDO", "PENDIENTE"),
    )
    c.execute(
        """INSERT INTO pagos_pendientes
        (proveedor, concepto, monto, fecha_vencimiento, dias_vencimiento, prioridad, estado)
        VALUES (?,?,?,?,?,?,?)""",
        ("Papelería Central", "Suministros oficina", 450000, "2026-06-26", 0, "HOY", "PENDIENTE"),
    )
    c.execute(
        """INSERT INTO correos_procesados
        (message_id, origen, remitente, asunto, categoria, destino_reenvio, accion)
        VALUES (?,?,?,?,?,?,?)""",
        ("demo-001", "GMAIL", "facturas@proveedor.com", "Factura #1234", "factura", "contabilidad@empresa.com", "REENVIADO"),
    )
    c.execute(
        """INSERT INTO creditos_analizados
        (cliente, nit, cupo_solicitado, cupo_aprobado, decision, condiciones, justificacion, estado_habilitacion)
        VALUES (?,?,?,?,?,?,?,?)""",
        (
            "Distribuidora Norte",
            "901555666-7",
            5000000,
            4000000,
            "CONDICIONAL",
            "Garantía bancaria 20%",
            "Capacidad de pago aceptable con condiciones.",
            "PENDIENTE",
        ),
    )
    conn.commit()
    conn.close()
    logger.info("Datos demo cargados en la base de datos.")
