"""Tablas SQLite para módulo Personal / RRHH (sin IA)."""
import logging

from database import get_conn

logger = logging.getLogger(__name__)


def inicializar_tablas_rrhh() -> None:
    """Crea tablas RRHH según especificación del módulo Personal."""
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS novedades_rrhh (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado TEXT NOT NULL,
        tipo TEXT NOT NULL,
        fecha_inicio DATE,
        fecha_fin DATE,
        dias_habiles INTEGER,
        estado TEXT DEFAULT 'PENDIENTE',
        notas TEXT,
        fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS dotacion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado TEXT NOT NULL,
        item TEXT NOT NULL,
        talla TEXT,
        fecha_entrega DATE,
        proxima_entrega DATE,
        entregado BOOLEAN DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS candidatos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        cargo TEXT,
        fecha_aplicacion DATE,
        estado TEXT DEFAULT 'RECIBIDO',
        notas TEXT,
        dias_proceso INTEGER
    );

    CREATE TABLE IF NOT EXISTS empleados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        cargo TEXT,
        fecha_ingreso DATE,
        salario NUMERIC,
        tipo_contrato TEXT,
        cedula TEXT,
        ruta_expediente TEXT,
        activo BOOLEAN DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS expediente_documentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado TEXT NOT NULL,
        ruta_absoluta TEXT UNIQUE NOT NULL,
        nombre_archivo TEXT NOT NULL,
        extension TEXT,
        categoria TEXT,
        tamano_bytes INTEGER,
        fecha_modificacion REAL,
        texto_extraible INTEGER DEFAULT 0,
        preview TEXT,
        fecha_indexado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS expediente_sync (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        ultima_sync TIMESTAMP,
        archivos_total INTEGER DEFAULT 0,
        empleados_total INTEGER DEFAULT 0,
        carpeta_base TEXT
    );

    CREATE TABLE IF NOT EXISTS empleados_carpetas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_carpeta TEXT UNIQUE NOT NULL,
        nombre_display TEXT NOT NULL,
        ruta_carpeta TEXT NOT NULL,
        activo BOOLEAN DEFAULT 1,
        fecha_deteccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ultima_actualizacion TIMESTAMP,
        total_documentos INTEGER DEFAULT 0,
        docs_faltantes TEXT,
        completitud_pct INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS documentos_empleado (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado_id INTEGER REFERENCES empleados_carpetas(id),
        nombre_archivo TEXT NOT NULL,
        ruta_archivo TEXT NOT NULL,
        categoria TEXT NOT NULL,
        extension TEXT,
        tamanio_kb INTEGER,
        fecha_archivo DATE,
        fecha_deteccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(empleado_id, nombre_archivo)
    );

    CREATE TABLE IF NOT EXISTS log_cambios_carpetas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado TEXT NOT NULL,
        tipo_cambio TEXT NOT NULL,
        archivo TEXT,
        categoria TEXT,
        fecha_cambio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        procesado BOOLEAN DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS empleados_fenix (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_completo TEXT NOT NULL,
        cedula TEXT,
        tipo_plantilla TEXT DEFAULT 'nomina_activo',
        activo BOOLEAN DEFAULT 1,
        cargo TEXT,
        departamento TEXT,
        jefe_inmediato TEXT,
        lugar_labor TEXT,
        tipo_contrato TEXT,
        termino TEXT,
        fecha_ingreso DATE,
        vencimiento_contrato DATE,
        fecha_preaviso DATE,
        fecha_nacimiento DATE,
        telefono TEXT,
        email_corporativo TEXT,
        email_personal TEXT,
        direccion TEXT,
        barrio TEXT,
        ciudad TEXT,
        salario_ibc TEXT,
        salud TEXT,
        pension TEXT,
        cesantias TEXT,
        caja_compensacion TEXT,
        ref_emergencia TEXT,
        parentesco_emergencia TEXT,
        tel_emergencia TEXT,
        observaciones TEXT,
        carpeta_vinculada TEXT,
        datos_json TEXT,
        origen TEXT DEFAULT 'import',
        fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS novedades_fenix (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado_id INTEGER,
        nombre_completo TEXT NOT NULL,
        cedula TEXT,
        fecha_ingreso DATE,
        pendiente_dotacion TEXT,
        examenes_periodicos TEXT,
        meses_json TEXT,
        fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS vacaciones_fenix (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado_id INTEGER,
        nombre_completo TEXT NOT NULL,
        hoja_origen TEXT,
        dias_pendientes TEXT,
        dias_tomar TEXT,
        dias_pendientes_2025 TEXT,
        fecha_regreso DATE,
        observaciones TEXT,
        datos_json TEXT
    );

    CREATE TABLE IF NOT EXISTS cumpleanos_fenix (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        dia TEXT,
        mes TEXT
    );

    CREATE TABLE IF NOT EXISTS contratos_fijos_fenix (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado_id INTEGER,
        nombre_completo TEXT NOT NULL,
        cedula TEXT,
        cargo TEXT,
        fecha_inicio DATE,
        termino TEXT,
        vencimiento_contrato DATE,
        fecha_preaviso DATE,
        datos_json TEXT
    );

    CREATE TABLE IF NOT EXISTS personal_fenix_sync (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        ruta_archivo TEXT,
        ultima_importacion TIMESTAMP,
        empleados INTEGER DEFAULT 0,
        vinculados INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS contratos_activos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado_carpeta_id INTEGER,
        nombre_completo TEXT NOT NULL UNIQUE,
        cedula TEXT,
        fecha_ingreso DATE,
        cargo TEXT,
        sueldo_bruto TEXT,
        area TEXT,
        modalidad_trabajo TEXT,
        tipo_contrato TEXT,
        fecha_inicio DATE,
        fecha_fin DATE,
        estado TEXT DEFAULT 'ACTIVO',
        sctr TEXT,
        vida_ley TEXT,
        examen_medico TEXT,
        induccion TEXT,
        epp TEXT,
        doc_foto TEXT DEFAULT 'NO',
        doc_foto_ruta TEXT,
        doc_cv TEXT DEFAULT 'NO',
        doc_cv_ruta TEXT,
        doc_antecedentes TEXT DEFAULT 'NO',
        doc_antecedentes_ruta TEXT,
        doc_contrato TEXT DEFAULT 'NO',
        doc_contrato_ruta TEXT,
        doc_dni TEXT DEFAULT 'NO',
        doc_dni_ruta TEXT,
        doc_recibo_servicios TEXT DEFAULT 'NO',
        doc_recibo_ruta TEXT,
        doc_croquis TEXT DEFAULT 'NO',
        doc_croquis_ruta TEXT,
        doc_declaracion TEXT DEFAULT 'NO',
        doc_declaracion_ruta TEXT,
        doc_certificados TEXT DEFAULT 'NO',
        doc_certificados_ruta TEXT,
        observaciones TEXT,
        origen TEXT DEFAULT 'sync',
        fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    try:
        c.execute("ALTER TABLE empleados ADD COLUMN ruta_expediente TEXT")
    except Exception:
        pass
    _seed_empleados_demo(c)
    conn.commit()
    conn.close()
    logger.info("Tablas RRHH inicializadas.")


def _seed_empleados_demo(c) -> None:
    c.execute("SELECT COUNT(*) FROM empleados")
    if c.fetchone()[0] > 0:
        return
    try:
        from modulos.rrhh_expediente import carpeta_personal_base

        base = carpeta_personal_base()
        if base.is_dir() and any(p.is_dir() for p in base.iterdir()):
            return
    except Exception:
        pass
    demo = [
        ("María López", "Asistente contable", "2022-03-15", 2800000, "Término fijo", "1020304050"),
        ("Carlos Ruiz", "Auxiliar administrativo", "2023-01-10", 2200000, "Indefinido", "1030405060"),
        ("Ana Gómez", "Coordinadora RRHH", "2021-06-01", 3500000, "Indefinido", "1040506070"),
    ]
    for nom, cargo, fi, sal, tc, cc in demo:
        c.execute(
            """INSERT INTO empleados (nombre, cargo, fecha_ingreso, salario, tipo_contrato, cedula, activo)
               VALUES (?,?,?,?,?,?,1)""",
            (nom, cargo, fi, sal, tc, cc),
        )
