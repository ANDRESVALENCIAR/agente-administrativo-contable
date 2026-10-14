"""Página Inicio — panel principal (diseño "Shaki Black")."""
from datetime import date, datetime
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st

from core.formato_col import fecha_larga_es
from dashboard.estilos import ACCENT, PLOTLY_LAYOUT
from database import marcar_alerta_resuelta, obtener_alertas_activas, obtener_correos_ultimos_dias, obtener_estadisticas_hoy
from utils.calendario_maestro import tareas_hoy, tareas_vencidas

_MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
_TAG = {
    "CRITICO": ("sk-tag-crit", "CRÍTICA"),
    "URGENTE": ("sk-tag-urg", "URGENTE"),
    "AVISO": ("sk-tag-av", "AVISO"),
    "INFO": ("sk-tag-av", "INFO"),
}


def _miles(n: float | int) -> str:
    return f"{n:,.0f}".replace(",", ".")


def _resumen_pagos() -> dict:
    try:
        from utils.alertas_pagos import resumen_pagos_widget

        return resumen_pagos_widget()
    except Exception:
        return {"vencidos": 0, "hoy": 0, "proximos_7d": 0, "total_pendiente": 0, "aprobados": 0}


def _atencion(alertas: list) -> None:
    st.markdown(
        f'<div class="sk-card-h"><h4>Requiere tu atención</h4>'
        f'<span class="sk-row-s">{len(alertas)} abiertas</span></div>',
        unsafe_allow_html=True,
    )
    if not alertas:
        st.markdown('<div class="sk-row"><span class="sk-row-s">Todo en orden. Sin alertas activas.</span></div>',
                    unsafe_allow_html=True)
        return
    for a in alertas[:6]:
        clase, etiqueta = _TAG.get(a[2], ("sk-tag-av", str(a[2])))
        c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
        with c1:
            st.markdown(
                f'<div class="sk-row"><span class="sk-tag {clase}">{etiqueta}</span>'
                f'<div><div class="sk-row-t">{escape(str(a[4]))}</div>'
                f'<div class="sk-row-s">{escape(str(a[3]).capitalize())} · {escape(str(a[5] or ""))}</div></div></div>',
                unsafe_allow_html=True,
            )
        with c2:
            if st.button("Resolver", key=f"alerta_{a[0]}", width="stretch"):
                marcar_alerta_resuelta(a[0])
                st.rerun()


def _calendario_tributario() -> None:
    """Próximos 7 días de la agenda unificada (pagos, impuestos, personal, proveedores…)."""
    st.markdown('<div class="sk-card-h"><h4>Próximo en la agenda</h4></div>', unsafe_allow_html=True)
    try:
        from datetime import timedelta

        from modulos import agenda_unificada as ag

        hoy = date.today()
        filas = [e for e in ag.eventos(hoy - timedelta(days=60), hoy + timedelta(days=7), incluir_hechos=False)
                 if e["fuente"] not in ("AGENTE", "FESTIVO")][:6]
    except Exception:
        filas = []
    if not filas:
        st.markdown('<div class="sk-row"><span class="sk-row-s">Nada pendiente en los próximos 7 días.</span></div>',
                    unsafe_allow_html=True)
        return
    html = []
    for e in filas:
        f = e["fecha"]
        dias = (f - hoy).days
        estado = (f'<span class="sk-venc">Vencido hace {-dias} días</span>' if dias < 0 else
                  '<span class="sk-venc">Hoy</span>' if dias == 0 else f"en {dias} días")
        fuente = ag.FUENTES[e["fuente"]]
        html.append(
            f'<div class="sk-row"><div class="sk-date"><b>{f.day:02d}</b><span>{_MESES[f.month - 1]}</span></div>'
            f'<div><div class="sk-row-t">{escape(e["titulo"])}</div>'
            f'<div class="sk-row-s"><span style="color:{fuente["color"]}">{escape(fuente["nombre"])}</span> · {estado}</div>'
            f'</div></div>'
        )
    st.markdown("".join(html), unsafe_allow_html=True)


# ── Portada "Comando": saludo, buscador grande y 4 tarjetas ─────────────────────────────────────────────
SUGERENCIAS = ["¿Cómo vamos?", "¿Cuánta plata hay en bancos?", "¿Me alcanza la plata?", "¿Qué tengo hoy?",
               "¿Qué impuestos vienen?", "¿Cuánto nos deben los clientes?"]

CSS_PORTADA = f"""
<style>
[data-testid="stMain"] {{
  background-image: radial-gradient(rgba(255,255,255,.07) 1px, transparent 1px) !important;
  background-size: 22px 22px !important;
}}
.st-key-chat_btn_box {{ display: none !important; }}
.pt-top {{ display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px; font-family:'Geist Mono',monospace;
  font-size:11px; letter-spacing:.2em; color:#8B8E96; text-transform:uppercase; }}
.pt-top b {{ color:{ACCENT}; font-weight:500; letter-spacing:.14em; }}
.pt-hola {{ text-align:center; font-weight:300; font-size:clamp(38px,5.6vw,74px); line-height:1.02;
  letter-spacing:-.035em; color:#F4F4F5; margin:42px 0 26px; }}
.pt-hola span {{ color:{ACCENT}; font-weight:500; }}
.st-key-buscador {{ max-width:860px; margin:0 auto; }}
.st-key-buscador [data-testid="stForm"] {{ background:#111216; border:1px solid #2A2C33; border-radius:22px;
  padding:8px 8px 8px 22px; box-shadow:0 0 0 1px {ACCENT}59, 0 0 60px {ACCENT}2E; transition:box-shadow .2s; }}
.st-key-buscador [data-testid="stForm"]:focus-within {{ box-shadow:0 0 0 1px {ACCENT}, 0 0 56px {ACCENT}59; }}
.st-key-buscador [data-testid="stHorizontalBlock"] {{ align-items:center; flex-wrap:nowrap !important; gap:10px; }}
.st-key-buscador [data-testid="stColumn"] {{ min-width:0 !important; }}
.st-key-buscador [data-baseweb="input"], .st-key-buscador [data-baseweb="base-input"] {{
  background:transparent !important; border:0 !important; box-shadow:none !important; }}
.st-key-buscador input {{ height:58px !important; font-size:20px !important; color:#F4F4F5 !important;
  background:transparent !important; padding-left:4px !important; }}
.st-key-buscador input::placeholder {{ color:#7C7F88 !important; }}
.st-key-buscador [data-testid="stTextInputRootElement"], .st-key-buscador [data-testid="stTextInputRootElement"]:focus-within {{
  border:0 !important; box-shadow:none !important; outline:none !important; background:transparent !important; }}
.st-key-buscador [data-testid="InputInstructions"] {{ display:none !important; }}
.st-key-buscador [data-testid="stColumn"]:last-child {{ flex:0 0 58px !important; width:58px !important; }}
.st-key-buscador [data-testid="stColumn"]:first-child {{ flex:1 1 auto !important; }}
.st-key-buscador button {{ height:54px !important; min-height:54px !important; min-width:54px !important; border-radius:15px !important;
  background:{ACCENT} !important; border:0 !important; color:#0A0A0A !important; font-size:22px !important;
  font-weight:600 !important; }}
.st-key-sugerencias_inicio {{ max-width:860px; margin:14px auto 0; }}
.st-key-sugerencias_inicio [data-testid="stButtonGroup"] {{ justify-content:center; }}
.st-key-sugerencias_inicio [data-testid="stButtonGroup"] > div {{ justify-content:center; }}
.st-key-sugerencias_inicio button {{ border-radius:99px !important; background:#0E0F13 !important;
  border:1px solid #2A2C33 !important; color:#D4D4D8 !important; padding:6px 16px !important; }}
.st-key-sugerencias_inicio button:hover {{ border-color:{ACCENT} !important; color:#fff !important; }}
.st-key-respuesta_inicio {{ max-width:860px; margin:22px auto 0; background:rgba(17,18,22,.92);
  border:1px solid #2A2C33; border-radius:20px; padding:20px 24px 14px; }}
.pt-preg {{ font-family:'Geist Mono',monospace; font-size:11px; letter-spacing:.16em; color:#8B8E96;
  text-transform:uppercase; display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap; }}
.pt-preg b {{ color:#D4D4D8; font-weight:500; letter-spacing:.04em; text-transform:none; font-family:'Geist',sans-serif;
  font-size:14px; }}
.pt-kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin:44px 0 30px; }}
.pt-kpi {{ border:1px solid #1F2127; background:rgba(17,18,22,.85); border-radius:18px; padding:20px 22px;
  display:flex; flex-direction:column; gap:6px; min-width:0; }}
.pt-kpi.alerta {{ border-color:#3A2414; background:rgba(30,16,8,.85); }}
.pt-kpi small {{ font-family:'Geist Mono',monospace; font-size:10.5px; letter-spacing:.16em; color:#8B8E96;
  text-transform:uppercase; }}
.pt-kpi.alerta small {{ color:#FFB07A; }}
.pt-kpi b {{ font-size:38px; font-weight:300; letter-spacing:-.02em; color:#F4F4F5; line-height:1.1; }}
.pt-kpi.alerta b {{ color:{ACCENT}; }}
.pt-kpi b i {{ font-style:normal; font-size:18px; color:#8B8E96; }}
.pt-kpi span {{ font-size:13px; color:#A1A1AA; }}
.pt-kpi.alerta span {{ color:#D4A383; }}
@media (max-width: 640px) {{
  .pt-hola {{ margin:22px 0 18px; }}
  .st-key-buscador input {{ font-size:17px !important; height:50px !important; }}
}}
</style>
"""


def _saludo() -> str:
    h = datetime.now().hour
    return "Buenos días" if h < 12 else "Buenas tardes" if h < 19 else "Buenas noches"


def _preguntar_desde_portada(texto: str) -> None:
    """Responde en la portada y deja la conversación en el chat para seguirla."""
    from dashboard.chat import chat_responder
    from modulos import asistente as _as

    st.session_state.setdefault("chat_historial", [])
    st.session_state.setdefault("chat_mensajes_ui", [])
    motor = _as.motor_para(texto, st.session_state.chat_historial)
    with st.spinner("Shaki está analizando con IA…" if motor == "ia" else "Shaki está consultando…"):
        r, st.session_state.chat_historial = chat_responder(texto, st.session_state.chat_historial)
    st.session_state.chat_mensajes_ui += [{"rol": "user", "texto": texto}, {"rol": "agent", "texto": r}]
    st.session_state["portada_resp"] = {"pregunta": texto, "respuesta": r, "motor": motor}


def _portada(n_alertas: int, criticas: int) -> None:
    from config import cfg

    st.markdown(CSS_PORTADA, unsafe_allow_html=True)
    hoy = fecha_larga_es(datetime.now(), con_hora=False)
    aviso = (f"<b>● {n_alertas} alertas · {criticas} críticas</b>" if criticas else
             f"<b>● {n_alertas} alertas abiertas</b>" if n_alertas else "<b>● Todo en orden</b>")
    st.markdown(f'<div class="pt-top"><span>{escape(hoy)} · {escape(cfg.NOMBRE_EMPRESA)}</span>{aviso}</div>'
                f'<div class="pt-hola">{_saludo()}, {escape(cfg.NOMBRE_USUARIA)}.<br><span>¿Qué quieres saber?</span></div>',
                unsafe_allow_html=True)

    with st.container(key="buscador"):
        with st.form("form_buscador", clear_on_submit=True, border=False):
            c1, c2 = st.columns([12, 1])
            q = c1.text_input("Pregúntale a Shaki", label_visibility="collapsed",
                              placeholder="Pregúntale a Shaki: pagos, cartera, impuestos, personas…")
            enviar = c2.form_submit_button("→", help="Preguntar")
        if enviar and q.strip():
            _preguntar_desde_portada(q.strip())

    with st.container(key="sugerencias_inicio"):
        n = st.session_state.get("portada_sug_n", 0)
        elegida = st.pills("Sugerencias", SUGERENCIAS, key=f"portada_sug_{n}", label_visibility="collapsed")
        if elegida:
            st.session_state.portada_sug_n = n + 1
            _preguntar_desde_portada(elegida)
            st.rerun()

    resp = st.session_state.get("portada_resp")
    if resp:
        with st.container(key="respuesta_inicio"):
            etiqueta = "IA · Claude" if resp["motor"] == "ia" else "Motor local · gratis"
            st.markdown(f'<div class="pt-preg"><b>{escape(resp["pregunta"])}</b><span>{etiqueta}</span></div>',
                        unsafe_allow_html=True)
            st.markdown(str(resp["respuesta"]).replace("$", "\\$").replace("\n", "  \n"))
            b1, b2, _ = st.columns([1.4, 1, 3])
            if b1.button("Seguir conversando", key="portada_seguir", icon=":material/chat:"):
                st.session_state["abrir_chat"] = True
                st.rerun()
            if b2.button("Cerrar", key="portada_cerrar", icon=":material/close:"):
                st.session_state.pop("portada_resp", None)
                st.rerun()


def _tarjetas(stats: dict, alertas: list, n_tareas: int, control: dict | None) -> None:
    criticas = sum(1 for a in alertas if a[2] == "CRITICO")
    if control:
        urg = control["vencidos"] + control["hoy"]
        pagos = (("Vencidos o para hoy", _miles(urg), f"{control['manana']} mañana · {control['semana']} en 7 días")
                 if urg else ("Pagos del mes", _miles(control["mes_pendientes"]),
                              f"{control['manana']} mañana · {control['semana']} en 7 días"))
        tercera = ("Cuotas pagadas", f"{control['mes_pagados']} <i>/ {control['mes_total']}</i>",
                   f"Mes al día {control['al_dia_pct']} %")
    else:
        w = _resumen_pagos()
        pagos = ("Pagos vencidos", _miles(w.get("vencidos", 0) or 0),
                 f"{_miles(w.get('hoy', 0) or 0)} hoy · {_miles(w.get('proximos_7d', 0) or 0)} en 7 días")
        tercera = ("Pendiente por pagar", f"${_miles(w.get('total_pendiente', 0) or 0)}",
                   f"{_miles(stats['pagos_pendientes'])} por aprobar")
    items = [
        ("", *pagos),
        ("alerta" if criticas else "", "Alertas", _miles(stats["alertas_activas"]),
         f"{criticas} críticas por resolver" if criticas else "sin críticas"),
        ("", *tercera),
        ("", "Tareas hoy", _miles(n_tareas), f"Costo IA del mes ${stats['costo_mes']}"),
    ]
    st.markdown('<div class="pt-kpis">' + "".join(
        f'<div class="pt-kpi {c}"><small>{l}</small><b>{v}</b><span>{escape(str(s))}</span></div>'
        for c, l, v, s in items) + "</div>", unsafe_allow_html=True)


def render() -> None:
    """Renderiza el panel principal."""
    stats = obtener_estadisticas_hoy()
    alertas = obtener_alertas_activas()
    df_hoy = tareas_hoy()

    try:
        from modulos import control_pagos as cp

        control = cp.resumen() if cp.hay_datos() else None
    except Exception:
        control = None
    criticas = sum(1 for a in alertas if a[2] == "CRITICO")
    _portada(len(alertas), criticas)
    _tarjetas(stats, alertas, len(df_hoy), control)

    df_venc = tareas_vencidas()
    if not df_venc.empty:
        st.warning(f"{len(df_venc)} tarea(s) del calendario vencida(s). Revise el módulo Calendario.")

    izq, der = st.columns([1.55, 1], gap="large")
    with izq:
        _atencion(alertas)
    with der:
        _calendario_tributario()

    st.write("")
    izq, der = st.columns([1.55, 1], gap="large")
    with izq:
        if not df_hoy.empty:
            st.markdown('<div class="sk-card-h"><h4>Agenda del agente — hoy</h4></div>', unsafe_allow_html=True)
            st.dataframe(
                df_hoy[["titulo", "modulo", "prioridad", "tipo"]].head(8),
                width="stretch",
                hide_index=True,
            )
        datos = obtener_correos_ultimos_dias(7)
        if datos:
            df = pd.DataFrame(datos, columns=["fecha", "total", "categoria"])
            fig = px.bar(df, x="fecha", y="total", color="categoria", height=220,
                         title="Correos clasificados · 7 días")
            fig.update_layout(**PLOTLY_LAYOUT, legend_title_text="")
            st.plotly_chart(fig, width="stretch")
    with der:
        st.markdown('<div class="sk-card-h"><h4>Actividad reciente</h4></div>', unsafe_allow_html=True)
        filas = []
        for acc in (stats.get("ultimas_acciones") or [])[:8]:
            marca = "" if acc[3] == "EXITOSO" else ' <span class="sk-venc">· error</span>'
            filas.append(f'<div class="sk-log"><b>{escape(str(acc[0]))}</b> · {escape(str(acc[2] or ""))[:90]}{marca}</div>')
        st.markdown("".join(filas) or '<div class="sk-log">Sin actividad todavía.</div>', unsafe_allow_html=True)
