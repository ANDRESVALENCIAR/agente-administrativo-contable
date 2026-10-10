"""
Revisión de impuestos — el contador sube los insumos de cada declaración (borrador PDF,
liquidación en Excel, soportes) y Shaki emite un informe escrito: está bien o qué diferencias hay.

- Un "espacio" por impuesto y periodo: data/revisiones/<año>/<impuesto>/<periodo>/ (NO se sube a git).
- Cada revisión queda en la tabla impuestos_revisiones con su veredicto, hallazgos e informe HTML.
- Retención en la fuente (350): motor experto completo (modulos.revision_350).
- Demás impuestos: borrador vs. liquidación renglón por renglón, redondeo, plazo y — si hay
  ANTHROPIC_API_KEY — concepto adicional de Claude sobre lo extraído.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any

from config import cfg
from database import get_conn, registrar_accion
from modulos import calendario_tributario_2026 as cal

logger = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent.parent / "data" / "revisiones"

IMPUESTOS: dict[str, dict[str, str]] = {
    "RET": {"nombre": "Retención en la fuente", "corto": "Retención", "form": "350", "per": "mensual",
            "entidad": "DIAN", "grupo": "RET"},
    "IVA": {"nombre": "IVA bimestral", "corto": "IVA", "form": "300", "per": "bimestral", "entidad": "DIAN",
            "grupo": "IVA_BIM"},
    "ICA": {"nombre": "ICA Bogotá", "corto": "ICA", "form": "ICA", "per": "bimestral", "entidad": "SHD Bogotá",
            "grupo": "ICA_BIM"},
    "RETEICA": {"nombre": "ReteICA Bogotá", "corto": "ReteICA", "form": "ReteICA", "per": "bimestral",
                "entidad": "SHD Bogotá", "grupo": "RETEICA"},
    "RENTA": {"nombre": "Renta personas jurídicas", "corto": "Renta", "form": "110", "per": "anual",
              "entidad": "DIAN", "grupo": "RENTA"},
    "EXOGENA": {"nombre": "Información exógena", "corto": "Exógena", "form": "1001…", "per": "anual",
                "entidad": "DIAN", "grupo": "EXOGENA"},
    "PREDIAL": {"nombre": "Predial y vehículos", "corto": "Predial/Veh.", "form": "SHD", "per": "anual",
                "entidad": "SHD Bogotá", "grupo": "PREDIAL"},
}
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
         "Noviembre", "Diciembre"]
BIM = ["Ene–Feb", "Mar–Abr", "May–Jun", "Jul–Ago", "Sep–Oct", "Nov–Dic"]
NIVELES = ["CRITICO", "ALTO", "MEDIO", "INFO"]


# ───────────────────────── Periodos ─────────────────────────

def periodos(imp: str, anio: int) -> list[tuple[str, str]]:
    per = IMPUESTOS[imp]["per"]
    if per == "mensual":
        return [(f"{anio}-{m:02d}", f"{MESES[m - 1]} {anio}") for m in range(1, 13)]
    if per == "bimestral":
        return [(f"{anio}-B{b}", f"Bimestre {b} · {BIM[b - 1]} {anio}") for b in range(1, 7)]
    return [(f"{anio}", f"Año gravable {anio}")]


def etiqueta_periodo(imp: str, codigo: str) -> str:
    anio = int(codigo[:4])
    return dict(periodos(imp, anio)).get(codigo, codigo)


def periodo_sugerido(imp: str, hoy: date | None = None) -> str:
    """El periodo que normalmente se está preparando hoy (el anterior al mes en curso)."""
    hoy = hoy or date.today()
    per = IMPUESTOS[imp]["per"]
    if per == "mensual":
        a, m = (hoy.year, hoy.month - 1) if hoy.month > 1 else (hoy.year - 1, 12)
        return f"{a}-{m:02d}"
    if per == "bimestral":
        b = (hoy.month - 1) // 2   # bimestre anterior al actual
        return f"{hoy.year}-B{b}" if b >= 1 else f"{hoy.year - 1}-B6"
    return f"{hoy.year - 1}"


def vencimiento(imp: str, codigo: str) -> date | None:
    anio = int(codigo[:4])
    claves = []
    if imp == "RET":
        claves = [f"DIAN-RET-{anio}-{codigo[5:7]}"]
    elif imp in ("IVA", "ICA", "RETEICA"):
        n = codigo.split("B")[-1]
        claves = [{"IVA": f"DIAN-IVAB-{anio}-{n}", "ICA": f"SHD-ICAB-{anio}-{n}",
                   "RETEICA": f"SHD-RETEICA-{anio}-{n}"}[imp]]
    elif imp == "RENTA":
        claves = [f"DIAN-RENTA-{anio}-1"]
    elif imp == "EXOGENA":
        claves = [f"DIAN-EXO-{anio}"]
    for o in cal.obligaciones():
        if o["clave"] in claves:
            return date.fromisoformat(o["fecha"])
    return None


# ───────────────────────── BD ─────────────────────────

def inicializar_tablas() -> None:
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS impuestos_revisiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            impuesto TEXT NOT NULL,
            anio INTEGER NOT NULL,
            periodo TEXT NOT NULL,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            veredicto TEXT,
            nivel TEXT,
            resumen TEXT,
            total_a_pagar REAL,
            n_criticos INTEGER DEFAULT 0,
            n_altos INTEGER DEFAULT 0,
            n_medios INTEGER DEFAULT 0,
            resultado_json TEXT,
            archivos_json TEXT,
            informe_path TEXT,
            opinion_ia TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_rev_imp ON impuestos_revisiones(impuesto, anio, periodo);
        """
    )
    conn.commit()
    conn.close()


def _guardar(fila: dict[str, Any]) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO impuestos_revisiones (impuesto, anio, periodo, veredicto, nivel, resumen, total_a_pagar, "
        "n_criticos, n_altos, n_medios, resultado_json, archivos_json, informe_path, opinion_ia) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (fila["impuesto"], fila["anio"], fila["periodo"], fila["veredicto"], fila["nivel"], fila["resumen"],
         fila.get("total_a_pagar"), fila["n_criticos"], fila["n_altos"], fila["n_medios"],
         fila["resultado_json"], fila["archivos_json"], fila.get("informe_path"), fila.get("opinion_ia")),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def actualizar_informe(rid: int, ruta: str, opinion: str | None = None) -> None:
    conn = get_conn()
    if opinion is None:
        conn.execute("UPDATE impuestos_revisiones SET informe_path=? WHERE id=?", (ruta, rid))
    else:
        conn.execute("UPDATE impuestos_revisiones SET informe_path=?, opinion_ia=? WHERE id=?", (ruta, opinion, rid))
    conn.commit()
    conn.close()


def listar(anio: int | None = None, impuesto: str | None = None) -> list[dict[str, Any]]:
    inicializar_tablas()
    sql = "SELECT * FROM impuestos_revisiones WHERE 1=1"
    args: list[Any] = []
    if anio:
        sql += " AND anio=?"
        args.append(anio)
    if impuesto:
        sql += " AND impuesto=?"
        args.append(impuesto)
    sql += " ORDER BY creado_en DESC, id DESC"
    conn = get_conn()
    cur = conn.execute(sql, args)
    cols = [d[0] for d in cur.description]
    filas = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()
    return filas


def obtener(rid: int) -> dict[str, Any] | None:
    inicializar_tablas()
    conn = get_conn()
    cur = conn.execute("SELECT * FROM impuestos_revisiones WHERE id=?", (rid,))
    r = cur.fetchone()
    cols = [d[0] for d in cur.description]
    conn.close()
    if not r:
        return None
    d = dict(zip(cols, r))
    d["resultado"] = json.loads(d.get("resultado_json") or "{}")
    d["archivos"] = json.loads(d.get("archivos_json") or "[]")
    return d


def ultima_por_periodo(anio: int) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for f in listar(anio):
        out.setdefault((f["impuesto"], f["periodo"]), f)
    return out


# ───────────────────────── Archivos ─────────────────────────

def carpeta(imp: str, codigo: str) -> Path:
    p = RAIZ / codigo[:4] / imp / codigo
    p.mkdir(parents=True, exist_ok=True)
    return p


def _nombre_seguro(nombre: str) -> str:
    base = re.sub(r"[^\w.\- ]+", "_", Path(nombre).name).strip() or "archivo"
    return base[:120]


def guardar_archivos(imp: str, codigo: str, archivos: list[tuple[str, bytes]]) -> list[dict[str, Any]]:
    """archivos = [(nombre, contenido)] → copia a la carpeta del periodo con sello de hora."""
    destino = carpeta(imp, codigo)
    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = []
    for nombre, contenido in archivos:
        ruta = destino / f"{sello}_{_nombre_seguro(nombre)}"
        ruta.write_bytes(contenido)
        out.append({"nombre": nombre, "ruta": str(ruta), "tipo": _tipo(nombre), "bytes": len(contenido)})
    return out


def guardar_archivos_desde_rutas(imp: str, codigo: str, rutas: list[str]) -> list[dict[str, Any]]:
    return guardar_archivos(imp, codigo, [(Path(r).name, Path(r).read_bytes()) for r in rutas])


def _tipo(nombre: str) -> str:
    ext = Path(nombre).suffix.lower()
    return "pdf" if ext == ".pdf" else "excel" if ext in (".xlsx", ".xlsm", ".xls") else \
        "csv" if ext in (".csv", ".txt") else "otro"


# ───────────────────────── Revisión ─────────────────────────

def _veredicto(hallazgos: list[dict]) -> tuple[str, str, dict[str, int]]:
    cuenta = {n: sum(1 for h in hallazgos if h["nivel"] == n) for n in NIVELES}
    form_mal = any(h["nivel"] in ("CRITICO", "ALTO") and h["area"] in ("Formulario", "Cuadre contable",
                                                                       "Autorretención", "Art. 383")
                   for h in hallazgos)
    if form_mal:
        v = "CON DIFERENCIAS"
    elif cuenta["CRITICO"] or cuenta["ALTO"]:
        v = "FORMULARIO CORRECTO · CON ALERTAS"
    elif cuenta["MEDIO"]:
        v = "CORRECTO CON OBSERVACIONES"
    else:
        v = "CORRECTO"
    nivel = next((n for n in NIVELES if cuenta[n]), "OK")
    return v, nivel, cuenta


def _resumen(imp: str, codigo: str, res: dict, veredicto: str) -> str:
    c = res.get("datos", {}).get("campos", {})
    partes = [f"{IMPUESTOS[imp]['nombre']} {etiqueta_periodo(imp, codigo)}: {veredicto.lower()}."]
    total = c.get(138) if imp == "RET" else None
    if total:
        partes.append(f"Total a pagar ${total:,.0f}".replace(",", ".") + ".")
    crit = [h["titulo"] for h in res["hallazgos"] if h["nivel"] == "CRITICO"][:3]
    if crit:
        partes.append("Crítico: " + "; ".join(crit) + ".")
    return " ".join(partes)


def revisar_generico(imp: str, codigo: str, pdfs: list[dict], excels: list[dict], hoy: date) -> dict[str, Any]:
    from modulos.revision_350 import _h, aritmetica, comparar_borrador, pesos
    from modulos.revision_lectores import leer_excel_formulario, leer_pdf_formulario

    res: dict[str, Any] = {"hallazgos": [], "verificaciones": [], "tablas": {}, "datos": {}}
    pdf_c: dict[int, float] = {}
    for p in pdfs:
        try:
            d = leer_pdf_formulario(p["ruta"])
            pdf_c.update({k: v for k, v in d["campos"].items() if k >= 26})
            res["datos"].setdefault("texto_pdf", d["texto"][:6000])
        except Exception as e:
            res["hallazgos"].append(_h("INFO", "Insumos", f"No se pudo leer {p['nombre']}", str(e)))
    xl_c: dict[int, float] = {}
    for x in excels:
        try:
            d = leer_excel_formulario(x["ruta"], IMPUESTOS[imp]["form"])
            if len(d["campos"]) > len(xl_c):
                xl_c = d["campos"]
                res["datos"]["hoja_formulario"] = d["hoja"]
        except Exception as e:
            res["hallazgos"].append(_h("INFO", "Insumos", f"No se pudo leer {x['nombre']}", str(e)))
    c = {**xl_c, **pdf_c}
    res["datos"]["campos"] = c
    if pdf_c and xl_c:
        filas, h = comparar_borrador(pdf_c, xl_c)
        res["tablas"]["borrador_vs_liquidacion"] = filas
        res["hallazgos"] += h
        if not h:
            res["verificaciones"].append({"titulo": f"Borrador = liquidación en {len(filas)} renglones",
                                          "detalle": "Comparación renglón por renglón"})
    if c:
        no_mil = [k for k, v in c.items() if v and abs(v) >= 1 and v % 1000]
        if no_mil and IMPUESTOS[imp]["entidad"] == "DIAN":
            res["hallazgos"].append(_h("MEDIO", "Formulario", "Valores sin redondear a miles",
                                       "Renglones: " + ", ".join(map(str, sorted(no_mil))), norma="Art. 577 ET"))
        elif IMPUESTOS[imp]["entidad"] == "DIAN":
            res["verificaciones"].append({"titulo": "Valores redondeados a miles", "detalle": "Art. 577 ET"})
    else:
        res["hallazgos"].append(_h("INFO", "Insumos", "No se encontraron renglones del formulario en los archivos",
                                   "Suba el borrador en PDF generado por la DIAN/SHD y la liquidación en Excel."))
    venc = vencimiento(imp, codigo)
    if venc:
        if hoy <= venc:
            res["verificaciones"].append({"titulo": f"En plazo: vence el {venc:%d/%m/%Y} ({(venc - hoy).days} días)",
                                          "detalle": IMPUESTOS[imp]["entidad"]})
        else:
            res["hallazgos"].append(_h("ALTO", "Presentación", f"El plazo venció el {venc:%d/%m/%Y}",
                                       "Si aún no se presentó, debe liquidarse sanción de extemporaneidad e intereses.",
                                       norma="Art. 641 ET / régimen SHD"))
    res["hallazgos"].append(_h("INFO", "Alcance", f"Revisión estándar para {IMPUESTOS[imp]['nombre']}",
                               "Se compararon borrador y liquidación renglón por renglón, redondeos y plazo. "
                               "Las reglas expertas por renglón (como las de retención) se activan para este impuesto "
                               "cuando se cargue su primera liquidación completa."))
    _ = pesos
    return res


def revisar(imp: str, codigo: str, archivos: list[dict[str, Any]], hoy: date | None = None,
            con_ia: bool = False) -> dict[str, Any]:
    """Ejecuta la revisión sobre archivos ya guardados y la registra. Devuelve la fila guardada."""
    from modulos.revision_informe import generar_html

    inicializar_tablas()
    hoy = hoy or date.today()
    pdfs = [a for a in archivos if a["tipo"] == "pdf"]
    excels = [a for a in archivos if a["tipo"] == "excel"]
    anio = int(codigo[:4])
    if imp == "RET":
        from modulos import revision_350
        from modulos.revision_lectores import leer_pdf_formulario

        pdf_c: dict[int, float] = {}
        for p in pdfs:
            try:
                d = leer_pdf_formulario(p["ruta"])
                if len(d["campos"]) > len(pdf_c):
                    pdf_c = d["campos"]
            except Exception as e:
                logger.warning("PDF ilegible %s: %s", p["nombre"], e)
        ruta_xl = next((x["ruta"] for x in excels if x["ruta"].lower().endswith((".xlsm", ".xlsx"))),
                       excels[0]["ruta"] if excels else None)
        try:
            from modulos import radar_tributario as rt
            perfil_reteica = rt.perfil().get("RETEICA")
        except Exception:
            perfil_reteica = None
        res = revision_350.revisar(pdf_c, ruta_xl, anio, int(codigo[5:7]), hoy=hoy, perfil_reteica=perfil_reteica)
    else:
        res = revisar_generico(imp, codigo, pdfs, excels, hoy)
    orden = {n: i for i, n in enumerate(NIVELES)}
    res["hallazgos"].sort(key=lambda h: orden.get(h["nivel"], 9))
    veredicto, nivel, cuenta = _veredicto(res["hallazgos"])
    resumen = _resumen(imp, codigo, res, veredicto)
    total = res.get("datos", {}).get("campos", {}).get(138) if imp == "RET" else None
    fila = {"impuesto": imp, "anio": anio, "periodo": codigo, "veredicto": veredicto, "nivel": nivel,
            "resumen": resumen, "total_a_pagar": total, "n_criticos": cuenta["CRITICO"], "n_altos": cuenta["ALTO"],
            "n_medios": cuenta["MEDIO"], "resultado_json": json.dumps(res, default=str, ensure_ascii=False),
            "archivos_json": json.dumps([{k: a[k] for k in ("nombre", "ruta", "tipo", "bytes")} for a in archivos],
                                        ensure_ascii=False)}
    rid = _guardar(fila)
    opinion = opinion_ia(imp, codigo, res, veredicto) if con_ia else None
    guardado = obtener(rid)
    html = generar_html(guardado, opinion=opinion)
    ruta_inf = carpeta(imp, codigo) / f"informe_{imp}_{codigo}_{datetime.now():%Y%m%d-%H%M%S}.html"
    ruta_inf.write_text(html, encoding="utf-8")
    actualizar_informe(rid, str(ruta_inf), opinion)
    try:
        registrar_accion("revision_impuestos", "revisar", f"{imp} {codigo}: {veredicto}", "EXITOSO")
    except Exception:
        pass
    return obtener(rid)


def revisar_rutas(imp: str, codigo: str, rutas: list[str], hoy: date | None = None, con_ia: bool = False) -> dict:
    """Atajo para scripts: copia los archivos a la carpeta del periodo y revisa."""
    return revisar(imp, codigo, guardar_archivos_desde_rutas(imp, codigo, rutas), hoy=hoy, con_ia=con_ia)


# ───────────────────────── IA (opcional) ─────────────────────────

def ia_disponible() -> bool:
    return bool((getattr(cfg, "ANTHROPIC_API_KEY", "") or "").strip())


def opinion_ia(imp: str, codigo: str, res: dict, veredicto: str) -> str | None:
    """Concepto adicional de Claude sobre lo ya extraído (no envía los archivos completos)."""
    if not ia_disponible():
        return None
    try:
        from conexiones.claude_client import llamar_claude

        datos = {
            "impuesto": IMPUESTOS[imp]["nombre"], "periodo": etiqueta_periodo(imp, codigo), "veredicto": veredicto,
            "renglones": res.get("datos", {}).get("campos", {}),
            "hallazgos": [{k: h[k] for k in ("nivel", "area", "titulo", "detalle")} for h in res["hallazgos"]],
            "verificaciones_ok": [v["titulo"] for v in res["verificaciones"]],
        }
        prompt = (
            "Eres revisor fiscal senior en Colombia (DIAN y Secretaría de Hacienda de Bogotá). Revisa este resultado "
            "automático de la revisión de una declaración de EQUIPOS INDUSTRIALES FÉNIX S.A.S. y escribe en español, "
            "máximo 250 palabras: 1) si coincides con el veredicto, 2) riesgos que falten, 3) las 3 acciones más "
            "urgentes con su norma. No inventes cifras que no estén en los datos.\n\n"
            + json.dumps(datos, ensure_ascii=False, default=str)[:12000]
        )
        return llamar_claude(prompt, max_tokens=900, modulo="revision_impuestos", usar_cache=False)
    except Exception as e:
        logger.warning("Opinión IA no disponible: %s", e)
        return None


def borrar_carpeta_revision(imp: str, codigo: str) -> None:  # utilidad para pruebas
    shutil.rmtree(RAIZ / codigo[:4] / imp / codigo, ignore_errors=True)
