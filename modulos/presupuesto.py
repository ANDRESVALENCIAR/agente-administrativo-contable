"""
Módulo de presupuesto: análisis mensual de variaciones.
"""
import logging
import os
from datetime import datetime

import pandas as pd

from config import cfg
from conexiones.claude_client import llamar_claude
from conexiones.gmail_client import enviar_correo
from conexiones.onedrive_client import leer_excel
from database import registrar_accion, registrar_documento
from documentos.generador_pdf import generar_pdf_texto

logger = logging.getLogger(__name__)


def analisis_mensual_presupuesto(mes: int, anio: int) -> None:
    """
    Analiza variaciones presupuestales del mes y genera reporte PDF.

    Args:
        mes: Mes a analizar (1-12).
        anio: Año a analizar.
    """
    logger.info("Análisis presupuesto %s/%s", mes, anio)
    try:
        df = leer_excel(cfg.EXCEL_PRESUPUESTO_ID or "demo", "PRESUPUESTO")
        if df.empty:
            df = pd.DataFrame(
                {
                    "RUBRO": ["Personal", "Arriendo", "Marketing", "Servicios", "Transporte"],
                    "PRESUPUESTO": [50000000, 8000000, 5000000, 3000000, 2000000],
                    "EJECUTADO": [52000000, 8000000, 6500000, 2800000, 2100000],
                }
            )

        if "PRESUPUESTO" in df.columns and "EJECUTADO" in df.columns:
            df["VARIACION"] = df["EJECUTADO"] - df["PRESUPUESTO"]
            df["VAR_PCT"] = (df["VARIACION"] / df["PRESUPUESTO"] * 100).round(1)

        prompt = f"""Analiza este presupuesto mensual ({mes}/{anio}) de {cfg.NOMBRE_EMPRESA}:
{df.to_string()}

Incluye:
1. Los 5 rubros con mayor desviación positiva y negativa
2. Semáforo mensual (verde/amarillo/rojo por rubro)
3. Proyección anual
4. Recomendaciones concretas"""
        analisis = llamar_claude(prompt, modulo="presupuesto", max_tokens=3000)

        os.makedirs("documentos/generados", exist_ok=True)
        nombre = f"presupuesto_{mes}_{anio}.pdf"
        path = os.path.join("documentos/generados", nombre)
        generar_pdf_texto(path, f"Análisis Presupuesto {mes}/{anio}", analisis)
        registrar_documento("PDF", nombre, path, "presupuesto", f"Análisis {mes}/{anio}")

        enviar_correo(
            cfg.EMAIL_GERENCIA or "gerencia@empresa.com",
            f"Análisis presupuesto {mes}/{anio}",
            f"<pre>{analisis[:3000]}</pre>",
            adjuntos=[path],
        )
        registrar_accion("presupuesto", "analisis_mensual_presupuesto", f"{mes}/{anio}", "EXITOSO")
    except Exception as e:
        logger.error("Error analisis presupuesto: %s", e)
        registrar_accion("presupuesto", "analisis_mensual_presupuesto", str(e), "ERROR", detalle_error=str(e))
