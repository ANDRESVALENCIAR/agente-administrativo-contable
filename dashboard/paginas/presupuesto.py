"""Página Presupuesto — análisis y proyección."""
from datetime import date

import pandas as pd
import streamlit as st

from config import cfg
from conexiones.claude_client import llamar_claude
from dashboard.utils.db_helper import execute, query_df
from dashboard.utils.reportes import generar_reporte
from modulos.presupuesto import analisis_mensual_presupuesto


def render() -> None:
    """Renderiza módulo presupuesto."""
    st.markdown("## Presupuesto")
    mes = st.number_input("Mes", 1, 12, date.today().month)
    anio = st.number_input("Año", 2020, 2035, date.today().year)

    df = query_df("SELECT * FROM presupuesto_rubros WHERE mes=? AND anio=?", (mes, anio))
    if df.empty:
        st.info("Sin datos. Agregue rubros abajo o cargue Excel.")
    else:
        df["variacion"] = df["ejecutado"] - df["presupuesto"]
        df["variacion_pct"] = (df["variacion"] / df["presupuesto"] * 100).round(1)
        df["semaforo"] = df["variacion_pct"].apply(
            lambda x: "🔴" if abs(x) > 10 else "🟡" if abs(x) > 5 else "🟢"
        )
        st.dataframe(df, use_container_width=True)
        st.bar_chart(df.set_index("rubro")[["presupuesto", "ejecutado"]])

    uploaded = st.file_uploader("Cargar ejecución real (Excel)", type=["xlsx"])
    if uploaded:
        imp = pd.read_excel(uploaded)
        st.dataframe(imp.head(), use_container_width=True)

    with st.form("rubro"):
        rubro = st.text_input("Rubro")
        pres = st.number_input("Presupuesto", min_value=0.0)
        ejec = st.number_input("Ejecutado", min_value=0.0)
        if st.form_submit_button("Guardar rubro"):
            execute(
                """INSERT INTO presupuesto_rubros (rubro,mes,anio,presupuesto,ejecutado) VALUES (?,?,?,?,?)
                   ON CONFLICT(rubro,mes,anio) DO UPDATE SET presupuesto=excluded.presupuesto, ejecutado=excluded.ejecutado""",
                (rubro, mes, anio, pres, ejec),
            )
            st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Análisis mensual con IA"):
            analisis_mensual_presupuesto(int(mes), int(anio))
            st.success("Análisis generado (PDF en documentos/).")
    with col2:
        crec = st.number_input("% crecimiento proyección", value=5.0)
        if st.button("Generar proyección"):
            if not df.empty:
                proy = df.copy()
                proy["presupuesto_propuesto"] = proy["presupuesto"] * (1 + crec / 100)
                st.dataframe(proy[["rubro", "presupuesto_propuesto"]])

    if not df.empty and st.button("Hallazgos IA"):
        hallazgos = llamar_claude(
            f"3-5 hallazgos clave del presupuesto {mes}/{anio} de {cfg.NOMBRE_EMPRESA}:\n{df.to_string()}",
            modulo="presupuesto",
        )
        st.markdown(hallazgos)

    if not df.empty and st.button("Exportar Excel"):
        data, nombre = generar_reporte("presupuesto", df, "excel")
        st.download_button("Descargar", data, nombre)
