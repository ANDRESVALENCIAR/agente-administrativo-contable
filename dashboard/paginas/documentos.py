"""Página Documentos generados."""
import os

import streamlit as st

from dashboard.utils.db_helper import query_df


def render() -> None:
    """Lista documentos generados con filtros y descarga."""
    st.markdown("## Documentos generados")
    df = query_df("SELECT * FROM documentos_generados ORDER BY id DESC")
    if df.empty:
        st.info("No hay documentos aún. Se generan al liquidar comisiones, certificaciones, créditos, etc.")
        return

    tipos = sorted(df["tipo"].dropna().unique().tolist())
    modulos = sorted(df["modulo_origen"].dropna().unique().tolist())
    c1, c2, c3 = st.columns(3)
    tipo_f = c1.selectbox("Tipo", ["Todos"] + tipos)
    mod_f = c2.selectbox("Módulo", ["Todos"] + modulos)
    buscar = c3.text_input("Buscar nombre")

    filtrado = df.copy()
    if tipo_f != "Todos":
        filtrado = filtrado[filtrado["tipo"] == tipo_f]
    if mod_f != "Todos":
        filtrado = filtrado[filtrado["modulo_origen"] == mod_f]
    if buscar.strip():
        filtrado = filtrado[
            filtrado["nombre_archivo"].str.contains(buscar.strip(), case=False, na=False)
        ]

    st.caption(f"{len(filtrado)} documento(s)")
    for _, row in filtrado.iterrows():
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{row['nombre_archivo']}** — {row['descripcion']}")
        c1.caption(f"{row['tipo']} · {row['modulo_origen']} · {row['timestamp']}")
        if row["path_local"] and os.path.exists(row["path_local"]):
            with open(row["path_local"], "rb") as f:
                c2.download_button(
                    "Descargar",
                    f.read(),
                    row["nombre_archivo"],
                    key=f"doc_{row['id']}",
                )
        else:
            c2.caption("Archivo no local")
