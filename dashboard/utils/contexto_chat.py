"""Contexto en tiempo real por módulo para el chat interactivo."""
from datetime import date

from dashboard.utils.db_helper import query_df
from database import obtener_alertas_activas, obtener_estadisticas_hoy, obtener_pagos_pendientes


def _tabla_existe(nombre: str) -> bool:
    try:
        query_df("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nombre,))
        return not query_df("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nombre,)).empty
    except Exception:
        return False


def _resumen_df(sql: str, etiqueta: str, cols: list[str], limite: int = 5) -> str:
    try:
        df = query_df(sql)
        if df.empty:
            return f"{etiqueta}: sin registros."
        lineas = []
        for _, row in df.head(limite).iterrows():
            partes = [f"{c}={row[c]}" for c in cols if c in df.columns]
            lineas.append("  · " + " | ".join(str(p) for p in partes))
        extra = f" (+{len(df) - limite} más)" if len(df) > limite else ""
        return f"{etiqueta} ({len(df)} total{extra}):\n" + "\n".join(lineas)
    except Exception as e:
        return f"{etiqueta}: no disponible ({e})"


def construir_contexto_modulos() -> str:
    """Arma snapshot de todos los módulos para el system prompt del chat."""
    stats = obtener_estadisticas_hoy()
    alertas = obtener_alertas_activas()[:5]
    pagos = obtener_pagos_pendientes()[:5]

    alertas_txt = "\n".join(f"  · [{a[3]}] {a[4]}: {a[5]}" for a in alertas) or "  · Sin alertas activas"
    pagos_txt = "\n".join(f"  · #{p[0]} {p[2]}: ${p[4]:,.0f} ({p[7]})" for p in pagos) or "  · Sin pagos pendientes"

    bloques = [
        f"=== RESUMEN GENERAL ({date.today().isoformat()}) ===",
        f"Correos hoy: {stats['correos_hoy']} | Alertas activas: {stats['alertas_activas']} | "
        f"Pagos por aprobar: {stats['pagos_pendientes']} | Costo API hoy: ${stats['costo_hoy']}",
        "",
        "=== ALERTAS ===",
        alertas_txt,
        "",
        "=== PAGOS (aprobar/rechazar por ID) ===",
        pagos_txt,
        "",
        "=== CORREOS ===",
        _resumen_df(
            "SELECT categoria, COUNT(*) as total FROM correos_procesados GROUP BY categoria ORDER BY total DESC",
            "Por categoría",
            ["categoria", "total"],
            8,
        ),
        "",
        "=== IMPUESTOS ===",
        _resumen_df(
            "SELECT impuesto, periodo, fecha_vencimiento, estado FROM impuestos_maestro ORDER BY fecha_vencimiento LIMIT 8",
            "Vencimientos",
            ["impuesto", "periodo", "fecha_vencimiento", "estado"],
        ),
        "",
        "=== CONTABILIDAD ===",
        _resumen_df(
            "SELECT fuente, saldo, fecha FROM conciliacion_bancaria ORDER BY fecha DESC",
            "Conciliación",
            ["fuente", "saldo", "fecha"],
        ),
        "",
        "=== CXP / CXC ===",
        _resumen_df(
            "SELECT cliente, saldo, dias_mora, bloqueado FROM cartera_cxc ORDER BY dias_mora DESC",
            "Cartera clientes",
            ["cliente", "saldo", "dias_mora", "bloqueado"],
        ),
        _resumen_df(
            "SELECT proveedor, concepto, monto, fecha_pago FROM cxp_programados ORDER BY fecha_pago",
            "CXP programados",
            ["proveedor", "concepto", "monto", "fecha_pago"],
        ),
        "",
        "=== CRÉDITOS ===",
        _resumen_df(
            "SELECT cliente, cupo_solicitado, decision, estado_habilitacion FROM creditos_analizados ORDER BY id DESC",
            "Solicitudes",
            ["cliente", "cupo_solicitado", "decision", "estado_habilitacion"],
        ),
        "",
        "=== COMISIONES ===",
        _resumen_df(
            "SELECT asesor, ventas, comision_neta, periodo FROM comisiones_detalle ORDER BY id DESC",
            "Liquidación",
            ["asesor", "ventas", "comision_neta", "periodo"],
        ),
        "",
        "=== PERSONAL / RRHH ===",
        _resumen_df(
            "SELECT empleado, tipo, fecha_fin, estado FROM contratos_rrhh ORDER BY fecha_fin",
            "Contratos",
            ["empleado", "tipo", "fecha_fin", "estado"],
        ),
        _resumen_df(
            "SELECT empleado, tipo, fecha_inicio, estado FROM novedades_rrhh ORDER BY id DESC",
            "Novedades",
            ["empleado", "tipo", "fecha_inicio", "estado"],
        ),
        "",
        "=== PRESUPUESTO ===",
        _resumen_df(
            "SELECT rubro, presupuesto, ejecutado FROM presupuesto_rubros ORDER BY rubro",
            "Rubros",
            ["rubro", "presupuesto", "ejecutado"],
        ),
        "",
        "=== JURÍDICO ===",
        _resumen_df(
            "SELECT nombre, version, estado FROM politicas_internas ORDER BY id DESC",
            "Políticas",
            ["nombre", "version", "estado"],
        ),
    ]
    return "\n".join(bloques)
