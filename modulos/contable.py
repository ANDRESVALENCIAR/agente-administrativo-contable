"""
Módulo contable: conciliación bancaria e informes de gerencia.
"""
import logging
import os
from datetime import datetime

from config import cfg
from conexiones.claude_client import llamar_claude
from conexiones.gmail_client import enviar_correo
from conexiones.onedrive_client import leer_excel
from database import registrar_accion, registrar_documento
from documentos.generador_word import generar_word_texto

logger = logging.getLogger(__name__)


def verificar_conciliacion_bancaria() -> None:
    """Cruza saldos bancarios vs contables y genera reporte con Claude."""
    logger.info("Verificando conciliación bancaria...")
    try:
        conciliacion = leer_excel(cfg.EXCEL_CONCILIACION_ID or "demo", "CONCILIACION")
        resumen = conciliacion.to_string() if not conciliacion.empty else "Datos demo: saldo banco $10M, contable $9.8M, diferencia $200K"

        prompt = f"""Analiza esta conciliación bancaria colombiana y genera reporte estándar:
- Partidas en tránsito
- Diferencias identificadas
- Recomendaciones de ajuste

Datos:
{resumen}"""
        informe = llamar_claude(prompt, modulo="contable", max_tokens=2500)

        import sqlite3
        from datetime import date

        conn = sqlite3.connect(cfg.DATABASE_PATH)
        c = conn.cursor()
        if not conciliacion.empty and "SALDO" in conciliacion.columns:
            for _, fila in conciliacion.iterrows():
                fuente = str(fila.get("FUENTE", fila.get("BANCO", "Banco")))
                saldo = float(fila.get("SALDO", 0))
                c.execute(
                    """INSERT OR REPLACE INTO conciliacion_bancaria (fuente, saldo, fecha)
                       VALUES (?,?,?)""",
                    (fuente, saldo, date.today().isoformat()),
                )
        else:
            c.execute(
                """INSERT OR REPLACE INTO conciliacion_bancaria (fuente, saldo, fecha)
                   VALUES (?,?,?)""",
                ("Conciliación automática", 0, date.today().isoformat()),
            )
        conn.commit()
        conn.close()

        enviar_correo(
            cfg.EMAIL_CONTABILIDAD or "contabilidad@empresa.com",
            f"Conciliación bancaria — {datetime.now().strftime('%d/%m/%Y')}",
            f"<pre>{informe}</pre>",
        )
        registrar_accion("contable", "verificar_conciliacion_bancaria", "Informe enviado", "EXITOSO")
    except Exception as e:
        logger.error("Error conciliación: %s", e)
        registrar_accion("contable", "verificar_conciliacion_bancaria", str(e), "ERROR", detalle_error=str(e))


def generar_informe_gerencia(anio: int) -> str:
    """
    Genera informe ejecutivo anual en Word.

    Args:
        anio: Año del informe.

    Returns:
        Ruta del documento generado.
    """
    logger.info("Generando informe de gerencia %s", anio)
    try:
        ventas = leer_excel(cfg.EXCEL_VENTAS_ID or "demo", "VENTAS")
        presupuesto = leer_excel(cfg.EXCEL_PRESUPUESTO_ID or "demo", "PRESUPUESTO")
        datos = f"Ventas:\n{ventas.head(10).to_string() if not ventas.empty else 'N/A'}\n\nPresupuesto:\n{presupuesto.head(10).to_string() if not presupuesto.empty else 'N/A'}"

        prompt = f"""Genera informe ejecutivo anual {anio} para {cfg.NOMBRE_EMPRESA}:
- Estado de resultados resumido
- Balance general resumido
- Cumplimiento metas por asesor
- Presupuesto vs ejecución
- Indicadores clave
- Hallazgos y recomendaciones

Datos disponibles:
{datos}"""
        informe = llamar_claude(prompt, modulo="contable", max_tokens=4000)
        os.makedirs("documentos/generados", exist_ok=True)
        nombre = f"informe_gerencia_{anio}.docx"
        path = os.path.join("documentos/generados", nombre)
        generar_word_texto(path, f"Informe de Gerencia {anio} — {cfg.NOMBRE_EMPRESA}", informe)
        registrar_documento("DOCX", nombre, path, "contable", f"Informe gerencia {anio}")
        enviar_correo(
            cfg.EMAIL_GERENCIA or "gerencia@empresa.com",
            f"Informe de gerencia {anio}",
            f"<p>Informe anual adjunto.</p>",
            adjuntos=[path],
        )
        registrar_accion("contable", "generar_informe_gerencia", str(anio), "EXITOSO")
        return path
    except Exception as e:
        logger.error("Error informe gerencia: %s", e)
        registrar_accion("contable", "generar_informe_gerencia", str(e), "ERROR", detalle_error=str(e))
        return ""
