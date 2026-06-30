import json
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "documentos" / "exports" / "analisis_personal_activo.json"
d = json.loads(p.read_text(encoding="utf-8"))

print("=== RESUMEN POR EMPLEADO ===\n")
for e in d["empleados"]:
    contratos = [x for x in e["documentos"] if x["categoria"] == "contrato"]
    campos_agg = {}
    for doc in e["documentos"]:
        for k, v in doc.get("campos", {}).items():
            if k not in campos_agg and v:
                campos_agg[k] = v
    cats = ", ".join(f"{k}({v})" for k, v in sorted(e["categorias"].items()))
    print(e["empleado"])
    print(f"  PDFs: {e['total_pdfs']} | Sin texto OCR: {e['escaneados_sin_texto']}")
    print(f"  Tipos: {cats}")
    if contratos:
        for c in contratos:
            extra = c.get("campos") or {}
            flag = " [texto OK]" if c["texto_extraible"] else " [escaneado]"
            print(f"  -> Contrato: {c['archivo']}{flag} {extra}")
    if campos_agg:
        print(f"  Datos clave: {campos_agg}")
    print()
