"""Página Personal — RRHH completo."""
from datetime import date, timedelta

import streamlit as st

from dashboard.utils.db_helper import execute, query_df
from modulos.personal import (
    calcular_prima,
    calcular_vacaciones,
    elaborar_certificacion,
    elaborar_contrato,
)


def render() -> None:
    """Renderiza módulo personal."""
    st.markdown("## Personal / RRHH")
    tabs = st.tabs(["Novedades", "Contratos", "Certificaciones", "Vacaciones/Primas", "Dotación", "Exámenes", "Candidatos"])

    with tabs[0]:
        with st.form("nov"):
            emp = st.text_input("Empleado")
            tipo = st.selectbox("Tipo", ["Permiso", "Incapacidad", "Vacaciones", "Préstamo", "Ingreso", "Retiro"])
            fi = st.date_input("Desde", date.today())
            ff = st.date_input("Hasta", date.today())
            if st.form_submit_button("Registrar"):
                execute(
                    "INSERT INTO personal_novedades (empleado,tipo,fecha_inicio,fecha_fin) VALUES (?,?,?,?)",
                    (emp, tipo, fi.isoformat(), ff.isoformat()),
                )
                st.rerun()
        st.dataframe(query_df("SELECT * FROM personal_novedades ORDER BY id DESC"), use_container_width=True)

    with tabs[1]:
        df = query_df("SELECT * FROM contratos_rrhh ORDER BY fecha_fin")
        st.dataframe(df, use_container_width=True)
        with st.form("contr"):
            emp = st.text_input("Empleado contrato")
            tipo = st.selectbox("Tipo contrato", ["LABORAL_TERMINO_FIJO", "LABORAL_INDEFINIDO", "PRESTACION_SERVICIOS"])
            if st.form_submit_button("Generar contrato DOCX"):
                path = elaborar_contrato(tipo, {"NOMBRE_EMPLEADO": emp, "CEDULA": "1234567890", "CARGO": "Analista"})
                st.success(f"Generado: {path}")

    with tabs[2]:
        emp = st.text_input("Empleado certificación", key="cert_emp")
        tipo_c = st.selectbox("Tipo cert", ["laboral", "ingresos", "tiempo_servicio", "cargo"])
        if st.button("Generar PDF"):
            path = elaborar_certificacion(emp, tipo_c)
            st.success(f"Certificación: {path}")

    with tabs[3]:
        eid = st.text_input("ID empleado")
        if st.button("Calcular vacaciones"):
            st.json(calcular_vacaciones(eid))
        if st.button("Calcular prima"):
            st.json(calcular_prima(eid, "2026-1"))

    with tabs[4]:
        with st.form("dot"):
            emp = st.text_input("Empleado dotación")
            per = st.text_input("Período", "2026-S1")
            items = st.text_input("Items", "Camisa, Pantalón, Botas")
            if st.form_submit_button("Registrar entrega"):
                execute(
                    "INSERT INTO dotacion_rrhh (empleado,periodo,items,entregado,fecha_entrega) VALUES (?,?,?,1,?)",
                    (emp, per, items, date.today().isoformat()),
                )
                st.rerun()
        st.dataframe(query_df("SELECT * FROM dotacion_rrhh"), use_container_width=True)

    with tabs[5]:
        with st.form("exam"):
            emp = st.text_input("Empleado examen")
            tipo = st.selectbox("Tipo examen", ["Ingreso", "Periódico", "Retiro"])
            fv = st.date_input("Vencimiento", date.today() + timedelta(days=365))
            if st.form_submit_button("Registrar examen"):
                execute(
                    "INSERT INTO examenes_medicos (empleado,tipo,fecha_vencimiento) VALUES (?,?,?)",
                    (emp, tipo, fv.isoformat()),
                )
                st.rerun()
        st.dataframe(query_df("SELECT * FROM examenes_medicos ORDER BY fecha_vencimiento"), use_container_width=True)

    with tabs[6]:
        with st.form("cand"):
            nom = st.text_input("Nombre candidato")
            cargo = st.text_input("Cargo")
            notas = st.text_area("Notas entrevista")
            if st.form_submit_button("Guardar candidato"):
                execute(
                    "INSERT INTO candidatos_rrhh (nombre,cargo,fecha,notas_entrevista) VALUES (?,?,?,?)",
                    (nom, cargo, date.today().isoformat(), notas),
                )
                st.rerun()
        st.dataframe(query_df("SELECT * FROM candidatos_rrhh ORDER BY id DESC"), use_container_width=True)
