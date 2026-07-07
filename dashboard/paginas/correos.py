"""Página Correos — reglas y procesados."""
import streamlit as st

from config import en_modo_demo
from dashboard.utils.db_helper import execute, query_df
from modulos.correos import procesar_correos, sincronizar_reglas_desde_config


def render() -> None:
    """Renderiza módulo correos."""
    st.markdown("## Correos")
    if en_modo_demo():
        st.info("Modo demo: la clasificación usa respuestas simuladas. Configure Gmail/Outlook en `.env` para producción.")
    t1, t2 = st.tabs(["Procesados", "Reglas de reenvío"])

    with t1:
        if st.button("Procesar correos ahora"):
            with st.spinner("Clasificando..."):
                procesar_correos()
            st.success("Procesamiento completado.")
            st.rerun()
        df = query_df(
            "SELECT timestamp, origen, remitente, asunto, categoria, destino_reenvio, accion "
            "FROM correos_procesados ORDER BY id DESC LIMIT 100"
        )
        if df.empty:
            st.info("Sin correos procesados.")
        else:
            cat = st.selectbox("Categoría", ["Todas"] + df["categoria"].dropna().unique().tolist())
            if cat != "Todas":
                df = df[df["categoria"] == cat]
            st.dataframe(df, use_container_width=True, hide_index=True)

    with t2:
        st.caption("Claude Haiku clasifica automáticamente. Las reglas activas en BD tienen prioridad sobre .env.")
        if st.button("Sincronizar reglas desde .env"):
            n = sincronizar_reglas_desde_config()
            st.success(f"{n} reglas sincronizadas desde configuración.")
            st.rerun()
        reglas = query_df("SELECT * FROM reglas_correo ORDER BY categoria")
        st.dataframe(reglas, use_container_width=True, hide_index=True)
        with st.form("regla"):
            cat = st.text_input(
                "Categoría",
                placeholder="factura, pqr, solicitud_pago, cobranza, extracto_bancario...",
            )
            dest = st.text_input("Destino email")
            activo = st.checkbox("Activa", value=True)
            if st.form_submit_button("Guardar regla"):
                execute(
                    """INSERT INTO reglas_correo (categoria, destino, activo) VALUES (?,?,?)
                       ON CONFLICT(categoria) DO UPDATE SET destino=excluded.destino, activo=excluded.activo""",
                    (cat, dest, 1 if activo else 0),
                )
                st.rerun()
        for _, r in reglas.iterrows():
            if st.button(f"Eliminar {r['categoria']}", key=f"del_{r['id']}"):
                execute("DELETE FROM reglas_correo WHERE id=?", (r["id"],))
                st.rerun()
