"""Pestaña Contratos Activos — informe empleado por empleado estilo Excel."""
from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.utils.db_helper import query_df
from dashboard.utils.rrhh_helpers import exportar_contratos_activos_excel, parse_fecha
from modulos.contratos_activos import (
    COLUMNAS_INFORME,
    guardar_contrato_activo,
    obtener_contrato,
    sincronizar_contratos_activos,
)

CSS_CONTRATOS = """
<style>
.ca-header {
    background: #4a4a4a; color: #fff; font-weight: 700; font-size: 11px;
    padding: 6px 8px; text-align: center; border: 1px solid #333;
    white-space: nowrap;
}
.ca-cell {
    background: #fff9c4; color: #000; font-size: 11px;
    padding: 6px 8px; border: 1px solid #ccc; min-height: 28px;
}
.ca-cell-ok { background: #c8e6c9 !important; }
.ca-cell-no { background: #ffcdd2 !important; color: #b71c1c; font-weight: 600; }
.ca-cell-pend { background: #fff59d !important; color: #e65100; }
.ca-row-label {
    background: #e8e8e8; font-weight: 600; font-size: 11px;
    padding: 6px 8px; border: 1px solid #ccc; min-width: 140px;
}
.ca-empleado-titulo {
    background: #2c3e50; color: #fff; padding: 10px 14px;
    font-size: 15px; font-weight: 700; border-radius: 4px 4px 0 0;
    margin-top: 12px;
}
.ca-scroll { overflow-x: auto; width: 100%; }
.ca-grid { display: grid; gap: 0; min-width: max-content; }
</style>
"""


def _fmt(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    s = str(val)
    return s[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", s) else s


def _clase_doc(val: str) -> str:
    v = (val or "").upper()
    if v == "SI":
        return "ca-cell-ok"
    if v == "PENDIENTE":
        return "ca-cell-pend"
    if v in ("NO", ""):
        return "ca-cell-no"
    return "ca-cell"


def _render_ficha_empleado(row: dict) -> None:
    """Informe horizontal empleado por empleado (como el Excel de referencia)."""
    nombre = row.get("nombre_completo", "—")
    st.markdown(f'<div class="ca-empleado-titulo">{nombre}</div>', unsafe_allow_html=True)

    grupos = [
        ("DATOS PERSONALES Y CONTRATO", [
            "nombre_completo", "cedula", "fecha_ingreso", "cargo", "sueldo_bruto",
            "area", "modalidad_trabajo", "tipo_contrato", "fecha_inicio", "fecha_fin", "estado",
        ]),
        ("SEGUROS Y CUMPLIMIENTO", ["sctr", "vida_ley", "examen_medico", "induccion", "epp"]),
        ("DOCUMENTACIÓN EN CARPETA", [
            "doc_foto", "doc_cv", "doc_antecedentes", "doc_contrato", "doc_dni",
            "doc_recibo_servicios", "doc_croquis", "doc_declaracion", "doc_certificados",
        ]),
    ]
    labels = {k: v for k, v in COLUMNAS_INFORME}

    html = '<div class="ca-scroll"><table style="width:100%;border-collapse:collapse;margin-bottom:8px;">'
    for titulo, campos in grupos:
        html += f'<tr><td colspan="{len(campos)}" style="background:#5d6d7e;color:#fff;padding:4px 8px;font-size:11px;font-weight:700;">{titulo}</td></tr><tr>'
        for c in campos:
            html += f'<td class="ca-header">{labels.get(c, c)}</td>'
        html += "</tr><tr>"
        for c in campos:
            val = _fmt(row.get(c))
            clase = _clase_doc(val) if c.startswith("doc_") or c in ("sctr", "vida_ley", "examen_medico", "induccion", "epp") else "ca-cell"
            html += f'<td class="{clase}">{val}</td>'
        html += "</tr>"
    html += "</table></div>"
    st.markdown(html, unsafe_allow_html=True)

    if row.get("observaciones"):
        st.caption(f"Observaciones: {row['observaciones']}")


def _render_tabla_resumen(df: pd.DataFrame) -> None:
    """Vista resumen tipo planilla — todas las columnas en una tabla."""
    if df.empty:
        return
    cols_show = [k for k, _ in COLUMNAS_INFORME if k in df.columns]
    labels = [v for k, v in COLUMNAS_INFORME if k in df.columns]
    vista = df[cols_show].copy()
    vista.columns = labels

    def _color(col):
        if col.name in ("FOTO", "CV", "ANTECEDENTES", "CONTRATO FIRMADO", "DNI ESCANEADO",
                        "RECIBO LUZ/AGUA", "CROQUIS", "DECLARACIÓN JURADA", "CERTIFICADOS",
                        "SCTR", "VIDA LEY", "EXAMEN MÉDICO", "INDUCCIÓN", "EPP"):
            return vista[col.name].apply(
                lambda x: "background-color:#ffcdd2" if str(x).upper() == "NO"
                else "background-color:#c8e6c9" if str(x).upper() == "SI"
                else "background-color:#fff59d" if str(x).upper() == "PENDIENTE"
                else "background-color:#fff9c4"
            )
        return ["background-color:#fff9c4"] * len(vista)

    styled = vista.style.apply(_color, axis=0)
    st.dataframe(styled, use_container_width=True, hide_index=True, height=400)


def render() -> None:
    st.markdown(CSS_CONTRATOS, unsafe_allow_html=True)
    st.markdown("## Contratos Activos")
    st.caption(
        "Informe de contratos y documentación por empleado. "
        "Se alimenta de las carpetas PERSONAL ACTIVO, Archivo General Fénix y edición manual."
    )

    c1, c2, c3, c4 = st.columns(4)
    df_all = query_df("SELECT * FROM contratos_activos ORDER BY nombre_completo")
    c1.metric("Empleados", len(df_all))
    docs_ok = 0
    if not df_all.empty:
        doc_cols = [c for c in df_all.columns if c.startswith("doc_") and not c.endswith("_ruta")]
        docs_ok = int((df_all[doc_cols] == "SI").sum().sum())
    c2.metric("Documentos OK", docs_ok)
    c3.metric("Faltantes (NO)", int((df_all.filter(like="doc_").eq("NO")).sum().sum()) if not df_all.empty else 0)
    c4.metric("Origen sync", int((df_all["origen"] == "sync").sum()) if not df_all.empty and "origen" in df_all.columns else 0)

    col_a, col_b, col_c = st.columns(3)
    if col_a.button("🔄 Sincronizar carpetas + Fénix", key="sync_contratos", type="primary"):
        with st.spinner("Sincronizando…"):
            try:
                from modulos.carpetas_rrhh import escanear_carpetas_personal
                escanear_carpetas_personal()
                r = sincronizar_contratos_activos()
                st.success(f"Sincronizado: {r['creados']} nuevos · {r['actualizados']} actualizados")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    if col_b.button("📊 Exportar Excel", key="exp_contratos"):
        try:
            path = exportar_contratos_activos_excel()
            st.success(f"Guardado: `{path}`")
        except Exception as e:
            st.error(str(e))

    vista = col_c.radio("Vista", ["Empleado por empleado", "Planilla completa"], horizontal=True, key="vista_ca")

    if df_all.empty:
        st.warning("No hay contratos activos. Pulse **Sincronizar carpetas + Fénix** o registre manualmente.")
        _form_nuevo()
        return

    if vista == "Planilla completa":
        st.subheader("Planilla — Contratos Activos")
        _render_tabla_resumen(df_all)
        st.divider()

    st.subheader("Detalle empleado por empleado")
    ids = df_all["id"].tolist()
    nombres = df_all["nombre_completo"].tolist()

    idx_key = "ca_idx"
    if idx_key not in st.session_state:
        st.session_state[idx_key] = 0
    st.session_state[idx_key] = max(0, min(st.session_state[idx_key], len(ids) - 1))

    busqueda = st.text_input(
        "🔍 Buscar empleado",
        key="ca_buscar",
        placeholder="Escriba nombre, cédula o cargo…",
    )
    q = busqueda.strip().upper()
    if q:
        indices_ok = [
            i for i in range(len(ids))
            if q in nombres[i].upper()
            or q in str(df_all.iloc[i].get("cedula") or "").upper()
            or q in str(df_all.iloc[i].get("cargo") or "").upper()
        ]
        if not indices_ok:
            st.warning(f"No se encontró ningún empleado con «{busqueda}».")
            return
        if st.session_state[idx_key] not in indices_ok:
            st.session_state[idx_key] = indices_ok[0]
    else:
        indices_ok = list(range(len(ids)))

    pos_actual = (
        indices_ok.index(st.session_state[idx_key])
        if st.session_state[idx_key] in indices_ok
        else 0
    )

    nav1, nav2, nav3 = st.columns([1, 4, 1])
    if nav1.button("◀ Anterior", key="ca_prev", disabled=pos_actual <= 0):
        st.session_state[idx_key] = indices_ok[pos_actual - 1]
        st.rerun()
    if nav3.button("Siguiente ▶", key="ca_next", disabled=pos_actual >= len(indices_ok) - 1):
        st.session_state[idx_key] = indices_ok[pos_actual + 1]
        st.rerun()

    with nav2:
        sel_pos = st.selectbox(
            "Seleccionar empleado",
            range(len(indices_ok)),
            index=pos_actual,
            format_func=lambda j: f"{indices_ok[j] + 1}/{len(ids)} — {nombres[indices_ok[j]]}",
        )
        st.session_state[idx_key] = indices_ok[sel_pos]

    reg_id = int(ids[st.session_state[idx_key]])
    row = obtener_contrato(reg_id) or {}
    _render_ficha_empleado(row)

    rutas_doc = {k: v for k, v in row.items() if k.endswith("_ruta") and v}
    with st.expander("Abrir documentos de la carpeta"):
        for campo, ruta in sorted(rutas_doc.items()):
            if ruta and Path(ruta).is_file():
                label = campo.replace("doc_", "").replace("_ruta", "").upper()
                if st.button(f"📂 Abrir {label}", key=f"open_{reg_id}_{campo}"):
                    if os.name == "nt":
                        os.startfile(ruta)  # noqa: S606

    with st.expander("✏️ Editar manualmente", expanded=False):
        _form_editar(row)

    st.divider()
    with st.expander("➕ Registrar empleado manual"):
        _form_nuevo()


def _campos_form(row: dict | None = None) -> dict:
    row = row or {}
    c1, c2, c3 = st.columns(3)
    with c1:
        nombre = st.text_input("Nombres y apellidos *", value=row.get("nombre_completo") or "")
        cedula = st.text_input("DNI / Cédula", value=row.get("cedula") or "")
        fi = parse_fecha(row.get("fecha_ingreso"), date.today())
        fecha_ing = st.date_input("Fecha ingreso", fi)
        cargo = st.text_input("Cargo", value=row.get("cargo") or "")
        sueldo = st.text_input("Sueldo bruto", value=str(row.get("sueldo_bruto") or ""))
    with c2:
        area = st.text_input("Área", value=row.get("area") or "")
        modalidad = st.text_input("Modalidad trabajo", value=row.get("modalidad_trabajo") or "")
        tipo_c = st.text_input("Tipo contrato", value=row.get("tipo_contrato") or "")
        f_ini = parse_fecha(row.get("fecha_inicio"), date.today())
        fecha_ini = st.date_input("Fecha inicio", f_ini)
        ff = parse_fecha(row.get("fecha_fin"))
        fecha_fin = st.date_input("Fecha fin", ff or date.today(), disabled=ff is None)
        estado = st.selectbox("Estado", ["ACTIVO", "INACTIVO"], index=0 if row.get("estado") != "INACTIVO" else 1)
    with c3:
        sctr = st.selectbox("SCTR", ["SI", "NO", "PENDIENTE"], index=["SI", "NO", "PENDIENTE"].index(row.get("sctr") or "NO") if (row.get("sctr") or "NO") in ["SI", "NO", "PENDIENTE"] else 1)
        vida = st.selectbox("Vida ley", ["SI", "NO", "PENDIENTE"], index=1)
        examen = st.selectbox("Examen médico", ["SI", "NO", "PENDIENTE"],
                              index=["SI", "NO", "PENDIENTE"].index(row.get("examen_medico") or "NO") if (row.get("examen_medico") or "NO") in ["SI", "NO", "PENDIENTE"] else 1)
        induccion = st.selectbox("Inducción", ["SI", "NO", "PENDIENTE"], index=1)
        epp = st.selectbox("EPP", ["SI", "NO", "PENDIENTE"],
                           index=["SI", "NO", "PENDIENTE"].index(row.get("epp") or "NO") if (row.get("epp") or "NO") in ["SI", "NO", "PENDIENTE"] else 1)

    st.markdown("**Documentación**")
    d1, d2, d3 = st.columns(3)
    opts = ["SI", "NO", "PENDIENTE"]
    with d1:
        doc_foto = st.selectbox("Foto", opts, index=opts.index(row.get("doc_foto") or "NO") if (row.get("doc_foto") or "NO") in opts else 1)
        doc_cv = st.selectbox("CV", opts, index=opts.index(row.get("doc_cv") or "NO") if (row.get("doc_cv") or "NO") in opts else 1)
        doc_ant = st.selectbox("Antecedentes", opts, index=opts.index(row.get("doc_antecedentes") or "NO") if (row.get("doc_antecedentes") or "NO") in opts else 1)
    with d2:
        doc_cont = st.selectbox("Contrato firmado", opts, index=opts.index(row.get("doc_contrato") or "NO") if (row.get("doc_contrato") or "NO") in opts else 1)
        doc_dni = st.selectbox("DNI escaneado", opts, index=opts.index(row.get("doc_dni") or "NO") if (row.get("doc_dni") or "NO") in opts else 1)
        doc_rec = st.selectbox("Recibo luz/agua", opts, index=opts.index(row.get("doc_recibo_servicios") or "NO") if (row.get("doc_recibo_servicios") or "NO") in opts else 1)
    with d3:
        doc_cro = st.selectbox("Croquis", opts, index=opts.index(row.get("doc_croquis") or "NO") if (row.get("doc_croquis") or "NO") in opts else 1)
        doc_dec = st.selectbox("Declaración jurada", opts, index=opts.index(row.get("doc_declaracion") or "NO") if (row.get("doc_declaracion") or "NO") in opts else 1)
        doc_cert = st.selectbox("Certificados", opts, index=opts.index(row.get("doc_certificados") or "NO") if (row.get("doc_certificados") or "NO") in opts else 1)

    obs = st.text_area("Observaciones", value=row.get("observaciones") or "")

    return {
        "nombre_completo": nombre.strip(),
        "cedula": cedula,
        "fecha_ingreso": fecha_ing.isoformat(),
        "cargo": cargo,
        "sueldo_bruto": sueldo,
        "area": area,
        "modalidad_trabajo": modalidad,
        "tipo_contrato": tipo_c,
        "fecha_inicio": fecha_ini.isoformat(),
        "fecha_fin": fecha_fin.isoformat() if ff else None,
        "estado": estado,
        "sctr": sctr,
        "vida_ley": vida,
        "examen_medico": examen,
        "induccion": induccion,
        "epp": epp,
        "doc_foto": doc_foto,
        "doc_cv": doc_cv,
        "doc_antecedentes": doc_ant,
        "doc_contrato": doc_cont,
        "doc_dni": doc_dni,
        "doc_recibo_servicios": doc_rec,
        "doc_croquis": doc_cro,
        "doc_declaracion": doc_dec,
        "doc_certificados": doc_cert,
        "observaciones": obs,
    }


def _form_editar(row: dict) -> None:
    with st.form(f"edit_ca_{row.get('id')}"):
        datos = _campos_form(row)
        datos["id"] = row.get("id")
        if st.form_submit_button("Guardar cambios"):
            if not datos["nombre_completo"]:
                st.error("El nombre es obligatorio.")
            else:
                guardar_contrato_activo(datos)
                st.success("Guardado en memoria.")
                st.rerun()


def _form_nuevo() -> None:
    with st.form("nuevo_ca"):
        datos = _campos_form()
        if st.form_submit_button("Registrar contrato activo"):
            if not datos["nombre_completo"]:
                st.error("El nombre es obligatorio.")
            else:
                guardar_contrato_activo(datos)
                st.success("Empleado registrado.")
                st.rerun()
