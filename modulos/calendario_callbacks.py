"""Callbacks registrados para el calendario maestro."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger(__name__)


def generar_resumen_dia() -> dict[str, Any]:
    """Resumen matutino: tareas del día y pendientes vencidas."""
    from database import registrar_accion
    from utils.calendario_maestro import es_festivo, tareas_hoy, tareas_vencidas

    hoy = tareas_hoy()
    vencidas = tareas_vencidas()
    festivo = es_festivo(datetime.now().date())
    msg = (
        f"Tareas hoy: {len(hoy)} · Vencidas: {len(vencidas)} · "
        f"Festivo: {'Sí' if festivo else 'No'}"
    )
    registrar_accion("SISTEMA", "generar_resumen_dia", msg, "EXITOSO")
    return {"tareas_hoy": len(hoy), "vencidas": len(vencidas), "festivo": festivo}


def analisis_presupuesto_mes_actual() -> None:
    from modulos.presupuesto import analisis_mensual_presupuesto

    now = datetime.now()
    analisis_mensual_presupuesto(now.month, now.year)


def revision_normatividad_semanal() -> None:
    from modulos.juridico import revisar_normatividad

    revisar_normatividad()


def revision_formularios_mes() -> None:
    from modulos.impuestos import revision_formularios

    now = datetime.now()
    revision_formularios(now.month, now.year)


def revisar_politicas_internas() -> None:
    from modulos.juridico import revisar_politicas

    revisar_politicas()


def sincronizar_cartera_cxc() -> None:
    from modulos.cxp_cxc import sincronizar_cartera_desde_excel

    sincronizar_cartera_desde_excel()


def liquidar_comisiones_mes_anterior() -> None:
    """Liquida comisiones del mes calendario anterior (tarea programada)."""
    from dateutil.relativedelta import relativedelta
    from modulos.comisiones import liquidar_comisiones_mes

    ref = datetime.now() - relativedelta(months=1)
    liquidar_comisiones_mes(ref.month, ref.year)


def _lazy(name: str, import_path: str, attr: str) -> Callable[..., Any]:
    def _fn(*args, **kwargs):
        import importlib

        mod = importlib.import_module(import_path)
        fn = getattr(mod, attr)
        return fn(*args, **kwargs)

    _fn.__name__ = name
    return _fn


CALLBACKS: dict[str, Callable[..., Any]] = {
    "escanear_carpetas_personal": _lazy(
        "escanear_carpetas_personal", "modulos.carpetas_rrhh", "escanear_carpetas_personal"
    ),
    "generar_alertas_carpetas": _lazy(
        "generar_alertas_carpetas", "modulos.carpetas_rrhh", "generar_alertas_carpetas"
    ),
    "generar_resumen_dia": generar_resumen_dia,
    "procesar_correos": _lazy("procesar_correos", "modulos.correos", "procesar_correos"),
    "generar_resumen_diario_correos": _lazy(
        "generar_resumen_diario_correos", "modulos.correos", "generar_resumen_diario_correos"
    ),
    "revisar_vencimientos": _lazy("revisar_vencimientos", "modulos.impuestos", "revisar_vencimientos"),
    "enviar_recordatorios_vencimientos": _lazy(
        "enviar_recordatorios_vencimientos",
        "modulos.impuestos_calendario",
        "enviar_recordatorios_vencimientos",
    ),
    "sincronizar_calendario_opendata": _lazy(
        "sincronizar_calendario_opendata",
        "modulos.impuestos_calendario",
        "sincronizar_calendario_opendata",
    ),
    "revisar_cxp_diario": _lazy("revisar_cxp_diario", "modulos.pagos", "revisar_cxp_diario"),
    "revision_nomina": _lazy("revision_nomina", "modulos.pagos", "revision_nomina"),
    "revisar_pagos_pendientes": _lazy(
        "revisar_pagos_pendientes", "modulos.pagos", "revisar_pagos_pendientes"
    ),
    "alerta_pagos_manana": _lazy("alerta_pagos_manana", "modulos.pagos", "alerta_pagos_manana"),
    "alertas_impuestos_24h": _lazy("alertas_impuestos_24h", "modulos.radar_tributario", "enviar_alertas_24h"),
    "alertas_escanear": _lazy("alertas_escanear", "modulos.motor_alertas", "escanear_programado"),
    "alertas_resumen_diario": _lazy("alertas_resumen_diario", "modulos.motor_alertas", "enviar_resumen_diario"),
    "alertas_pagos_24h": _lazy("alertas_pagos_24h", "modulos.control_pagos", "enviar_alertas_24h"),
    "importar_control_pagos": _lazy("importar_control_pagos", "modulos.control_pagos", "importar_si_existe"),
    "alerta_nomina_semanal": _lazy("alerta_nomina_semanal", "modulos.pagos", "alerta_nomina_semanal"),
    "alerta_vencimiento_impuesto": _lazy(
        "alerta_vencimiento_impuesto", "modulos.pagos", "alerta_vencimiento_impuesto"
    ),
    "sincronizar_pagos_excel": _lazy(
        "sincronizar_pagos_excel", "utils.sync_pagos", "sincronizar_bidireccional"
    ),
    "actualizar_novedades_diarias": _lazy(
        "actualizar_novedades_diarias", "modulos.personal", "actualizar_novedades_diarias"
    ),
    "revisar_contratos": _lazy("revisar_contratos", "modulos.personal", "revisar_contratos"),
    "preparar_reunion_semanal": _lazy(
        "preparar_reunion_semanal", "modulos.cxp_cxc", "preparar_reunion_semanal"
    ),
    "revisar_mora_clientes": _lazy("revisar_mora_clientes", "modulos.creditos", "revisar_mora_clientes"),
    "verificar_conciliacion_bancaria": _lazy(
        "verificar_conciliacion_bancaria", "modulos.contable", "verificar_conciliacion_bancaria"
    ),
    "analisis_mensual_presupuesto": analisis_presupuesto_mes_actual,
    "revisar_normatividad": revision_normatividad_semanal,
    "vigilar_dian": _lazy("vigilar_dian", "modulos.impuestos", "vigilar_dian"),
    "liquidar_comisiones_mes": liquidar_comisiones_mes_anterior,
    "revision_formularios": revision_formularios_mes,
    "revisar_politicas": revisar_politicas_internas,
    "sincronizar_cartera_cxc": sincronizar_cartera_cxc,
}


def ejecutar_callback(nombre: str, parametros: dict | None = None) -> Any:
    fn = CALLBACKS.get(nombre)
    if not fn:
        raise KeyError(f"Callback no registrado: {nombre}")
    params = parametros or {}
    if params:
        return fn(**params)
    return fn()
