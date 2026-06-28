"""
Generador de documentos PDF — reportlab (core) o fpdf2.
"""
import logging
import os

from core.documentos_engine import render_plantilla
from core.formato_col import ahora_bogota

logger = logging.getLogger(__name__)


def generar_pdf_texto(path: str, titulo: str, contenido: str, contexto: dict | None = None) -> str:
    """
    Genera PDF con título y cuerpo.
    Si hay plantilla Jinja2, renderiza antes de generar.
    """
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if contexto:
            contenido = render_plantilla(
                contexto.get("plantilla", "carta_generica.txt"),
                {**contexto, "titulo": titulo, "cuerpo": contenido},
            )
        from fpdf import FPDF
        from core.registro_libs import registrar_uso_libreria

        registrar_uso_libreria("documentos", "fpdf2")
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, titulo, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=9)
        pdf.cell(0, 6, ahora_bogota().strftime("%d/%m/%Y %H:%M"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        for linea in contenido.split("\n"):
            pdf.multi_cell(0, 6, linea)
        pdf.output(path)
        logger.info("PDF generado: %s", path)
        return path
    except Exception as e:
        logger.error("Error generando PDF: %s", e)
        raise
