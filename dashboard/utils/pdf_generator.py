"""Certificación laboral PDF con reportlab (sin IA)."""
import os
from datetime import date

from config import cfg

REPRESENTANTE_LEGAL = os.getenv("REPRESENTANTE_LEGAL", "Representante Legal")


def generar_certificacion(
    nombre_empleado: str,
    cargo: str,
    fecha_ingreso: date,
    salario: float,
    tipo_contrato: str,
    cedula: str = "",
) -> str:
    """Genera PDF en documentos/certificaciones/cert_{empleado}_{fecha}.pdf"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

    os.makedirs("documentos/certificaciones", exist_ok=True)
    slug = nombre_empleado.replace(" ", "_").lower()
    path = os.path.join("documentos", "certificaciones", f"cert_{slug}_{date.today().isoformat()}.pdf")

    ciudad = cfg.CIUDAD_EMPRESA or "Bogotá D.C."
    nit = cfg.NIT_EMPRESA or "901146454-6"
    hoy = date.today().strftime("%d/%m/%Y")
    salario_fmt = f"${salario:,.0f}"

    texto = f"""
{ciudad}, {hoy}<br/><br/>
La empresa <b>{cfg.NOMBRE_EMPRESA}</b>, identificada con NIT <b>{nit}</b>, certifica que el(la)
señor(a) <b>{nombre_empleado}</b>, identificado(a) con cédula de ciudadanía
No. <b>{cedula or '_______________'}</b>, labora en esta empresa desde el
<b>{fecha_ingreso.strftime('%d/%m/%Y')}</b> hasta la fecha, desempeñando el cargo de
<b>{cargo}</b> con contrato a <b>{tipo_contrato}</b>, devengando un salario de
<b>{salario_fmt}</b> pesos mensuales.<br/><br/>
La presente certificación se expide a solicitud del interesado para los fines que estime conveniente.<br/><br/>
Atentamente,<br/><br/><br/>
_______________________________<br/>
<b>{REPRESENTANTE_LEGAL}</b><br/>
Representante Legal<br/>
{cfg.NOMBRE_EMPRESA}
"""

    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=3 * cm, rightMargin=3 * cm,
                            topMargin=3 * cm, bottomMargin=3 * cm)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("Body", parent=styles["Normal"], fontName="Helvetica", fontSize=11, leading=16)
    titulo = ParagraphStyle("Titulo", parent=styles["Heading1"], fontName="Helvetica-Bold",
                            fontSize=14, alignment=1)

    elems = []
    logo = os.path.join("assets", "logo.png")
    if os.path.exists(logo):
        elems.append(Image(logo, width=4 * cm, height=2 * cm))
    else:
        elems.append(Paragraph(f"<b>{cfg.NOMBRE_EMPRESA}</b>", titulo))
    elems.append(Spacer(1, 0.5 * cm))
    elems.append(Paragraph(texto, body))
    doc.build(elems)
    return path
