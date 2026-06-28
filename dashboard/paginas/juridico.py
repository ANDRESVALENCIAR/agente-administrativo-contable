"""Página Jurídico — contratos, normatividad, políticas."""
from datetime import date

import streamlit as st

from conexiones.claude_client import llamar_claude
from dashboard.utils.db_helper import execute, query_df
from modulos.juridico import generar_contrato, revisar_normatividad


def render() -> None:
    """Renderiza módulo jurídico."""
    st.markdown("## Jurídico")
    t1, t2, t3, t4 = st.tabs(["Contratos", "Revisión IA", "Normatividad", "Políticas y jornadas"])

    with t1:
        tipo = st.selectbox("Tipo", ["LABORAL_TERMINO_FIJO", "LABORAL_INDEFINIDO", "PRESTACION_SERVICIOS", "OTROSI"])
        datos = {
            "NOMBRE_EMPLEADO": st.text_input("Nombre"),
            "CEDULA": st.text_input("Documento"),
            "CARGO": st.text_input("Cargo / Objeto"),
            "SALARIO": st.number_input("Valor", min_value=0),
        }
        if st.button("Generar DOCX"):
            path = generar_contrato(tipo, datos)
            st.success(f"Contrato: {path}")

    with t2:
        archivo = st.text_area("Pegue texto del contrato a revisar")
        if st.button("Analizar riesgos con IA") and archivo:
            riesgos = llamar_claude(
                f"Identifica riesgos legales en este contrato colombiano y sugiere modificaciones:\n{archivo[:4000]}",
                modulo="juridico",
                max_tokens=2000,
            )
            st.markdown(riesgos)

    with t3:
        if st.button("Buscar novedades normativas"):
            revisar_normatividad()
            st.success("Vigilancia ejecutada.")
        with st.form("norm"):
            tipo = st.selectbox("Tipo norma", ["Laboral", "Comercial", "Tributaria"])
            tit = st.text_input("Título")
            resp = st.text_input("Responsable")
            if st.form_submit_button("Agregar norma"):
                execute(
                    "INSERT INTO normatividad (tipo,titulo,fecha_actualizacion,responsable) VALUES (?,?,?,?)",
                    (tipo, tit, date.today().isoformat(), resp),
                )
                st.rerun()
        st.dataframe(query_df("SELECT * FROM normatividad ORDER BY id DESC"), use_container_width=True)

    with t4:
        with st.form("pol"):
            nom = st.text_input("Política")
            ver = st.text_input("Versión", "1.0")
            est = st.selectbox("Estado", ["VIGENTE", "EN REVISIÓN", "DEROGADA"])
            if st.form_submit_button("Guardar política"):
                execute(
                    "INSERT INTO politicas_internas (nombre,version,fecha,estado) VALUES (?,?,?,?)",
                    (nom, ver, date.today().isoformat(), est),
                )
                st.rerun()
        st.dataframe(query_df("SELECT * FROM politicas_internas"), use_container_width=True)
        st.subheader("Jornadas laborales")
        with st.form("jor"):
            emp = st.text_input("Empleado jornada")
            mod = st.selectbox("Modalidad", ["Presencial", "Híbrido", "Remoto"])
            if st.form_submit_button("Asignar"):
                execute("INSERT INTO jornadas_laborales (empleado,modalidad) VALUES (?,?)", (emp, mod))
                st.rerun()
        st.dataframe(query_df("SELECT * FROM jornadas_laborales"), use_container_width=True)
