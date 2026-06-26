"""
Módulo de comisiones: liquidación mensual por asesor.
"""
import logging
import os
from datetime import datetime

import pandas as pd

from config import cfg
from conexiones.claude_client import llamar_claude_simple
from conexiones.gmail_client import enviar_correo
from conexiones.onedrive_client import leer_excel, escribir_excel
from database import registrar_accion, registrar_documento
from documentos.generador_pdf import generar_pdf_texto

logger = logging.getLogger(__name__)

BASE_COMISION = 0.025
DESCUENTO_RECAUDO = 0.20
RETENCION_FUENTE = 0.11
UMBRAL_RETENCION = 1_090_000
RETENCION_ICA_CALI = 0.004


def _calcular_comision_asesor(ventas_netas: float, recaudo_pct: float, anticipo: float) -> dict:
    """Calcula comisión neta de un asesor según reglas colombianas."""
    base = ventas_netas * BASE_COMISION
    if recaudo_pct < 0.80:
        base *= 1 - DESCUENTO_RECAUDO
    base -= anticipo
    ret_fuente = RETENCION_FUENTE * base if base > UMBRAL_RETENCION else 0
    ret_ica = RETENCION_ICA_CALI * base
    neto = base - ret_fuente - ret_ica
    return {
        "ventas_netas": ventas_netas,
        "base_comision": round(base, 0),
        "retencion_fuente": round(ret_fuente, 0),
        "retencion_ica": round(ret_ica, 0),
        "neto_pagar": round(neto, 0),
    }


def liquidar_comisiones_mes(mes: int, anio: int) -> None:
    """
    Liquida comisiones del mes para todos los asesores.

    Args:
        mes: Mes a liquidar (1-12).
        anio: Año a liquidar.
    """
    logger.info("Liquidando comisiones %s/%s", mes, anio)
    try:
        df = leer_excel(cfg.EXCEL_VENTAS_ID or "demo", "VENTAS")
        if df.empty:
            df = pd.DataFrame(
                [
                    {"ASESOR": "Juan Pérez", "VENTAS_NETAS": 45000000, "RECAUDO_PCT": 0.85, "ANTICIPO": 500000, "EMAIL": "juan@empresa.com"},
                    {"ASESOR": "María López", "VENTAS_NETAS": 32000000, "RECAUDO_PCT": 0.75, "ANTICIPO": 0, "EMAIL": "maria@empresa.com"},
                ]
            )

        os.makedirs("documentos/generados", exist_ok=True)
        consolidado = []

        for _, fila in df.iterrows():
            asesor = str(fila.get("ASESOR", "Asesor"))
            calc = _calcular_comision_asesor(
                float(fila.get("VENTAS_NETAS", 0)),
                float(fila.get("RECAUDO_PCT", 1)),
                float(fila.get("ANTICIPO", 0)),
            )
            prompt = f"Resume en 3 líneas la liquidación de comisión de {asesor}: {calc}"
            resumen = llamar_claude_simple(prompt, modulo="comisiones")

            nombre_pdf = f"comision_{asesor.replace(' ', '_')}_{mes}_{anio}.pdf"
            path_pdf = os.path.join("documentos/generados", nombre_pdf)
            texto = f"""LIQUIDACIÓN DE COMISIONES — {mes}/{anio}
Asesor: {asesor}
Ventas netas: ${calc['ventas_netas']:,.0f}
Base comisión: ${calc['base_comision']:,.0f}
Retención fuente: ${calc['retencion_fuente']:,.0f}
Retención ICA Cali: ${calc['retencion_ica']:,.0f}
NETO A PAGAR: ${calc['neto_pagar']:,.0f}

{resumen}"""
            generar_pdf_texto(path_pdf, f"Comisión {asesor}", texto)
            registrar_documento("PDF", nombre_pdf, path_pdf, "comisiones", f"Comisión {asesor} {mes}/{anio}")

            email_asesor = str(fila.get("EMAIL", cfg.EMAIL_GERENCIA or ""))
            if email_asesor:
                enviar_correo(
                    email_asesor,
                    f"Liquidación comisiones {mes}/{anio}",
                    f"<pre>{texto}</pre>",
                    adjuntos=[path_pdf],
                )
            consolidado.append({"ASESOR": asesor, **calc})

        df_consolidado = pd.DataFrame(consolidado)
        escribir_excel(cfg.EXCEL_VENTAS_ID or "demo", "LIQUIDACION", df_consolidado)

        enviar_correo(
            cfg.EMAIL_CONTABILIDAD or "contabilidad@empresa.com",
            f"Consolidado comisiones {mes}/{anio}",
            f"<pre>{df_consolidado.to_string()}</pre>",
        )
        registrar_accion("comisiones", "liquidar_comisiones_mes", f"{len(consolidado)} asesores", "EXITOSO")
    except Exception as e:
        logger.error("Error liquidar_comisiones_mes: %s", e, exc_info=True)
        registrar_accion("comisiones", "liquidar_comisiones_mes", str(e), "ERROR", detalle_error=str(e))
