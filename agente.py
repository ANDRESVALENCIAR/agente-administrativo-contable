"""
Agente administrativo principal. Ejecutar con: python agente.py
Corre 24/7 en Railway. Todos los módulos se disparan automáticamente.
"""
import logging
import time
from datetime import datetime

import schedule

from database import cargar_datos_demo, crear_alerta, inicializar_db
from config import cfg, en_modo_demo
from modulos.contable import verificar_conciliacion_bancaria
from modulos.correos import generar_resumen_diario_correos, procesar_correos
from modulos.creditos import revisar_mora_clientes
from modulos.cxp_cxc import preparar_reunion_semanal
from modulos.impuestos import revisar_vencimientos, vigilar_dian
from modulos.juridico import revisar_normatividad
from modulos.pagos import revisar_cxp_diario, revision_nomina
from modulos.personal import actualizar_novedades_diarias, revisar_contratos
from modulos.presupuesto import analisis_mensual_presupuesto

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
    """Ejecuta función con manejo de errores y logging."""
    try:
        logger.info("▶ Iniciando: %s", nombre)
        fn()
        logger.info("✓ Completado: %s", nombre)
    except Exception as e:
        logger.error("✗ Error en %s: %s", nombre, e, exc_info=True)
        crear_alerta("URGENTE", "agente", f"Error en {nombre}", str(e))


def solo_dia(dia_mes: int, fn, nombre: str) -> None:
    """Ejecuta función solo en un día específico del mes."""
    if datetime.now().day == dia_mes:
        run(fn, nombre)


def solo_mes_dia(mes: int, dia: int, fn, nombre: str) -> None:
    """Ejecuta función solo en un mes y día específico."""
    now = datetime.now()
    if now.month == mes and now.day == dia:
        run(fn, nombre)


schedule.every(30).minutes.do(lambda: run(procesar_correos, "Procesar correos"))

schedule.every().day.at("07:00").do(lambda: run(revisar_vencimientos, "Vencimientos impuestos"))
schedule.every().day.at("07:05").do(lambda: run(revisar_cxp_diario, "CXP administrativos"))
schedule.every().day.at("08:00").do(lambda: run(actualizar_novedades_diarias, "Novedades personal"))
schedule.every().day.at("18:00").do(lambda: run(generar_resumen_diario_correos, "Resumen correos"))

schedule.every().monday.at("06:00").do(lambda: run(preparar_reunion_semanal, "Reunión CXP/CXC"))
schedule.every().monday.at("08:00").do(lambda: run(vigilar_dian, "Vigilancia DIAN"))
schedule.every().monday.at("08:30").do(lambda: run(revisar_mora_clientes, "Mora clientes"))
schedule.every().friday.at("09:00").do(lambda: run(verificar_conciliacion_bancaria, "Conciliación bancaria"))

schedule.every().day.at("07:30").do(
    lambda: solo_dia(
        5,
        lambda: analisis_mensual_presupuesto(datetime.now().month, datetime.now().year),
        "Análisis presupuesto",
    )
)
schedule.every().day.at("07:35").do(lambda: solo_dia(1, revisar_contratos, "Revisión contratos"))
schedule.every().day.at("07:45").do(lambda: solo_dia(24, revision_nomina, "Revisión nómina"))
schedule.every().monday.at("09:00").do(
    lambda: run(revisar_normatividad, "Revisión normatividad") if datetime.now().day <= 7 else None
)

if __name__ == "__main__":
    inicializar_db()
    if en_modo_demo():
        cargar_datos_demo()
        logger.warning("Modo DEMO activo — configure .env con credenciales reales.")

    logger.info("=" * 60)
    logger.info("AGENTE ADMINISTRATIVO INICIADO — %s", datetime.now())
    logger.info("Empresa: %s", cfg.NOMBRE_EMPRESA)
    logger.info("=" * 60)

    run(revisar_vencimientos, "Revisión inicial impuestos")
    run(revisar_cxp_diario, "Revisión inicial CXP")

    logger.info("Scheduler activo. Ctrl+C para detener.")
    while True:
        schedule.run_pending()
        time.sleep(60)
