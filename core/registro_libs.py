"""Registro de librerías instaladas y mapeo por módulo del agente."""
import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

_LIBRERIAS = {
    "sqlalchemy": "Core / BD",
    "pandas": "Contabilidad",
    "numpy": "Contabilidad",
    "openpyxl": "Contabilidad",
    "xlsxwriter": "Contabilidad",
    "num2words": "Contabilidad",
    "reportlab": "Documentos",
    "fpdf2": "Documentos",
    "jinja2": "Documentos",
    "python_docx": "Documentos",
    "holidays": "Personal / RRHH",
    "httpx": "Integraciones",
    "tenacity": "Integraciones",
    "requests": "Integraciones",
    "beautifulsoup4": "Impuestos",
    "lxml": "Impuestos",
    "anthropic": "IA",
    "langchain": "IA",
    "langchain_anthropic": "IA",
    "tiktoken": "IA",
    "schedule": "Agente",
    "apscheduler": "Agente",
    "plotly": "Dashboard",
    "pydantic": "Utilidades",
}

# Nombre pip -> nombre import
_IMPORT_MAP = {
    "fpdf2": "fpdf",
    "python_docx": "docx",
    "beautifulsoup4": "bs4",
    "langchain_anthropic": "langchain_anthropic",
}

LIBRERIAS_POR_MODULO: dict[str, list[str]] = {
    "agente": ["schedule", "apscheduler", "sqlalchemy"],
    "contabilidad": ["pandas", "numpy", "openpyxl", "xlsxwriter", "num2words", "sqlalchemy"],
    "impuestos": ["httpx", "tenacity", "requests", "beautifulsoup4", "lxml", "pandas"],
    "personal": ["holidays", "python_docx", "reportlab", "num2words", "pandas"],
    "documentos": ["reportlab", "fpdf2", "jinja2", "python_docx"],
    "correos": ["anthropic", "httpx"],
    "creditos": ["reportlab", "anthropic", "pandas"],
    "pagos": ["pandas", "openpyxl"],
    "comisiones": ["pandas", "openpyxl"],
    "cxp_cxc": ["pandas", "python_docx"],
    "presupuesto": ["pandas", "plotly", "anthropic"],
    "juridico": ["anthropic", "python_docx"],
    "chat": ["anthropic", "langchain", "langchain_anthropic", "tiktoken"],
    "dashboard": ["streamlit", "plotly", "pandas", "sqlalchemy"],
}


def _probe(nombre_pip: str) -> bool:
    mod = _IMPORT_MAP.get(nombre_pip, nombre_pip.replace("-", "_"))
    try:
        importlib.import_module(mod)
        return True
    except ImportError:
        return False


def librerias_disponibles() -> dict[str, bool]:
    """Retorna dict nombre_libreria -> instalada."""
    return {k: _probe(k) for k in _LIBRERIAS}


def verificar_librerias() -> dict[str, Any]:
    """
    Verifica librerías al arrancar el agente.
    Loguea faltantes y retorna resumen.
    """
    estado = librerias_disponibles()
    ok = [k for k, v in estado.items() if v]
    falt = [k for k, v in estado.items() if not v]
    logger.info("Librerías activas (%s): %s", len(ok), ", ".join(sorted(ok)))
    if falt:
        logger.warning("Librerías no instaladas (%s): %s", len(falt), ", ".join(sorted(falt)))
    return {"activas": ok, "faltantes": falt, "detalle": estado}


def registrar_uso_libreria(modulo: str, libreria: str) -> None:
    """Traza qué módulo usa qué librería (debug)."""
    logger.debug("Módulo %s → librería %s", modulo, libreria)
