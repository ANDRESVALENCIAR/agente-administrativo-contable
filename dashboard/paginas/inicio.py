"""Página Inicio — panel principal."""
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from database import marcar_alerta_resuelta, obtener_alertas_activas, obtener_correos_ultimos_dias, obtener_estadisticas_hoy
from utils.calendario_maestro import tareas_hoy, tareas_vencidas


def render() -> None:
    """Renderiza el panel principal."""
    stats = obtener_estadisticas_hoy()
    st.markdown("## Panel principal")
    st.caption(datetime.now().strftime("%A %d de %B de %Y · %H:%M"))

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Alertas activas", stats["alertas_activas"])
    m2.metric("Pagos por aprobar", stats["pagos_pendientes"])
    m3.metric("Correos hoy", stats["correos_hoy"])
    m4.metric("Tareas hoy", len(tareas_hoy()))
    m5.metric("Costo API hoy", f"${stats['costo_hoy']}")

    df_venc = tareas_vencidas()
    if not df_venc.empty:
        st.warning(f"⚠️ {len(df_venc)} tarea(s) del calendario vencida(s). Revise el módulo Calendario.")

    st.divider()
    st.markdown('<p class="section-title">Alertas activas</p>', unsafe_allow_html=True)
    alertas = obtener_alertas_activas()
    if alertas:
        for alerta in alertas[:5]:
            nivel_css = {"CRITICO": "alert-critico", "URGENTE": "alert-urgente", "AVISO": "alert-aviso"}.get(
                alerta[3], "alert-aviso"
            )
            col_a, col_b = st.columns([5, 1])
            with col_a:
                st.markdown(
                    f'<div class="{nivel_css}"><strong>[{alerta[3]}]</strong> {alerta[4]}'
                    f"<br><small>{alerta[5]}</small></div>",
                    unsafe_allow_html=True,
                )
            with col_b:
                if st.button("Resolver", key=f"alerta_{alerta[0]}"):
                    marcar_alerta_resuelta(alerta[0])
                    st.rerun()
    else:
        st.success("Sin alertas activas.")

    df_hoy = tareas_hoy()
    if not df_hoy.empty:
        st.divider()
        st.markdown('<p class="section-title">Tareas del calendario — hoy</p>', unsafe_allow_html=True)
        st.dataframe(
            df_hoy[["titulo", "modulo", "prioridad", "tipo"]].head(8),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.markdown('<p class="section-title">Últimas acciones</p>', unsafe_allow_html=True)
    for acc in stats.get("ultimas_acciones", []) or []:
        icono = "✅" if acc[3] == "EXITOSO" else "❌"
        st.caption(f"{icono} **{acc[0]}** · {acc[2]}")

    datos = obtener_correos_ultimos_dias(7)
    if datos:
        st.divider()
        df = pd.DataFrame(datos, columns=["fecha", "total", "categoria"])
        fig = px.bar(df, x="fecha", y="total", color="categoria", height=200)
        fig.update_layout(plot_bgcolor="#fff", paper_bgcolor="#fff")
        st.plotly_chart(fig, use_container_width=True)
