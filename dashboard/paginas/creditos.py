"""Página Créditos — evaluación y bloqueos."""
import streamlit as st

from dashboard.utils.db_helper import execute, query_df
from modulos.creditos import analizar_solicitud_credito


def render() -> None:
    """Renderiza módulo créditos."""
    st.markdown("## Créditos")
    tab1, tab2 = st.tabs(["Evaluación", "Cartera activa"])

    with tab1:
        with st.form("cred_eval"):
            cliente = st.text_input("Cliente")
            nit = st.text_input("NIT")
            cupo = st.number_input("Cupo solicitado", min_value=0, step=100000)
            ingresos = st.number_input("Ingresos mensuales", min_value=0, step=100000)
            deuda = st.number_input("Deuda actual", min_value=0, step=100000)
            activos = st.number_input("Activos", min_value=0, step=100000)
            req_ok = st.checkbox("Cumple requisitos documentales")
            if st.form_submit_button("Evaluar con IA"):
                datos = {
                    "cliente": cliente,
                    "nit": nit,
                    "cupo_solicitado": cupo,
                    "ingresos_mensuales": ingresos,
                    "deuda_actual": deuda,
                    "activos": activos,
                    "requisitos": req_ok,
                }
                with st.spinner("Analizando..."):
                    r = analizar_solicitud_credito(datos)
                st.json(r)

    with tab2:
        df = query_df("SELECT * FROM creditos_analizados ORDER BY id DESC")
        cartera = query_df("SELECT * FROM cartera_cxc ORDER BY dias_mora DESC")
        if not df.empty:
            st.dataframe(df[["cliente", "cupo_solicitado", "decision", "estado_habilitacion"]], use_container_width=True)
        if not cartera.empty:
            st.subheader("Semáforo de mora")
            for _, row in cartera.iterrows():
                dias = row["dias_mora"]
                color = "🟢" if dias < 30 else "🟡" if dias < 60 else "🔴"
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.write(f"{color} **{row['cliente']}** — ${row['saldo']:,.0f} — {dias} días mora")
                bloq = row.get("bloqueado", 0)
                c2.write("BLOQUEADO" if bloq else "Activo")
                with c3:
                    if st.button("Bloquear" if not bloq else "Desbloquear", key=f"bl_{row['id']}"):
                        nuevo = 0 if bloq else 1
                        execute(
                            "UPDATE cartera_cxc SET bloqueado=?, notas=? WHERE id=?",
                            (nuevo, f"Bloqueo manual {st.session_state.get('user','admin')}", row["id"]),
                        )
                        st.rerun()
