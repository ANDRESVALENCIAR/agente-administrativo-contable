"""
Generador de documentos PDF con fpdf2.
"""
import logging
import os

from fpdf import FPDF

logger = logging.getLogger(__name__)


class PDFEmpresa(FPDF):
    """PDF con encabezado corporativo."""

    def header(self) -> None:
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, self.title_text, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)


def generar_pdf_texto(path: str, titulo: str, contenido: str) -> str:
    """
    Genera un PDF con título y texto plano.

    Args:
        path: Ruta de salida del PDF.
        titulo: Título del documento.
        contenido: Texto del cuerpo.

    Returns:
        Ruta del archivo generado.
    """
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        pdf = PDFEmpresa()
        pdf.title_text = titulo
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", size=10)
        for linea in contenido.split("\n"):
            pdf.multi_cell(0, 6, linea)
        pdf.output(path)
        logger.info("PDF generado: %s", path)
        return path
    except Exception as e:
        logger.error("Error generando PDF: %s", e)
        raise
