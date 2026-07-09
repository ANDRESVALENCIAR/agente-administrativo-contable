"""Tablas adicionales para módulos UI del prompt maestro."""
import logging
import sqlite3
from datetime import date, timedelta

from config import cfg
from database import get_conn

logger = logging.getLogger(__name__)


def inicializar_tablas_modulos() -> None:
    """Crea tablas de módulos Streamlit si no existen."""
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS impuestos_maestro (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        impuesto TEXT NOT NULL,
        periodo TEXT NOT NULL,
        fecha_vencimiento DATE,
        estado TEXT DEFAULT 'PENDIENTE',
        formulario TEXT,
        observaciones TEXT,
        UNIQUE(impuesto, periodo)
    );

    CREATE TABLE IF NOT EXISTS revisiones_dian (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        usuario TEXT,
        notas TEXT
    );

    CREATE TABLE IF NOT EXISTS reglas_correo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categoria TEXT UNIQUE NOT NULL,
        destino TEXT NOT NULL,
        activo INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS historial_pagos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proveedor TEXT,
        concepto TEXT,
        valor REAL,
        fecha_pago DATE,
        comprobante TEXT,
        estado TEXT DEFAULT 'PAGADO',
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS checklist_pagos_periodo (
        periodo TEXT PRIMARY KEY,
        nomina_revisada INTEGER DEFAULT 0,
        comisiones_liquidadas INTEGER DEFAULT 0,
        actualizado DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS cartera_cxc (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente TEXT,
        nit TEXT,
        saldo REAL,
        dias_mora INTEGER DEFAULT 0,
        ultima_gestion TEXT,
        notas TEXT,
        bloqueado INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS cxp_programados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proveedor TEXT,
        concepto TEXT,
        monto REAL,
        fecha_pago DATE,
        estado TEXT DEFAULT 'PROGRAMADO',
        pp_via_confirmado INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS incapacidades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado TEXT,
        fecha_inicio DATE,
        dias INTEGER,
        estado TEXT DEFAULT 'RADICADA',
        notas TEXT
    );

    CREATE TABLE IF NOT EXISTS comisiones_detalle (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asesor TEXT,
        ventas REAL DEFAULT 0,
        recaudo REAL DEFAULT 0,
        notas_credito REAL DEFAULT 0,
        anticipos REAL DEFAULT 0,
        comision_bruta REAL DEFAULT 0,
        deducciones REAL DEFAULT 0,
        retenciones REAL DEFAULT 0,
        comision_neta REAL DEFAULT 0,
        pagado INTEGER DEFAULT 0,
        periodo TEXT
    );

    CREATE TABLE IF NOT EXISTS retenciones_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        porcentaje REAL,
        umbral REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS personal_novedades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado TEXT,
        tipo TEXT,
        fecha_inicio DATE,
        fecha_fin DATE,
        estado TEXT DEFAULT 'REGISTRADO',
        notas TEXT
    );

    CREATE TABLE IF NOT EXISTS contratos_rrhh (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado TEXT,
        tipo TEXT,
        fecha_inicio DATE,
        fecha_fin DATE,
        estado TEXT DEFAULT 'VIGENTE'
    );

    CREATE TABLE IF NOT EXISTS dotacion_rrhh (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado TEXT,
        periodo TEXT,
        items TEXT,
        entregado INTEGER DEFAULT 0,
        fecha_entrega DATE
    );

    CREATE TABLE IF NOT EXISTS examenes_medicos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado TEXT,
        tipo TEXT,
        fecha_vencimiento DATE,
        estado TEXT DEFAULT 'VIGENTE'
    );

    CREATE TABLE IF NOT EXISTS candidatos_rrhh (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        cargo TEXT,
        fecha DATE,
        notas_entrevista TEXT
    );

    CREATE TABLE IF NOT EXISTS presupuesto_rubros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rubro TEXT,
        mes INTEGER,
        anio INTEGER,
        presupuesto REAL DEFAULT 0,
        ejecutado REAL DEFAULT 0,
        UNIQUE(rubro, mes, anio)
    );

    CREATE TABLE IF NOT EXISTS conciliacion_bancaria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fuente TEXT,
        saldo REAL,
        fecha DATE,
        UNIQUE(fuente, fecha)
    );

    CREATE TABLE IF NOT EXISTS normatividad (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT,
        titulo TEXT,
        fecha_actualizacion DATE,
        responsable TEXT
    );

    CREATE TABLE IF NOT EXISTS politicas_internas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        version TEXT,
        fecha DATE,
        estado TEXT DEFAULT 'VIGENTE'
    );

    CREATE TABLE IF NOT EXISTS jornadas_laborales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado TEXT,
        modalidad TEXT
    );

    CREATE TABLE IF NOT EXISTS cache_api (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clave TEXT UNIQUE,
        respuesta TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()
    _seed_datos_demo()
    try:
        from modulos.comparador_comisiones import inicializar_tablas_comparador
        inicializar_tablas_comparador()
    except Exception as e:
        logger.warning("Tablas comparador comisiones: %s", e)


def _seed_datos_demo() -> None:
    """Datos demo para módulos UI."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM impuestos_maestro")
    if c.fetchone()[0] > 0:
        conn.close()
        return

    hoy = date.today()
    impuestos = [
        ("IVA", "2026-06", (hoy + timedelta(days=10)).isoformat(), "PENDIENTE", "350", ""),
        ("Retefuente", "2026-06", (hoy + timedelta(days=5)).isoformat(), "EN REVISIÓN", "350", "Revisar soporte"),
    ]
    for imp, per, fv, est, form, obs in impuestos:
        c.execute(
            "INSERT OR IGNORE INTO impuestos_maestro (impuesto,periodo,fecha_vencimiento,estado,formulario,observaciones) VALUES (?,?,?,?,?,?)",
            (imp, per, fv, est, form, obs),
        )

    reglas = [
        ("factura", cfg.EMAIL_CONTABILIDAD or "contabilidad@empresa.com"),
        ("pqr", cfg.EMAIL_SERVICIO or "servicio@empresa.com"),
        ("registro_proveedor", cfg.EMAIL_COMPRAS or "compras@empresa.com"),
        ("solicitud_pago", cfg.EMAIL_PAGOS or "pagos@empresa.com"),
        ("cobranza", cfg.EMAIL_CARTERA or "cartera@empresa.com"),
        ("juridico", cfg.EMAIL_LEGAL or "legal@empresa.com"),
        ("extracto_bancario", cfg.EMAIL_CONTABILIDAD or "contabilidad@empresa.com"),
        ("comunicacion_interna", cfg.EMAIL_GERENCIA or "gerencia@empresa.com"),
        ("nomina", cfg.EMAIL_RRHH or "rrhh@empresa.com"),
        ("incapacidad", cfg.EMAIL_RRHH or "rrhh@empresa.com"),
        ("otro", cfg.EMAIL_GERENCIA or "gerencia@empresa.com"),
    ]
    for cat, dest in reglas:
        c.execute(
            "INSERT OR IGNORE INTO reglas_correo (categoria, destino, activo) VALUES (?,?,1)",
            (cat, dest),
        )

    c.execute(
        "INSERT INTO cartera_cxc (cliente,nit,saldo,dias_mora,bloqueado) VALUES (?,?,?,?,?)",
        ("Cliente Alfa", "900111222-3", 3200000, 75, 0),
    )
    c.execute(
        "INSERT INTO cartera_cxc (cliente,nit,saldo,dias_mora,bloqueado) VALUES (?,?,?,?,?)",
        ("Comercial ABC", "800333444-1", 1200000, 45, 0),
    )
    c.execute(
        "INSERT INTO cartera_cxc (cliente,nit,saldo,dias_mora,bloqueado) VALUES (?,?,?,?,?)",
        ("Distribuidora Norte", "901555666-7", 850000, 15, 0),
    )
    c.execute(
        "INSERT INTO cxp_programados (proveedor,concepto,monto,fecha_pago) VALUES (?,?,?,?)",
        ("Proveedor Beta", "Servicios", 1800000, hoy.isoformat()),
    )
    c.execute(
        "INSERT INTO comisiones_detalle (asesor,ventas,recaudo,comision_bruta,comision_neta,periodo) VALUES (?,?,?,?,?,?)",
        ("Juan Pérez", 45000000, 38000000, 1125000, 980000, "2026-06"),
    )
    c.execute(
        "INSERT INTO contratos_rrhh (empleado,tipo,fecha_inicio,fecha_fin) VALUES (?,?,?,?)",
        ("María López", "Término fijo", "2025-01-01", (hoy + timedelta(days=20)).isoformat()),
    )
    c.execute(
        "INSERT OR IGNORE INTO presupuesto_rubros (rubro,mes,anio,presupuesto,ejecutado) VALUES (?,?,?,?,?)",
        ("Personal", hoy.month, hoy.year, 50000000, 52000000),
    )
    for rubro, pres, ejec in [("Operación", 30000000, 28500000), ("Marketing", 8000000, 9200000)]:
        c.execute(
            "INSERT OR IGNORE INTO presupuesto_rubros (rubro,mes,anio,presupuesto,ejecutado) VALUES (?,?,?,?,?)",
            (rubro, hoy.month, hoy.year, pres, ejec),
        )
    c.execute(
        "INSERT INTO conciliacion_bancaria (fuente,saldo,fecha) VALUES (?,?,?)",
        ("Banco Lili", 10500000, hoy.isoformat()),
    )
    c.execute(
        "INSERT INTO conciliacion_bancaria (fuente,saldo,fecha) VALUES (?,?,?)",
        ("Contabilidad", 10480000, hoy.isoformat()),
    )
    c.execute(
        "INSERT INTO retenciones_config (nombre,porcentaje,umbral) VALUES (?,?,?)",
        ("Retención fuente", 11.0, 1090000),
    )
    c.execute(
        "INSERT INTO historial_pagos (proveedor,concepto,valor,fecha_pago,comprobante) VALUES (?,?,?,?,?)",
        ("Papelería Central", "Suministros", 450000, (hoy - timedelta(days=3)).isoformat(), "TRF-001"),
    )
    c.execute(
        "INSERT INTO incapacidades (empleado,fecha_inicio,dias,estado) VALUES (?,?,?,?)",
        ("Carlos Ruiz", (hoy - timedelta(days=5)).isoformat(), 3, "RADICADA"),
    )
    c.execute(
        "INSERT INTO personal_novedades (empleado,tipo,fecha_inicio,fecha_fin,estado) VALUES (?,?,?,?,?)",
        ("Ana Gómez", "Vacaciones", (hoy + timedelta(days=7)).isoformat(), (hoy + timedelta(days=14)).isoformat(), "APROBADO"),
    )
    c.execute(
        "INSERT INTO dotacion_rrhh (empleado,periodo,items,entregado) VALUES (?,?,?,?)",
        ("Pedro Sánchez", "2026-S1", "Camisa, pantalón, botas", 0),
    )
    c.execute(
        "INSERT INTO examenes_medicos (empleado,tipo,fecha_vencimiento) VALUES (?,?,?)",
        ("María López", "Periódico", (hoy + timedelta(days=30)).isoformat()),
    )
    c.execute(
        "INSERT INTO candidatos_rrhh (nombre,cargo,fecha,notas_entrevista) VALUES (?,?,?,?)",
        ("Laura Martínez", "Asistente contable", hoy.isoformat(), "Buen perfil, referencias OK"),
    )
    c.execute(
        "INSERT INTO normatividad (tipo,titulo,fecha_actualizacion,responsable) VALUES (?,?,?,?)",
        ("Laboral", "Reforma laboral 2025", hoy.isoformat(), "Jurídico"),
    )
    c.execute(
        "INSERT INTO politicas_internas (nombre,version,fecha) VALUES (?,?,?)",
        ("Política de datos", "v2.1", hoy.isoformat()),
    )
    c.execute(
        "INSERT INTO jornadas_laborales (empleado,modalidad) VALUES (?,?)",
        ("María López", "Híbrida"),
    )
    conn.commit()
    conn.close()
    logger.info("Datos demo módulos UI cargados.")


def _periodo_actual() -> str:
    return date.today().strftime("%Y-%m")


def obtener_checklist_pagos_periodo(periodo: str | None = None) -> dict[str, bool]:
    """Retorna estado del checklist de nómina/comisiones del período."""
    periodo = periodo or _periodo_actual()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT nomina_revisada, comisiones_liquidadas FROM checklist_pagos_periodo WHERE periodo=?",
        (periodo,),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return {"nomina_revisada": False, "comisiones_liquidadas": False}
    return {"nomina_revisada": bool(row[0]), "comisiones_liquidadas": bool(row[1])}


def guardar_checklist_pagos_periodo(
    nomina_revisada: bool,
    comisiones_liquidadas: bool,
    periodo: str | None = None,
) -> None:
    """Persiste checklist de cierre de período en pagos."""
    periodo = periodo or _periodo_actual()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO checklist_pagos_periodo (periodo, nomina_revisada, comisiones_liquidadas, actualizado)
           VALUES (?,?,?,CURRENT_TIMESTAMP)
           ON CONFLICT(periodo) DO UPDATE SET
             nomina_revisada=excluded.nomina_revisada,
             comisiones_liquidadas=excluded.comisiones_liquidadas,
             actualizado=CURRENT_TIMESTAMP""",
        (periodo, int(nomina_revisada), int(comisiones_liquidadas)),
    )
    conn.commit()
    conn.close()
