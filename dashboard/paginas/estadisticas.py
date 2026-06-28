"""Página Estadísticas y costos API."""
import streamlit as st
import plotly.express as px

from dashboard.utils.db_helper import query_df


def render() -> None:
    """Renderiza estadísticas del sistema."""
    st.markdown("## Estadísticas")
    df_tokens = query_df(
        """SELECT fecha,
           tokens_input_sonnet + tokens_input_haiku as tokens_in,
           tokens_output_sonnet + tokens_output_haiku as tokens_out,
           costo_estimado_usd as costo FROM uso_tokens_diario ORDER BY fecha DESC LIMIT 30"""
    )
    df_log = query_df(
        """SELECT modulo, SUM(tokens_input) as tin, SUM(tokens_output) as tout, SUM(costo_usd) as costo
           FROM log_acciones GROUP BY modulo ORDER BY costo DESC"""
    )

    if not df_tokens.empty:
        st.markdown("#### Costo API últimos 30 días")
        fig = px.area(df_tokens, x="fecha", y="costo", height=200)
        fig.update_layout(plot_bgcolor="#fff", paper_bgcolor="#fff")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Costos API desde log_acciones:")
        df_log = query_df(
            """SELECT DATE(timestamp) as fecha, SUM(costo_usd) as costo
               FROM log_acciones GROUP BY DATE(timestamp) ORDER BY fecha DESC LIMIT 30"""
        )
        if not df_log.empty:
            st.line_chart(df_log.set_index("fecha"))

    if not df_log.empty:
        st.markdown("#### Tokens por módulo")
        st.dataframe(df_log, use_container_width=True)

    cache = query_df("SELECT COUNT(*) as entradas FROM cache_api")
    st.metric("Consultas en caché API", int(cache.iloc[0]["entradas"]) if not cache.empty else 0)
