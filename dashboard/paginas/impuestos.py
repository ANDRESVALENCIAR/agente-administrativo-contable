"""Página Impuestos — tabla maestra y DIAN."""
from datetime import date, timedelta

import streamlit as st

from dashboard.utils.db_helper import execute, query_df
from dashboard.utils.reportes import generar_reporte
from database import crear_alerta


def render() -> None:
    """Renderiza módulo impuestos."""
    st.markdown("## Impuestos")
    df = query_df("SELECT * FROM impuestos_maestro ORDER BY fecha_vencimiento")

    st.subheader("Estado de impuestos")
    if not df.empty:
        hoy = date.today()
        df_display = df.copy()
        df_display["dias"] = df_display["fecha_vencimiento"].apply(
            lambda x: (date.fromisoformat(str(x)) - hoy).days if x else 999
        )
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        if st.button("Exportar Excel"):
            data, nombre = generar_reporte("impuestos", df, "excel")
            st.download_button("Descargar", data, nombre)
    else:
        st.info("Sin impuestos registrados.")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Agregar / actualizar")
        with st.form("imp_form"):
            imp = st.text_input("Impuesto")
            per = st.text_input("Periodo", "2026-06")
            fv = st.date_input("Vencimiento", date.today() + timedelta(days=30))
            est = st.selectbox("Estado", ["PENDIENTE", "EN REVISIÓN", "PRESENTADO", "PAGADO"])
            form = st.text_input("Formulario", "350")
            obs = st.text_area("Observaciones")
            if st.form_submit_button("Guardar"):
                execute(
                    """INSERT INTO impuestos_maestro (impuesto,periodo,fecha_vencimiento,estado,formulario,observaciones)
                       VALUES (?,?,?,?,?,?)
                       ON CONFLICT(impuesto,periodo) DO UPDATE SET
                       fecha_vencimiento=excluded.fecha_vencimiento, estado=excluded.estado,
                       formulario=excluded.formulario, observaciones=excluded.observaciones""",
                    (imp, per, fv.isoformat(), est, form, obs),
                )
                dias = (fv - date.today()).days
                if dias <= 15 and est not in ("PRESENTADO", "PAGADO"):
                    crear_alerta("URGENTE", "impuestos", f"{imp} {per} vence en {dias}d", obs or "")
                st.success("Guardado.")
                st.rerun()

    with col2:
        st.subheader("Revisar DIAN")
        st.link_button("Abrir dian.gov.co", "https://www.dian.gov.co")
        if st.button("Registrar revisión DIAN"):
            execute(
                "INSERT INTO revisiones_dian (usuario, notas) VALUES (?,?)",
                ("Usuario dashboard", f"Revisión manual {date.today()}"),
            )
            st.success("Revisión registrada con timestamp.")

    rev = query_df("SELECT * FROM revisiones_dian ORDER BY id DESC LIMIT 10")
    if not rev.empty:
        st.caption("Últimas revisiones DIAN")
        st.dataframe(rev, use_container_width=True, hide_index=True)
