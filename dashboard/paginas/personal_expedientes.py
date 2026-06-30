"""UI pestaña Expedientes — carpetas inteligentes RRHH."""
from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from dashboard.utils.db_helper import query_df
from dashboard.utils.rrhh_helpers import exportar_informe_empleados_activos
from modulos.carpetas_rrhh import (
    archivar_empleado,
    escanear_carpetas_personal,
    ruta_personal_activo,
    watcher_esta_activo,
)

ICONOS = {
    "cedula_cc": "🪪",
    "contrato": "📄",
    "examen_medico": "🏥",
    "arl": "🦺",
    "eps": "💊",
    "certificacion_lab": "📜",
    "certificacion_ban": "🏦",
    "hoja_vida": "📋",
    "afiliacion": "✅",
    "otro": "📎",
}

ETIQUETAS = {
    "cedula_cc": "Cédula",
    "contrato": "Contrato",
    "examen_medico": "Examen médico",
    "arl": "ARL",
    "eps": "EPS",
    "certificacion_ban": "Cert. bancaria",
    "hoja_vida": "Hoja de vida",
    "afiliacion": "Afiliación",
}


def _color_completitud(pct: int) -> str:
    if pct >= 100:
        return "#30D158"
    if pct >= 50:
        return "#FF9F0A"
    return "#FF453A"


def _barra_completitud(pct: int) -> None:
    color = _color_completitud(pct)
    st.markdown(
        f"""<div style="background:#333;border-radius:6px;height:22px;width:100%;overflow:hidden;">
        <div style="background:{color};width:{pct}%;height:100%;text-align:center;
        color:#000;font-size:12px;line-height:22px;font-weight:bold;">{pct}%</div></div>""",
        unsafe_allow_html=True,
    )


def _abrir_archivo(ruta: str) -> None:
    if os.name == "nt" and Path(ruta).is_file():
        os.startfile(ruta)  # noqa: S606
    else:
        st.info(f"Ruta: {ruta}")


def render_lista() -> None:
    base = ruta_personal_activo()
    dot = "🟢" if watcher_esta_activo() else "🟡"
    st.markdown(f"{dot} **Vigilando** `{base}`")

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    if c1.button("🔍 Escanear ahora", key="scan_carpetas"):
        with st.spinner("Escaneando PERSONAL ACTIVO…"):
            r = escanear_carpetas_personal()
        st.success(
            f"{r['total_empleados']} empleados · {r['total_documentos']} docs · "
            f"+{r['archivos_nuevos']} nuevos"
        )
        st.rerun()

    if c4.button("📊 Exportar informe", key="export_informe_activos"):
        path = exportar_informe_empleados_activos()
        st.success(f"Informe guardado: `{path}`")

    df = query_df(
        """SELECT id, nombre_display, nombre_carpeta, total_documentos,
                  completitud_pct, ultima_actualizacion, docs_faltantes
           FROM empleados_carpetas WHERE activo=1
           ORDER BY nombre_display"""
    )

    c2.metric("Empleados", len(df) if not df.empty else 0)
    c3.metric("Documentos", int(df["total_documentos"].sum()) if not df.empty else 0)

    if df.empty:
        st.warning(f"No hay empleados indexados. Carpeta: `{base}`")
        return

    st.subheader("Informe — personal activo")
    informe = df[
        ["nombre_display", "total_documentos", "completitud_pct", "docs_faltantes", "ultima_actualizacion"]
    ].copy()
    informe.columns = ["Empleado", "Docs", "Completitud %", "Faltantes (JSON)", "Actualizado"]
    st.dataframe(informe, use_container_width=True, hide_index=True)

    st.subheader("Detalle por empleado")
    for _, row in df.iterrows():
        eid = int(row["id"])
        pct = int(row["completitud_pct"] or 0)
        cols = st.columns([3, 1, 2, 1, 1])
        cols[0].markdown(f"**{row['nombre_display']}**")
        cols[1].write(f"📁 {row['total_documentos']}")
        with cols[2]:
            _barra_completitud(pct)
        cols[3].caption(str(row["ultima_actualizacion"] or "—")[:16])
        if cols[4].button("Ver", key=f"ver_exp_{eid}"):
            st.session_state["exp_detalle_id"] = eid
            st.session_state["exp_detalle_nombre"] = row["nombre_carpeta"]
            st.rerun()


def render_detalle(empleado_id: int, nombre_carpeta: str) -> None:
    if st.button("← Volver a lista"):
        st.session_state.pop("exp_detalle_id", None)
        st.session_state.pop("exp_detalle_nombre", None)
        st.rerun()

    emp = query_df("SELECT * FROM empleados_carpetas WHERE id=?", (empleado_id,))
    if emp.empty:
        st.error("Empleado no encontrado.")
        return
    row = emp.iloc[0]
    pct = int(row["completitud_pct"] or 0)

    st.markdown(f"## {row['nombre_display']}")
    _barra_completitud(pct)
    st.caption(f"Carpeta: `{row['ruta_carpeta']}` · {row['total_documentos']} documentos")

    docs = query_df(
        """SELECT nombre_archivo, categoria, tamanio_kb, ruta_archivo
           FROM documentos_empleado WHERE empleado_id=?
           ORDER BY categoria, nombre_archivo""",
        (empleado_id,),
    )

    st.subheader("Documentos presentes")
    if docs.empty:
        st.info("Sin documentos indexados.")
    else:
        for i, d in docs.iterrows():
            icon = ICONOS.get(d["categoria"], "📎")
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.write(f"{icon} {d['nombre_archivo']} — _{d['categoria']}_")
            c2.caption(f"{d['tamanio_kb']} KB")
            if c3.button("Abrir", key=f"open_{empleado_id}_{i}"):
                _abrir_archivo(d["ruta_archivo"])

    st.subheader("Documentos faltantes")
    try:
        faltantes = json.loads(row["docs_faltantes"] or "[]")
    except json.JSONDecodeError:
        faltantes = []
    if faltantes:
        for f in faltantes:
            st.markdown(f"- :red[{ETIQUETAS.get(f, f)}]")
    else:
        st.success("Expediente completo.")

    st.subheader("Historial de cambios")
    log = query_df(
        """SELECT tipo_cambio, archivo, categoria, fecha_cambio
           FROM log_cambios_carpetas WHERE empleado=? ORDER BY id DESC LIMIT 30""",
        (nombre_carpeta,),
    )
    st.dataframe(log, use_container_width=True, hide_index=True)

    if st.button("🚪 Archivar empleado (PERSONAL RETIRADO)", type="primary"):
        try:
            dest = archivar_empleado(nombre_carpeta)
            st.success(f"Archivado: {dest}")
            st.session_state.pop("exp_detalle_id", None)
            st.rerun()
        except Exception as e:
            st.error(str(e))


@st.fragment(run_every=5)
def render_expedientes_vivo() -> None:
    eid = st.session_state.get("exp_detalle_id")
    nombre = st.session_state.get("exp_detalle_nombre")
    if eid and nombre:
        render_detalle(int(eid), nombre)
    else:
        render_lista()
