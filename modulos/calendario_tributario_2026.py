"""
Calendario tributario oficial 2026 (y vencimientos de enero-febrero 2027) para
EQUIPOS INDUSTRIALES FÉNIX S.A.S. — NIT 901.146.454-6.

DIAN: persona jurídica, NO gran contribuyente. Plazos por último dígito del NIT (4)
y, para exógena, por los dos últimos (54), sin dígito de verificación.
  Fuente: DUR 1625 de 2016 (art. 1.6.1.13.2.x) modificado por el Decreto 2229 de 2023;
  julio 2026 ajustado por la Ley 2578 de 2026 (nuevo festivo) — Comunicado DIAN 092 del
  2-jul-2026. Consolidado en el Calendario Tributario CIJUF actualizado al 2-jul-2026.
SHD Bogotá: Resolución SDH-000195 del 12 de diciembre de 2025.

La DIAN y la SHD no publican estos plazos como API de datos abiertos; se toman de la norma
oficial. Si el NIT configurado no termina en 4 / 54, este calendario NO aplica.
"""
from __future__ import annotations

NIT_ULTIMO_DIGITO = "4"
NIT_DOS_DIGITOS = "54"

F_DIAN = "Decreto 2229 de 2023 (DUR 1625/2016) · julio ajustado por Ley 2578/2026, Comunicado DIAN 092/2026"
F_SHD = "Resolución SDH-000195 de 2025 (Secretaría Distrital de Hacienda de Bogotá)"
URL_DIAN = "https://www.dian.gov.co/Prensa/Paginas/NG-Comunicado-de-Prensa-092-2026.aspx"
URL_SHD = "https://www.haciendabogota.gov.co/"

# Grupos de obligaciones (se activan según el perfil del contribuyente)
GRUPOS = {
    "RET": "Retención en la fuente (mensual)",
    "IVA_BIM": "IVA bimestral",
    "IVA_CUAT": "IVA cuatrimestral",
    "RENTA": "Renta personas jurídicas",
    "EXOGENA": "Información exógena nacional",
    "ACTIVOS_EXT": "Activos en el exterior (si superan 2.000 UVT)",
    "PATRIMONIO": "Impuesto al patrimonio",
    "ICA_BIM": "ICA bimestral Bogotá",
    "ICA_ANUAL": "ICA anual Bogotá",
    "RETEICA": "ReteICA Bogotá (agente retenedor)",
    "PREDIAL": "Predial unificado Bogotá",
    "VEHICULOS": "Impuesto de vehículos Bogotá",
}

# Perfil de EIF SAS confirmado por el usuario (oct-2026)
PERFIL_POR_DEFECTO = {
    "RET": True, "IVA_BIM": True, "IVA_CUAT": False, "RENTA": True, "EXOGENA": True,
    "ACTIVOS_EXT": True, "PATRIMONIO": False, "ICA_BIM": True, "ICA_ANUAL": False,
    "RETEICA": False, "PREDIAL": True, "VEHICULOS": True,
}

_MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
          "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _ret() -> list[dict]:
    fechas = ["2026-02-13", "2026-03-13", "2026-04-16", "2026-05-15", "2026-06-16", "2026-07-15",
              "2026-08-18", "2026-09-14", "2026-10-15", "2026-11-17", "2026-12-15", "2027-01-18"]
    return [
        {"clave": f"DIAN-RET-2026-{m + 1:02d}", "grupo": "RET", "entidad": "DIAN",
         "impuesto": "Retención en la fuente", "periodo": f"{_MESES[m]} 2026", "formulario": "350",
         "tipo": "DECLARACIÓN Y PAGO", "fecha": f, "fuente": F_DIAN}
        for m, f in enumerate(fechas)
    ]


def _iva_bim() -> list[dict]:
    per = [("Ene–Feb", "2026-03-13"), ("Mar–Abr", "2026-05-15"), ("May–Jun", "2026-07-15"),
           ("Jul–Ago", "2026-09-14"), ("Sep–Oct", "2026-11-17"), ("Nov–Dic", "2027-01-18")]
    return [
        {"clave": f"DIAN-IVAB-2026-{i + 1}", "grupo": "IVA_BIM", "entidad": "DIAN", "impuesto": "IVA bimestral",
         "periodo": f"{p} 2026", "formulario": "300", "tipo": "DECLARACIÓN Y PAGO", "fecha": f, "fuente": F_DIAN}
        for i, (p, f) in enumerate(per)
    ]


def _iva_cuat() -> list[dict]:
    per = [("Ene–Abr", "2026-05-15"), ("May–Ago", "2026-09-14"), ("Sep–Dic", "2027-01-18")]
    return [
        {"clave": f"DIAN-IVAC-2026-{i + 1}", "grupo": "IVA_CUAT", "entidad": "DIAN",
         "impuesto": "IVA cuatrimestral", "periodo": f"{p} 2026", "formulario": "300",
         "tipo": "DECLARACIÓN Y PAGO", "fecha": f, "fuente": F_DIAN}
        for i, (p, f) in enumerate(per)
    ]


def _anuales_dian() -> list[dict]:
    return [
        {"clave": "DIAN-RENTA-2025-1", "grupo": "RENTA", "entidad": "DIAN", "impuesto": "Renta personas jurídicas",
         "periodo": "Año gravable 2025 · declaración y 1ª cuota", "formulario": "110",
         "tipo": "DECLARACIÓN Y PAGO", "fecha": "2026-05-15", "fuente": F_DIAN},
        {"clave": "DIAN-RENTA-2025-2", "grupo": "RENTA", "entidad": "DIAN", "impuesto": "Renta personas jurídicas",
         "periodo": "Año gravable 2025 · 2ª cuota", "formulario": "490", "tipo": "PAGO",
         "fecha": "2026-07-15", "fuente": F_DIAN},
        {"clave": "DIAN-EXO-2025", "grupo": "EXOGENA", "entidad": "DIAN", "impuesto": "Información exógena",
         "periodo": "Año gravable 2025 · NIT …54", "formulario": "Formatos 1001-1012…",
         "tipo": "PRESENTACIÓN", "fecha": "2026-05-29", "fuente": F_DIAN},
        {"clave": "DIAN-ACTEXT-2026", "grupo": "ACTIVOS_EXT", "entidad": "DIAN", "impuesto": "Activos en el exterior",
         "periodo": "Patrimonio a 1-ene-2026", "formulario": "160", "tipo": "PRESENTACIÓN",
         "fecha": "2026-05-15", "fuente": F_DIAN},
        {"clave": "DIAN-PATRI-2025-1", "grupo": "PATRIMONIO", "entidad": "DIAN", "impuesto": "Impuesto al patrimonio",
         "periodo": "2026 · declaración y 1ª cuota", "formulario": "420", "tipo": "DECLARACIÓN Y PAGO",
         "fecha": "2026-05-15", "fuente": F_DIAN},
        {"clave": "DIAN-PATRI-2025-2", "grupo": "PATRIMONIO", "entidad": "DIAN", "impuesto": "Impuesto al patrimonio",
         "periodo": "2026 · 2ª cuota", "formulario": "490", "tipo": "PAGO", "fecha": "2026-09-14", "fuente": F_DIAN},
    ]


def _shd() -> list[dict]:
    ica = [("Bimestre 1 · Ene–Feb", "2026-04-10"), ("Bimestre 2 · Mar–Abr", "2026-06-12"),
           ("Bimestre 3 · May–Jun", "2026-08-21"), ("Bimestre 4 · Jul–Ago", "2026-10-09"),
           ("Bimestre 5 · Sep–Oct", "2026-12-11"), ("Bimestre 6 · Nov–Dic", "2027-02-12")]
    reteica = [("Bimestre 1 · Ene–Feb", "2026-03-20"), ("Bimestre 2 · Mar–Abr", "2026-05-22"),
               ("Bimestre 3 · May–Jun", "2026-07-17"), ("Bimestre 4 · Jul–Ago", "2026-09-18"),
               ("Bimestre 5 · Sep–Oct", "2026-11-20"), ("Bimestre 6 · Nov–Dic", "2027-01-15")]
    out = [
        {"clave": f"SHD-ICAB-2026-{i + 1}", "grupo": "ICA_BIM", "entidad": "SHD Bogotá", "impuesto": "ICA bimestral",
         "periodo": f"{p} 2026", "formulario": "Declaración ICA", "tipo": "DECLARACIÓN Y PAGO", "fecha": f,
         "fuente": F_SHD}
        for i, (p, f) in enumerate(ica)
    ]
    out += [
        {"clave": f"SHD-RETEICA-2026-{i + 1}", "grupo": "RETEICA", "entidad": "SHD Bogotá",
         "impuesto": "ReteICA", "periodo": f"{p} 2026", "formulario": "Declaración ReteICA",
         "tipo": "DECLARACIÓN Y PAGO", "fecha": f, "fuente": F_SHD}
        for i, (p, f) in enumerate(reteica)
    ]
    out += [
        {"clave": "SHD-ICAA-2026", "grupo": "ICA_ANUAL", "entidad": "SHD Bogotá", "impuesto": "ICA anual",
         "periodo": "Año gravable 2026", "formulario": "Declaración ICA", "tipo": "DECLARACIÓN Y PAGO",
         "fecha": "2027-02-26", "fuente": F_SHD},
        {"clave": "SHD-PRED-2026-DESC", "grupo": "PREDIAL", "entidad": "SHD Bogotá", "impuesto": "Predial unificado",
         "periodo": "2026 · pago con 10% de descuento", "formulario": "Predial", "tipo": "PAGO",
         "fecha": "2026-04-17", "fuente": F_SHD},
        {"clave": "SHD-PRED-2026", "grupo": "PREDIAL", "entidad": "SHD Bogotá", "impuesto": "Predial unificado",
         "periodo": "2026 · plazo sin descuento", "formulario": "Predial", "tipo": "DECLARACIÓN Y PAGO",
         "fecha": "2026-07-10", "fuente": F_SHD},
        {"clave": "SHD-VEH-2026", "grupo": "VEHICULOS", "entidad": "SHD Bogotá", "impuesto": "Vehículos",
         "periodo": "2026 · plazo sin descuento", "formulario": "Vehículos", "tipo": "DECLARACIÓN Y PAGO",
         "fecha": "2026-07-24", "fuente": F_SHD},
    ]
    return out


def obligaciones() -> list[dict]:
    """Todas las obligaciones del calendario (activas o no según perfil)."""
    out = _ret() + _iva_bim() + _iva_cuat() + _anuales_dian() + _shd()
    for o in out:
        o["url_fuente"] = URL_DIAN if o["entidad"] == "DIAN" else URL_SHD
    return out
