"""Calendario maestro — agenda centralizada 24/7 del AGENTE ADMIN SHAKI."""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any

import holidays
import pandas as pd
from dateutil.relativedelta import relativedelta

from database import get_conn

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_executor_thread: threading.Thread | None = None
_executor_activo = False

MODULOS_VALIDOS = {
    "RRHH",
    "IMPUESTOS",
    "CARTERA",
    "PAGOS",
    "CORREOS",
    "CONTABILIDAD",
    "JURIDICO",
    "COMISIONES",
    "SISTEMA",
    "MANUAL",
    "CXP_CXC",
    "CREDITOS",
    "PRESUPUESTO",
}

TIPOS_VALIDOS = {
    "AUTOMATICA",
    "RECORDATORIO",
    "VENCIMIENTO",
    "REUNION",
    "TAREA_MANUAL",
    "ALERTA",
}


# ── Festivos Colombia ──────────────────────────────────────────────────────────


def get_festivos_colombia(año: int | None = None) -> set[date]:
    """Festivos colombianos (Ley Emiliani). Incluye año actual y siguiente."""
    if año is None:
        año = date.today().year
    co = holidays.Colombia(years=[año, año + 1])
    return set(co.keys())


def es_festivo(fecha: date) -> bool:
    return fecha in get_festivos_colombia(fecha.year)


def es_dia_habil(fecha: date) -> bool:
    return fecha.weekday() < 5 and not es_festivo(fecha)


def siguiente_dia_habil(desde: date | None = None) -> date:
    if desde is None:
        desde = date.today()
    siguiente = desde + timedelta(days=1)
    while not es_dia_habil(siguiente):
        siguiente += timedelta(days=1)
    return siguiente


def dias_habiles_entre(inicio: date, fin: date) -> int:
    total = 0
    actual = inicio
    while actual <= fin:
        if es_dia_habil(actual):
            total += 1
        actual += timedelta(days=1)
    return total


# ── Base de datos ──────────────────────────────────────────────────────────────


def inicializar_tablas_calendario_maestro() -> None:
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS calendario_maestro (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        descripcion TEXT,
        modulo TEXT NOT NULL,
        tipo TEXT NOT NULL,
        prioridad TEXT DEFAULT 'MEDIA',
        fecha_inicio DATETIME NOT NULL,
        fecha_fin DATETIME,
        recurrencia TEXT,
        recurrencia_config TEXT,
        activa BOOLEAN DEFAULT 1,
        es_festivo_colombia BOOLEAN DEFAULT 0,
        ejecutada BOOLEAN DEFAULT 0,
        fecha_ultima_ejecucion DATETIME,
        fecha_proxima_ejecucion DATETIME,
        resultado_ultima_ejecucion TEXT,
        funcion_callback TEXT,
        parametros_callback TEXT,
        creada_por TEXT DEFAULT 'SISTEMA',
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS log_ejecuciones_calendario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tarea_id INTEGER REFERENCES calendario_maestro(id),
        titulo TEXT,
        modulo TEXT,
        fecha_ejecucion DATETIME,
        estado TEXT,
        duracion_segundos REAL,
        detalle TEXT,
        error TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_cal_fecha ON calendario_maestro(fecha_proxima_ejecucion);
    CREATE INDEX IF NOT EXISTS idx_cal_modulo ON calendario_maestro(modulo);
    CREATE INDEX IF NOT EXISTS idx_cal_activa ON calendario_maestro(activa);
    """)
    conn.commit()
    conn.close()
    sembrar_tareas_iniciales()


def _parse_hora(config: dict | None) -> tuple[int, int]:
    hora = (config or {}).get("hora", "08:00")
    partes = str(hora).split(":")
    return int(partes[0]), int(partes[1]) if len(partes) > 1 else 0


def _combinar_fecha_hora(fecha: date, config: dict | None) -> datetime:
    h, m = _parse_hora(config)
    return datetime.combine(fecha, datetime.min.time().replace(hour=h, minute=m))


def _ajustar_si_pasado(dt: datetime) -> datetime:
    ahora = datetime.now()
    if dt >= ahora:
        return dt
    return ahora + timedelta(minutes=1)


def _primera_ejecucion(
    fecha_inicio: datetime,
    recurrencia: str | None,
    config: dict | None,
) -> datetime:
    cfg = config or {}
    ahora = datetime.now()
    base = fecha_inicio if fecha_inicio > ahora else ahora

    if not recurrencia:
        return _ajustar_si_pasado(fecha_inicio)

    if recurrencia == "INTERVALO":
        minutos = int(cfg.get("minutos", 30))
        return ahora + timedelta(minutes=minutos)

    hoy = base.date()
    candidato = _combinar_fecha_hora(hoy, cfg)

    if recurrencia == "DIARIA":
        if candidato <= ahora:
            candidato = _combinar_fecha_hora(hoy + timedelta(days=1), cfg)
        return candidato

    if recurrencia == "DIAS_HABILES":
        d = hoy
        if not es_dia_habil(d) or _combinar_fecha_hora(d, cfg) <= ahora:
            d = siguiente_dia_habil(hoy if es_dia_habil(hoy) else hoy)
            while not es_dia_habil(d):
                d += timedelta(days=1)
            if es_dia_habil(hoy) and _combinar_fecha_hora(hoy, cfg) > ahora:
                d = hoy
            elif d == hoy:
                d = siguiente_dia_habil(hoy)
        candidato = _combinar_fecha_hora(d, cfg)
        while candidato <= ahora or not es_dia_habil(candidato.date()):
            d = siguiente_dia_habil(candidato.date())
            candidato = _combinar_fecha_hora(d, cfg)
        return candidato

    if recurrencia == "SEMANAL":
        dias = cfg.get("dias_semana", [0])
        for offset in range(8):
            d = hoy + timedelta(days=offset)
            if d.weekday() in dias:
                cand = _combinar_fecha_hora(d, cfg)
                if cand > ahora:
                    return cand
        return _combinar_fecha_hora(hoy + timedelta(days=7), cfg)

    if recurrencia == "MENSUAL":
        dia_mes = int(cfg.get("dia_mes", fecha_inicio.day))
        d = date(hoy.year, hoy.month, min(dia_mes, 28))
        try:
            d = date(hoy.year, hoy.month, dia_mes)
        except ValueError:
            d = date(hoy.year, hoy.month, 28)
        cand = _combinar_fecha_hora(d, cfg)
        if cand <= ahora:
            prox = hoy + relativedelta(months=1)
            try:
                d = date(prox.year, prox.month, dia_mes)
            except ValueError:
                d = date(prox.year, prox.month, 28)
            cand = _combinar_fecha_hora(d, cfg)
        return cand

    if recurrencia == "ANUAL":
        cand = _combinar_fecha_hora(
            date(hoy.year, fecha_inicio.month, fecha_inicio.day), cfg
        )
        if cand <= ahora:
            cand = _combinar_fecha_hora(
                date(hoy.year + 1, fecha_inicio.month, fecha_inicio.day), cfg
            )
        return cand

    return _ajustar_si_pasado(fecha_inicio)


# ── API del Calendario ─────────────────────────────────────────────────────────


def agregar_tarea(
    titulo: str,
    modulo: str,
    tipo: str,
    fecha_inicio: datetime,
    descripcion: str | None = None,
    fecha_fin: datetime | None = None,
    prioridad: str = "MEDIA",
    recurrencia: str | None = None,
    recurrencia_config: dict | None = None,
    funcion_callback: str | None = None,
    parametros_callback: dict | None = None,
    creada_por: str = "SISTEMA",
) -> int:
    """Agrega una tarea al calendario maestro. Retorna el ID creado."""
    config_json = json.dumps(recurrencia_config or {}, ensure_ascii=False)
    params_json = json.dumps(parametros_callback or {}, ensure_ascii=False)
    proxima = _primera_ejecucion(fecha_inicio, recurrencia, recurrencia_config)

    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO calendario_maestro
           (titulo, descripcion, modulo, tipo, prioridad, fecha_inicio, fecha_fin,
            recurrencia, recurrencia_config, activa, fecha_proxima_ejecucion,
            funcion_callback, parametros_callback, creada_por)
           VALUES (?,?,?,?,?,?,?,?,?,1,?,?,?,?)""",
        (
            titulo,
            descripcion,
            modulo.upper(),
            tipo.upper(),
            prioridad.upper(),
            fecha_inicio.isoformat(timespec="seconds"),
            fecha_fin.isoformat(timespec="seconds") if fecha_fin else None,
            recurrencia,
            config_json,
            proxima.isoformat(timespec="seconds"),
            funcion_callback,
            params_json,
            creada_por,
        ),
    )
    tarea_id = c.lastrowid
    conn.commit()
    conn.close()
    logger.info("Tarea calendario #%s: %s [%s]", tarea_id, titulo, modulo)
    return int(tarea_id)


def _row_to_dict(row: tuple, cols: list[str]) -> dict:
    return dict(zip(cols, row))


def _query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def tareas_hoy(modulo: str | None = None) -> pd.DataFrame:
    """Tareas programadas para hoy (por fecha_proxima o rango del día)."""
    hoy = date.today().isoformat()
    sql = """
        SELECT id, titulo, descripcion, modulo, tipo, prioridad,
               fecha_proxima_ejecucion, recurrencia, activa, funcion_callback
        FROM calendario_maestro
        WHERE activa=1
          AND date(fecha_proxima_ejecucion) = ?
    """
    params: tuple = (hoy,)
    if modulo:
        sql += " AND modulo=?"
        params = (hoy, modulo.upper())
    df = _query_df(sql + " ORDER BY fecha_proxima_ejecucion", params)
    df["es_festivo_hoy"] = es_festivo(date.today())
    df["es_dia_habil_hoy"] = es_dia_habil(date.today())
    return df


def tareas_semana(fecha_inicio: date | None = None) -> pd.DataFrame:
    inicio = fecha_inicio or date.today()
    fin = inicio + timedelta(days=6)
    df = _query_df(
        """SELECT id, titulo, modulo, tipo, prioridad, fecha_proxima_ejecucion,
                  recurrencia, activa
           FROM calendario_maestro
           WHERE activa=1
             AND date(fecha_proxima_ejecucion) BETWEEN ? AND ?
           ORDER BY fecha_proxima_ejecucion""",
        (inicio.isoformat(), fin.isoformat()),
    )
    if not df.empty:
        df["festivo"] = df["fecha_proxima_ejecucion"].apply(
            lambda x: es_festivo(pd.to_datetime(x).date()) if x else False
        )
        df["fin_de_semana"] = df["fecha_proxima_ejecucion"].apply(
            lambda x: pd.to_datetime(x).weekday() >= 5 if x else False
        )
    return df


def tareas_mes(año: int | None = None, mes: int | None = None) -> pd.DataFrame:
    hoy = date.today()
    año = año or hoy.year
    mes = mes or hoy.month
    inicio = date(año, mes, 1)
    fin = inicio + relativedelta(months=1) - timedelta(days=1)
    df = _query_df(
        """SELECT id, titulo, modulo, tipo, prioridad, fecha_proxima_ejecucion,
                  recurrencia, activa, ejecutada
           FROM calendario_maestro
           WHERE activa=1
             AND date(fecha_proxima_ejecucion) BETWEEN ? AND ?
           ORDER BY fecha_proxima_ejecucion""",
        (inicio.isoformat(), fin.isoformat()),
    )
    festivos_mes = {d for d in get_festivos_colombia(año) if d.month == mes}
    df.attrs["festivos_mes"] = sorted(festivos_mes)
    if not df.empty:
        df["festivo"] = df["fecha_proxima_ejecucion"].apply(
            lambda x: es_festivo(pd.to_datetime(x).date()) if x else False
        )
    return df


def cancelar_tarea(tarea_id: int) -> None:
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE calendario_maestro SET activa=0 WHERE id=?", (tarea_id,))
    conn.commit()
    conn.close()


def tareas_vencidas() -> pd.DataFrame:
    """Tareas que debían ejecutarse y siguen pendientes."""
    return _query_df(
        """SELECT id, titulo, modulo, tipo, prioridad, fecha_proxima_ejecucion,
                  funcion_callback, recurrencia
           FROM calendario_maestro
           WHERE activa=1
             AND fecha_proxima_ejecucion < datetime('now', '-5 minutes')
           ORDER BY fecha_proxima_ejecucion"""
    )


def calcular_proxima_ejecucion(tarea_id: int) -> datetime | None:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """SELECT fecha_inicio, recurrencia, recurrencia_config, fecha_proxima_ejecucion
           FROM calendario_maestro WHERE id=?""",
        (tarea_id,),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None

    fecha_inicio = datetime.fromisoformat(row[0])
    recurrencia = row[1]
    config = json.loads(row[2] or "{}")
    actual = datetime.fromisoformat(row[3]) if row[3] else datetime.now()
    ahora = datetime.now()

    if not recurrencia:
        return None

    if recurrencia == "INTERVALO":
        return ahora + timedelta(minutes=int(config.get("minutos", 30)))

    if recurrencia == "DIARIA":
        prox = actual.date() + timedelta(days=1)
        return _combinar_fecha_hora(prox, config)

    if recurrencia == "DIAS_HABILES":
        d = siguiente_dia_habil(actual.date())
        return _combinar_fecha_hora(d, config)

    if recurrencia == "SEMANAL":
        dias = config.get("dias_semana", [0])
        for offset in range(1, 8):
            d = actual.date() + timedelta(days=offset)
            if d.weekday() in dias:
                return _combinar_fecha_hora(d, config)
        return actual + timedelta(days=7)

    if recurrencia == "MENSUAL":
        dia_mes = int(config.get("dia_mes", actual.day))
        prox = actual.date() + relativedelta(months=1)
        try:
            d = date(prox.year, prox.month, dia_mes)
        except ValueError:
            d = date(prox.year, prox.month, 28)
        return _combinar_fecha_hora(d, config)

    if recurrencia == "ANUAL":
        prox = date(actual.year + 1, fecha_inicio.month, fecha_inicio.day)
        return _combinar_fecha_hora(prox, config)

    return actual + timedelta(days=1)


def marcar_ejecutada(
    tarea_id: int,
    estado: str,
    detalle: str | None = None,
    error: str | None = None,
    duracion: float = 0.0,
) -> None:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT titulo, modulo, recurrencia FROM calendario_maestro WHERE id=?",
        (tarea_id,),
    )
    row = c.fetchone()
    if not row:
        conn.close()
        return

    titulo, modulo, recurrencia = row
    ahora = datetime.now().isoformat(timespec="seconds")
    proxima = calcular_proxima_ejecucion(tarea_id)
    proxima_str = proxima.isoformat(timespec="seconds") if proxima else None
    activa = 1 if recurrencia else 0

    c.execute(
        """UPDATE calendario_maestro
           SET ejecutada=1,
               fecha_ultima_ejecucion=?,
               resultado_ultima_ejecucion=?,
               fecha_proxima_ejecucion=?,
               activa=?
           WHERE id=?""",
        (ahora, estado, proxima_str, activa, tarea_id),
    )
    c.execute(
        """INSERT INTO log_ejecuciones_calendario
           (tarea_id, titulo, modulo, fecha_ejecucion, estado, duracion_segundos, detalle, error)
           VALUES (?,?,?,?,?,?,?,?)""",
        (tarea_id, titulo, modulo, ahora, estado, duracion, detalle, error),
    )
    conn.commit()
    conn.close()


def ejecutar_tarea_por_id(tarea_id: int) -> None:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """SELECT titulo, modulo, recurrencia, funcion_callback, parametros_callback
           FROM calendario_maestro WHERE id=? AND activa=1""",
        (tarea_id,),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return

    titulo, modulo, recurrencia, callback_name, params_json = row
    hoy = date.today()

    if recurrencia == "DIAS_HABILES" and not es_dia_habil(hoy):
        marcar_ejecutada(
            tarea_id,
            "OMITIDO_FESTIVO",
            detalle=f"Omitido: {'festivo' if es_festivo(hoy) else 'fin de semana'}",
        )
        return

    if not callback_name:
        marcar_ejecutada(tarea_id, "PENDIENTE", detalle="Sin callback definido")
        return

    inicio = time.perf_counter()
    try:
        from modulos.calendario_callbacks import ejecutar_callback

        params = json.loads(params_json or "{}")
        resultado = ejecutar_callback(callback_name, params)
        duracion = time.perf_counter() - inicio
        detalle = str(resultado)[:500] if resultado is not None else "OK"
        marcar_ejecutada(tarea_id, "EXITOSO", detalle=detalle, duracion=duracion)
        logger.info("✓ Calendario #%s %s", tarea_id, titulo)
    except Exception as exc:
        duracion = time.perf_counter() - inicio
        marcar_ejecutada(tarea_id, "ERROR", error=str(exc), duracion=duracion)
        logger.error("✗ Calendario #%s %s: %s", tarea_id, titulo, exc)


def _revisar_y_ejecutar_pendientes() -> None:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """SELECT id FROM calendario_maestro
           WHERE activa=1
             AND fecha_proxima_ejecucion IS NOT NULL
             AND fecha_proxima_ejecucion <= datetime('now')
           ORDER BY prioridad DESC, fecha_proxima_ejecucion"""
    )
    ids = [r[0] for r in c.fetchall()]
    conn.close()

    for tarea_id in ids:
        threading.Thread(
            target=ejecutar_tarea_por_id,
            args=(tarea_id,),
            daemon=True,
            name=f"cal-task-{tarea_id}",
        ).start()


def iniciar_executor() -> threading.Thread:
    """Loop en hilo daemon: revisa cada minuto tareas pendientes."""
    global _executor_thread, _executor_activo

    if _executor_activo and _executor_thread and _executor_thread.is_alive():
        return _executor_thread

    def loop() -> None:
        global _executor_activo
        _executor_activo = True
        logger.info("Calendario maestro: executor iniciado")
        while _executor_activo:
            try:
                with _lock:
                    _revisar_y_ejecutar_pendientes()
            except Exception as exc:
                logger.error("Error en executor calendario: %s", exc)
            time.sleep(60)

    _executor_thread = threading.Thread(target=loop, daemon=True, name="calendario-maestro")
    _executor_thread.start()
    return _executor_thread


def executor_esta_activo() -> bool:
    return _executor_activo and _executor_thread is not None and _executor_thread.is_alive()


def obtener_log_reciente(limite: int = 50) -> pd.DataFrame:
    return _query_df(
        """SELECT id, tarea_id, titulo, modulo, fecha_ejecucion, estado,
                  duracion_segundos, detalle, error
           FROM log_ejecuciones_calendario
           ORDER BY id DESC LIMIT ?""",
        (limite,),
    )


def listar_todas_activas() -> pd.DataFrame:
    return _query_df(
        """SELECT id, titulo, modulo, tipo, prioridad, recurrencia,
                  fecha_proxima_ejecucion, fecha_ultima_ejecucion,
                  resultado_ultima_ejecucion, activa
           FROM calendario_maestro
           WHERE activa=1
           ORDER BY fecha_proxima_ejecucion"""
    )


# ── Tareas precargadas ─────────────────────────────────────────────────────────


def _ya_existe(c, titulo: str, modulo: str) -> bool:
    c.execute(
        "SELECT 1 FROM calendario_maestro WHERE titulo=? AND modulo=?",
        (titulo, modulo),
    )
    return c.fetchone() is not None


def sembrar_tareas_iniciales() -> int:
    """Inserta tareas del sistema si no existen. Retorna cantidad sembrada."""
    ahora = datetime.now()
    base_hoy = datetime.combine(date.today(), datetime.min.time())

    plantillas = [
        {
            "titulo": "Escaneo carpetas PERSONAL ACTIVO",
            "modulo": "SISTEMA",
            "tipo": "AUTOMATICA",
            "descripcion": "Detecta nuevos documentos y empleados en OneDrive",
            "fecha_inicio": base_hoy,
            "prioridad": "ALTA",
            "recurrencia": "DIAS_HABILES",
            "recurrencia_config": {"hora": "07:00"},
            "funcion_callback": "escanear_carpetas_personal",
        },
        {
            "titulo": "Alertas documentos faltantes RRHH",
            "modulo": "RRHH",
            "tipo": "ALERTA",
            "descripcion": "Genera alertas por expedientes incompletos",
            "fecha_inicio": base_hoy,
            "prioridad": "MEDIA",
            "recurrencia": "DIAS_HABILES",
            "recurrencia_config": {"hora": "07:15"},
            "funcion_callback": "generar_alertas_carpetas",
        },
        {
            "titulo": "Resumen matutino del día",
            "modulo": "SISTEMA",
            "tipo": "AUTOMATICA",
            "descripcion": "Resumen de tareas y pendientes del día",
            "fecha_inicio": base_hoy,
            "prioridad": "MEDIA",
            "recurrencia": "DIAS_HABILES",
            "recurrencia_config": {"hora": "07:30"},
            "funcion_callback": "generar_resumen_dia",
        },
        {
            "titulo": "Revisión vencimientos impuestos",
            "modulo": "IMPUESTOS",
            "tipo": "VENCIMIENTO",
            "fecha_inicio": base_hoy,
            "recurrencia": "DIARIA",
            "recurrencia_config": {"hora": "07:00"},
            "funcion_callback": "revisar_vencimientos",
        },
        {
            "titulo": "Recordatorios impuestos 48h/24h",
            "modulo": "IMPUESTOS",
            "tipo": "RECORDATORIO",
            "fecha_inicio": base_hoy,
            "recurrencia": "DIARIA",
            "recurrencia_config": {"hora": "07:02"},
            "funcion_callback": "enviar_recordatorios_vencimientos",
        },
        {
            "titulo": "Recordatorios impuestos (cada 2h)",
            "modulo": "IMPUESTOS",
            "tipo": "RECORDATORIO",
            "fecha_inicio": ahora,
            "recurrencia": "INTERVALO",
            "recurrencia_config": {"minutos": 120},
            "funcion_callback": "enviar_recordatorios_vencimientos",
        },
        {
            "titulo": "Sync calendario DIAN/SHD open data",
            "modulo": "IMPUESTOS",
            "tipo": "AUTOMATICA",
            "fecha_inicio": base_hoy,
            "recurrencia": "SEMANAL",
            "recurrencia_config": {"hora": "06:30", "dias_semana": [0]},
            "funcion_callback": "sincronizar_calendario_opendata",
        },
        {
            "titulo": "Vigilancia DIAN",
            "modulo": "IMPUESTOS",
            "tipo": "AUTOMATICA",
            "fecha_inicio": base_hoy,
            "recurrencia": "SEMANAL",
            "recurrencia_config": {"hora": "08:00", "dias_semana": [0]},
            "funcion_callback": "vigilar_dian",
        },
        {
            "titulo": "Revisión CXP administrativos",
            "modulo": "PAGOS",
            "tipo": "AUTOMATICA",
            "fecha_inicio": base_hoy,
            "recurrencia": "DIARIA",
            "recurrencia_config": {"hora": "07:05"},
            "funcion_callback": "revisar_cxp_diario",
        },
        {
            "titulo": "Novedades personal",
            "modulo": "RRHH",
            "tipo": "AUTOMATICA",
            "fecha_inicio": base_hoy,
            "recurrencia": "DIARIA",
            "recurrencia_config": {"hora": "08:00"},
            "funcion_callback": "actualizar_novedades_diarias",
        },
        {
            "titulo": "Procesar correos",
            "modulo": "CORREOS",
            "tipo": "AUTOMATICA",
            "fecha_inicio": ahora,
            "recurrencia": "INTERVALO",
            "recurrencia_config": {"minutos": 30},
            "funcion_callback": "procesar_correos",
        },
        {
            "titulo": "Resumen diario de correos",
            "modulo": "CORREOS",
            "tipo": "AUTOMATICA",
            "fecha_inicio": base_hoy,
            "recurrencia": "DIARIA",
            "recurrencia_config": {"hora": "18:00"},
            "funcion_callback": "generar_resumen_diario_correos",
        },
        {
            "titulo": "Reunión semanal CXP/CXC",
            "modulo": "CXP_CXC",
            "tipo": "REUNION",
            "fecha_inicio": base_hoy,
            "recurrencia": "SEMANAL",
            "recurrencia_config": {"hora": "06:00", "dias_semana": [0]},
            "funcion_callback": "preparar_reunion_semanal",
        },
        {
            "titulo": "Revisión mora clientes",
            "modulo": "CARTERA",
            "tipo": "ALERTA",
            "fecha_inicio": base_hoy,
            "recurrencia": "SEMANAL",
            "recurrencia_config": {"hora": "08:30", "dias_semana": [0]},
            "funcion_callback": "revisar_mora_clientes",
        },
        {
            "titulo": "Conciliación bancaria",
            "modulo": "CONTABILIDAD",
            "tipo": "AUTOMATICA",
            "fecha_inicio": base_hoy,
            "recurrencia": "SEMANAL",
            "recurrencia_config": {"hora": "09:00", "dias_semana": [4]},
            "funcion_callback": "verificar_conciliacion_bancaria",
        },
        {
            "titulo": "Análisis mensual presupuesto",
            "modulo": "PRESUPUESTO",
            "tipo": "AUTOMATICA",
            "fecha_inicio": base_hoy,
            "recurrencia": "MENSUAL",
            "recurrencia_config": {"hora": "07:30", "dia_mes": 5},
            "funcion_callback": "analisis_mensual_presupuesto",
        },
        {
            "titulo": "Revisión contratos personal",
            "modulo": "RRHH",
            "tipo": "VENCIMIENTO",
            "fecha_inicio": base_hoy,
            "recurrencia": "MENSUAL",
            "recurrencia_config": {"hora": "07:35", "dia_mes": 1},
            "funcion_callback": "revisar_contratos",
        },
        {
            "titulo": "Revisión nómina",
            "modulo": "PAGOS",
            "tipo": "AUTOMATICA",
            "fecha_inicio": base_hoy,
            "recurrencia": "MENSUAL",
            "recurrencia_config": {"hora": "07:45", "dia_mes": 24},
            "funcion_callback": "revision_nomina",
        },
        {
            "titulo": "Revisión normatividad jurídica",
            "modulo": "JURIDICO",
            "tipo": "AUTOMATICA",
            "fecha_inicio": base_hoy,
            "recurrencia": "SEMANAL",
            "recurrencia_config": {"hora": "09:00", "dias_semana": [0]},
            "funcion_callback": "revisar_normatividad",
        },
    ]

    conn = get_conn()
    c = conn.cursor()
    antes = c.execute("SELECT COUNT(*) FROM calendario_maestro").fetchone()[0]

    for t in plantillas:
        if not _ya_existe(c, t["titulo"], t["modulo"]):
            config_json = json.dumps(t.get("recurrencia_config") or {}, ensure_ascii=False)
            proxima = _primera_ejecucion(
                t["fecha_inicio"], t.get("recurrencia"), t.get("recurrencia_config")
            )
            c.execute(
                """INSERT INTO calendario_maestro
                   (titulo, descripcion, modulo, tipo, prioridad, fecha_inicio,
                    recurrencia, recurrencia_config, activa, fecha_proxima_ejecucion,
                    funcion_callback, creada_por)
                   VALUES (?,?,?,?,?,?,?,?,1,?,?, 'SISTEMA')""",
                (
                    t["titulo"],
                    t.get("descripcion"),
                    t["modulo"],
                    t["tipo"],
                    t.get("prioridad", "MEDIA"),
                    t["fecha_inicio"].isoformat(timespec="seconds"),
                    t.get("recurrencia"),
                    config_json,
                    proxima.isoformat(timespec="seconds"),
                    t.get("funcion_callback"),
                ),
            )

    conn.commit()
    despues = c.execute("SELECT COUNT(*) FROM calendario_maestro").fetchone()[0]
    conn.close()
    nuevas = despues - antes
    if nuevas:
        logger.info("Calendario maestro: %s tareas sembradas", nuevas)
    return nuevas
