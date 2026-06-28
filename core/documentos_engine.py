"""Generación PDF y plantillas Jinja2."""
import logging
import os
from io import BytesIO

logger = logging.getLogger(__name__)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False

try:
    from jinja2 import Environment, FileSystemLoader, Template

    _HAS_JINJA = True
except ImportError:
    _HAS_JINJA = False


def render_plantilla(nombre_archivo: str, contexto: dict, carpeta: str = "documentos/plantillas") -> str:
    """
    Renderiza plantilla .txt o .html con Jinja2.

    Returns:
        Texto renderizado.
    """
    if not _HAS_JINJA:
        return str(contexto)
    from core.registro_libs import registrar_uso_libreria

    registrar_uso_libreria("documentos", "jinja2")
    path = os.path.join(carpeta, nombre_archivo)
    if os.path.exists(path):
        env = Environment(loader=FileSystemLoader(carpeta), autoescape=True)
        return env.get_template(nombre_archivo).render(**contexto)
    tpl = Template("{{ empresa }} — {{ titulo }}\n\n{{ cuerpo }}")
    return tpl.render(**contexto)


def generar_pdf_tabla(titulo: str, columnas: list[str], filas: list[list], path: str) -> bytes:
    """
    PDF con tabla vía reportlab; fallback fpdf2.

    Returns:
        Bytes del PDF.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    if _HAS_REPORTLAB:
        from core.registro_libs import registrar_uso_libreria

        registrar_uso_libreria("documentos", "reportlab")
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()
        elems = [Paragraph(titulo, styles["Title"]), Spacer(1, 12)]
        data = [columnas] + filas
        tabla = Table(data, repeatRows=1)
        tabla.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#185FA5")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elems.append(tabla)
        doc.build(elems)
        out = buf.getvalue()
        with open(path, "wb") as f:
            f.write(out)
        return out

    from fpdf import FPDF
    from core.registro_libs import registrar_uso_libreria

    registrar_uso_libreria("documentos", "fpdf2")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, titulo, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=8)
    pdf.multi_cell(0, 5, " | ".join(columnas))
    for fila in filas:
        pdf.multi_cell(0, 5, " | ".join(str(c) for c in fila))
    out = bytes(pdf.output())
    with open(path, "wb") as f:
        f.write(out)
    return out
