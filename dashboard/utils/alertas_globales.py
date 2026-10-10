"""Verificación centralizada de alertas (compatibilidad): delega en el motor de alertas."""


def verificar_alertas_globales() -> int:
    """
    Corre el escáner de carpetas de RRHH (crea sus propias alertas) y el motor de reglas,
    que crea, actualiza y cierra solas las alertas vivas.

    Returns:
        Cantidad de alertas nuevas creadas.
    """
    nuevas = 0
    try:
        from modulos.carpetas_rrhh import generar_alertas_carpetas

        nuevas += generar_alertas_carpetas() or 0
    except Exception:
        pass
    try:
        from modulos import motor_alertas

        nuevas += motor_alertas.escanear().get("nuevas", 0)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Motor de alertas: %s", exc)
    return nuevas
