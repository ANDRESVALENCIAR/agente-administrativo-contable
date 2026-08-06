"""Catálogos de periodicidades y categorías de gasto para EIF SAS."""
from __future__ import annotations

import json
import logging

from database import get_conn

logger = logging.getLogger(__name__)

PERIODICIDADES_STD = [
    ("MENSUAL", "Mensual", "📅", "Cada mes, fecha fija", False, 30),
    ("SEMANAL", "Semanal", "📆", "Cada semana (ej: nómina)", False, 7),
    ("QUINCENAL", "Quincenal", "📆", "Días 1 y 16 de cada mes", False, 15),
    ("BIMESTRAL", "Bimestral", "📅", "Cada 2 meses", False, 60),
    ("SEMESTRAL", "Semestral", "📅", "Cada 6 meses", False, 180),
    ("ANUAL", "Anual", "🗓️", "Una vez al año", False, 365),
    ("IMPUESTO_MENSUAL", "Impuesto Mensual", "🏛️", "Tributario mensual (DIAN/SHD)", True, 30),
    ("IMPUESTO_BIMESTRAL", "Impuesto Bimestral", "🏛️", "IVA, ICA (cada 2 meses)", True, 60),
    ("IMPUESTO_ANUAL", "Impuesto Anual", "🏛️", "Renta, Exógena", True, 365),
    ("ESPORADICO", "Esporádico", "⚡", "Sin frecuencia fija", False, None),
    ("COMPRA", "Compra", "🛒", "Adquisición única", False, None),
    ("REUNION", "Reunión/Cita", "🤝", "Evento puntual", False, None),
]

CATEGORIAS_GASTO = [
    (
        "NOMINA_RRHH",
        "Nómina / RRHH",
        "👥",
        "#0071E3",
        [
            "NOMINA", "PRIMA", "VACACION", "CESANTIA", "DOTACION", "LIQUIDACION",
            "PLANILLA", "COMISION", "GIRO CTAS", "CRUCE CTAS", "PAGO NOMINA",
        ],
        "PAGOS",
    ),
    (
        "IMPUESTOS_DIAN",
        "Impuestos DIAN",
        "🏛️",
        "#AF52DE",
        [
            "IVA", "RETENCION", "RENTA", "DECLARACION", "EXOGENA",
            "ANTICIPO IVA", "DIAN", "CERTIFICADO INGRESOS",
        ],
        "IMPUESTOS",
    ),
    (
        "IMPUESTOS_SHD",
        "Impuestos SHD",
        "🏛️",
        "#5856D6",
        ["ICA", "RETEICA", "SHD", "PREDIAL", "INDUSTRIA COMERCIO"],
        "IMPUESTOS",
    ),
    (
        "SERVICIOS_PUBLICOS",
        "Servicios Públicos",
        "💡",
        "#FF9F0A",
        [
            "LUZ", "AGUA", "GAS", "INTERNET", "CELSIA", "CODENSA", "ACUAVALLE",
            "ETB", "CLARO", "TIGO", "UNE", "MOVISTAR", "EPM", "WIFI",
        ],
        "PAGOS",
    ),
    (
        "TELECOMUNICACIONES",
        "Telecomunicaciones",
        "📡",
        "#64D2FF",
        [
            "MOVISTAR CORPORATIVO", "CLARO OF", "TIGO UNE", "ETB DEDICADO",
            "SERVIDOR", "HOSTING", "DOMINIO",
        ],
        "PAGOS",
    ),
    (
        "ARRIENDO_INMUEBLE",
        "Arriendo / Inmueble",
        "🏠",
        "#30D158",
        ["ARRIENDO", "LEASING SVH", "BODEGAJE"],
        "PAGOS",
    ),
    (
        "ADMON_INMUEBLE",
        "Admón. Inmueble",
        "🏢",
        "#34C759",
        ["ADMON", "ADMINISTRACION", "SENDEROS", "CENTRUM SVH"],
        "PAGOS",
    ),
    (
        "CREDITOS_BANCARIOS",
        "Créditos Bancarios",
        "💳",
        "#FF453A",
        [
            "CUOTA", "BANCO DE BOGOTA", "BANCOLOMBIA", "DAVIVIENDA", "FALABELLA",
            "CMR", "TC ", "TARJETA", "NUBANK", "CREDITO",
        ],
        "CREDITOS",
    ),
    (
        "SALUD_EPS",
        "Salud EPS",
        "🏥",
        "#FF375F",
        ["COOMEVA", "EPS", "MEDICINA PREPAGADA"],
        "PERSONAL",
    ),
    (
        "SALUD_CITAS",
        "Salud / Citas",
        "🩺",
        "#FF2D55",
        [
            "CITA", "EXAMEN MEDICO", "LABORATORIO", "OFTALMOLOGIA",
            "ODONTOLOGIA", "OTORRINO", "CITOLOGIA",
        ],
        "PERSONAL",
    ),
    (
        "EDUCACION_COLEGIOS",
        "Educación Colegios",
        "🎒",
        "#FFD60A",
        [
            "PENSION", "COLEGIO", "DIANA OESE", "ACADEMIA", "DEPORTIVO CALI",
            "RUTA", "CAFETERIA", "UNIFORMES",
        ],
        "PAGOS",
    ),
    (
        "EDUCACION_UNIVERSIDAD",
        "Educación Universidad",
        "🎓",
        "#FFCC00",
        [
            "USB", "MATRICULA", "DERECHO", "EPISTEMOLOGIA", "INGLES",
            "EXAMEN FINAL", "MOODLE",
        ],
        "PAGOS",
    ),
    (
        "TECNOLOGIA_SOFTWARE",
        "Tecnología / Software",
        "💻",
        "#5E5CE6",
        ["BITRIX", "BUFFER", "CAMINOWEB", "WAZZUP", "SOFTWARE", "SUSCRIPCION", "AXXIS"],
        "PAGOS",
    ),
    (
        "VEHICULOS",
        "Vehículos",
        "🚗",
        "#8E8E93",
        ["SOAT", "TECNICOMECANICA", "GASOLINA", "BMW", "MOTO", "PASE MOTO", "BAVARIAN"],
        "PAGOS",
    ),
    (
        "SEGUROS_POLIZAS",
        "Seguros / Pólizas",
        "🛡️",
        "#636366",
        ["SEGURO", "POLIZA", "ARL"],
        "PAGOS",
    ),
    (
        "PERSONAL_FAMILIA",
        "Personal / Familia",
        "👨‍👩‍👧",
        "#FF9F0A",
        [
            "AYUDA", "AHIJADO", "MAMI", "CUMPLEANOS", "ANIVERSARIO",
            "DIA PADRE", "DIA FAMILIA", "ENTRENADOR", "TOMAS",
        ],
        "PAGOS",
    ),
    (
        "PROVEEDORES_EXT",
        "Proveedores Externos",
        "🔧",
        "#A2845E",
        [
            "SERVICIOS XYZ", "PAPELERIA", "MANTENIMIENTO", "MANT PISCINA",
            "ASEO", "EMPLEADA",
        ],
        "PAGOS",
    ),
    (
        "COMPRAS_VARIAS",
        "Compras Varias",
        "🛒",
        "#AC8E68",
        ["LLEGADA", "COMPRA", "MERCADO", "ALKOSTO", "ARMANI", "GUAYOS", "ZAPATOS", "LIBROS"],
        "PAGOS",
    ),
    (
        "JURIDICO",
        "Jurídico",
        "⚖️",
        "#1C1C1E",
        ["ABOGADO", "MUNARTH", "CONTRATO", "PREAVISO", "SIC", "AUDIENCIA", "DERECHOS"],
        "JURIDICO",
    ),
    (
        "TAREAS_ADMIN",
        "Tareas Admin",
        "📝",
        "#AEAEB2",
        [
            "ACTUALIZAR", "GRABAR", "REPORTAR", "ENTREGAR", "INGRESAR",
            "HACER", "VERIFICAR", "CORRECCION",
        ],
        "PAGOS",
    ),
    ("OTRO", "Otro / Sin clasificar", "❓", "#C7C7CC", [], "PAGOS"),
]


def inicializar_catalogos_gastos() -> None:
    """Crea tablas de catálogo y gastos_maestro; siembra valores oficiales."""
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cat_periodicidades (
            codigo TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            icono TEXT,
            descripcion TEXT,
            es_impuesto INTEGER DEFAULT 0,
            frecuencia_dias INTEGER,
            activo INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS cat_categorias_gasto (
            codigo TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            icono TEXT,
            color_hex TEXT,
            keywords TEXT,
            modulo_agente TEXT,
            activo INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS gastos_maestro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detalle_original TEXT NOT NULL,
            detalle_limpio TEXT,
            proveedor_original TEXT,
            proveedor_limpio TEXT,
            periodicidad_original TEXT,
            periodicidad_std TEXT REFERENCES cat_periodicidades(codigo),
            categoria TEXT REFERENCES cat_categorias_gasto(codigo),
            centro_costos TEXT,
            clasificado_auto INTEGER DEFAULT 1,
            requiere_revision INTEGER DEFAULT 0,
            confianza REAL DEFAULT 0,
            fecha_clasificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            origen TEXT DEFAULT 'EXCEL'
        );

        CREATE INDEX IF NOT EXISTS idx_gastos_cat ON gastos_maestro(categoria);
        CREATE INDEX IF NOT EXISTS idx_gastos_per ON gastos_maestro(periodicidad_std);
        CREATE INDEX IF NOT EXISTS idx_gastos_rev ON gastos_maestro(requiere_revision);
        CREATE INDEX IF NOT EXISTS idx_gastos_det ON gastos_maestro(detalle_limpio);
        """
    )
    for codigo, label, icono, desc, es_imp, freq in PERIODICIDADES_STD:
        conn.execute(
            """INSERT INTO cat_periodicidades
               (codigo, label, icono, descripcion, es_impuesto, frecuencia_dias, activo)
               VALUES (?,?,?,?,?,?,1)
               ON CONFLICT(codigo) DO UPDATE SET
                 label=excluded.label, icono=excluded.icono,
                 descripcion=excluded.descripcion, es_impuesto=excluded.es_impuesto,
                 frecuencia_dias=excluded.frecuencia_dias, activo=1""",
            (codigo, label, icono, desc, int(es_imp), freq),
        )
    for codigo, label, icono, color, keywords, modulo in CATEGORIAS_GASTO:
        conn.execute(
            """INSERT INTO cat_categorias_gasto
               (codigo, label, icono, color_hex, keywords, modulo_agente, activo)
               VALUES (?,?,?,?,?,?,1)
               ON CONFLICT(codigo) DO UPDATE SET
                 label=excluded.label, icono=excluded.icono, color_hex=excluded.color_hex,
                 keywords=excluded.keywords, modulo_agente=excluded.modulo_agente, activo=1""",
            (codigo, label, icono, color, json.dumps(keywords, ensure_ascii=False), modulo),
        )
    conn.commit()
    conn.close()
    logger.info("Catálogos de gastos inicializados.")


def mapa_categorias() -> dict[str, dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT codigo, label, icono, color_hex FROM cat_categorias_gasto WHERE activo=1"
    ).fetchall()
    conn.close()
    return {r[0]: {"label": r[1], "icono": r[2], "color": r[3]} for r in rows}


def mapa_periodicidades() -> dict[str, dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT codigo, label, icono FROM cat_periodicidades WHERE activo=1"
    ).fetchall()
    conn.close()
    return {r[0]: {"label": r[1], "icono": r[2]} for r in rows}
