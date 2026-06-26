"""
Módulo jurídico: contratos, normatividad y políticas internas.
"""
import logging
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from config import cfg
from conexiones.claude_client import llamar_claude
from conexiones.gmail_client import enviar_correo
from database import crear_alerta, registrar_accion
from modulos.personal import elaborar_contrato

logger = logging.getLogger(__name__)


def generar_contrato(tipo: str, datos: dict) -> str:
    """
    Genera contrato jurídico en DOCX.

    Args:
        tipo: Tipo de contrato (ver elaborar_contrato en personal).
        datos: Datos del contrato.

    Returns:
        Ruta del documento generado.
    """
    return elaborar_contrato(tipo, datos)


def revisar_normatividad() -> None:
    """Scraping de mintrabajo.gov.co y dian.gov.co para nuevas resoluciones."""
    logger.info("Revisando normatividad laboral y tributaria...")
    sitios = [
        ("MinTrabajo", "https://www.mintrabajo.gov.co"),
        ("DIAN", "https://www.dian.gov.co"),
    ]
    novedades = []
    for nombre, url in sitios:
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "AgenteAdmin/1.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            titulos = [a.get_text(strip=True) for a in soup.find_all("a")[:20] if a.get_text(strip=True)]
            keywords = ["resolución", "decreto", "circular", "norma", "reforma"]
            relevantes = [t for t in titulos if any(k in t.lower() for k in keywords)]
            if relevantes:
                novedades.append(f"{nombre}: {relevantes[:3]}")
        except Exception as e:
            logger.error("Error scraping %s: %s", nombre, e)

    if novedades:
        texto = "\n".join(novedades)
        crear_alerta("AVISO", "juridico", "Posibles novedades normativas", texto)
        enviar_correo(
            cfg.EMAIL_JURIDICO or "juridico@empresa.com",
            "Alerta normatividad",
            f"<pre>{texto}</pre>",
        )
    registrar_accion("juridico", "revisar_normatividad", f"{len(novedades)} sitios con novedades", "EXITOSO")


def revisar_politicas() -> None:
    """Alerta políticas internas no revisadas en más de 6 meses."""
    logger.info("Revisando políticas internas...")
    import sqlite3

    conn = sqlite3.connect(cfg.DATABASE_PATH)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS politicas (
            id INTEGER PRIMARY KEY, nombre TEXT, ultima_revision DATE)"""
    )
    c.execute("SELECT COUNT(*) FROM politicas")
    if c.fetchone()[0] == 0:
        limite = (datetime.now() - timedelta(days=200)).date()
        c.execute(
            "INSERT INTO politicas (nombre, ultima_revision) VALUES (?,?)",
            ("Política SST", limite.isoformat()),
        )
        conn.commit()

    c.execute(
        "SELECT nombre, ultima_revision FROM politicas WHERE ultima_revision < ?",
        ((datetime.now() - timedelta(days=180)).date().isoformat(),),
    )
    vencidas = c.fetchall()
    conn.close()

    for nombre, ultima in vencidas:
        crear_alerta(
            "AVISO",
            "juridico",
            f"Política sin revisar: {nombre}",
            f"Última revisión: {ultima}. Requiere actualización (>6 meses).",
        )
    registrar_accion("juridico", "revisar_politicas", f"{len(vencidas)} políticas vencidas", "EXITOSO")
