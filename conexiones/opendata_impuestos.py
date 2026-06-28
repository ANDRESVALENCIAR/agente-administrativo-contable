"""
Open data tributario: DIAN (calendario fiscal JSON) y SHD Bogotá (Resolución SDH-000195/2025).
"""
import json
import logging
from datetime import date
from typing import Any

from config import cfg
from core.http_cliente import fetch_url

logger = logging.getLogger(__name__)

DIAN_FISCAL_API = "https://calendariosnacionales.com/co/v1/{anio}/fiscal/personas-juridicas.json"

# Calendario distrital Bogotá 2026 — Resolución SDH-000195 (datos abiertos / publicación oficial)
CALENDARIO_SHD_BOGOTA_2026: list[dict[str, Any]] = [
    {"impuesto": "ICA bimestral", "periodo": "2026-B1", "fecha": "2026-04-10", "formulario": "D-ICA", "entidad": "SHD Bogotá"},
    {"impuesto": "ICA bimestral", "periodo": "2026-B2", "fecha": "2026-06-12", "formulario": "D-ICA", "entidad": "SHD Bogotá"},
    {"impuesto": "ICA bimestral", "periodo": "2026-B3", "fecha": "2026-08-21", "formulario": "D-ICA", "entidad": "SHD Bogotá"},
    {"impuesto": "ICA bimestral", "periodo": "2026-B4", "fecha": "2026-10-09", "formulario": "D-ICA", "entidad": "SHD Bogotá"},
    {"impuesto": "ICA bimestral", "periodo": "2026-B5", "fecha": "2026-12-11", "formulario": "D-ICA", "entidad": "SHD Bogotá"},
    {"impuesto": "ICA bimestral", "periodo": "2026-B6", "fecha": "2027-02-12", "formulario": "D-ICA", "entidad": "SHD Bogotá"},
    {"impuesto": "ICA anual régimen común", "periodo": "2026", "fecha": "2027-02-26", "formulario": "D-ICA", "entidad": "SHD Bogotá"},
    {"impuesto": "Predial unificado", "periodo": "2026", "fecha": "2026-06-30", "formulario": "D-PU", "entidad": "SHD Bogotá"},
    {"impuesto": "Impuesto vehículos", "periodo": "2026", "fecha": "2026-07-31", "formulario": "D-VH", "entidad": "SHD Bogotá"},
]


def _ultimo_digito_nit() -> str:
    """Último dígito del NIT sin dígito de verificación (plazos DIAN)."""
    nit = (cfg.NIT_EMPRESA or "").strip()
    if "-" in nit:
        base = nit.split("-")[0].replace(".", "")
        return base[-1] if base else "0"
    limpio = nit.replace(".", "").replace("-", "")
    return limpio[-2] if len(limpio) >= 2 else limpio[-1] if limpio else "0"


def obtener_vencimientos_dian(anio: int | None = None) -> list[dict[str, Any]]:
    """Descarga calendario fiscal DIAN (open data derivado de plazos oficiales)."""
    anio = anio or date.today().year
    url = DIAN_FISCAL_API.format(anio=anio)
    try:
        raw = fetch_url(url, timeout=30)
        data = json.loads(raw)
        items = []
        for d in data.get("deadlines", []):
            items.append(
                {
                    "impuesto": d.get("name", ""),
                    "periodo": d.get("period", ""),
                    "fecha": d.get("date"),
                    "formulario": d.get("model", ""),
                    "entidad": "DIAN",
                    "categoria": d.get("category", ""),
                    "frecuencia": d.get("frequency", ""),
                    "fuente_url": d.get("sourceUrl", "https://www.dian.gov.co/"),
                }
            )
        logger.info("Open data DIAN: %s vencimientos cargados (%s)", len(items), anio)
        return items
    except Exception as e:
        logger.error("Error open data DIAN: %s", e)
        return []


def obtener_vencimientos_shd_bogota(anio: int | None = None) -> list[dict[str, Any]]:
    """Calendario SHD Bogotá (Resolución SDH-000195 / datos abiertos distritales)."""
    anio = anio or date.today().year
    if anio != 2026:
        logger.warning("Calendario SHD embebido solo para 2026; use sincronización manual para %s", anio)
    return [dict(x) for x in CALENDARIO_SHD_BOGOTA_2026]


def obtener_todos_vencimientos_opendata(anio: int | None = None) -> list[dict[str, Any]]:
    """Consolida DIAN + SHD Bogotá."""
    dian = obtener_vencimientos_dian(anio)
    shd = obtener_vencimientos_shd_bogota(anio)
    nota_nit = f"NIT {cfg.NIT_EMPRESA} — verificar plazo según último dígito ({_ultimo_digito_nit()}) en dian.gov.co"
    for item in dian:
        item["observaciones"] = nota_nit
    for item in shd:
        item["observaciones"] = "Secretaría Distrital de Hacienda — Bogotá D.C."
    return dian + shd
