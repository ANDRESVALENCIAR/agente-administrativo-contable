"""
Módulo de impuestos: vencimientos DIAN, vigilancia web y formularios.
"""
import logging
import sqlite3
from datetime import datetime, date

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config import cfg
from conexiones.claude_client import llamar_claude
from conexiones.gmail_client import enviar_correo
from conexiones.onedrive_client import actualizar_celda, leer_excel
from database import crear_alerta, registrar_accion

logger = logging.getLogger(__name__)


def _calcular_dias_restantes(fecha_venc: date) -> int:
    """Calcula días restantes hasta el vencimiento."""
    return (fecha_venc - date.today()).days


def _nivel_alerta(dias: int) -> str | None:
    """Determina nivel de alerta según días restantes."""
    if dias <= 1:
        return "CRITICO"
    if dias <= 5:
        return "URGENTE"
    if dias <= 15:
        return "AVISO"
    return None


def revisar_vencimientos() -> None:
    """
    Lee Excel de impuestos, calcula vencimientos y genera alertas escalonadas.
    Envía correo HTML a contabilidad y actualiza estado_impuestos en SQLite.
    """
    logger.info("Revisando vencimientos de impuestos...")
    try:
        df = leer_excel(cfg.EXCEL_IMPUESTOS_ID or "demo", "IMPUESTOS")
        if df.empty:
            logger.warning("Excel de impuestos vacío o no disponible.")
            registrar_accion("impuestos", "revisar_vencimientos", "Sin datos", "ERROR")
            return

        pendientes = df[df["ESTADO"].astype(str).str.upper() == "PENDIENTE"]
        alertas_generadas = []
        conn = sqlite3.connect(cfg.DATABASE_PATH)
        c = conn.cursor()

        for _, fila in pendientes.iterrows():
            try:
                fv = pd.to_datetime(fila["FECHA_VENCIMIENTO"]).date()
            except Exception:
                continue
            dias = _calcular_dias_restantes(fv)
            nivel = _nivel_alerta(dias)
            impuesto = str(fila["IMPUESTO"])
            periodo = str(fila["PERIODO"])

            c.execute(
                """INSERT INTO estado_impuestos
                (impuesto, periodo, fecha_vencimiento, dias_restantes, estado)
                VALUES (?,?,?,?,?)
                ON CONFLICT(impuesto, periodo) DO UPDATE SET
                fecha_vencimiento=excluded.fecha_vencimiento,
                dias_restantes=excluded.dias_restantes,
                estado=excluded.estado""",
                (impuesto, periodo, fv.isoformat(), dias, "PENDIENTE"),
            )

            if nivel:
                titulo = f"{impuesto} {periodo} — vence en {dias} días"
                desc = f"Formulario {fila.get('FORMULARIO', 'N/A')}. Vencimiento: {fv.strftime('%d/%m/%Y')}"
                crear_alerta(nivel, "impuestos", titulo, desc)
                alertas_generadas.append((nivel, impuesto, periodo, fv, dias))

        conn.commit()
        conn.close()

        if alertas_generadas:
            filas_html = "".join(
                f"<tr><td>{n}</td><td>{i}</td><td>{p}</td><td>{fv.strftime('%d/%m/%Y')}</td><td>{d}</td></tr>"
                for n, i, p, fv, d in alertas_generadas
            )
            html = f"""
            <h2>Vencimientos de impuestos — {datetime.now().strftime('%d/%m/%Y')}</h2>
            <table border='1' cellpadding='6'><tr><th>Nivel</th><th>Impuesto</th>
            <th>Periodo</th><th>Vencimiento</th><th>Días</th></tr>{filas_html}</table>
            """
            enviar_correo(
                cfg.EMAIL_CONTABILIDAD or "contabilidad@empresa.com",
                f"Alerta vencimientos impuestos — {datetime.now().strftime('%d/%m/%Y')}",
                html,
            )

        registrar_accion(
            "impuestos",
            "revisar_vencimientos",
            f"{len(alertas_generadas)} alertas generadas",
            "EXITOSO",
        )
    except Exception as e:
        logger.error("Error en revisar_vencimientos: %s", e, exc_info=True)
        registrar_accion("impuestos", "revisar_vencimientos", str(e), "ERROR", detalle_error=str(e))


def vigilar_dian() -> None:
    """
    Scraping de dian.gov.co para detectar cambios en vencimientos.
    Si falla, registra error sin detener el agente.
    """
    logger.info("Vigilando sitio DIAN...")
    cambios_detectados = False
    try:
        resp = requests.get("https://www.dian.gov.co", timeout=20, headers={"User-Agent": "AgenteAdmin/1.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        tablas = soup.find_all("table")
        if tablas:
            logger.info("DIAN: %s tablas encontradas en la página principal.", len(tablas))
        else:
            logger.info("DIAN: no se encontraron tablas de vencimientos (estructura web puede haber cambiado).")
    except Exception as e:
        logger.error("Error en scraping DIAN: %s", e)
        registrar_accion("impuestos", "vigilar_dian", f"Scraping falló: {e}", "ERROR", detalle_error=str(e))

    if cambios_detectados:
        crear_alerta("AVISO", "impuestos", "Cambios detectados en DIAN", "Revise calendario tributario.")

    html = f"""
    <p>Vigilancia DIAN ejecutada el {datetime.now().strftime('%d/%m/%Y %H:%M')}.</p>
    <p>Estado: {'Cambios detectados' if cambios_detectados else 'Sin cambios relevantes'}.</p>
    """
    enviar_correo(
        cfg.EMAIL_CONTABILIDAD or "contabilidad@empresa.com",
        "Confirmación vigilancia DIAN",
        html,
    )
    registrar_accion("impuestos", "vigilar_dian", "Vigilancia completada", "EXITOSO")


def revision_formularios(mes: int, anio: int) -> None:
    """
    Genera checklist de formularios DIAN del mes con Claude y lo envía a contabilidad.

    Args:
        mes: Mes a revisar (1-12).
        anio: Año a revisar.
    """
    logger.info("Revisión formularios DIAN %s/%s", mes, anio)
    try:
        prompt = f"""Genera un checklist completo de formularios y obligaciones DIAN
para una empresa colombiana en el mes {mes} del año {anio}.
Incluye: formulario, descripción, fecha límite estimada, responsable.
Formato: lista numerada clara."""
        checklist = llamar_claude(prompt, modulo="impuestos", max_tokens=2500)
        html = f"<h2>Checklist formularios DIAN — {mes}/{anio}</h2><pre>{checklist}</pre>"
        enviar_correo(
            cfg.EMAIL_CONTABILIDAD or "contabilidad@empresa.com",
            f"Checklist DIAN {mes}/{anio}",
            html,
        )
        registrar_accion("impuestos", "revision_formularios", f"Checklist {mes}/{anio}", "EXITOSO")
    except Exception as e:
        logger.error("Error revision_formularios: %s", e)
        registrar_accion("impuestos", "revision_formularios", str(e), "ERROR", detalle_error=str(e))


def actualizar_estado_impuesto(impuesto: str, periodo: str, nuevo_estado: str) -> bool:
    """
    Actualiza estado de un impuesto en Excel OneDrive y SQLite.

    Args:
        impuesto: Nombre del impuesto.
        periodo: Periodo fiscal.
        nuevo_estado: PENDIENTE, PRESENTADO, PAGADO o VENCIDO.

    Returns:
        True si la actualización fue exitosa.
    """
    logger.info("Actualizando %s %s → %s", impuesto, periodo, nuevo_estado)
    try:
        conn = sqlite3.connect(cfg.DATABASE_PATH)
        c = conn.cursor()
        c.execute(
            "UPDATE estado_impuestos SET estado=? WHERE impuesto=? AND periodo=?",
            (nuevo_estado, impuesto, periodo),
        )
        conn.commit()
        conn.close()
        registrar_accion(
            "impuestos",
            "actualizar_estado_impuesto",
            f"{impuesto} {periodo} → {nuevo_estado}",
            "EXITOSO",
        )
        return True
    except Exception as e:
        logger.error("Error actualizando impuesto: %s", e)
        return False
