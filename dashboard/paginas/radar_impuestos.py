"""Radar tributario — tablero futurista de obligaciones DIAN y SHD Bogotá."""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta
from html import escape

import streamlit as st
import streamlit.components.v1 as components

from config import cfg
from modulos import calendario_tributario_2026 as cal
from modulos import radar_tributario as rt

C_DIAN = "#7DD3FC"
C_SHD = "#C4B5FD"
C_ACC = "#FF6A3D"
MESES_C = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
MESES_L = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre",
           "Octubre", "Noviembre", "Diciembre"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

CSS = """
<style>
.rt-chip { display:inline-block; font-size:10px; font-family:'Geist Mono',monospace; letter-spacing:.06em;
           padding:3px 8px; border-radius:6px; font-weight:500; white-space:nowrap; }
.s-VENCIDO, .s-HOY { background:#FF6A3D; color:#0A0B0D; }
.s-MAÑANA { background:#F5C542; color:#0A0B0D; }
.s-ESTA-SEMANA { border:1px solid #F5C542; color:#F5C542; }
.s-PROGRAMADO { border:1px solid #3F3F46; color:#C4C4CC; }
.s-PRESENTADO { background:#14321F; color:#4ADE80; }
.s-NO-APLICA { border:1px dashed #3F3F46; color:#71717A; }
.e-DIAN { color:#7DD3FC; } .e-SHD { color:#C4B5FD; }
.rt-ent { font-size:10px; font-family:'Geist Mono',monospace; letter-spacing:.08em; }
.rt-t { font-size:15px; color:#FFFFFF; font-weight:500; line-height:1.3; }
.rt-s { font-size:12.5px; color:#8B8B93; margin-top:3px; line-height:1.45; }
.rt-d { text-align:right; font-family:'Geist Mono',monospace; }
.rt-d b { display:block; font-size:22px; font-weight:400; color:#FFFFFF; line-height:1; }
.rt-d span { font-size:10px; color:#8B8B93; letter-spacing:.06em; }
.rt-mes { display:flex; justify-content:space-between; align-items:baseline; margin:26px 0 6px 0;
          padding-bottom:8px; border-bottom:1px solid #1F2024; }
.rt-mes b { font-size:18px; color:#FFFFFF; font-weight:500; }
.rt-mes span { font-size:11px; color:#8B8B93; font-family:'Geist Mono',monospace; }
.rt-card { background:#0F1012; border:1px solid #1F2024; border-radius:18px; padding:18px 20px; }
.rt-card h4 { margin:0 0 8px 0; font-size:16px; font-weight:500; color:#FFFFFF; }
.rt-next { background:linear-gradient(135deg,#0E1620 0%,#0F1012 60%); border:1px solid #1E2A36;
           border-radius:18px; padding:16px 18px; height:100%; }
.rt-next.shd { background:linear-gradient(135deg,#15121F 0%,#0F1012 60%); border-color:#2A2340; }
.rt-tl { position:relative; height:132px; margin:6px 0 4px 0; }
.rt-tl-track { position:absolute; left:0; right:0; top:58px; height:2px;
               background:linear-gradient(90deg,#FF6A3D 0%,#26272C 8%,#26272C 100%); }
.rt-tl-m { position:absolute; top:52px; width:14px; height:14px; margin-left:-7px; border-radius:50%;
           box-shadow:0 0 0 4px #0A0B0D, 0 0 18px currentColor; }
.rt-tl-l { position:absolute; width:120px; margin-left:-60px; text-align:center; font-size:10.5px;
           color:#C4C4CC; line-height:1.25; }
.rt-tl-l b { display:block; font-family:'Geist Mono',monospace; font-size:10px; color:#8B8B93; font-weight:400; }
.rt-tl-tick { position:absolute; top:68px; font-size:9.5px; color:#52525B; font-family:'Geist Mono',monospace;
              margin-left:-12px; }
.rt-src { font-size:12px; color:#8B8B93; line-height:1.7; }
.rt-src b { color:#E8E8EA; font-weight:500; }
</style>
"""


def _fecha(d: str) -> date:
    return date.fromisoformat(str(d))


# ───────────────────────── Hero futurista (iframe con reloj en vivo) ─────────────────────────

def _orbita_svg(obls: list[dict], hoy: date, anio: int, cumplimiento: int) -> str:
    cx = cy = 170
    r_mes, r_dot = 138, 112
    partes = [f'<circle cx="{cx}" cy="{cy}" r="{r_mes}" fill="none" stroke="#1F2024" stroke-width="1"/>',
              f'<circle cx="{cx}" cy="{cy}" r="{r_dot}" fill="none" stroke="#16171A" stroke-width="22"/>',
              f'<circle cx="{cx}" cy="{cy}" r="78" fill="none" stroke="#141518" stroke-width="1" stroke-dasharray="2 5"/>']
    for m in range(12):
        a = math.radians(m * 30 - 90)
        x1, y1 = cx + 126 * math.cos(a), cy + 126 * math.sin(a)
        x2, y2 = cx + 150 * math.cos(a), cy + 150 * math.sin(a)
        partes.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#26272C"/>')
        am = math.radians(m * 30 + 15 - 90)
        tx, ty = cx + 158 * math.cos(am), cy + 158 * math.sin(am)
        partes.append(f'<text x="{tx:.1f}" y="{ty + 3:.1f}" text-anchor="middle" font-size="8.5" '
                      f'fill="{"#E8E8EA" if m + 1 == hoy.month else "#52525B"}" font-family="Geist Mono, ui-monospace, monospace">{MESES_C[m]}</text>')
    inicio = date(anio, 1, 1)
    dias_anio = 365 + (1 if anio % 4 == 0 else 0)
    for o in obls:
        f = _fecha(o["fecha_limite"])
        if f.year != anio:
            continue
        a = math.radians((f - inicio).days / dias_anio * 360 - 90)
        off = 9 if o["entidad"] != "DIAN" else -9
        x, y = cx + (r_dot + off) * math.cos(a), cy + (r_dot + off) * math.sin(a)
        col = C_DIAN if o["entidad"] == "DIAN" else C_SHD
        if o["estado"] == "PRESENTADO":
            partes.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{col}" opacity="0.28"/>')
        else:
            partes.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{col}" filter="url(#glow)">'
                          f'<title>{escape(o["impuesto"])} · {escape(o["periodo"] or "")} · {f:%d/%m}</title></circle>')
    a = math.radians((hoy - inicio).days / dias_anio * 360 - 90) if hoy.year == anio else None
    if a is not None:
        x, y = cx + 150 * math.cos(a), cy + 150 * math.sin(a)
        partes.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{C_ACC}" stroke-width="1.5" '
                      f'opacity=".85"/><circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{C_ACC}" filter="url(#glow)"/>')
    partes.append(f'<circle cx="{cx}" cy="{cy}" r="62" fill="#0A0B0D" stroke="#1F2024"/>'
                  f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" font-size="30" font-weight="300" fill="#FFFFFF" '
                  f'font-family="Geist, system-ui, sans-serif">{cumplimiento}%</text>'
                  f'<text x="{cx}" y="{cy + 22}" text-anchor="middle" font-size="8" fill="#8B8B93" '
                  f'font-family="Geist Mono, ui-monospace, monospace" letter-spacing="1">AL DÍA {anio}</text>')
    return (f'<svg viewBox="0 0 340 340" width="290" height="290" role="img" aria-label="Órbita tributaria {anio}">'
            f'<defs><filter id="glow" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="2.4" '
            f'result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
            f'{"".join(partes)}</svg>')


def _hero(prox: dict | None, obls: list[dict], hoy: date, r: dict) -> None:
    anio = hoy.year
    orbita = _orbita_svg(obls, hoy, anio, r["cumplimiento"])
    if prox:
        f = _fecha(prox["fecha_limite"])
        objetivo = datetime(f.year, f.month, f.day, 23, 59, 59).isoformat()
        col = C_DIAN if prox["entidad"] == "DIAN" else C_SHD
        titulo = f'{escape(prox["impuesto"])}'
        sub = f'{escape(prox["periodo"] or "")} · Formulario {escape(prox["formulario"] or "—")} · ' \
              f'{DIAS[f.weekday()]} {f.day} de {MESES_L[f.month - 1].lower()}'
        ent = escape(prox["entidad"])
    else:
        objetivo, col, titulo, sub, ent = "", "#4ADE80", "Sin declaraciones pendientes", "Todo presentado", "—"
    nit = escape(cfg.NIT_EMPRESA)
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#0A0B0D;color:#E8E8EA;font-family:Geist,system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{position:relative;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:24px;padding:22px 26px;
  border:1px solid #1F2024;border-radius:22px;overflow:hidden;
  background:radial-gradient(1200px 400px at 10% -20%,rgba(125,211,252,.08),transparent 60%),
             radial-gradient(800px 380px at 100% 120%,rgba(196,181,253,.07),transparent 60%),#0B0C0F}}
.grid{{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),
  linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:28px 28px;
  mask-image:linear-gradient(180deg,#000 0%,transparent 90%);pointer-events:none}}
.l{{position:relative;flex:1 1 300px;min-width:0}}
.eb{{font-family:'Geist Mono',monospace;font-size:11px;letter-spacing:.14em;color:#8B8B93}}
.eb i{{display:inline-block;width:7px;height:7px;border-radius:50%;background:#4ADE80;margin-right:8px;
  box-shadow:0 0 10px #4ADE80;animation:p 2s infinite}}
@keyframes p{{0%,100%{{opacity:1}}50%{{opacity:.35}}}}
.lab{{margin-top:22px;font-family:'Geist Mono',monospace;font-size:11px;letter-spacing:.12em;color:{col}}}
.t{{font-size:30px;font-weight:500;letter-spacing:-.02em;color:#fff;margin:6px 0 4px}}
.s{{font-size:13.5px;color:#A1A1AA}}
.cd{{display:flex;gap:10px;margin-top:22px}}
.u{{min-width:68px;padding:11px 8px 9px;border-radius:14px;background:rgba(255,255,255,.03);border:1px solid #1F2024;text-align:center}}
.u b{{display:block;font-family:'Geist Mono',monospace;font-size:34px;font-weight:400;color:#fff;letter-spacing:-.02em;
  text-shadow:0 0 22px {col}55}}
.u span{{font-family:'Geist Mono',monospace;font-size:9.5px;letter-spacing:.14em;color:#8B8B93}}
.r{{position:relative;flex:none}}
.leg{{display:flex;gap:16px;justify-content:center;font-family:'Geist Mono',monospace;font-size:10px;color:#8B8B93;margin-top:-6px}}
.leg i{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px}}
@media(max-width:600px){{.r{{display:none}}.t{{font-size:24px}}.u{{min-width:0;flex:1}}.u b{{font-size:26px}}
  .eb{{font-size:9.5px;letter-spacing:.08em}}}}
</style></head><body><div class="wrap"><div class="grid"></div>
<div class="l">
  <div class="eb"><i></i>RADAR TRIBUTARIO · NIT {nit} · DIAN DÍGITO {cal.NIT_ULTIMO_DIGITO} · SHD BOGOTÁ</div>
  <div class="lab">PRÓXIMA PRESENTACIÓN · {ent}</div>
  <div class="t">{titulo}</div>
  <div class="s">{sub}</div>
  <div class="cd" id="cd">
    <div class="u"><b id="d">--</b><span>DÍAS</span></div>
    <div class="u"><b id="h">--</b><span>HORAS</span></div>
    <div class="u"><b id="m">--</b><span>MIN</span></div>
    <div class="u"><b id="x">--</b><span>SEG</span></div>
  </div>
</div>
<div class="r">{orbita}
  <div class="leg"><span><i style="background:{C_DIAN}"></i>DIAN</span><span><i style="background:{C_SHD}"></i>SHD</span>
  <span><i style="background:{C_ACC}"></i>HOY</span></div></div>
</div>
<script>
const T={json.dumps(objetivo)};
function pad(n){{return String(n).padStart(2,'0')}}
function tick(){{ if(!T) return; let ms=new Date(T)-new Date(); if(ms<0) ms=0;
  const s=Math.floor(ms/1000); document.getElementById('d').textContent=pad(Math.floor(s/86400));
  document.getElementById('h').textContent=pad(Math.floor(s%86400/3600));
  document.getElementById('m').textContent=pad(Math.floor(s%3600/60));
  document.getElementById('x').textContent=pad(s%60); }}
tick(); setInterval(tick,1000);
</script></body></html>"""
    components.html(html, height=372)


# ───────────────────────── Bloques ─────────────────────────

def _kpis(r: dict, prox: dict | None, hoy: date) -> None:
    dias = (_fecha(prox["fecha_limite"]) - hoy).days if prox else "—"
    items = [
        ("Próxima en", f"{dias}", "DÍAS" if prox else "SIN PENDIENTES", False),
        ("Próximos 30 días", r["prox30"], "DECLARACIONES", False),
        ("Pendientes del año", r["pendientes"], f"DIAN {r['dian']} · SHD {r['shd']}", False),
        ("Vencidas", r["vencidas"], "SIN PRESENTAR", r["vencidas"] > 0),
        ("Cumplimiento", f"{r['cumplimiento']}%", f"{r['presentadas']} PRESENTADAS", False),
    ]
    html = "".join(
        f'<div class="sk-kpi"><span class="sk-kpi-l">{l}</span>'
        f'<span class="sk-kpi-v" style="{"color:" + C_ACC if a else ""}">{v}</span>'
        f'<span class="sk-kpi-f">{f}</span></div>' for l, v, f, a in items
    )
    st.markdown(f'<div class="sk-kpis" style="margin:16px 0 8px 0">{html}</div>', unsafe_allow_html=True)


def _linea_tiempo(obls: list[dict], hoy: date, dias: int = 90) -> None:
    fin = hoy + timedelta(days=dias)
    vis = [o for o in obls if o["estado"] == "PENDIENTE" and hoy <= _fecha(o["fecha_limite"]) <= fin]
    marcas, etiquetas, ticks = [], [], []
    for k in range(0, dias + 1, 15):
        d = hoy + timedelta(days=k)
        ticks.append(f'<div class="rt-tl-tick" style="left:{k / dias * 100:.2f}%">{d.day}/{d.month}</div>')
    for i, o in enumerate(vis):
        f = _fecha(o["fecha_limite"])
        pos = (f - hoy).days / dias * 100
        col = C_DIAN if o["entidad"] == "DIAN" else C_SHD
        marcas.append(f'<div class="rt-tl-m" style="left:{pos:.2f}%;background:{col};color:{col}" '
                      f'title="{escape(o["impuesto"])} {escape(o["periodo"] or "")}"></div>')
        top = 0 if i % 2 == 0 else 92  # etiquetas alternan arriba / abajo de la línea
        etiquetas.append(f'<div class="rt-tl-l" style="left:{pos:.2f}%;top:{top}px"><b>{f.day} {MESES_C[f.month - 1]}</b>'
                         f'{escape(o["impuesto"].replace("Retención en la fuente", "Retención"))}</div>')
    st.markdown(
        f'<div class="rt-mes"><b>Próximos {dias} días</b><span>{len(vis)} PRESENTACIÓN(ES)</span></div>'
        f'<div class="rt-tl"><div class="rt-tl-track"></div>{"".join(ticks)}{"".join(marcas)}{"".join(etiquetas)}</div>',
        unsafe_allow_html=True,
    )


def _tarjetas_proximas(obls: list[dict], hoy: date) -> None:
    pend = [o for o in obls if o["estado"] == "PENDIENTE" and _fecha(o["fecha_limite"]) >= hoy][:3]
    if not pend:
        return
    cols = st.columns(len(pend), gap="medium")
    for c, o in zip(cols, pend):
        f = _fecha(o["fecha_limite"])
        dias = (f - hoy).days
        sem = rt.semaforo(o, hoy)
        es_dian = o["entidad"] == "DIAN"
        with c:
            st.markdown(
                f'<div class="rt-next {"" if es_dian else "shd"}">'
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'<span class="rt-ent {"e-DIAN" if es_dian else "e-SHD"}">{escape(o["entidad"])}</span>'
                f'<span class="rt-chip s-{sem.replace(" ", "-")}">{sem}</span></div>'
                f'<div class="rt-t" style="margin-top:12px">{escape(o["impuesto"])}</div>'
                f'<div class="rt-s">{escape(o["periodo"] or "")} · F. {escape(o["formulario"] or "")}</div>'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-end;margin-top:16px">'
                f'<div class="rt-s">{DIAS[f.weekday()]}<br><b style="color:#fff;font-size:15px;font-weight:500">'
                f'{f.day} {MESES_L[f.month - 1].lower()}</b></div>'
                f'<div class="rt-d"><b>{dias}</b><span>DÍAS</span></div></div></div>',
                unsafe_allow_html=True,
            )
            if st.button("Ya lo presenté", key=f"rt_np_{o['id']}", type="primary", use_container_width=True):
                rt.marcar_presentado(o["id"], por="dashboard")
                st.rerun()


def _fila(o: dict, hoy: date) -> None:
    sem = rt.semaforo(o, hoy)
    f = _fecha(o["fecha_limite"])
    es_dian = o["entidad"] == "DIAN"
    c1, c2, c3, c4 = st.columns([1.0, 3.2, 0.7, 2.6], vertical_alignment="center")
    c1.markdown(f'<span class="rt-chip s-{sem.replace(" ", "-")}">{sem}</span>', unsafe_allow_html=True)
    extra = []
    if o.get("referencia"):
        extra.append(f"ref {escape(o['referencia'])}")
    if o.get("nota"):
        extra.append(escape(o["nota"]))
    if o.get("alerta_24h_enviada") and o["estado"] == "PENDIENTE":
        extra.append("alerta enviada")
    c2.markdown(
        f'<div class="rt-t">{escape(o["impuesto"])} <span class="rt-ent {"e-DIAN" if es_dian else "e-SHD"}">'
        f'· {escape(o["entidad"])}</span></div>'
        f'<div class="rt-s">{escape(o["periodo"] or "")} · F. {escape(o["formulario"] or "")}'
        f'{" · " + " · ".join(extra) if extra else ""}</div>',
        unsafe_allow_html=True,
    )
    c3.markdown(f'<div class="rt-d"><b style="font-size:18px">{f.day:02d}</b><span>{MESES_C[f.month - 1]}</span></div>',
                unsafe_allow_html=True)
    with c4:
        if o["estado"] == "PENDIENTE":
            b1, b2 = st.columns([1.5, 1])
            if b1.button("Presentado", key=f"rt_ok_{o['id']}", type="primary", use_container_width=True):
                rt.marcar_presentado(o["id"], por="dashboard")
                st.rerun()
            with b2.popover("Más", use_container_width=True):
                if st.button("Enviar alerta ahora", key=f"rt_al_{o['id']}", use_container_width=True):
                    res = rt.enviar_alerta([o], marcar=False)
                    st.error("Sin canal de correo") if res["sin_canal"] else st.success(f"{res['correos']} correo(s)")
                if st.button("No aplica", key=f"rt_na_{o['id']}", use_container_width=True):
                    rt.cambiar_estado(o["id"], "NO APLICA")
                    st.rerun()
        elif st.button("Reabrir", key=f"rt_re_{o['id']}", use_container_width=True):
            rt.cambiar_estado(o["id"], "PENDIENTE")
            st.rerun()


def _agenda(hoy: date) -> None:
    c1, c2, c3 = st.columns([1.4, 1, 1])
    vista = c1.selectbox("Ver", ["Pendientes", "Todo el año", "Presentadas"], key="rt_vista")
    entidad = c2.selectbox("Entidad", ["Todas", "DIAN", "SHD Bogotá"], key="rt_ent")
    grupos = ["Todos"] + sorted({o["impuesto"] for o in rt.listar()})
    imp = c3.selectbox("Impuesto", grupos, key="rt_imp")
    estados = {"Pendientes": ("PENDIENTE",), "Presentadas": ("PRESENTADO",), "Todo el año": None}[vista]
    filas = rt.listar(estados=estados)
    if entidad != "Todas":
        filas = [o for o in filas if o["entidad"] == entidad]
    if imp != "Todos":
        filas = [o for o in filas if o["impuesto"] == imp]
    if not filas:
        st.markdown('<div class="sk-row"><span class="sk-row-s">Nada en esta vista.</span></div>', unsafe_allow_html=True)
        return
    mes_actual = None
    for o in filas:
        f = _fecha(o["fecha_limite"])
        if (f.year, f.month) != mes_actual:
            mes_actual = (f.year, f.month)
            n = len([x for x in filas if _fecha(x["fecha_limite"]).month == f.month and
                     _fecha(x["fecha_limite"]).year == f.year])
            st.markdown(f'<div class="rt-mes"><b>{MESES_L[f.month - 1]} {f.year}</b><span>{n} OBLIGACIÓN(ES)</span></div>',
                        unsafe_allow_html=True)
        _fila(o, hoy)


def _configuracion() -> None:
    izq, der = st.columns([1.1, 1], gap="large")
    with izq:
        st.markdown('<div class="rt-card"><h4>Mis obligaciones</h4><div class="rt-src">Activa solo lo que '
                    'aparece en el RUT de la empresa. Al guardar, el radar se recalcula.</div></div>',
                    unsafe_allow_html=True)
        p = rt.perfil()
        nuevo = {}
        for k, nombre in cal.GRUPOS.items():
            ent = "DIAN" if k in ("RET", "IVA_BIM", "IVA_CUAT", "RENTA", "EXOGENA", "ACTIVOS_EXT", "PATRIMONIO") else "SHD"
            nuevo[k] = st.toggle(f"{nombre} · {ent}", value=p.get(k, False), key=f"rt_pf_{k}")
        if nuevo["IVA_BIM"] and nuevo["IVA_CUAT"]:
            st.warning("IVA bimestral y cuatrimestral son excluyentes: deje solo uno.")
        if nuevo["ICA_BIM"] and nuevo["ICA_ANUAL"]:
            st.warning("ICA bimestral y anual son excluyentes: deje solo uno.")
        if st.button("Guardar perfil", key="rt_pf_save", type="primary"):
            rt.guardar_perfil(nuevo)
            st.success("Perfil guardado y calendario recalculado.")
            st.rerun()
    with der:
        from conexiones.notificador import canal_correo

        canal = canal_correo()
        dest = rt.destinos()
        pend = rt.para_alerta()
        st.markdown(
            f'<div class="rt-card"><h4>Alerta 24 horas · presentación</h4><div class="rt-src">'
            f'Envío automático: <b>08:05</b> y repaso <b>16:35</b>, un día antes de cada vencimiento.<br>'
            f'Canal: <b>{escape(canal) if canal else "<span style=color:#F5C542>sin configurar (SMTP)</span>"}</b><br>'
            f'Para: <b>{escape(", ".join(dest))}</b><br>Botón: <b>Ya lo presenté</b> → '
            f'{escape(getattr(cfg, "APP_PUBLIC_URL", ""))}<br>'
            f'Por avisar hoy/mañana: <b>{len(pend)}</b></div></div>',
            unsafe_allow_html=True,
        )
        b1, b2 = st.columns(2)
        if b1.button("Enviar ahora", key="rt_send", use_container_width=True, disabled=not pend):
            res = rt.enviar_alerta(pend)
            st.error("Sin canal de correo") if res["sin_canal"] else st.success(f"Enviado a {res['correos']} correo(s)")
        if b2.button("Probar envío", key="rt_test", use_container_width=True):
            muestra = rt.listar(date.today(), None, estados=("PENDIENTE",))[:1]
            if not muestra:
                st.info("No hay declaraciones pendientes para usar de ejemplo.")
            else:
                res = rt.enviar_alerta(muestra, marcar=False)
                st.error("Sin canal de correo") if res["sin_canal"] else st.success(
                    f"Prueba enviada a {res['correos']} correo(s)")
        st.write("")
        st.markdown(
            f'<div class="rt-card"><h4>Fuentes oficiales</h4><div class="rt-src">'
            f'<b>DIAN</b> · {escape(cal.F_DIAN)}<br>'
            f'<b>SHD Bogotá</b> · {escape(cal.F_SHD)}<br>'
            f'NIT {escape(cfg.NIT_EMPRESA)} · último dígito <b>{cal.NIT_ULTIMO_DIGITO}</b> · dos últimos '
            f'<b>{cal.NIT_DOS_DIGITOS}</b> · persona jurídica, no gran contribuyente.<br>'
            f'La DIAN y la SHD no publican estos plazos como API abierta: el radar usa la norma oficial. '
            f'Si cambian (p. ej. por un festivo nuevo), se actualiza el calendario.</div></div>',
            unsafe_allow_html=True,
        )


# ───────────────────────── Página ─────────────────────────

def render() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    rt.inicializar_tablas()
    if not rt.calendario_aplica():
        st.error(f"El calendario cargado es para NIT terminado en {cal.NIT_DOS_DIGITOS}; el configurado es "
                 f"{cfg.NIT_EMPRESA}. Revise NIT_EMPRESA en .env.")
        return
    if not rt.listar(incluir_no_aplica=True):
        rt.sincronizar()
    hoy = date.today()
    obls = rt.listar()
    r = rt.resumen(hoy)
    prox = rt.proxima(hoy)

    t_radar, t_agenda, t_conf = st.tabs(["Radar", "Agenda tributaria", "Obligaciones y alertas"])
    with t_radar:
        _hero(prox, obls, hoy, r)
        _kpis(r, prox, hoy)
        _linea_tiempo(obls, hoy)
        st.markdown('<div class="rt-mes"><b>Lo que viene</b><span>MARCA CUANDO LO PRESENTES</span></div>',
                    unsafe_allow_html=True)
        _tarjetas_proximas(obls, hoy)
    with t_agenda:
        _agenda(hoy)
    with t_conf:
        _configuracion()
