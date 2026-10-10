"""Incrustar HTML propio (informes, radar, correos de muestra) con la API moderna de Streamlit.

st.iframe reemplaza a st.components.v1.html (obsoleto desde Streamlit 1.5x). Si la versión instalada
todavía no lo trae, se usa el método anterior para que nada se rompa."""
from __future__ import annotations

import streamlit as st


def html(contenido: str, height: int = 600, scrolling: bool = False) -> None:
    if hasattr(st, "iframe"):
        st.iframe(contenido, height=height)
    else:  # Streamlit antiguo
        import streamlit.components.v1 as components

        components.html(contenido, height=height, scrolling=scrolling)
