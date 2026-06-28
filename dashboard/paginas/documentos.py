"""Página Documentos generados."""
import os

import streamlit as st

from dashboard.utils.db_helper import query_df


def render() -> None:
    """Lista documentos generados."""
    st.markdown("## Documentos generados")
    df = query_df("SELECT * FROM documentos_generados ORDER BY id DESC")
    if df.empty:
        st.info("No hay documentos aún.")
        return
    for _, row in df.iterrows():
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{row['nombre_archivo']}** — {row['descripcion']}")
        c1.caption(f"{row['tipo']} · {row['timestamp']}")
        if row["path_local"] and os.path.exists(row["path_local"]):
            with open(row["path_local"], "rb") as f:
                c2.download_button("Descargar", f.read(), row["nombre_archivo"], key=f"doc_{row['id']}")
