"""Pestaña Archivo General Fénix — importar, consultar, editar y exportar."""
from __future__ import annotations

import json
from datetime import date

import streamlit as st

from dashboard.utils.db_helper import query_df
from dashboard.utils.rrhh_helpers import exportar_archivo_general_fenix, parse_fecha
from modulos.personal_fenix import (
    guardar_empleado_manual,
    importar_archivo_general,
    obtener_estado_importacion,
    ruta_archivo_general,
    vincular_carpetas,
)

TIPOS_PLANTILLA = ["nomina_activo", "prestacion_servicios", "retirado"]
ETIQUETAS_TIPO = {
    "nomina_activo": "Nómina activa",
    "prestacion_servicios": "Prestación de servicios",
    "retirado": "Retirado",
}


def render() -> None:
    st.markdown("## Archivo General Personal Fénix 2026")
    estado = obtener_estado_importacion()
    sync = estado.get("sync") or {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Activos", estado.get("activos", 0))
    c2.metric("Retirados", estado.get("retirados", 0))
    c3.metric("Vinculados carpetas", sync.get("vinculados", 0))
    ultima = str(sync.get("ultima_importacion") or "—")[:19]
    c4.metric("Última importación", ultima)

    st.caption(f"Archivo: `{ruta_archivo_general()}`")

    with st.expander("Importar / sincronizar", expanded=not estado.get("activos")):
        ruta_custom = st.text_input(
            "Ruta del Excel (opcional)",
            value=str(ruta_archivo_general()),
            key="fenix_ruta",
        )
        up = st.file_uploader("O subir Excel manualmente", type=["xlsx"], key="fenix_upload")

        col_a, col_b, col_c = st.columns(3)
        if col_a.button("📥 Importar desde archivo", key="btn_import_fenix", type="primary"):
            with st.spinner("Importando ARCHIVO GENERAL…"):
                try:
                    if up:
                        import tempfile
                        from pathlib import Path
                        tmp = Path(tempfile.gettempdir()) / "archivo_fenix_upload.xlsx"
                        tmp.write_bytes(up.getvalue())
                        r = importar_archivo_general(tmp)
                    else:
                        r = importar_archivo_general(ruta_custom)
                    st.success(
                        f"Importado: {r['empleados']} empleados · {r['novedades']} novedades · "
                        f"{r['vacaciones']} vacaciones · {r['cumpleanos']} cumpleaños · "
                        f"{r['contratos_fijos']} contratos · {r['vinculados']} carpetas vinculadas"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        if col_b.button("🔗 Vincular carpetas", key="btn_vinc_fenix"):
            r = vincular_carpetas()
            st.success(f"Vinculados: {r['vinculados']} · Empleados sync: {r['empleados_sync']}")
            st.rerun()

        if col_c.button("📊 Exportar Excel completo", key="btn_exp_fenix"):
            with st.spinner("Generando Excel…"):
                try:
                    path = exportar_archivo_general_fenix()
                    st.success(f"Descargado en: `{path}`")
                except Exception as e:
                    st.error(str(e))

    tabs = st.tabs(
        ["Personal activo", "Prestación servicios", "Retirados", "Novedades", "Vacaciones", "Cumpleaños", "Contratos fijos", "Alta manual"]
    )

    with tabs[0]:
        _tabla_empleados("nomina_activo", activo=1)

    with tabs[1]:
        _tabla_empleados("prestacion_servicios", activo=1)

    with tabs[2]:
        _tabla_empleados("retirado", activo=0)

    with tabs[3]:
        df = query_df(
            """SELECT nombre_completo, cedula, fecha_ingreso, pendiente_dotacion,
                      examenes_periodicos, meses_json FROM novedades_fenix ORDER BY nombre_completo"""
        )
        if df.empty:
            st.info("Sin novedades. Importe el archivo general.")
        else:
            for _, row in df.iterrows():
                try:
                    meses = json.loads(row["meses_json"] or "{}")
                except json.JSONDecodeError:
                    meses = {}
                meses_txt = ", ".join(f"{k}: {v}" for k, v in meses.items() if v) or "—"
                st.markdown(f"**{row['nombre_completo']}** — Dotación: {row['pendiente_dotacion'] or '—'}")
                st.caption(f"Exámenes: {row['examenes_periodicos'] or '—'} · Meses: {meses_txt}")

    with tabs[4]:
        st.dataframe(
            query_df(
                """SELECT nombre_completo, hoja_origen, dias_pendientes, dias_tomar,
                          dias_pendientes_2025, fecha_regreso, observaciones
                   FROM vacaciones_fenix ORDER BY nombre_completo"""
            ),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[5]:
        st.dataframe(
            query_df("SELECT nombre, dia, mes FROM cumpleanos_fenix ORDER BY mes, dia"),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[6]:
        st.dataframe(
            query_df(
                """SELECT nombre_completo, cedula, cargo, fecha_inicio, termino,
                          vencimiento_contrato, fecha_preaviso FROM contratos_fijos_fenix
                   ORDER BY vencimiento_contrato"""
            ),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[7]:
        _form_alta_manual()


def _tabla_empleados(tipo: str, activo: int) -> None:
    df = query_df(
        """SELECT id, nombre_completo, cedula, cargo, departamento, fecha_ingreso,
                  telefono, email_corporativo, salario_ibc, tipo_contrato,
                  carpeta_vinculada, origen
           FROM empleados_fenix WHERE tipo_plantilla=? AND activo=?
           ORDER BY nombre_completo""",
        (tipo, activo),
    )
    if df.empty:
        st.info(f"Sin registros de {ETIQUETAS_TIPO.get(tipo, tipo)}. Use Importar.")
        return

    st.dataframe(df, use_container_width=True, hide_index=True)

    ids = df["id"].tolist()
    nombres = df["nombre_completo"].tolist()
    sel = st.selectbox(
        "Ver / editar empleado",
        range(len(ids)),
        format_func=lambda i: nombres[i],
        key=f"sel_fenix_{tipo}",
    )
    emp_id = int(ids[sel])
    row = query_df("SELECT * FROM empleados_fenix WHERE id=?", (emp_id,)).iloc[0]

    with st.form(f"edit_fenix_{emp_id}"):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre completo", value=row["nombre_completo"] or "")
            cedula = st.text_input("Cédula", value=row["cedula"] or "")
            cargo = st.text_input("Cargo", value=row["cargo"] or "")
            dept = st.text_input("Departamento", value=row["departamento"] or "")
            tel = st.text_input("Teléfono", value=row["telefono"] or "")
        with c2:
            email = st.text_input("Correo corporativo", value=row["email_corporativo"] or "")
            sal = st.text_input("Salario / IBC", value=str(row["salario_ibc"] or ""))
            tc = st.text_input("Tipo contrato", value=row["tipo_contrato"] or "")
            fi = parse_fecha(row["fecha_ingreso"], date.today())
            fecha_ing = st.date_input("Fecha ingreso", fi)
            obs = st.text_area("Observaciones", value=row["observaciones"] or "", height=80)

        if st.form_submit_button("Guardar cambios en memoria"):
            guardar_empleado_manual({
                "id": emp_id,
                "nombre_completo": nombre,
                "cedula": cedula,
                "tipo_plantilla": tipo,
                "activo": activo,
                "cargo": cargo,
                "departamento": dept,
                "fecha_ingreso": fecha_ing.isoformat(),
                "telefono": tel,
                "email_corporativo": email,
                "salario_ibc": sal,
                "tipo_contrato": tc,
                "observaciones": obs,
            })
            st.success("Guardado en base de datos (memoria persistente).")
            st.rerun()

    with st.expander("Datos completos del Excel"):
        try:
            datos = json.loads(row["datos_json"] or "{}")
            st.json(datos)
        except json.JSONDecodeError:
            st.write(row["datos_json"])


def _form_alta_manual() -> None:
    with st.form("alta_manual_fenix"):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre completo *")
            cedula = st.text_input("Cédula")
            cargo = st.text_input("Cargo")
            tipo = st.selectbox("Tipo plantilla", TIPOS_PLANTILLA)
        with c2:
            fecha_ing = st.date_input("Fecha ingreso", date.today())
            tel = st.text_input("Teléfono")
            email = st.text_input("Correo corporativo")
            sal = st.text_input("Salario / IBC")
        obs = st.text_area("Observaciones")
        if st.form_submit_button("Registrar empleado"):
            if not nombre.strip():
                st.error("El nombre es obligatorio.")
            else:
                guardar_empleado_manual({
                    "nombre_completo": nombre.strip(),
                    "cedula": cedula,
                    "tipo_plantilla": tipo,
                    "activo": 0 if tipo == "retirado" else 1,
                    "cargo": cargo,
                    "fecha_ingreso": fecha_ing.isoformat(),
                    "telefono": tel,
                    "email_corporativo": email,
                    "salario_ibc": sal,
                    "observaciones": obs,
                })
                st.success("Empleado registrado manualmente.")
                st.rerun()
