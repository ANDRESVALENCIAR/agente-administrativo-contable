"""Página Personal / RRHH — sin IA (pandas, dateutil, openpyxl, reportlab)."""
from datetime import date, timedelta

import streamlit as st

from dashboard.utils.db_helper import execute, query_df
from dashboard.utils.pdf_generator import generar_certificacion
from dashboard.utils.rrhh_helpers import (
    calcular_vacaciones,
    dias_en_proceso,
    dias_habiles,
    exportar_candidatos_excel,
    exportar_dotacion_excel,
    exportar_novedades_excel,
    proxima_dotacion,
    resumen_vacaciones_todos,
)
from database import registrar_documento
from dashboard.paginas.personal_expedientes import render_expedientes_vivo
from modulos.rrhh_expediente import guardar_certificacion_en_expediente

TIPOS_NOVEDAD = ["Permiso", "Vacaciones", "Incapacidad", "Licencia"]
ESTADOS_NOVEDAD = ["PENDIENTE", "APROBADO", "RECHAZADO"]
ITEMS_DOTACION = ["Camisa", "Pantalón", "Zapatos", "Chaqueta", "Overol", "EPP"]
ESTADOS_CANDIDATO = ["RECIBIDO", "EN PROCESO", "ENTREVISTADO", "CONTRATADO", "DESCARTADO"]


def _lista_empleados() -> list[str]:
    df = query_df(
        """SELECT nombre_display AS nombre FROM empleados_carpetas WHERE activo=1
           UNION SELECT nombre FROM empleados WHERE activo=1 ORDER BY 1"""
    )
    return df["nombre"].tolist() if not df.empty else []


def render() -> None:
    """Renderiza módulo Personal / RRHH."""
    st.markdown("## Personal / RRHH")
    empleados = _lista_empleados()
    tabs = st.tabs(
        [
            "📂 Expedientes",
            "Novedades",
            "Vacaciones/Primas",
            "Certificaciones",
            "Dotación",
            "Candidatos",
            "Contratos",
            "Exámenes",
        ]
    )

    with tabs[0]:
        render_expedientes_vivo()

    with tabs[1]:
        with st.form("form_novedad"):
            c1, c2 = st.columns(2)
            with c1:
                emp = st.selectbox("Empleado", empleados or ["— Sin empleados —"], key="nov_emp")
                tipo = st.selectbox("Tipo", TIPOS_NOVEDAD)
                estado = st.selectbox("Estado", ESTADOS_NOVEDAD)
            with c2:
                fi = st.date_input("Fecha inicio", date.today(), key="nov_fi")
                ff = st.date_input("Fecha fin", date.today(), key="nov_ff")
                notas = st.text_area("Notas", height=68)
            if st.form_submit_button("Registrar"):
                if not empleados or emp.startswith("—"):
                    st.error("Seleccione un empleado válido.")
                elif ff < fi:
                    st.error("La fecha fin no puede ser anterior a la fecha inicio.")
                else:
                    dh = dias_habiles(fi, ff)
                    execute(
                        """INSERT INTO novedades_rrhh
                           (empleado, tipo, fecha_inicio, fecha_fin, dias_habiles, estado, notas)
                           VALUES (?,?,?,?,?,?,?)""",
                        (emp, tipo, fi.isoformat(), ff.isoformat(), dh, estado, notas or None),
                    )
                    st.success(f"Novedad registrada ({dh} días hábiles).")
                    st.rerun()

        if st.button("Exportar Excel", key="exp_nov"):
            with st.spinner("Generando Excel…"):
                try:
                    path = exportar_novedades_excel()
                    st.success(f"Archivo guardado: {path}")
                except Exception as e:
                    st.error(str(e))

        st.dataframe(
            query_df(
                """SELECT id, empleado, tipo, fecha_inicio, fecha_fin, dias_habiles, estado, notas
                   FROM novedades_rrhh ORDER BY id DESC"""
            ),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[2]:
        st.caption("Cálculo local: 15 días por año trabajado; disfrutados = novedades tipo Vacaciones.")
        res = resumen_vacaciones_todos()
        if res.empty:
            st.info("No hay empleados activos registrados.")
        else:
            st.dataframe(res, use_container_width=True, hide_index=True)
        st.divider()
        if empleados:
            sel = st.selectbox("Detalle por empleado", empleados, key="vac_sel")
            emp_row = query_df("SELECT fecha_ingreso FROM empleados WHERE nombre=?", (sel,))
            if not emp_row.empty and emp_row.iloc[0]["fecha_ingreso"]:
                fi = emp_row.iloc[0]["fecha_ingreso"]
                if isinstance(fi, str):
                    fi = date.fromisoformat(fi)
                st.json(calcular_vacaciones(sel, fi))

    with tabs[3]:
        df_emp = query_df(
            """SELECT e.nombre, e.cargo, e.fecha_ingreso, e.salario, e.tipo_contrato, e.cedula,
                      c.nombre_carpeta
               FROM empleados e
               LEFT JOIN empleados_carpetas c ON UPPER(e.nombre)=UPPER(c.nombre_carpeta)
               WHERE e.activo=1"""
        )
        if df_emp.empty:
            df_emp = query_df(
                """SELECT nombre_carpeta AS nombre, NULL AS cargo, NULL AS fecha_ingreso,
                          NULL AS salario, NULL AS tipo_contrato, NULL AS cedula, nombre_carpeta
                   FROM empleados_carpetas WHERE activo=1"""
            )
        if not df_emp.empty:
            nombres = df_emp["nombre"].tolist()
            idx = st.selectbox("Empleado", range(len(nombres)), format_func=lambda i: nombres[i], key="cert_idx")
            row = df_emp.iloc[idx]
            nombre = row["nombre"]
            nombre_carpeta = row.get("nombre_carpeta") or nombre
            cargo = st.text_input("Cargo", value=row.get("cargo") or "")
            fecha_ing = row["fecha_ingreso"]
            if isinstance(fecha_ing, str):
                fecha_ing = date.fromisoformat(fecha_ing)
            fecha_ingreso = st.date_input("Fecha ingreso", fecha_ing or date.today())
            salario = st.number_input("Salario mensual", min_value=0.0, value=float(row.get("salario") or 0))
            tipo_contrato = st.text_input("Tipo contrato", value=row.get("tipo_contrato") or "Indefinido")
            cedula = st.text_input("Cédula", value=row.get("cedula") or "")
        else:
            nombre = st.text_input("Nombre empleado")
            cargo = st.text_input("Cargo")
            fecha_ingreso = st.date_input("Fecha ingreso", date.today())
            salario = st.number_input("Salario mensual", min_value=0.0, value=0.0)
            tipo_contrato = st.text_input("Tipo contrato", "Indefinido")
            cedula = st.text_input("Cédula")

        st.caption(
            "El PDF se guarda en el proyecto y se copia automáticamente a la carpeta OneDrive del empleado."
        )

        if st.button("Generar Certificación", key="btn_cert"):
            if not nombre or not cargo:
                st.error("Nombre y cargo son obligatorios.")
            else:
                with st.spinner("Generando PDF y copiando al expediente…"):
                    try:
                        path = generar_certificacion(
                            nombre, cargo, fecha_ingreso, salario, tipo_contrato, cedula
                        )
                        path_expediente = guardar_certificacion_en_expediente(nombre_carpeta, path)
                        registrar_documento(
                            "certificacion_laboral",
                            path.split("/")[-1].split("\\")[-1],
                            path,
                            "personal",
                            f"Certificación laboral — {nombre}",
                        )
                        st.success(
                            f"**Certificación generada**\n\n"
                            f"- Copia proyecto: `{path}`\n"
                            f"- Expediente empleado: `{path_expediente}`"
                        )
                    except Exception as e:
                        st.error(f"Error al generar PDF: {e}")

    with tabs[4]:
        with st.form("form_dotacion"):
            c1, c2 = st.columns(2)
            with c1:
                emp_d = st.selectbox("Empleado", empleados or ["—"], key="dot_emp")
                item = st.selectbox("Ítem", ITEMS_DOTACION)
            with c2:
                talla = st.text_input("Talla")
                f_ent = st.date_input("Fecha entrega", date.today())
            if st.form_submit_button("Registrar entrega"):
                if not empleados:
                    st.error("No hay empleados registrados.")
                else:
                    prox = proxima_dotacion(f_ent)
                    execute(
                        """INSERT INTO dotacion (empleado, item, talla, fecha_entrega, proxima_entrega, entregado)
                           VALUES (?,?,?,?,?,1)""",
                        (emp_d, item, talla or None, f_ent.isoformat(), prox.isoformat()),
                    )
                    st.success(f"Entrega registrada. Próxima entrega: {prox.isoformat()}")
                    st.rerun()

        if st.button("Exportar Excel", key="exp_dot"):
            with st.spinner("Generando Excel…"):
                try:
                    path = exportar_dotacion_excel()
                    st.success(f"Archivo guardado: {path}")
                except Exception as e:
                    st.error(str(e))

        df_dot = query_df(
            """SELECT id, empleado, item, talla, fecha_entrega, proxima_entrega, entregado
               FROM dotacion ORDER BY proxima_entrega"""
        )
        if not df_dot.empty:
            limite = date.today() + timedelta(days=15)
            df_dot["alerta"] = df_dot["proxima_entrega"].apply(
                lambda x: "⚠ ≤15 días"
                if x and date.fromisoformat(str(x)[:10]) <= limite
                else ""
            )
        st.dataframe(df_dot, use_container_width=True, hide_index=True)

    with tabs[5]:
        with st.form("form_candidato"):
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nombre")
                cargo_c = st.text_input("Cargo")
            with c2:
                f_app = st.date_input("Fecha aplicación", date.today())
                notas_c = st.text_area("Notas", height=68)
            if st.form_submit_button("Guardar candidato"):
                if not nom:
                    st.error("El nombre es obligatorio.")
                else:
                    dias = dias_en_proceso(f_app)
                    execute(
                        """INSERT INTO candidatos (nombre, cargo, fecha_aplicacion, estado, notas, dias_proceso)
                           VALUES (?,?,?,?,?,?)""",
                        (nom, cargo_c or None, f_app.isoformat(), "RECIBIDO", notas_c or None, dias),
                    )
                    st.success("Candidato registrado.")
                    st.rerun()

        if st.button("Exportar Excel", key="exp_cand"):
            with st.spinner("Generando Excel…"):
                try:
                    path = exportar_candidatos_excel()
                    st.success(f"Archivo guardado: {path}")
                except Exception as e:
                    st.error(str(e))

        df_c = query_df(
            """SELECT id, nombre, cargo, fecha_aplicacion, estado, dias_proceso, notas
               FROM candidatos ORDER BY id DESC"""
        )
        if not df_c.empty:
            st.dataframe(df_c, use_container_width=True, hide_index=True)
            st.markdown("**Cambiar estado**")
            for _, row in df_c.iterrows():
                cid = int(row["id"])
                cols = st.columns([3, 2, 1])
                cols[0].write(f"{row['nombre']} — {row.get('cargo') or '—'}")
                cols[1].write(f"Actual: **{row['estado']}** ({row['dias_proceso']} días)")
                nuevo = cols[2].selectbox(
                    "Estado",
                    ESTADOS_CANDIDATO,
                    key=f"est_cand_{cid}",
                    label_visibility="collapsed",
                )
                if cols[2].button("Actualizar", key=f"upd_cand_{cid}"):
                    dias = dias_en_proceso(date.fromisoformat(str(row["fecha_aplicacion"])[:10]))
                    execute(
                        "UPDATE candidatos SET estado=?, dias_proceso=? WHERE id=?",
                        (nuevo, dias, cid),
                    )
                    st.rerun()
        else:
            st.info("Sin candidatos registrados.")

    with tabs[6]:
        with st.form("form_contrato"):
            c1, c2 = st.columns(2)
            with c1:
                emp_c = st.selectbox("Empleado", empleados or ["—"], key="cont_emp")
                tipo_c = st.selectbox("Tipo contrato", ["Indefinido", "Fijo", "Obra o labor", "Aprendizaje"])
            with c2:
                fi_c = st.date_input("Fecha inicio", date.today(), key="cont_fi")
                ff_c = st.date_input("Fecha fin", date.today() + timedelta(days=365), key="cont_ff")
            if st.form_submit_button("Registrar contrato"):
                if empleados and not emp_c.startswith("—"):
                    execute(
                        """INSERT INTO contratos_rrhh (empleado, tipo, fecha_inicio, fecha_fin, estado)
                           VALUES (?,?,?,?, 'VIGENTE')""",
                        (emp_c, tipo_c, fi_c.isoformat(), ff_c.isoformat()),
                    )
                    st.success("Contrato registrado.")
                    st.rerun()
                else:
                    st.error("Seleccione un empleado válido.")
        st.dataframe(
            query_df("SELECT * FROM contratos_rrhh ORDER BY fecha_fin"),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[7]:
        with st.form("form_examen"):
            emp_e = st.text_input("Empleado examen")
            tipo_e = st.selectbox("Tipo examen", ["Ingreso", "Periódico", "Retiro"])
            fv = st.date_input("Vencimiento", date.today() + timedelta(days=365))
            if st.form_submit_button("Registrar examen"):
                execute(
                    "INSERT INTO examenes_medicos (empleado, tipo, fecha_vencimiento) VALUES (?,?,?)",
                    (emp_e, tipo_e, fv.isoformat()),
                )
                st.rerun()
        st.dataframe(
            query_df("SELECT * FROM examenes_medicos ORDER BY fecha_vencimiento"),
            use_container_width=True,
            hide_index=True,
        )
