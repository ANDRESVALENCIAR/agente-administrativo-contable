"""Página Alertas — sistema centralizado."""
import streamlit as st

from dashboard.utils.alertas_globales import verificar_alertas_globales
from database import crear_alerta, marcar_alerta_resuelta, marcar_alerta_vista, obtener_alertas_activas


def render() -> None:
    """Renderiza alertas globales."""
    st.markdown("## Alertas del sistema")
    c1, c2 = st.columns(2)
    if c1.button("🔄 Verificar alertas automáticas"):
        n = verificar_alertas_globales()
        st.success(f"Verificación completada. {n} alerta(s) nueva(s).")
        st.rerun()

    with c2.expander("➕ Crear alerta manual"):
        with st.form("alerta_manual"):
            nivel = st.selectbox("Nivel", ["INFO", "AVISO", "URGENTE", "CRITICO"])
            modulo = st.text_input("Módulo", "manual")
            titulo = st.text_input("Título")
            descripcion = st.text_area("Descripción")
            if st.form_submit_button("Registrar alerta"):
                if titulo.strip():
                    crear_alerta(nivel, modulo.strip(), titulo.strip(), descripcion or "")
                    st.success("Alerta creada.")
                    st.rerun()
                else:
                    st.error("El título es obligatorio.")

    alertas = obtener_alertas_activas()
    if not alertas:
        st.success("Sin alertas activas.")
        return

    filtro = st.selectbox("Filtrar por nivel", ["Todos", "CRITICO", "URGENTE", "AVISO", "INFO"])
    for alerta in alertas:
        if filtro != "Todos" and alerta[3] != filtro:
            continue
        visto = alerta[6] if len(alerta) > 6 else 0
        etiqueta = f"[{alerta[3]}] {alerta[4]} · {alerta[2]}"
        if visto:
            etiqueta += " · vista"
        with st.expander(etiqueta, expanded=alerta[3] == "CRITICO"):
            st.write(alerta[5])
            st.caption(f"Registrada: {alerta[1]}")
            b1, b2 = st.columns(2)
            if b1.button("Marcar resuelta", key=f"res_{alerta[0]}"):
                marcar_alerta_resuelta(alerta[0])
                st.rerun()
            if b2.button("Marcar vista", key=f"vis_{alerta[0]}"):
                marcar_alerta_vista(alerta[0])
                st.rerun()
