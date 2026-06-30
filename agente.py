"""
Agente administrativo principal. Ejecutar con: python agente.py
Corre 24/7 en Railway. Todas las tareas pasan por el Calendario Maestro.
"""
import logging
import time
from datetime import datetime

from database import cargar_datos_demo, inicializar_db
from config import cfg, en_modo_demo
from core.registro_libs import verificar_librerias
from core.db_sqlalchemy import get_engine
from modulos.impuestos import revisar_vencimientos
from modulos.pagos import revisar_cxp_diario
from utils.calendario_maestro import iniciar_executor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("agente.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("agente_principal")


def run(fn, nombre: str) -> None:
    """Ejecuta función con manejo de errores (arranque inicial)."""
    try:
        logger.info("▶ Iniciando: %s", nombre)
        fn()
        logger.info("✓ Completado: %s", nombre)
    except Exception as e:
        logger.error("✗ Error en %s: %s", nombre, e, exc_info=True)
        from database import crear_alerta

        crear_alerta("URGENTE", "agente", f"Error en {nombre}", str(e))


if __name__ == "__main__":
    inicializar_db()
    get_engine()
    resumen_libs = verificar_librerias()
    if en_modo_demo():
        cargar_datos_demo()
        logger.warning("Modo DEMO activo — configure .env con credenciales reales.")

    logger.info("=" * 60)
    logger.info("AGENTE ADMINISTRATIVO INICIADO — %s", datetime.now())
    logger.info("Empresa: %s", cfg.NOMBRE_EMPRESA)
    logger.info("Librerías activas: %s", len(resumen_libs["activas"]))
    logger.info("Calendario maestro: única fuente de programación")
    logger.info("=" * 60)

    run(revisar_vencimientos, "Revisión inicial impuestos")
    run(revisar_cxp_diario, "Revisión inicial CXP")

    iniciar_executor()
    logger.info("Calendario maestro activo. Ctrl+C para detener.")
    while True:
        time.sleep(3600)
