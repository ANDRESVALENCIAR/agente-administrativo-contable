"""
Módulo de correos: clasificar, reenviar y registrar todos los correos entrantes.
Corre cada 30 minutos. Es el módulo de mayor impacto diario.
"""
import logging
import sqlite3
from datetime import datetime

from config import cfg
from conexiones.claude_client import llamar_claude_simple
from conexiones.gmail_client import enviar_correo
from conexiones.gmail_client import leer_correos_nuevos as gmail_nuevos
from conexiones.gmail_client import mover_a_papelera
from conexiones.gmail_client import reenviar_correo as gmail_reenviar
from conexiones.outlook_client import leer_correos_nuevos as outlook_nuevos
from conexiones.outlook_client import reenviar_correo as outlook_reenviar
from database import crear_alerta, registrar_accion

logger = logging.getLogger(__name__)

PROMPT_CLASIFICACION = """Clasifica este correo en UNA de estas categorías:
- factura: facturas, cuentas de cobro, documentos de cobro
- pqr: peticiones, quejas, reclamos de clientes
- pago: solicitudes de pago, confirmaciones, referencias bancarias
- proveedor: registro de proveedores, cotizaciones, ofertas
- comunicacion: comunicaciones internas, circulares
- incapacidad: incapacidades médicas para radicar en EPS
- juridico: contratos, demandas, requerimientos legales
- spam: publicidad, newsletters no solicitados, irrelevantes

Asunto: {asunto}
Remitente: {remitente}
Cuerpo (primeras 400 palabras): {cuerpo}

Responde SOLO con el nombre de la categoría en minúsculas."""


def procesar_correos() -> None:
    """
    Lee correos de Gmail y Outlook, los clasifica con Claude y los reenvía al responsable.
    """
    logger.info("Iniciando procesamiento de correos...")
    correos_gmail = gmail_nuevos(max_resultados=50)
    correos_outlook = outlook_nuevos(max_resultados=50)
    todos = correos_gmail + correos_outlook

    if not todos:
        logger.info("No hay correos nuevos.")
        return

    procesados = 0
    errores = 0

    for correo in todos:
        try:
            prompt = PROMPT_CLASIFICACION.format(
                asunto=correo["asunto"],
                remitente=correo["remitente"],
                cuerpo=correo["cuerpo"],
            )
            categoria = llamar_claude_simple(prompt, modulo="correos").strip().lower()

            cats_validas = [
                "factura",
                "pqr",
                "pago",
                "proveedor",
                "comunicacion",
                "incapacidad",
                "juridico",
                "spam",
            ]
            if categoria not in cats_validas:
                categoria = "comunicacion"

            destino = cfg.DESTINOS_CORREO.get(categoria)
            accion = ""

            if categoria == "spam":
                if correo["origen"] == "GMAIL":
                    mover_a_papelera(correo["id"])
                accion = "ELIMINADO"
            elif destino:
                nota = f"Categoría detectada: {categoria.upper()} | Procesado por agente admin"
                if correo["origen"] == "GMAIL":
                    gmail_reenviar(correo["id"], destino, nota)
                else:
                    outlook_reenviar(correo["id"], destino, nota)
                accion = f"REENVIADO → {destino}"

            conn = sqlite3.connect(cfg.DATABASE_PATH)
            c = conn.cursor()
            c.execute(
                """INSERT OR IGNORE INTO correos_procesados
                (message_id, origen, remitente, asunto, categoria, destino_reenvio, accion)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    correo["id"],
                    correo["origen"],
                    correo["remitente"],
                    correo["asunto"],
                    categoria,
                    destino,
                    accion,
                ),
            )
            conn.commit()
            conn.close()
            procesados += 1

        except Exception as e:
            logger.error("Error procesando correo %s: %s", correo.get("id"), e)
            errores += 1

    registrar_accion(
        "correos",
        "procesar_correos",
        f"{procesados} correos procesados, {errores} errores",
        "EXITOSO" if errores == 0 else "ERROR",
    )
    logger.info("Correos: %s procesados, %s errores.", procesados, errores)


def generar_resumen_diario_correos() -> None:
    """Envía resumen del día a gerencia a las 6 PM."""
    conn = sqlite3.connect(cfg.DATABASE_PATH)
    c = conn.cursor()
    c.execute(
        """SELECT categoria, COUNT(*) as total
                 FROM correos_procesados
                 WHERE DATE(timestamp) = DATE('now')
                 GROUP BY categoria ORDER BY total DESC"""
    )
    resumen = c.fetchall()
    conn.close()

    if not resumen:
        return

    tabla = "".join([f"<tr><td>{cat}</td><td>{tot}</td></tr>" for cat, tot in resumen])
    total = sum(r[1] for r in resumen)

    html = f"""
    <h2>Resumen de correos — {datetime.now().strftime('%d/%m/%Y')}</h2>
    <p>Total procesados hoy: <strong>{total}</strong></p>
    <table border='1' cellpadding='6' style='border-collapse:collapse'>
        <tr><th>Categoría</th><th>Cantidad</th></tr>
        {tabla}
    </table>
    <p><em>Generado automáticamente por el Agente Administrativo</em></p>
    """
    destino = cfg.EMAIL_GERENCIA or "gerencia@empresa.com"
    enviar_correo(
        destino,
        f"Resumen correos {datetime.now().strftime('%d/%m/%Y')}",
        html,
    )
    registrar_accion("correos", "resumen_diario", f"Resumen enviado: {total} correos", "EXITOSO")
