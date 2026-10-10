"""Pestañas perezosas: solo se dibuja la pestaña abierta.

st.tabs normal ejecuta TODAS las pestañas en cada clic aunque solo se vea una. Desde Streamlit 1.5x
las pestañas pueden recordar cuál está abierta (on_change="rerun") y exponen `.open`; así cada página
calcula solo lo que se está mirando. En versiones anteriores se dibujan todas, como antes."""
from __future__ import annotations

from typing import Sequence

import streamlit as st


def pestanas(nombres: Sequence[str], key: str):
    try:
        return st.tabs(list(nombres), key=key, on_change="rerun")
    except TypeError:  # Streamlit sin pestañas con estado
        return st.tabs(list(nombres))


def abierta(tab) -> bool:
    """True si la pestaña está a la vista (o si esta versión de Streamlit no lo sabe)."""
    return getattr(tab, "open", None) is not False
