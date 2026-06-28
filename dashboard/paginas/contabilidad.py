"""Página Contabilidad — informe gerencia y conciliación."""
from datetime import date

import pandas as pd
import streamlit as st

from config import cfg, en_modo_demo
from conexiones.claude_client import llamar_claude
from dashboard.utils.db_helper import query_df
from dashboard.utils.reportes import generar_reporte
from modulos.contable import generar_informe_gerencia, verificar_conciliacion_bancaria


def render() -> None:
    """Renderiza módulo contable."""
    st.markdown("## Contabilidad")
    tab1, tab2 = st.tabs(["Informe Gerencia", "Conciliación Bancaria"])

    with tab1:
        st.subheader("Informe de Gerencia")
        archivo = st.file_uploader("Cargar EEFF (Excel/CSV)", type=["xlsx", "csv"], key="eeff")
        anio = st.number_input("Año", value=date.today().year, step=1)
        if archivo:
            df = pd.read_csv(archivo) if archivo.name.endswith(".csv") else pd.read_excel(archivo)
            st.dataframe(df.head(20), use_container_width=True)
            if st.button("Generar informe con IA"):
                with st.spinner("Analizando..."):
                    informe = llamar_claude(
                        f"Genera informe gerencia {anio} para {cfg.NOMBRE_EMPRESA} con estos datos:\n{df.head(15).to_string()}",
                        modulo="contable",
                    )
                st.markdown(informe)
        if st.button("Generar informe anual (Word)"):
            path = generar_informe_gerencia(int(anio))
            st.success(f"Informe generado: {path}" if path else "Error al generar.")

    with tab2:
        st.subheader("Conciliación Bancaria")
        df = query_df("SELECT * FROM conciliacion_bancaria ORDER BY fecha DESC")
        if df.empty:
            st.info("Sin datos de conciliación. Modo demo: agregue saldos manualmente.")
            with st.form("conc_form"):
                fuente = st.text_input("Fuente", "Banco")
                saldo = st.number_input("Saldo", min_value=0.0, step=1000.0)
                if st.form_submit_button("Agregar"):
                    from dashboard.utils.db_helper import execute
                    execute(
                        "INSERT OR REPLACE INTO conciliacion_bancaria (fuente,saldo,fecha) VALUES (?,?,?)",
                        (fuente, saldo, date.today().isoformat()),
                    )
                    st.rerun()
        else:
            st.dataframe(df, use_container_width=True)
            if len(df) >= 2:
                diff = abs(df.iloc[0]["saldo"] - df.iloc[1]["saldo"])
                if diff > 0:
                    st.error(f"⚠️ Diferencia detectada: ${diff:,.0f}")
                else:
                    st.success("✅ Saldos cuadrados.")
            if st.button("Ejecutar conciliación automática"):
                verificar_conciliacion_bancaria()
                st.success("Conciliación enviada a contabilidad." + (" (demo)" if en_modo_demo() else ""))
        if not df.empty and st.button("Exportar conciliación Excel"):
            data, nombre = generar_reporte("conciliacion", df, "excel")
            st.download_button("Descargar", data, nombre)
