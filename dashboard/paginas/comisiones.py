"""Página Comisiones — liquidación por asesor."""
import streamlit as st

from config import cfg
from conexiones.claude_client import llamar_claude_simple
from dashboard.utils.db_helper import execute, query_df
from dashboard.utils.reportes import generar_reporte
from modulos.comisiones import liquidar_comisiones_mes


def render() -> None:
    """Renderiza módulo comisiones."""
    st.markdown("## Comisiones")
    df = query_df("SELECT * FROM comisiones_detalle ORDER BY asesor")
    ret = query_df("SELECT * FROM retenciones_config")

    filtro = st.text_input("Filtrar por asesor (vista individual)")
    if filtro:
        df = df[df["asesor"].str.contains(filtro, case=False, na=False)]

    st.dataframe(df, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        uploaded = st.file_uploader("Cargar ventas Excel VIA", type=["xlsx"])
        if uploaded and st.button("Importar ventas"):
            import pandas as pd
            imp = pd.read_excel(uploaded)
            for _, row in imp.iterrows():
                execute(
                    """INSERT INTO comisiones_detalle (asesor,ventas,recaudo,periodo)
                       VALUES (?,?,?,?)""",
                    (row.get("ASESOR", ""), float(row.get("VENTAS", 0)), float(row.get("RECAUDO", 0)), "2026-06"),
                )
            st.rerun()

    with col2:
        if st.button("Liquidar mes actual"):
            from datetime import date
            liquidar_comisiones_mes(date.today().month, date.today().year)
            st.success("Liquidación ejecutada.")

    if not df.empty:
        asesor = st.selectbox("Asesor para revisión", df["asesor"].tolist())
        if st.button("Enviar mensaje de revisión"):
            fila = df[df["asesor"] == asesor].iloc[0]
            msg = llamar_claude_simple(
                f"Resume comisión de {asesor}: neto ${fila.get('comision_neta',0):,.0f}", modulo="comisiones"
            )
            st.info(msg)
        if st.button("Exportar liquidación Excel"):
            data, nombre = generar_reporte("comisiones", df, "excel")
            st.download_button("Descargar", data, nombre)

    st.subheader("Tabla paramétrica retenciones")
    st.dataframe(ret, use_container_width=True)
