"""Analiza PDFs del expediente PERSONAL ACTIVO (extracción local, sin IA)."""
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pdfplumber

BASE = Path(
    r"c:\Users\micro\OneDrive - viaindustrial.com\16. RRHH PERSONAL FUNCIONES\PERSONAL ACTIVO"
)
OUT = Path(__file__).resolve().parent.parent / "documentos" / "exports" / "analisis_personal_activo.json"

CATEGORIAS = {
    "contrato": r"contrato",
    "cedula": r"cedula|cc |c\.c|identidad|tarjeta",
    "certificacion_laboral": r"certificacion laboral|certificado laboral",
    "certificacion_otra": r"certificacion|certificado",
    "eps": r"\beps\b|salud",
    "arl": r"\barl\b",
    "pension": r"colpension|pension|caja",
    "examen_medico": r"examen|medico|recomendacion",
    "hoja_vida": r"hoja de vida|hv ",
    "policia_procuraduria": r"policia|procuraduria|ruaf|antecedente",
    "novedad": r"novedad|memorando",
    "cesantias": r"cesantia",
    "bancaria": r"bancaria|banco",
    "graduacion": r"acta de grado|grado",
    "otro": r".*",
}


def clasificar(nombre: str) -> str:
    n = nombre.lower()
    for cat, pat in CATEGORIAS.items():
        if cat == "otro":
            continue
        if re.search(pat, n):
            return cat
    return "otro"


def extraer_texto(pdf_path: Path, max_paginas: int = 5) -> tuple[str, int, bool]:
    """Retorna (texto, num_paginas, tiene_texto)."""
    texto_partes = []
    num_pag = 0
    try:
        with pdfplumber.open(pdf_path) as pdf:
            num_pag = len(pdf.pages)
            for page in pdf.pages[:max_paginas]:
                t = page.extract_text() or ""
                texto_partes.append(t)
    except Exception as e:
        return f"[ERROR: {e}]", 0, False
    texto = "\n".join(texto_partes).strip()
    return texto, num_pag, len(texto) >= 30


def extraer_campos(texto: str) -> dict:
    """Heurísticas sobre texto extraído."""
    campos = {}
    if not texto or texto.startswith("[ERROR"):
        return campos

    # Cédula / documento
    for pat in [
        r"(?:c[eé]dula|documento|cc|nit)[^\d]{0,20}(\d[\d\.]{5,12})",
        r"(\d{6,10})\s*(?:de|\.|,)",
    ]:
        m = re.search(pat, texto, re.I)
        if m:
            campos["documento"] = re.sub(r"\.", "", m.group(1))
            break

    # Salario
    m = re.search(
        r"(?:salario|deveng|remuner)[^\$\d]{0,30}(\$?\s*[\d\.]{1,3}(?:[\.,]\d{3})+)",
        texto,
        re.I,
    )
    if m:
        campos["salario_mencion"] = m.group(1).strip()

    # Cargo
    m = re.search(
        r"(?:cargo|desempe[nñ]ando|ocupa(?:ndo)? el cargo)[^\w]{0,20}([A-Za-zÁÉÍÓÚáéíóúñÑ\s]{4,60})",
        texto,
        re.I,
    )
    if m:
        campos["cargo_mencion"] = m.group(1).strip()[:60]

    # Fechas dd/mm/yyyy o dd-mm-yyyy
    fechas = re.findall(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b", texto)
    if fechas:
        campos["fechas_encontradas"] = fechas[:5]

    # Empresa
    if re.search(r"EIF|E\.I\.F|viaindustrial|via industrial", texto, re.I):
        campos["menciona_eif"] = True

    return campos


def analizar_empleado(carpeta: Path) -> dict:
    pdfs = sorted(carpeta.rglob("*.pdf"))
    docs = []
    cats = Counter()
    escaneados = 0

    for pdf in pdfs:
        if pdf.name.startswith("~$"):
            continue
        cat = clasificar(pdf.name)
        cats[cat] += 1
        texto, paginas, tiene_texto = extraer_texto(pdf)
        if not tiene_texto:
            escaneados += 1
        campos = extraer_campos(texto) if tiene_texto else {}
        docs.append(
            {
                "archivo": pdf.name,
                "categoria": cat,
                "paginas": paginas,
                "texto_extraible": tiene_texto,
                "campos": campos,
                "preview": (texto[:400] + "…") if len(texto) > 400 else texto,
            }
        )

    return {
        "empleado": carpeta.name,
        "total_pdfs": len(docs),
        "escaneados_sin_texto": escaneados,
        "categorias": dict(cats),
        "documentos": docs,
    }


def main() -> None:
    if not BASE.is_dir():
        print(f"No existe: {BASE}", file=sys.stderr)
        sys.exit(1)

    empleados = sorted(p for p in BASE.iterdir() if p.is_dir())
    resultado = {
        "fecha_analisis": datetime.now().isoformat(),
        "ruta_base": str(BASE),
        "total_empleados": len(empleados),
        "empleados": [],
        "resumen_global": {},
    }

    total_pdfs = 0
    total_escaneados = 0
    cats_global = Counter()

    for emp_dir in empleados:
        info = analizar_empleado(emp_dir)
        resultado["empleados"].append(info)
        total_pdfs += info["total_pdfs"]
        total_escaneados += info["escaneados_sin_texto"]
        cats_global.update(info["categorias"])
        print(f"  {info['empleado']}: {info['total_pdfs']} PDFs ({info['escaneados_sin_texto']} escaneados)")

    resultado["resumen_global"] = {
        "total_pdfs": total_pdfs,
        "escaneados_sin_texto": total_escaneados,
        "texto_extraible": total_pdfs - total_escaneados,
        "categorias": dict(cats_global.most_common()),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGuardado: {OUT}")
    print(json.dumps(resultado["resumen_global"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
