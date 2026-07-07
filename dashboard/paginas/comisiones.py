"""Página Comisiones — liquidación por asesor."""
from datetime import date

import pandas as pd
import streamlit as st

from config import cfg
from conexiones.claude_client import llamar_claude_simple
from dashboard.utils.db_helper import execute, query_df
from dashboard.utils.reportes import generar_reporte
from modulos.comisiones import _calcular_comision_asesor, liquidar_comisiones_mes


def render() -> None:
    """Renderiza módulo comisiones."""
    st.markdown("## Comisiones")
    periodo = date.today().strftime("%Y-%m")
    df = query_df("SELECT * FROM comisiones_detalle ORDER BY periodo DESC, asesor")
    ret = query_df("SELECT * FROM retenciones_config")

    filtro = st.text_input("Filtrar por asesor (vista individual)")
    if filtro:
        df = df[df["asesor"].str.contains(filtro, case=False, na=False)]

    st.dataframe(df, use_container_width=True, hide_index=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        uploaded = st.file_uploader("Cargar ventas Excel VIA", type=["xlsx"])
        if uploaded and st.button("Importar ventas"):
            imp = pd.read_excel(uploaded)
            for _, row in imp.iterrows():
                ventas = float(row.get("VENTAS_NETAS", row.get("VENTAS", 0)))
                recaudo_pct = float(row.get("RECAUDO_PCT", row.get("RECAUDO", 100)))
                if recaudo_pct > 1:
                    recaudo_pct /= 100
                anticipo = float(row.get("ANTICIPO", 0))
                calc = _calcular_comision_asesor(ventas, recaudo_pct, anticipo)
                execute(
                    """INSERT INTO comisiones_detalle
                       (asesor, ventas, recaudo, anticipos, comision_bruta, retenciones, comision_neta, periodo)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        row.get("ASESOR", ""),
                        ventas,
                        recaudo_pct * 100,
                        anticipo,
                        calc["base_comision"],
                        calc["retencion_fuente"] + calc["retencion_ica"],
                        calc["neto_pagar"],
                        periodo,
                    ),
                )
            st.success("Ventas importadas y comisiones calculadas.")
            st.rerun()

    with col2:
        if st.button("Liquidar mes actual"):
            hoy = date.today()
            liquidar_comisiones_mes(hoy.month, hoy.year)
            st.success("Liquidación del mes actual ejecutada.")

    with col3:
        if st.button("Liquidar mes anterior"):
            from dateutil.relativedelta import relativedelta

            ref = date.today() - relativedelta(months=1)
            liquidar_comisiones_mes(ref.month, ref.year)
            st.success(f"Liquidación {ref.month}/{ref.year} ejecutada.")

    if not df.empty:
        asesor = st.selectbox("Asesor para revisión", df["asesor"].tolist())
        if st.button("Enviar mensaje de revisión"):
            fila = df[df["asesor"] == asesor].iloc[0]
            msg = llamar_claude_simple(
                f"Resume comisión de {asesor}: neto ${fila.get('comision_neta', 0):,.0f}", modulo="comisiones"
            )
            st.info(msg)
        if st.button("Exportar liquidación Excel"):
            data, nombre = generar_reporte("comisiones", df, "excel")
            st.download_button("Descargar", data, nombre)

    st.subheader("Tabla paramétrica retenciones")
    st.dataframe(ret, use_container_width=True)
