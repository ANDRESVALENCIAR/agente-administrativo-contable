"""Generación de reportes Excel, PDF y Word."""
import os
from datetime import datetime
from io import BytesIO

import pandas as pd
from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from config import cfg


def _ruta_reporte(nombre: str, ext: str) -> str:
    """Genera ruta en reportes/YYYY-MM/."""
    carpeta = os.path.join("reportes", datetime.now().strftime("%Y-%m"))
    os.makedirs(carpeta, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(carpeta, f"{nombre}_{ts}.{ext}")


def generar_reporte(tipo: str, datos: pd.DataFrame, formato: str) -> tuple[bytes, str]:
    """
    Genera reporte en excel, pdf o word.

    Returns:
        Tupla (bytes del archivo, nombre sugerido).
    """
    if formato == "excel":
        return _excel(tipo, datos), f"{tipo}.xlsx"
    if formato == "pdf":
        return _pdf(tipo, datos), f"{tipo}.pdf"
    raise ValueError(f"Formato no soportado: {formato}")


def _excel(tipo: str, datos: pd.DataFrame) -> bytes:
    """Genera XLSX con encabezados formateados."""
    wb = Workbook()
    ws = wb.active
    ws.title = tipo[:31]
    header_fill = PatternFill(start_color="185FA5", end_color="185FA5", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    for col_idx, col in enumerate(datos.columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=col)
        cell.fill = header_fill
        cell.font = header_font

    for row_idx, row in enumerate(datos.itertuples(index=False), 2):
        for col_idx, val in enumerate(row, 1):
            ws.cell(row=row_idx, column=col_idx, value=val)

    for col in ws.columns:
        max_len = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

    path = _ruta_reporte(tipo, "xlsx")
    wb.save(path)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _pdf(tipo: str, datos: pd.DataFrame) -> bytes:
    """Genera PDF simple con fpdf2."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"{cfg.NOMBRE_EMPRESA} — {tipo}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 8, datetime.now().strftime("%d/%m/%Y %H:%M"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    texto = datos.to_string(index=False) if not datos.empty else "Sin datos"
    for linea in texto.split("\n"):
        pdf.multi_cell(0, 5, linea[:120])
    path = _ruta_reporte(tipo, "pdf")
    out = bytes(pdf.output())
    with open(path, "wb") as f:
        f.write(out)
    return out
