"""
Módulo CXP/CXC: consolidación para reuniones semanales.
"""
import logging
import os
import sqlite3
from datetime import date, datetime

from config import cfg
from conexiones.claude_client import llamar_claude
from conexiones.gmail_client import enviar_correo
from conexiones.onedrive_client import leer_excel
from database import registrar_accion, registrar_documento
from documentos.generador_word import generar_word_texto

logger = logging.getLogger(__name__)


def preparar_reunion_semanal() -> None:
    """
    Consolida cartera, CXP, presupuesto e incapacidades.
    Genera agenda con Claude y documento Word para la reunión semanal.
    """
    logger.info("Preparando reunión semanal CXP/CXC...")
    try:
        cartera = leer_excel(cfg.EXCEL_CXP_CXC_ID or "demo", "CARTERA_CLIENTES")
        cxp = leer_excel(cfg.EXCEL_CXP_CXC_ID or "demo", "CXP_ADMINISTRATIVOS")
        personal = leer_excel(cfg.EXCEL_PERSONAL_ID or "demo", "INCAPACIDADES")

        resumen = f"""
CARTERA (top 5):
{cartera.head(5).to_string() if not cartera.empty else 'Sin datos'}

CXP PENDIENTES:
{cxp[cxp['ESTADO'].astype(str).str.upper()=='PENDIENTE'].head(10).to_string() if not cxp.empty else 'Sin datos'}

INCAPACIDADES:
{personal.head(5).to_string() if not personal.empty else 'Sin datos'}
"""
        prompt = f"""Genera agenda completa de reunión semanal administrativa para {cfg.NOMBRE_EMPRESA}.
Incluye: resumen ejecutivo, puntos clave, alertas críticas, acciones pendientes.

Datos consolidados:
{resumen}"""
        agenda = llamar_claude(prompt, modulo="cxp_cxc", max_tokens=3000)

        os.makedirs("documentos/generados", exist_ok=True)
        nombre = f"agenda_reunion_{datetime.now().strftime('%Y%m%d')}.docx"
        path = os.path.join("documentos/generados", nombre)
        generar_word_texto(path, f"Agenda Reunión Semanal — {cfg.NOMBRE_EMPRESA}", agenda)

        registrar_documento("DOCX", nombre, path, "cxp_cxc", "Agenda reunión semanal")

        destinatarios = [
            cfg.EMAIL_GERENCIA,
            cfg.EMAIL_TESORERIA,
            cfg.EMAIL_CONTABILIDAD,
        ]
        for dest in destinatarios:
            if dest:
                enviar_correo(
                    dest,
                    f"Agenda reunión semanal — {datetime.now().strftime('%d/%m/%Y')}",
                    f"<h2>Agenda adjunta</h2><pre>{agenda[:2000]}</pre>",
                    adjuntos=[path] if os.path.exists(path) else None,
                )

        registrar_accion("cxp_cxc", "preparar_reunion_semanal", "Agenda generada", "EXITOSO")
    except Exception as e:
        logger.error("Error preparar_reunion_semanal: %s", e, exc_info=True)
        registrar_accion("cxp_cxc", "preparar_reunion_semanal", str(e), "ERROR", detalle_error=str(e))


def sincronizar_cartera_desde_excel() -> int:
    """Importa CARTERA_CLIENTES del Excel a SQLite. Retorna filas sincronizadas."""
    import sqlite3

    logger.info("Sincronizando cartera CXC desde Excel...")
    try:
        df = leer_excel(cfg.EXCEL_CXP_CXC_ID or "demo", "CARTERA_CLIENTES")
        if df.empty:
            registrar_accion("cxp_cxc", "sincronizar_cartera", "Sin datos", "ERROR")
            return 0

        conn = sqlite3.connect(cfg.DATABASE_PATH)
        c = conn.cursor()
        n = 0
        for _, fila in df.iterrows():
            cliente = str(fila.get("CLIENTE", ""))
            nit = str(fila.get("NIT", ""))
            saldo = float(fila.get("SALDO", 0))
            dias = int(fila.get("DIAS_MORA", 0))
            c.execute(
                "UPDATE cartera_cxc SET saldo=?, dias_mora=?, nit=?, ultima_gestion=? WHERE cliente=?",
                (saldo, dias, nit, date.today().isoformat(), cliente),
            )
            if c.rowcount == 0:
                c.execute(
                    """INSERT INTO cartera_cxc (cliente, nit, saldo, dias_mora, ultima_gestion)
                       VALUES (?,?,?,?,?)""",
                    (cliente, nit, saldo, dias, date.today().isoformat()),
                )
            n += 1
        conn.commit()
        conn.close()
        registrar_accion("cxp_cxc", "sincronizar_cartera", f"{n} clientes", "EXITOSO")
        return n
    except Exception as e:
        logger.error("Error sincronizar_cartera: %s", e, exc_info=True)
        registrar_accion("cxp_cxc", "sincronizar_cartera", str(e), "ERROR", detalle_error=str(e))
        return 0
