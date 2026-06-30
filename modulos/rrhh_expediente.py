"""Reexporta API de carpetas inteligentes (compatibilidad)."""
from modulos.carpetas_rrhh import (  # noqa: F401
    archivar_empleado,
    carpeta_personal_base,
    crear_carpeta_empleado,
    escanear_carpetas_personal,
    guardar_certificacion_en_carpeta as guardar_certificacion_en_expediente,
    obtener_estado_sync,
    ruta_personal_activo,
    sincronizar_expediente,
)
