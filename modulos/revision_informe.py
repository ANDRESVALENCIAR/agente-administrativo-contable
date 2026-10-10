"""Informe escrito de la revisión de impuestos (HTML autocontenido, listo para imprimir o PDF)."""
from __future__ import annotations

from datetime import date, datetime
from html import escape
from typing import Any

from config import cfg

COLOR = {"CRITICO": "#E5484D", "ALTO": "#F76B15", "MEDIO": "#D9A400", "INFO": "#6E6E76", "OK": "#2FB36D"}
NOMBRE_NIVEL = {"CRITICO": "Crítico", "ALTO": "Alto", "MEDIO": "Medio", "INFO": "Nota", "OK": "OK"}
RENGLONES_350 = {
    77: "Rentas de trabajo · base PN", 93: "Rentas de trabajo · retención PN", 79: "Honorarios · base PN",
    95: "Honorarios · retención PN", 29: "Honorarios · base PJ", 42: "Honorarios · retención PJ",
    31: "Servicios · base PJ", 44: "Servicios · retención PJ", 81: "Servicios · base PN", 97: "Servicios · retención PN",
    36: "Compras · base PJ", 49: "Compras · retención PJ", 86: "Compras · base PN", 102: "Compras · retención PN",
    59: "Autorretención especial · base", 68: "Autorretención especial · valor", 129: "Menos retenciones en exceso",
    130: "Total retenciones renta", 131: "ReteIVA a responsables de IVA", 134: "Total retenciones IVA",
    136: "Total retenciones", 137: "Sanciones", 138: "Total retenciones más sanciones", 980: "Pago total",
}


def _p(v: Any) -> str:
    if v in (None, ""):
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return escape(str(v))
    s = f"{abs(v):,.0f}".replace(",", ".")
    return f"−${s}" if v < 0 else f"${s}"


def _f(v: Any) -> str:
    if not v:
        return "—"
    if isinstance(v, str):
        try:
            v = date.fromisoformat(v[:10])
        except ValueError:
            return escape(v)
    return v.strftime("%d/%m/%Y")


def _chip(nivel: str) -> str:
    c = COLOR.get(nivel, "#6E6E76")
    return (f'<span class="chip" style="color:{c};border-color:{c}40;background:{c}14">'
            f'{NOMBRE_NIVEL.get(nivel, nivel)}</span>')


def _tabla(cols: list[tuple[str, str, str]], filas: list[dict]) -> str:
    """cols = [(clave, título, formato: t|p|f|pct|ok|uvt)]"""
    th = "".join(f'<th class="{"num" if fmt in ("p", "pct", "uvt") else ""}">{escape(t)}</th>' for _, t, fmt in cols)
    trs = []
    for f in filas:
        tds = []
        for k, _, fmt in cols:
            v = f.get(k)
            if fmt == "p":
                tds.append(f'<td class="num">{_p(v)}</td>')
            elif fmt == "f":
                tds.append(f"<td>{_f(v)}</td>")
            elif fmt == "pct":
                tds.append(f'<td class="num">{(v or 0) * 100:.2f}%</td>')
            elif fmt == "uvt":
                tds.append(f'<td class="num">{(v or 0):.2f}</td>')
            elif fmt == "ok":
                tds.append(f'<td>{"<b class=ok>✓</b>" if v else "<b class=bad>✕</b>"}</td>')
            elif fmt == "nivel":
                tds.append(f"<td>{_chip(v or 'INFO')}</td>")
            else:
                tds.append(f"<td>{escape(str(v if v is not None else '—'))}</td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
    return f'<table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>'


CSS = """
*{box-sizing:border-box}body{margin:0;background:#F4F4F6;color:#141418;font:15px/1.55 -apple-system,BlinkMacSystemFont,
"SF Pro Text","Segoe UI",Inter,Roboto,Arial,sans-serif}.wrap{max-width:980px;margin:0 auto;padding:28px 20px 60px}
.hero{background:radial-gradient(120% 140% at 0% 0%,#24242B 0%,#0B0B0E 60%);color:#fff;border-radius:22px;padding:30px 32px;
position:relative;overflow:hidden}.hero:after{content:"";position:absolute;right:-80px;top:-80px;width:280px;height:280px;
border-radius:50%;background:radial-gradient(circle,#FF6A3D55,transparent 70%)}.eyebrow{font-size:12px;letter-spacing:.14em;
text-transform:uppercase;color:#A1A1AA}.hero h1{font-size:30px;line-height:1.15;margin:8px 0 6px;font-weight:700;letter-spacing:-.02em}
.hero .sub{color:#C4C4CC}.ver{display:inline-block;margin-top:18px;padding:8px 14px;border-radius:999px;font-weight:700;
font-size:13px;letter-spacing:.06em}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0 0}
.kpi{background:#ffffff10;border:1px solid #ffffff1a;border-radius:14px;padding:12px 14px}.kpi b{display:block;font-size:22px}
.kpi span{font-size:11px;color:#A1A1AA;text-transform:uppercase;letter-spacing:.1em}
section{background:#fff;border-radius:18px;padding:22px 24px;margin-top:16px;box-shadow:0 1px 0 #00000008}
h2{font-size:18px;margin:0 0 12px;letter-spacing:-.01em}h3{font-size:15px;margin:16px 0 8px}
.chip{display:inline-block;border:1px solid;border-radius:999px;padding:1px 9px;font-size:11px;font-weight:700;
letter-spacing:.05em;text-transform:uppercase;white-space:nowrap}
.h{border-left:3px solid;padding:10px 14px;margin:10px 0;background:#FAFAFB;border-radius:0 12px 12px 0}
.h .t{font-weight:650}.h .d{color:#3F3F46;margin-top:4px}.h .a{margin-top:6px;font-size:14px}.h .n{color:#8B8B93;font-size:12px;margin-top:4px}
ol.acc li{margin:6px 0}table{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}
th{text-align:left;color:#6E6E76;font-weight:600;border-bottom:1px solid #E4E4E7;padding:7px 8px;font-size:12px}
td{border-bottom:1px solid #F0F0F2;padding:7px 8px;vertical-align:top}.num{text-align:right;font-variant-numeric:tabular-nums}
.ok{color:#2FB36D}.bad{color:#E5484D}ul.v{list-style:none;padding:0;margin:0}ul.v li{padding:6px 0;border-bottom:1px solid #F0F0F2}
ul.v li:before{content:"✓";color:#2FB36D;font-weight:800;margin-right:10px}.mut{color:#6E6E76;font-size:13px}
.ia{white-space:pre-wrap;background:#F7F5FF;border:1px solid #E6E0FF;border-radius:12px;padding:14px}
@media(max-width:640px){.kpis{grid-template-columns:repeat(2,1fr)}.hero h1{font-size:24px}section{padding:18px 16px}
table{display:block;overflow-x:auto}}
@media print{body{background:#fff}.wrap{padding:0}section,.hero{break-inside:avoid;box-shadow:none}
.hero{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
"""


def generar_html(rev: dict[str, Any], opinion: str | None = None) -> str:
    from modulos.revision_impuestos import IMPUESTOS, etiqueta_periodo

    res = rev.get("resultado") or {}
    imp = rev["impuesto"]
    info = IMPUESTOS.get(imp, {"nombre": imp, "form": "", "entidad": ""})
    hall = res.get("hallazgos", [])
    ver = res.get("verificaciones", [])
    tablas = res.get("tablas", {})
    datos = res.get("datos", {})
    campos = {int(k): v for k, v in (datos.get("campos") or {}).items()}
    nivel = rev.get("nivel") or "OK"
    color_ver = COLOR.get("OK" if rev["veredicto"] == "CORRECTO" else nivel, "#2FB36D")
    total = rev.get("total_a_pagar")
    venc = (datos.get("periodo") or {}).get("vence")
    creado = str(rev.get("creado_en") or datetime.now())[:16]

    kpis = [
        (_p(total) if total else "—", "Total a pagar"),
        (_f(venc) if venc else "—", "Vence"),
        (str(rev.get("n_criticos", 0)), "Críticos"),
        (str(len(ver)), "Verificaciones OK"),
    ]
    html = [f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Revisión {escape(info['nombre'])} {escape(rev['periodo'])}</title>
<style>{CSS}</style></head><body><div class="wrap">
<div class="hero"><div class="eyebrow">Shaki · Revisión de impuestos · {escape(cfg.NIT_EMPRESA if hasattr(cfg, 'NIT_EMPRESA') else '')}</div>
<h1>{escape(info['nombre'])} — {escape(etiqueta_periodo(imp, rev['periodo']))}</h1>
<div class="sub">Equipos Industriales Fénix S.A.S. · Formulario {escape(info.get('form', ''))} · {escape(info.get('entidad', ''))} · revisado el {escape(creado)}</div>
<div class="ver" style="background:{color_ver}22;color:{color_ver};border:1px solid {color_ver}66">{escape(rev['veredicto'])}</div>
<div class="kpis">{''.join(f'<div class="kpi"><b>{v}</b><span>{escape(t)}</span></div>' for v, t in kpis)}</div></div>"""]

    # Conclusión
    html.append(f"<section><h2>Conclusión</h2><p>{escape(rev.get('resumen') or '')}</p>")
    form_ok = not any(h["area"] in ("Formulario", "Cuadre contable", "Autorretención", "Art. 383")
                      and h["nivel"] in ("CRITICO", "ALTO") for h in hall)
    if imp == "RET" and campos:
        html.append(
            "<p>" + ("<b class=ok>El formulario está bien liquidado:</b> cuadra con la liquidación del contador, con la "
                     "contabilidad y con las tarifas vigentes." if form_ok else
                     "<b class=bad>El formulario tiene diferencias</b> que deben corregirse antes de presentarlo.")
            + (" Los puntos críticos están en <b>pagos y cumplimiento</b>, no en los cálculos." if form_ok and
               rev.get("n_criticos") else "") + "</p>")
    html.append("</section>")

    acciones = [h for h in hall if h.get("accion") and h["nivel"] in ("CRITICO", "ALTO", "MEDIO")]
    if acciones:
        html.append("<section><h2>Qué hay que hacer</h2><ol class='acc'>")
        for h in acciones:
            html.append(f"<li>{_chip(h['nivel'])} <b>{escape(h['titulo'])}.</b> {escape(h['accion'])}</li>")
        html.append("</ol></section>")

    if hall:
        html.append("<section><h2>Hallazgos</h2>")
        for h in hall:
            c = COLOR.get(h["nivel"], "#6E6E76")
            html.append(
                f'<div class="h" style="border-color:{c}"><div class="t">{_chip(h["nivel"])} &nbsp;{escape(h["titulo"])}'
                f' <span class="mut">· {escape(h["area"])}</span></div>'
                + (f'<div class="d">{escape(h["detalle"])}</div>' if h.get("detalle") else "")
                + (f'<div class="a"><b>Acción:</b> {escape(h["accion"])}</div>' if h.get("accion") else "")
                + (f'<div class="n">{escape(h["norma"])}</div>' if h.get("norma") else "") + "</div>")
        html.append("</section>")

    if ver:
        html.append("<section><h2>Lo que está bien</h2><ul class='v'>")
        for v in ver:
            html.append(f"<li><b>{escape(v['titulo'])}</b> <span class='mut'>· {escape(str(v.get('detalle', '')))}</span></li>")
        html.append("</ul></section>")

    if opinion:
        html.append(f"<section><h2>Concepto adicional (IA)</h2><div class='ia'>{escape(opinion)}</div></section>")

    html.append("<section><h2>Anexos de la revisión</h2>")
    if tablas.get("borrador_vs_liquidacion"):
        filas = [{**f, "nombre": RENGLONES_350.get(int(f["renglon"]), "") if imp == "RET" else ""}
                 for f in tablas["borrador_vs_liquidacion"]]
        html.append("<h3>Borrador vs. liquidación del contador</h3>" + _tabla(
            [("renglon", "Renglón", "t"), ("nombre", "Concepto", "t"), ("borrador", "Borrador PDF", "p"),
             ("liquidacion", "Liquidación Excel", "p"), ("ok", "", "ok")], filas))
    if tablas.get("cuadre_contable"):
        html.append("<h3>Cuadre con la contabilidad del mes</h3>" + _tabla(
            [("concepto", "Concepto", "t"), ("cuenta", "Cuenta", "t"), ("contabilidad", "Contabilidad", "p"),
             ("declarado", "Declarado", "p"), ("diferencia", "Diferencia", "p"), ("ok", "", "ok")],
            tablas["cuadre_contable"]))
    if tablas.get("art_383"):
        html.append("<h3>Retención por salarios (art. 383 ET) — recalculada</h3>" + _tabla(
            [("trabajador", "Persona", "t"), ("ingreso", "Ingreso", "p"), ("base", "Base gravable", "p"),
             ("uvt", "UVT", "uvt"), ("calculado", "Cálculo Shaki", "p"), ("declarado", "Retenido", "p"),
             ("ok", "", "ok")], tablas["art_383"]))
    if tablas.get("lineas_observadas"):
        html.append("<h3>Retenciones con observación</h3>" + _tabla(
            [("tercero", "Tercero", "t"), ("nit", "NIT", "t"), ("tp", "Tipo", "t"), ("cuenta", "Cuenta", "t"),
             ("base", "Base", "p"), ("retencion", "Retención", "p"), ("tasa", "Tarifa", "pct"),
             ("observacion", "Observación", "t")], tablas["lineas_observadas"]))
    if tablas.get("reteiva"):
        html.append("<h3>ReteIVA del mes por proveedor</h3>" + _tabla(
            [("tercero", "Proveedor", "t"), ("nit", "NIT", "t"), ("valor", "ReteIVA", "p")], tablas["reteiva"]))
    if tablas.get("pagos_retencion"):
        html.append("<h3>Pagos de retención en la fuente del año (cuenta 23658001)</h3>" + _tabla(
            [("periodo", "Periodo", "t"), ("valor", "Valor", "p"), ("vence", "Vencía", "f"), ("pagado", "Pagado", "f"),
             ("estado", "Estado", "nivel"), ("nota", "Detalle", "t")], tablas["pagos_retencion"])
            + "<p class='mut'>Fechas de pago tomadas del auxiliar contable; confirmar con los recibos 490 de la DIAN.</p>")
    if tablas.get("pagos_reteica"):
        html.append("<h3>ReteICA Bogotá por pagar (cuenta 23680199)</h3>" + _tabla(
            [("periodo", "Periodo", "t"), ("valor", "Valor", "p"), ("vence", "Vencía", "f"), ("pagado", "Pagado", "f"),
             ("estado", "Estado", "nivel"), ("nota", "Detalle", "t")], tablas["pagos_reteica"]))
    arch = rev.get("archivos") or []
    if arch:
        html.append("<h3>Insumos revisados</h3><ul>" + "".join(
            f"<li>{escape(a['nombre'])} <span class='mut'>· {a.get('bytes', 0) / 1024:,.0f} KB</span></li>"
            for a in arch) + "</ul>")
    html.append("</section>")
    html.append(
        "<section class='mut'><b>Alcance.</b> Revisión automática de Shaki con las normas vigentes a la fecha "
        "(UVT 2026 $52.374 — Res. DIAN 000238/2025; Decreto 0572/2025; arts. 383, 387, 206, 336, 437-2, 577, 580-1, "
        "634, 641 ET; calendario Decreto 2229/2023 y Res. SDH-000195/2025). Se basa únicamente en los archivos "
        "entregados; no reemplaza la firma del contador ni del revisor fiscal.</section>")
    html.append("</div></body></html>")
    return "".join(html)
