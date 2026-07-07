"""
Módulo de créditos: análisis de solicitudes y seguimiento de mora.
"""
import logging
import os
import sqlite3
from datetime import datetime

import pandas as pd

from config import cfg
from conexiones.claude_client import llamar_claude, llamar_claude_json
from conexiones.gmail_client import enviar_correo
from conexiones.onedrive_client import leer_excel
from database import crear_alerta, registrar_accion, registrar_documento
from documentos.generador_pdf import generar_pdf_texto

logger = logging.getLogger(__name__)


def _calcular_indicadores(datos: dict) -> dict:
    """Calcula indicadores financieros básicos del cliente."""
    ingresos = float(datos.get("ingresos_mensuales", 0) or 0)
    deuda = float(datos.get("deuda_actual", 0) or 0)
    activos = float(datos.get("activos", 1) or 1)
    cupo = float(datos.get("cupo_solicitado", 0) or 0)
    return {
        "capacidad_pago": round((ingresos - deuda * 0.1) / max(cupo, 1), 2),
        "endeudamiento": round(deuda / max(ingresos, 1), 2),
        "liquidez": round(activos / max(deuda, 1), 2),
        "rentabilidad_estimada": round(ingresos / max(activos, 1), 2),
    }


def analizar_solicitud_credito(datos_cliente: dict) -> dict:
    """
    Analiza solicitud de crédito, genera decisión y carta PDF.

    Args:
        datos_cliente: Dict con cliente, nit, ingresos, deuda, cupo_solicitado, etc.

    Returns:
        Dict con decisión, justificación y rutas de documentos.
    """
    logger.info("Analizando crédito para %s", datos_cliente.get("cliente"))
    try:
        indicadores = _calcular_indicadores(datos_cliente)
        prompt = f"""Analiza esta solicitud de crédito comercial en Colombia.
Cliente: {datos_cliente.get('cliente')}
NIT: {datos_cliente.get('nit')}
Cupo solicitado: ${datos_cliente.get('cupo_solicitado', 0):,.0f}
Indicadores: {indicadores}

Responde JSON con:
- decision: APROBADO, NEGADO o CONDICIONAL
- cupo_aprobado: número
- justificacion: texto formal
- condiciones: lista de condiciones si aplica
- carta_texto: carta formal completa para el cliente
- observaciones_via: texto breve para sistema VIA"""
        resultado = llamar_claude_json(prompt, modulo="creditos")

        os.makedirs("documentos/generados", exist_ok=True)
        nombre_pdf = f"carta_credito_{datos_cliente.get('nit', 'cliente')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        path_pdf = os.path.join("documentos/generados", nombre_pdf)
        carta = resultado.get("carta_texto", resultado.get("justificacion", "Carta de crédito"))
        generar_pdf_texto(path_pdf, f"Carta de Crédito — {cfg.NOMBRE_EMPRESA}", carta)

        conn = sqlite3.connect(cfg.DATABASE_PATH)
        c = conn.cursor()
        c.execute(
            """INSERT INTO creditos_analizados
            (cliente, nit, cupo_solicitado, cupo_aprobado, decision, condiciones,
             justificacion, carta_path, observaciones_via)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                datos_cliente.get("cliente"),
                datos_cliente.get("nit"),
                datos_cliente.get("cupo_solicitado"),
                resultado.get("cupo_aprobado"),
                resultado.get("decision", "CONDICIONAL"),
                str(resultado.get("condiciones", "")),
                resultado.get("justificacion", ""),
                path_pdf,
                resultado.get("observaciones_via", ""),
            ),
        )
        conn.commit()
        conn.close()

        registrar_documento("PDF", nombre_pdf, path_pdf, "creditos", f"Carta crédito {datos_cliente.get('cliente')}")
        registrar_accion("creditos", "analizar_solicitud_credito", resultado.get("decision", ""), "EXITOSO")
        return resultado
    except Exception as e:
        logger.error("Error analizar_solicitud_credito: %s", e, exc_info=True)
        registrar_accion("creditos", "analizar_solicitud_credito", str(e), "ERROR", detalle_error=str(e))
        return {"error": str(e)}


def revisar_mora_clientes() -> None:
    """Revisa cartera de clientes y genera alertas/correos de cobro según mora."""
    logger.info("Revisando mora de clientes...")
    try:
        df = leer_excel(cfg.EXCEL_CXP_CXC_ID or "demo", "CARTERA_CLIENTES")
        if df.empty:
            df = pd.DataFrame(
                [
                    {"CLIENTE": "Cliente Demo S.A.S.", "NIT": "900111222-3", "DIAS_MORA": 95, "SALDO": 5000000},
                    {"CLIENTE": "Comercial ABC", "NIT": "800333444-1", "DIAS_MORA": 45, "SALDO": 1200000},
                ]
            )

        for _, fila in df.iterrows():
            dias_mora = int(fila.get("DIAS_MORA", 0))
            cliente = str(fila.get("CLIENTE", ""))
            nit = str(fila.get("NIT", ""))
            saldo = float(fila.get("SALDO", 0))

            conn = sqlite3.connect(cfg.DATABASE_PATH)
            c = conn.cursor()
            c.execute(
                "UPDATE cartera_cxc SET saldo=?, dias_mora=?, nit=? WHERE cliente=?",
                (saldo, dias_mora, nit, cliente),
            )
            if c.rowcount == 0:
                c.execute(
                    "INSERT INTO cartera_cxc (cliente, nit, saldo, dias_mora) VALUES (?,?,?,?)",
                    (cliente, nit, saldo, dias_mora),
                )
            conn.commit()
            conn.close()

            if dias_mora > 90:
                crear_alerta(
                    "CRITICO",
                    "creditos",
                    f"Bloqueo sugerido: {cliente}",
                    f"Mora {dias_mora} días — saldo ${float(fila.get('SALDO', 0)):,.0f}",
                )
            elif 30 <= dias_mora <= 90:
                prompt = f"""Redacta correo formal de cobro para cliente colombiano:
Cliente: {cliente}
Días mora: {dias_mora}
Saldo: ${float(fila.get('SALDO', 0)):,.0f}
Tono profesional pero firme."""
                cuerpo = llamar_claude(prompt, modulo="creditos", max_tokens=800)
                enviar_correo(
                    cfg.EMAIL_TESORERIA or "tesoreria@empresa.com",
                    f"Cobro cartera — {cliente}",
                    f"<pre>{cuerpo}</pre>",
                )

        registrar_accion("creditos", "revisar_mora_clientes", "Revisión completada", "EXITOSO")
    except Exception as e:
        logger.error("Error revisar_mora_clientes: %s", e)
        registrar_accion("creditos", "revisar_mora_clientes", str(e), "ERROR", detalle_error=str(e))
