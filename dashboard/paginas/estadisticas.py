"""Página Estadísticas y costos API."""
import streamlit as st
import plotly.express as px

from core.registro_libs import LIBRERIAS_POR_MODULO, librerias_disponibles
from dashboard.utils.db_helper import query_df


def render() -> None:
    """Renderiza estadísticas del sistema."""
    st.markdown("## Estadísticas")
    df_tokens = query_df(
        """SELECT fecha,
           tokens_input_haiku + COALESCE(tokens_input_sonnet, 0) as tokens_in,
           tokens_output_haiku + COALESCE(tokens_output_sonnet, 0) as tokens_out,
           costo_estimado_usd as costo FROM uso_tokens_diario ORDER BY fecha DESC LIMIT 30"""
    )
    df_log = query_df(
        """SELECT modulo, SUM(tokens_input) as tin, SUM(tokens_output) as tout, SUM(costo_usd) as costo,
                  COUNT(*) as acciones
           FROM log_acciones GROUP BY modulo ORDER BY costo DESC"""
    )
    df_diario = query_df(
        """SELECT DATE(timestamp) as fecha, COUNT(*) as acciones, SUM(costo_usd) as costo
           FROM log_acciones GROUP BY DATE(timestamp) ORDER BY fecha DESC LIMIT 30"""
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Acciones registradas", int(df_log["acciones"].sum()) if not df_log.empty else 0)
    c2.metric("Costo API total", f"${df_log['costo'].sum():.4f}" if not df_log.empty else "$0")
    cache = query_df("SELECT COUNT(*) as entradas FROM cache_api")
    c3.metric("Consultas en caché API", int(cache.iloc[0]["entradas"]) if not cache.empty else 0)

    if not df_tokens.empty:
        st.markdown("#### Costo API últimos 30 días")
        fig = px.area(df_tokens, x="fecha", y="costo", height=220)
        fig.update_layout(plot_bgcolor="#fff", paper_bgcolor="#fff")
        st.plotly_chart(fig, use_container_width=True)
    elif not df_diario.empty:
        st.markdown("#### Actividad diaria (log_acciones)")
        fig = px.bar(df_diario, x="fecha", y="acciones", height=220)
        st.plotly_chart(fig, use_container_width=True)

    if not df_log.empty:
        st.markdown("#### Costo y acciones por módulo")
        col1, col2 = st.columns(2)
        with col1:
            fig2 = px.pie(df_log, names="modulo", values="costo", title="Costo API por módulo", height=280)
            st.plotly_chart(fig2, use_container_width=True)
        with col2:
            st.dataframe(df_log, use_container_width=True, hide_index=True)

    st.markdown("#### Librerías conectadas al agente")
    estado = librerias_disponibles()
    for modulo, libs in LIBRERIAS_POR_MODULO.items():
        activas = [lib for lib in libs if estado.get(lib, False)]
        st.caption(f"**{modulo.title()}**: {', '.join(activas) or '— sin libs instaladas —'}")
