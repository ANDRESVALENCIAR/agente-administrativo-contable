"""
Generador de documentos PDF — reportlab (core) o fpdf2.
"""
import logging
import os

from core.documentos_engine import render_plantilla
from core.formato_col import ahora_bogota

logger = logging.getLogger(__name__)

# Fuentes TTF Unicode candidatas (Windows, Linux/Railway, macOS).
# Helvetica de fpdf solo cubre latin-1 y falla con "—", "“", "•", "€", etc.
_FUENTES_UNICODE = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/calibrib.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
]

_REEMPLAZOS_LATIN1 = {
    "—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'",
    "•": "-", "…": "...", "€": "EUR", "\u00a0": " ",
}


def _configurar_fuente(pdf) -> str:
    """Registra una fuente Unicode si existe; si no, usa Helvetica (latin-1)."""
    for regular, negrita in _FUENTES_UNICODE:
        if os.path.exists(regular):
            pdf.add_font("Uni", "", regular)
            pdf.add_font("Uni", "B", negrita if os.path.exists(negrita) else regular)
            return "Uni"
    return "Helvetica"


def _texto_seguro(texto: str, familia: str) -> str:
    """Con Helvetica, reemplaza caracteres fuera de latin-1 para que no falle."""
    if familia != "Helvetica":
        return texto
    for k, v in _REEMPLAZOS_LATIN1.items():
        texto = texto.replace(k, v)
    return texto.encode("latin-1", "replace").decode("latin-1")


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
        familia = _configurar_fuente(pdf)
        pdf.set_font(familia, "B", 12)
        pdf.cell(0, 10, _texto_seguro(titulo, familia), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(familia, size=9)
        pdf.cell(0, 6, ahora_bogota().strftime("%d/%m/%Y %H:%M"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        for linea in contenido.split("\n"):
            pdf.multi_cell(0, 6, _texto_seguro(linea, familia), new_x="LMARGIN", new_y="NEXT")
        pdf.output(path)
        logger.info("PDF generado: %s", path)
        return path
    except Exception as e:
        logger.error("Error generando PDF: %s", e)
        raise
