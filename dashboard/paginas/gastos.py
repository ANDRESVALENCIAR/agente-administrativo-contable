"""UI Estandarización de Gastos y Periodicidad."""
from __future__ import annotations

import streamlit as st
import plotly.express as px

from modulos.catalogos_gastos import CATEGORIAS_GASTO, PERIODICIDADES_STD, mapa_categorias
from utils.estandarizar_gastos import (
    actualizar_categoria_gasto,
    estandarizar_todos,
    exportar_excel_estandarizado,
    gastos_maestro_vacio,
    marcar_restantes_como_otro,
    query_gastos,
    resumen_por_categoria,
    resumen_por_periodicidad,
    ruta_excel_estandarizar,
    sincronizar_periodicidad_control_pagos,
)

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def render() -> None:
    from dashboard.paginas import gastos_dashboard

    st.markdown("## Gastos")
    t_tab, t_est = st.tabs(["Tablero", "Catálogo y estandarización"])
    with t_tab:
        gastos_dashboard.render()
    with t_est:
        _render_estandarizacion()


def _render_estandarizacion() -> None:
    path = ruta_excel_estandarizar()
    st.caption(f"Fuente: `{path.name}` · hoja Hoja1")

    c1, c2, c3 = st.columns(3)
    if c1.button("🔄 Ejecutar estandarización", type="primary", key="gst_run"):
        with st.spinner("Procesando 4.089 registros..."):
            try:
                res = estandarizar_todos(reemplazar=True)
                st.success(
                    f"Listo · total={res['total']} · auto={res['clasificados_auto']} · "
                    f"revisión={res['requieren_revision']} · "
                    f"periodicidades corregidas={res['periodicidades_corregidas']}"
                )
                st.rerun()
            except Exception as e:
                st.error(str(e))
    if c2.button("Recargar si vacío", key="gst_if_empty"):
        if gastos_maestro_vacio():
            estandarizar_todos()
            st.rerun()
        else:
            st.info("gastos_maestro ya tiene datos.")

    if gastos_maestro_vacio():
        st.warning("Aún no hay datos estandarizados. Pulse **Ejecutar estandarización**.")
        return

    t1, t2, t3, t4, t5 = st.tabs(
        [
            "Resumen por categoría",
            "Todos los gastos",
            "Periodicidades",
            "Exportar",
            "Revisión manual",
        ]
    )
    with t1:
        _tab_resumen()
    with t2:
        _tab_todos()
    with t3:
        _tab_periodicidades()
    with t4:
        _tab_exportar()
    with t5:
        _tab_revision()


def _tab_resumen() -> None:
    df = resumen_por_categoria()
    if df.empty:
        st.info("Sin datos.")
        return

    if "gst_cat_sel" not in st.session_state:
        st.session_state.gst_cat_sel = None

    for _, r in df.iterrows():
        icono = r.get("icono") or "•"
        label = r.get("label") or r.get("categoria")
        qty = int(r.get("qty") or 0)
        pers = (r.get("periodicidades") or "").replace(",", ", ")
        cols = st.columns([5, 1])
        with cols[0]:
            if st.button(
                f"{icono} {label} — {qty} · {pers}",
                key=f"catbtn_{r['categoria']}",
                use_container_width=True,
            ):
                st.session_state.gst_cat_sel = r["categoria"]
        cols[1].markdown(
            f"<div style='background:{r.get('color_hex') or '#eee'};"
            f"height:36px;border-radius:8px'></div>",
            unsafe_allow_html=True,
        )

    rev = query_gastos(solo_revision=True)
    st.caption(f"⚡ Requieren revisión: **{len(rev)}**")

    sel = st.session_state.gst_cat_sel
    if sel:
        st.subheader(f"Detalle — {sel}")
        if st.button("Limpiar filtro categoría", key="gst_clr_cat"):
            st.session_state.gst_cat_sel = None
            st.rerun()
        det = query_gastos(categorias=[sel])
        st.dataframe(
            det[
                [
                    c
                    for c in [
                        "detalle_limpio",
                        "proveedor_limpio",
                        "periodicidad_std",
                        "requiere_revision",
                    ]
                    if c in det.columns
                ]
            ],
            use_container_width=True,
            hide_index=True,
            height=360,
        )


def _tab_todos() -> None:
    cats = [c[0] for c in CATEGORIAS_GASTO]
    pers = [p[0] for p in PERIODICIDADES_STD]
    f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
    cat_sel = f1.multiselect("Categoría", cats, key="gst_f_cat")
    per_sel = f2.multiselect("Periodicidad", pers, key="gst_f_per")
    buscar = f3.text_input("Buscar en detalle", key="gst_f_q")
    solo_rev = f4.checkbox("Solo revisión", key="gst_f_rev")

    df = query_gastos(
        categorias=cat_sel or None,
        periodicidades=per_sel or None,
        buscar=buscar or None,
        solo_revision=solo_rev,
    )
    if df.empty:
        st.info("Sin resultados.")
        return

    show = df[
        [
            "id",
            "detalle_limpio",
            "proveedor_limpio",
            "categoria",
            "periodicidad_std",
            "requiere_revision",
        ]
    ].copy()
    st.dataframe(show, use_container_width=True, hide_index=True, height=420)

    st.subheader("Clasificar fila en revisión")
    pendientes = df[df["requiere_revision"] == 1]
    if pendientes.empty:
        st.caption("No hay filas filtradas que requieran revisión.")
        return
    opts = {
        f"#{int(r.id)} · {(r.detalle_limpio or '')[:60]}": int(r.id)
        for _, r in pendientes.head(80).iterrows()
    }
    elegido = st.selectbox("Registro", list(opts.keys()), key="gst_cls_sel")
    nueva = st.selectbox("Categoría correcta", cats, key="gst_cls_cat")
    if st.button("Guardar clasificación", key="gst_cls_save"):
        actualizar_categoria_gasto(opts[elegido], nueva)
        st.success("Actualizado.")
        st.rerun()


def _tab_periodicidades() -> None:
    df = resumen_por_periodicidad()
    if df.empty:
        st.info("Sin datos.")
        return
    df = df.copy()
    df["etiqueta"] = df.apply(
        lambda r: f"{r.get('icono') or ''} {r.get('label') or r.get('codigo')}",
        axis=1,
    )
    st.dataframe(
        df[["etiqueta", "codigo", "qty"]],
        use_container_width=True,
        hide_index=True,
    )
    fig = px.bar(df, x="etiqueta", y="qty", title="Gastos por periodicidad estándar")
    fig.update_layout(xaxis_title="", yaxis_title="Cantidad", height=380)
    st.plotly_chart(fig, use_container_width=True)


def _tab_exportar() -> None:
    if st.button("⬇️ Generar Excel estandarizado", key="gst_exp"):
        data, nombre = exportar_excel_estandarizado()
        st.download_button(
            "Descargar Excel",
            data,
            file_name=nombre,
            mime=MIME_XLSX,
            key="gst_dl",
        )
        st.success(f"Archivo listo: {nombre}")

    st.divider()
    if st.button("🔗 Sincronizar con CONTROL_DE_PAGOS.xlsx", key="gst_sync_pagos"):
        with st.spinner("Cruzando detalles y actualizando periodicidad..."):
            res = sincronizar_periodicidad_control_pagos()
        st.success(
            f"BD pagos actualizados: {res['actualizados_bd']} · "
            f"Excel filas: {res['actualizados_excel']}"
        )


def _tab_revision() -> None:
    df = query_gastos(solo_revision=True)
    total_all = len(query_gastos())
    revisados = total_all - len(df)
    pct = (revisados / total_all * 100) if total_all else 0
    st.metric("Progreso revisión", f"{revisados} de {total_all}", f"{pct:.1f}%")
    st.caption(f"Pendientes de revisión: **{len(df)}**")

    if st.button("Auto-clasificar restantes como OTRO", key="gst_all_otro"):
        n = marcar_restantes_como_otro()
        st.success(f"{n} registros marcados como OTRO.")
        st.rerun()

    if df.empty:
        st.success("No hay registros pendientes de revisión.")
        return

    cats = [c[0] for c in CATEGORIAS_GASTO]
    cats_map = mapa_categorias()
    page_size = 15
    page = st.number_input("Página", min_value=1, value=1, key="gst_rev_page")
    start = (int(page) - 1) * page_size
    chunk = df.iloc[start : start + page_size]

    for _, r in chunk.iterrows():
        gid = int(r["id"])
        st.markdown(
            f"""
            <div style="border:1px solid #3A3320;background:#15130C;color:#E8E8EA;border-radius:12px;
                        padding:12px;margin-bottom:8px">
              <strong>#{gid}</strong> {r.get('detalle_limpio') or ''}<br>
              <span style="color:#8B8B93">{r.get('proveedor_limpio') or 'Sin proveedor'}</span>
              · per: {r.get('periodicidad_std')}
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_a, col_b = st.columns([3, 1])
        nueva = col_a.selectbox(
            "Categoría",
            cats,
            format_func=lambda x: f"{(cats_map.get(x) or {}).get('icono', '')} {x}",
            key=f"rev_cat_{gid}",
            label_visibility="collapsed",
        )
        if col_b.button("Confirmar", key=f"rev_ok_{gid}"):
            actualizar_categoria_gasto(gid, nueva)
            st.rerun()
