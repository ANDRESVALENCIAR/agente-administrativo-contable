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

CATEGORIAS_CORREO = [
    "factura",
    "pqr",
    "solicitud_pago",
    "registro_proveedor",
    "cobranza",
    "comunicacion_interna",
    "nomina",
    "juridico",
    "extracto_bancario",
    "incapacidad",
    "otro",
    "spam",
]

_ALIASES_CATEGORIA = {
    "pago": "solicitud_pago",
    "proveedor": "registro_proveedor",
    "comunicacion": "comunicacion_interna",
    "registro_prov": "registro_proveedor",
    "registro_proveedor": "registro_proveedor",
    "solicitud_pago": "solicitud_pago",
    "extracto_bancario": "extracto_bancario",
}


def normalizar_categoria(categoria: str) -> str:
    """Unifica categorías del clasificador con reglas PROMPT_MAESTRO_SHAKI_v2."""
    cat = (categoria or "").strip().lower().replace(" ", "_")
    cat = _ALIASES_CATEGORIA.get(cat, cat)
    if cat in CATEGORIAS_CORREO:
        return cat
    return "otro"


def obtener_destinos_correo() -> dict[str, str | None]:
    """
    Destinos por categoría: primero reglas activas en BD, luego config (.env).
    """
    destinos = dict(cfg.DESTINOS_CORREO)
    conn = sqlite3.connect(cfg.DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT categoria, destino FROM reglas_correo WHERE activo=1")
    for categoria, destino in c.fetchall():
        if destino:
            destinos[categoria.lower()] = destino
    conn.close()
    return destinos


def sincronizar_reglas_desde_config() -> int:
    """Inserta/actualiza reglas_correo desde DESTINOS_CORREO del .env."""
    conn = sqlite3.connect(cfg.DATABASE_PATH)
    c = conn.cursor()
    n = 0
    for categoria, destino in cfg.DESTINOS_CORREO.items():
        if not destino:
            continue
        c.execute(
            """INSERT INTO reglas_correo (categoria, destino, activo) VALUES (?,?,1)
               ON CONFLICT(categoria) DO UPDATE SET destino=excluded.destino, activo=1""",
            (categoria, destino),
        )
        n += 1
    conn.commit()
    conn.close()
    return n


PROMPT_CLASIFICACION = """Clasifica este correo en UNA de estas categorías:
- factura: facturas, cuentas de cobro, documentos de cobro
- pqr: peticiones, quejas, reclamos de clientes
- solicitud_pago: solicitudes de pago, confirmaciones, referencias bancarias
- registro_proveedor: registro de proveedores, cotizaciones, ofertas
- cobranza: gestión de cartera, recordatorios de pago, mora
- comunicacion_interna: comunicaciones internas, circulares
- nomina: nómina, prestaciones, seguridad social
- juridico: contratos, demandas, requerimientos legales
- extracto_bancario: extractos y movimientos bancarios
- incapacidad: incapacidades médicas para radicar en EPS
- otro: no encaja en las anteriores
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
            categoria = normalizar_categoria(llamar_claude_simple(prompt, modulo="correos"))

            destino = obtener_destinos_correo().get(categoria)
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
    <p><em>Generado automáticamente por AGENTE ADMIN SHAKI — EIF SAS</em></p>
    """
    destino = cfg.EMAIL_GERENCIA or "gerencia@empresa.com"
    enviar_correo(
        destino,
        f"Resumen correos {datetime.now().strftime('%d/%m/%Y')}",
        html,
    )
    registrar_accion("correos", "resumen_diario", f"Resumen enviado: {total} correos", "EXITOSO")
