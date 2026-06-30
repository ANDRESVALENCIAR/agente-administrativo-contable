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

    if datetime.now().day <= 7:
        revisar_normatividad()


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
}


def ejecutar_callback(nombre: str, parametros: dict | None = None) -> Any:
    fn = CALLBACKS.get(nombre)
    if not fn:
        raise KeyError(f"Callback no registrado: {nombre}")
    params = parametros or {}
    if params:
        return fn(**params)
    return fn()
