"""Informe escrito de la revisión contable (HTML autocontenido, listo para imprimir o guardar como PDF).

Todo sale de reglas fijas (modulos.auditoria_contable): cada hallazgo muestra la regla, la cifra y la evidencia
para que el contador o el revisor fiscal lo puedan verificar."""
from __future__ import annotations

from datetime import date, datetime
from html import escape
from typing import Any

from modulos.auditoria_contable import AREAS, MESES
from modulos.revision_informe import CSS as CSS_BASE

COLOR = {"CRITICO": "#E5484D", "ALTO": "#F76B15", "MEDIO": "#D9A400", "BAJO": "#6E6E76", "OK": "#2FB36D"}
NOMBRE = {"CRITICO": "Crítico", "ALTO": "Alto", "MEDIO": "Medio", "BAJO": "Bajo", "OK": "OK"}
ETIQUETAS = {"cuenta": "Cuenta", "nombre": "Nombre", "saldo": "Saldo", "saldo_anterior": "Saldo anterior",
             "calculado": "Calculado", "reportado": "Reportado", "suma_subcuentas": "Suma subcuentas",
             "registrado_directo_en_la_mayor": "Directo en la mayor", "auxiliar": "Auxiliar", "balance": "Balance",
             "diferencia": "Diferencia", "comprobante": "Comprobante", "comprobantes": "Comprobantes", "fecha": "Fecha",
             "valor": "Valor", "detalle": "Detalle", "nit": "NIT", "factura": "Factura", "registros": "Registros",
             "concepto": "Concepto", "causado_mes": "Causado en el mes", "base": "Base", "porcentaje": "% real",
             "ley": "% ley", "gasto_del_mes": "Gasto del mes", "provision_del_mes": "Provisión del mes",
             "debia_pagarse": "Debía pagarse", "pagos_del_mes": "Pagos del mes", "rubro": "Rubro",
             "estados_financieros": "Estados financieros", "balance_de_prueba": "Balance de prueba", "cuadra": "",
             "digito": "Dígito", "observado": "Observado", "esperado": "Esperado (Benford)", "n": "Registros"}
MONEDA = {"saldo", "saldo_anterior", "calculado", "reportado", "suma_subcuentas", "registrado_directo_en_la_mayor",
          "auxiliar", "balance", "diferencia", "valor", "causado_mes", "base", "gasto_del_mes", "provision_del_mes",
          "pagos_del_mes", "estados_financieros", "balance_de_prueba"}

CSS = CSS_BASE + """
.score{display:flex;gap:22px;align-items:center;margin-top:16px}.ring{width:96px;height:96px;border-radius:50%;
display:grid;place-items:center;font-size:30px;font-weight:700;position:relative}.ring small{display:block;font-size:10px;
font-weight:500;color:#A1A1AA;letter-spacing:.1em;text-align:center;margin-top:-4px}
.areas{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px}
.area{border:1px solid #E4E4E7;border-radius:12px;padding:10px 12px;font-size:13px}.area b{display:block;font-size:14px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
details{margin-top:6px}summary{cursor:pointer;color:#52525B;font-size:13px}
"""


def _p(v: Any) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return escape(str(v)) if v not in (None, "") else "—"
    s = f"{abs(v):,.0f}".replace(",", ".")
    return f"−${s}" if v < 0 else f"${s}"


def _fecha(d: Any) -> str:
    if isinstance(d, (date, datetime)):
        return f"{d.day} de {MESES[d.month - 1]} de {d.year}"
    return escape(str(d or "—"))


def _chip(nivel: str) -> str:
    c = COLOR[nivel]
    return f'<span class="chip" style="color:{c};border-color:{c}40;background:{c}14">{NOMBRE[nivel]}</span>'


def _tabla(filas: list[dict]) -> str:
    if not filas:
        return ""
    cols = list(dict.fromkeys(k for f in filas for k in f))
    th = "".join(f'<th class="{"num" if k in MONEDA else ""}">{escape(ETIQUETAS.get(k, k.replace("_", " ").capitalize()))}</th>'
                 for k in cols)
    trs = []
    for f in filas:
        tds = []
        for k in cols:
            v = f.get(k)
            if k in MONEDA:
                tds.append(f'<td class="num">{_p(v)}</td>')
            elif k in ("observado", "esperado") and isinstance(v, float):
                tds.append(f'<td class="num">{v * 100:.1f}%</td>')
            else:
                tds.append(f"<td>{escape(str(v if v is not None else '—'))}</td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"


def _hallazgo(h: dict) -> str:
    c = COLOR[h["nivel"]]
    valor = (f' · <b>{_p(h["valor"])}</b>' if isinstance(h.get("valor"), (int, float)) and abs(h["valor"]) >= 1
             and h["codigo"] not in ("G8", "D3") else "")
    ev = (f'<details><summary>Ver evidencia ({len(h["evidencia"])})</summary>{_tabla(h["evidencia"])}</details>'
          if h.get("evidencia") else "")
    rec = f'<div class="a">→ {escape(h["recomendacion"])}</div>' if h.get("recomendacion") else ""
    return (f'<div class="h" style="border-color:{c}"><div class="t">{_chip(h["nivel"])} &nbsp;{escape(h["titulo"])}{valor}</div>'
            f'<div class="d">{escape(h["detalle"])}</div>{rec}'
            f'<div class="n">Regla {h["codigo"]} · {escape(AREAS.get(h["area"], h["area"]))}</div>{ev}</div>')


def generar_html(r: dict[str, Any]) -> str:
    puntaje = r["puntaje"]
    color = {"Confiable": "#2FB36D", "Confiable con salvedades": "#D9A400"}.get(r["veredicto"], "#E5484D")
    hall = [h for h in r["hallazgos"] if h["nivel"] != "OK"]
    oks = [h for h in r["hallazgos"] if h["nivel"] == "OK"]
    registro = [h for h in hall if h["tipo"] == "registro"]
    riesgo = [h for h in hall if h["tipo"] == "riesgo"]
    c = r["conteo"]

    # resumen por área
    areas_html = []
    for a, nombre in AREAS.items():
        hs = [h for h in r["hallazgos"] if h["area"] == a]
        if not hs:
            continue
        peor = next((n for n in ("CRITICO", "ALTO", "MEDIO", "BAJO") if any(h["nivel"] == n for h in hs)), "OK")
        n_mal = sum(h["nivel"] != "OK" for h in hs)
        areas_html.append(f'<div class="area"><b><span class="dot" style="background:{COLOR[peor]}"></span>{escape(nombre)}</b>'
                          f'{"sin observaciones" if not n_mal else f"{n_mal} observación(es)"} · {len(hs)} revisión(es)</div>')

    acciones = [h for h in hall if h["nivel"] in ("CRITICO", "ALTO") and h.get("recomendacion")]
    acc_html = "".join(f"<li><b>{escape(h['titulo'])}</b>: {escape(h['recomendacion'])}</li>" for h in acciones[:10])

    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Revisión contable · {escape(r.get('empresa', ''))}</title>
<style>{CSS}</style></head><body><div class="wrap">
<div class="hero"><div class="eyebrow">Revisión contable · corte {_fecha(r.get('corte'))}</div>
<h1>{escape(r.get('empresa', ''))}</h1>
<div class="sub">Revisión automática con reglas fijas (sin inteligencia artificial): cada observación indica la regla,
la cifra y la evidencia, para que se pueda verificar a mano.</div>
<div class="score"><div class="ring" style="border:6px solid {color}">{puntaje}<small>/ 100</small></div>
<div><div class="ver" style="background:{color}22;color:{color}">{escape(r['veredicto'].upper())}</div>
<div class="sub" style="margin-top:8px">Confiabilidad del registro contable. Los riesgos de pago (impuestos y
prestaciones vencidas) se muestran aparte y no bajan esta nota.</div></div></div>
<div class="kpis"><div class="kpi"><b>{c['CRITICO']}</b><span>Críticos</span></div>
<div class="kpi"><b>{c['ALTO']}</b><span>Altos</span></div><div class="kpi"><b>{c['MEDIO'] + c['BAJO']}</b><span>Medios y bajos</span></div>
<div class="kpi"><b>{c['OK']}</b><span>Revisiones OK</span></div></div></div>

<section><h2>Resumen por área</h2><div class="areas">{''.join(areas_html)}</div>
{f'<h3>Acciones prioritarias</h3><ol class="acc">{acc_html}</ol>' if acc_html else ''}</section>

<section><h2>Errores e inconsistencias de registro ({len(registro)})</h2>
{''.join(_hallazgo(h) for h in registro) or '<p class="ok">No se encontraron errores de registro.</p>'}</section>

<section><h2>Riesgos de cumplimiento y de caja ({len(riesgo)})</h2>
<p class="mut">Son saldos bien registrados que muestran obligaciones vencidas o recursos sin legalizar. Total en
impuestos y prestaciones vencidos: <b>{_p(r.get('riesgos_total'))}</b>.</p>
{''.join(_hallazgo(h) for h in riesgo) or '<p class="ok">Sin riesgos detectados.</p>'}</section>

<section><h2>Lo que se verificó y está bien ({len(oks)})</h2>
<ul class="v">{''.join(f"<li><b>{escape(h['titulo'])}</b>{(' — ' + escape(h['detalle'])) if h['detalle'] else ''}"
                       f"{('<details><summary>Ver detalle</summary>' + _tabla(h['evidencia']) + '</details>') if h.get('evidencia') else ''}</li>"
                       for h in oks)}</ul></section>

<section><h2>Alcance y fuentes</h2><p class="mut">Archivos revisados: {escape(', '.join(r.get('fuentes') or []))}.<br>
Reglas aplicadas: integridad del balance (sumas iguales, ecuación patrimonial, aritmética y jerarquía de cuentas),
naturaleza de los saldos, cuentas transitorias y anticipos, impuestos (retenciones e IVA), nómina (porcentajes de ley y
pasivo provisionado), activos fijos, auxiliar (comprobantes cuadrados, duplicados, facturas repetidas, terceros, fechas,
montos redondos, ley de Benford), cruce con estados financieros y conciliación bancaria cuando se suministran.<br>
Esta revisión no reemplaza la auditoría ni la revisoría fiscal: señala dónde mirar con base en las cifras.<br>
Generado por Shaki el {_fecha(r.get('generado'))}.</p></section>
</div></body></html>"""
