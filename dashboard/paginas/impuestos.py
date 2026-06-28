"""Página Impuestos — open data DIAN/SHD, calendario y recordatorios."""
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from config import cfg
from dashboard.utils.db_helper import execute, query_df
from dashboard.utils.reportes import generar_reporte
from database import crear_alerta
from modulos.impuestos_calendario import (
    enviar_recordatorios_vencimientos,
    inicializar_tablas_calendario,
    listar_proximos_vencimientos,
    sincronizar_calendario_opendata,
)


def render() -> None:
    """Renderiza módulo impuestos con calendario open data."""
    st.markdown("## Impuestos")
    inicializar_tablas_calendario()

    tab_cal, tab_tabla, tab_admin = st.tabs(["📅 Calendario", "📋 Tabla maestra", "⚙️ Administrar"])

    with tab_cal:
        st.caption(
            "Fuentes: **DIAN** (calendario fiscal open data) + **SHD Bogotá** (Resolución SDH-000195/2026). "
            f"NIT empresa: **{cfg.NIT_EMPRESA}**"
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("🔄 Sincronizar open data", use_container_width=True):
                with st.spinner("Descargando DIAN + SHD Bogotá..."):
                    n = sincronizar_calendario_opendata(date.today().year)
                st.success(f"{n} vencimientos sincronizados.")
                st.rerun()
        with c2:
            if st.button("📧 Probar recordatorios", use_container_width=True):
                with st.spinner("Revisando ventanas 48h / 24h..."):
                    stats = enviar_recordatorios_vencimientos()
                st.info(f"Emails 48h: {stats['email_48h']} | WhatsApp 24h: {stats['whatsapp_24h']}")
        with c3:
            st.link_button("DIAN oficial", "https://www.dian.gov.co/Paginas/CalendarioTributario.aspx", use_container_width=True)

        cal = query_df(
            """SELECT entidad, impuesto, periodo, fecha_vencimiento, formulario, categoria
               FROM calendario_tributario ORDER BY fecha_vencimiento"""
        )
        if cal.empty:
            st.warning("Sin calendario. Pulse **Sincronizar open data**.")
        else:
            hoy = date.today()
            cal["fecha_vencimiento"] = pd.to_datetime(cal["fecha_vencimiento"])
            cal["dias"] = (cal["fecha_vencimiento"].dt.date - hoy).apply(lambda x: x.days)
            cal["color"] = cal["dias"].apply(
                lambda d: "Vencido" if d < 0 else "≤24h" if d <= 1 else "≤48h" if d <= 2 else "Próximo"
            )
            prox = cal[cal["dias"] >= 0].head(15)
            if not prox.empty:
                fig = px.scatter(
                    prox,
                    x="fecha_vencimiento",
                    y="entidad",
                    color="color",
                    hover_data=["impuesto", "periodo", "formulario", "dias"],
                    title="Próximos vencimientos tributarios",
                    height=380,
                )
                fig.update_layout(plot_bgcolor="#fff", paper_bgcolor="#fff")
                st.plotly_chart(fig, use_container_width=True)
            st.dataframe(
                cal[["entidad", "impuesto", "periodo", "fecha_vencimiento", "formulario", "dias", "color"]],
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("#### Recordatorios automáticos")
        st.markdown(
            """
            - **48 horas antes** → correo a contador, revisoría fiscal, contabilidad y gerencia
            - **24 horas antes** → WhatsApp a todos (`WHATSAPP_DESTINATARIOS` en `.env`)
            """
        )
        rec = query_df(
            """SELECT r.tipo, r.timestamp, r.destinos, c.impuesto, c.fecha_vencimiento
               FROM recordatorios_impuestos r
               JOIN calendario_tributario c ON c.id = r.calendario_id
               ORDER BY r.timestamp DESC LIMIT 20"""
        )
        if not rec.empty:
            st.dataframe(rec, use_container_width=True, hide_index=True)

    with tab_tabla:
        df = query_df("SELECT * FROM impuestos_maestro ORDER BY fecha_vencimiento")
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

    with tab_admin:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Agregar / actualizar manual")
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
            st.subheader("Enlaces oficiales")
            st.link_button("SHD Bogotá — Calendario", "https://www.haciendabogota.gov.co/es/calendario-tributario")
            st.link_button("Datos abiertos Bogotá", "https://datosabiertos.bogota.gov.co/")
            if st.button("Registrar revisión DIAN"):
                execute(
                    "INSERT INTO revisiones_dian (usuario, notas) VALUES (?,?)",
                    ("Usuario dashboard", f"Revisión manual {date.today()}"),
                )
                st.success("Revisión registrada.")

        rev = query_df("SELECT * FROM revisiones_dian ORDER BY id DESC LIMIT 10")
        if not rev.empty:
            st.caption("Últimas revisiones DIAN")
            st.dataframe(rev, use_container_width=True, hide_index=True)
