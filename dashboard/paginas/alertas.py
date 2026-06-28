"""Página Alertas — sistema centralizado."""
import streamlit as st

from dashboard.utils.alertas_globales import verificar_alertas_globales
from database import marcar_alerta_resuelta, obtener_alertas_activas


def render() -> None:
    """Renderiza alertas globales."""
    st.markdown("## Alertas del sistema")
    if st.button("🔄 Verificar alertas automáticas"):
        n = verificar_alertas_globales()
        st.success(f"Verificación completada. {n} alerta(s) nueva(s).")
        st.rerun()

    alertas = obtener_alertas_activas()
    if not alertas:
        st.success("Sin alertas activas.")
        return
    for alerta in alertas:
        with st.expander(f"[{alerta[3]}] {alerta[4]} · {alerta[2]}", expanded=alerta[3] == "CRITICO"):
            st.write(alerta[5])
            st.caption(f"Registrada: {alerta[1]}")
            if st.button("Marcar resuelta", key=f"res_{alerta[0]}"):
                marcar_alerta_resuelta(alerta[0])
                st.rerun()
