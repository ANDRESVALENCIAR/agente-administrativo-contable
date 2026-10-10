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


def _hero(w: dict, por_aprobar: int) -> None:
    hoy = fecha_larga_es(datetime.now(), con_hora=False)
    venc, hoy_n, prox, aprob = (int(w.get(k, 0) or 0) for k in ("vencidos", "hoy", "proximos_7d", "aprobados"))
    total = max(venc + hoy_n + prox + aprob, 1)
    seg = [
        (venc, ACCENT, "VENCIDOS"),
        (hoy_n + prox, "#E8E8EA", "HOY Y 7 DÍAS"),
        (aprob, "#3F3F46", "APROBADOS"),
    ]
    barra = "".join(
        f'<div style="flex:{max(n, 0)} 1 0;background:{c}"></div>' for n, c, _ in seg if n > 0
    ) or '<div style="flex:1 1 0;background:#26272C"></div>'
    leyenda = "".join(
        f'<span style="color:{"#C4C4CC" if c == "#E8E8EA" else "#8B8B93"}">■ {lbl} {round(n * 100 / total)}%</span>'
        for n, c, lbl in seg
    )
    st.markdown(
        f"""
        <div class="sk-hero">
          <div class="sk-eyebrow">{escape(hoy)} · Pendiente por pagar</div>
          <div class="sk-hero-num">${_miles(w.get("total_pendiente", 0) or 0)}</div>
          <div class="sk-hero-sub">
            <span><strong class="sk-acc">{_miles(venc)}</strong> vencidos</span>
            <span><strong>{_miles(por_aprobar)}</strong> por aprobar</span>
            <span><strong>{_miles(hoy_n)}</strong> vencen hoy</span>
            <span><strong>{_miles(prox)}</strong> en 7 días</span>
          </div>
          <div class="sk-bar">{barra}</div>
          <div class="sk-legend">{leyenda}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _hero_control(r: dict) -> None:
    """Hero cuando hay libro de Control de pagos cargado (cuotas, no saldos)."""
    hoy = fecha_larga_es(datetime.now(), con_hora=False)
    pct = r["al_dia_pct"]
    principal = r["vencidos"] + r["hoy"]
    if principal:
        titulo, numero = "Pagos vencidos o para hoy", _miles(principal)
    else:
        titulo, numero = "Pagos pendientes este mes", _miles(r["mes_pendientes"])
    valor = f' · ${_miles(r["valor_pendiente_mes"])} por pagar' if r["valor_pendiente_mes"] else ""
    st.markdown(
        f"""
        <div class="sk-hero">
          <div class="sk-eyebrow">{escape(hoy)} · {titulo}</div>
          <div class="sk-hero-num">{numero}</div>
          <div class="sk-hero-sub">
            <span><strong class="{'sk-acc' if r['vencidos'] else ''}">{_miles(r['vencidos'])}</strong> vencidos</span>
            <span><strong>{_miles(r['hoy'])}</strong> hoy</span>
            <span><strong>{_miles(r['manana'])}</strong> mañana (alerta 24h)</span>
            <span><strong>{_miles(r['semana'])}</strong> en 7 días{valor}</span>
          </div>
          <div class="sk-bar"><div style="flex:{max(pct, 1)} 1 0;background:#4ADE80"></div>
            <div style="flex:{max(100 - pct, 0)} 1 0;background:#26272C"></div></div>
          <div class="sk-legend"><span style="color:#4ADE80">■ MES AL DÍA {pct}%</span>
            <span>■ {r['mes_pagados']} DE {r['mes_total']} CUOTAS PAGADAS</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _kpis(stats: dict, alertas: list, n_tareas: int) -> None:
    criticas = sum(1 for a in alertas if a[2] == "CRITICO")
    items = [
        ("Alertas", stats["alertas_activas"], f"{criticas} CRÍTICAS" if criticas else "SIN CRÍTICAS"),
        ("Por aprobar", stats["pagos_pendientes"], "7 DÍAS"),
        ("Correos", stats["correos_hoy"], "HOY"),
        ("Tareas", n_tareas, "HOY"),
        ("Costo IA", f"${stats['costo_hoy']}", f"MES ${stats['costo_mes']}"),
    ]
    html = "".join(
        f'<div class="sk-kpi"><span class="sk-kpi-l">{l}</span>'
        f'<span class="sk-kpi-v">{v}</span><span class="sk-kpi-f">{f}</span></div>'
        for l, v, f in items
    )
    st.markdown(f'<div class="sk-kpis">{html}</div>', unsafe_allow_html=True)


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
            if st.button("Resolver", key=f"alerta_{a[0]}", use_container_width=True):
                marcar_alerta_resuelta(a[0])
                st.rerun()


def _calendario_tributario() -> None:
    """Próximas presentaciones del radar tributario (DIAN + SHD, NIT de la empresa)."""
    st.markdown('<div class="sk-card-h"><h4>Calendario tributario</h4></div>', unsafe_allow_html=True)
    try:
        from modulos import radar_tributario as rt

        hoy = date.today()
        filas = [o for o in rt.listar(estados=("PENDIENTE",))][:5]
    except Exception:
        filas = []
    if not filas:
        st.markdown('<div class="sk-row"><span class="sk-row-s">Sin declaraciones pendientes.</span></div>',
                    unsafe_allow_html=True)
        return
    html = []
    for o in filas:
        f = date.fromisoformat(str(o["fecha_limite"]))
        dias = (f - hoy).days
        estado = (f'<span class="sk-venc">Vencida hace {-dias} días</span>' if dias < 0 else
                  '<span class="sk-venc">Vence hoy</span>' if dias == 0 else f"{escape(o['entidad'])} · {dias} días")
        html.append(
            f'<div class="sk-row"><div class="sk-date"><b>{f.day:02d}</b><span>{_MESES[f.month - 1]}</span></div>'
            f'<div><div class="sk-row-t">{escape(o["impuesto"])}</div>'
            f'<div class="sk-row-s">{escape(o["periodo"] or "")} · {estado}</div></div></div>'
        )
    st.markdown("".join(html), unsafe_allow_html=True)


def render() -> None:
    """Renderiza el panel principal."""
    stats = obtener_estadisticas_hoy()
    alertas = obtener_alertas_activas()
    df_hoy = tareas_hoy()

    try:
        from modulos import control_pagos as cp

        usar_control = cp.hay_datos()
    except Exception:
        usar_control = False
    if usar_control:
        _hero_control(cp.resumen())
    else:
        _hero(_resumen_pagos(), stats["pagos_pendientes"])
    _kpis(stats, alertas, len(df_hoy))

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
                use_container_width=True,
                hide_index=True,
            )
        datos = obtener_correos_ultimos_dias(7)
        if datos:
            df = pd.DataFrame(datos, columns=["fecha", "total", "categoria"])
            fig = px.bar(df, x="fecha", y="total", color="categoria", height=220,
                         title="Correos clasificados · 7 días")
            fig.update_layout(**PLOTLY_LAYOUT, legend_title_text="")
            st.plotly_chart(fig, use_container_width=True)
    with der:
        st.markdown('<div class="sk-card-h"><h4>Actividad reciente</h4></div>', unsafe_allow_html=True)
        filas = []
        for acc in (stats.get("ultimas_acciones") or [])[:8]:
            marca = "" if acc[3] == "EXITOSO" else ' <span class="sk-venc">· error</span>'
            filas.append(f'<div class="sk-log"><b>{escape(str(acc[0]))}</b> · {escape(str(acc[2] or ""))[:90]}{marca}</div>')
        st.markdown("".join(filas) or '<div class="sk-log">Sin actividad todavía.</div>', unsafe_allow_html=True)
