"""UI Comparador VIA × Contabilidad — estilo dark + historial mensual."""
from __future__ import annotations

import os
from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import modulos.comparador_comisiones as comparador

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _cmp():
    """Recarga el módulo si Streamlit tenía una versión en caché sin las funciones nuevas."""
    if not hasattr(comparador, "generar_informe_excel_bytes"):
        import importlib
        importlib.reload(comparador)
    return comparador

CSS = """
<style>
.ca-wrap{background:#0d1013!important;color:#ffffff!important;padding:8px 0 24px;border-radius:12px}
.ca-wrap h3,.ca-wrap h3 span{font-family:Georgia,serif;color:#FFAD03!important;font-size:22px;margin:12px 0 6px}
.ca-wrap p{color:#ffffff!important;font-size:13px;margin-bottom:14px;opacity:.92}
.ca-step{background:#171B1E!important;border:1px solid #2a3138;border-radius:12px;padding:16px 18px;margin-bottom:14px;color:#ffffff!important}
.ca-step-h,.ca-step-h span{font-weight:600;font-size:16px;color:#ffffff!important;margin-bottom:10px}
.ca-num{color:#FFAD03!important;font-family:monospace;margin-right:8px}
.ca-metric{background:#1f2429!important;border:1px solid #2a3138;border-radius:8px;padding:12px;text-align:center;color:#ffffff!important}
.ca-metric-l{font-size:10px;color:#ffffff!important;opacity:.75;text-transform:uppercase;letter-spacing:.06em}
.ca-metric-v{font-size:22px;font-weight:700;color:#FFAD03!important}
.ca-ok{color:#3ddc97!important}
.ca-warn{color:#FFAD03!important}
.ca-err{color:#ff5d6c!important}
</style>
"""


def _html_path() -> Path:
    return Path(__file__).resolve().parent.parent / "static" / "comparador_comisiones.html"


def render_comparador() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="ca-wrap" style="background:#0d1013;color:#fff;padding:8px 0 24px;border-radius:12px">'
        '<h3 style="color:#FFAD03">Comparador de <span style="color:#FFAD03">comisiones</span> · VIA × Contabilidad</h3>'
        '<p style="color:#fff">Procesa reporte VIA, limpia contabilidad, cruza por SFE y archiva mes a mes en el módulo.</p></div>',
        unsafe_allow_html=True,
    )

    cmp = _cmp()
    cmp.inicializar_tablas_comparador()
    cruzar = cmp.cruzar
    process_via = cmp.process_via
    process_cont = cmp.process_cont
    guardar_cruce = cmp.guardar_cruce
    generar_informe_excel_bytes = cmp.generar_informe_excel_bytes
    generar_via_limpio_bytes = cmp.generar_via_limpio_bytes

    if "cmp_via" not in st.session_state:
        st.session_state.cmp_via = None
    if "cmp_cont" not in st.session_state:
        st.session_state.cmp_cont = None
    if "cmp_cross" not in st.session_state:
        st.session_state.cmp_cross = None

    col_p, col_m = st.columns([1, 3])
    with col_p:
        periodo = st.text_input("Periodo (YYYY-MM)", value=date.today().strftime("%Y-%m"), key="cmp_periodo")
    with col_m:
        titulo = st.text_input(
            "Título del procesamiento",
            placeholder="Ej: Comisiones Marzo 2026 – Cruce con Contabilidad",
            key="cmp_titulo",
        )

    st.markdown(
        '<div class="ca-step" style="background:#171B1E;color:#fff">'
        '<div class="ca-step-h" style="color:#fff"><span class="ca-num" style="color:#FFAD03">01</span> Cargar Comisión VIA</div></div>',
        unsafe_allow_html=True,
    )
    f_via = st.file_uploader("Archivo VIA (.xlsx)", type=["xlsx", "xlsm", "xls"], key="up_via")
    if f_via and st.button("Procesar VIA", key="btn_via"):
        try:
            st.session_state.cmp_via = process_via(BytesIO(f_via.read()))
            st.session_state.cmp_cross = None
            st.success(f"VIA procesado: {st.session_state.cmp_via['kept']} filas con SFE")
        except Exception as e:
            st.error(str(e))

    if st.session_state.cmp_via:
        v = st.session_state.cmp_via
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f'<div class="ca-metric" style="color:#fff"><div class="ca-metric-l" style="color:#fff">Filas crudas</div><div class="ca-metric-v">{v["raw_count"]}</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="ca-metric" style="color:#fff"><div class="ca-metric-l" style="color:#fff">Con SFE</div><div class="ca-metric-v ca-ok">{v["kept"]}</div></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="ca-metric" style="color:#fff"><div class="ca-metric-l" style="color:#fff">SFE únicas</div><div class="ca-metric-v">{v["unique_sfes"]}</div></div>', unsafe_allow_html=True)
        m4.markdown(f'<div class="ca-metric" style="color:#fff"><div class="ca-metric-l" style="color:#fff">Σ Abono</div><div class="ca-metric-v">${v["sum_abono"]:,.0f}</div></div>', unsafe_allow_html=True)
        st.dataframe(_df_via_preview(v), use_container_width=True, hide_index=True, height=220)
        via_bytes, via_name = generar_via_limpio_bytes(v, titulo or "VIA_Limpio")
        st.download_button(
            "⬇️ Descargar VIA limpio (Excel)",
            via_bytes,
            file_name=via_name,
            mime=MIME_XLSX,
            key="dl_via_limpio",
        )

    st.markdown(
        '<div class="ca-step" style="background:#171B1E;color:#fff">'
        '<div class="ca-step-h" style="color:#fff"><span class="ca-num" style="color:#FFAD03">02</span> Cargar Comisiones Contabilidad</div></div>',
        unsafe_allow_html=True,
    )
    f_cont = st.file_uploader("Archivo Contabilidad (.xlsx)", type=["xlsx", "xlsm", "xls"], key="up_cont")
    if f_cont and st.button("Procesar Contabilidad", key="btn_cont"):
        try:
            st.session_state.cmp_cont = process_cont(BytesIO(f_cont.read()))
            st.session_state.cmp_cross = None
            st.success(f"Contabilidad procesada: {len(st.session_state.cmp_cont['clean_rows'])} filas")
        except Exception as e:
            st.error(str(e))

    if st.session_state.cmp_cont:
        c = st.session_state.cmp_cont
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f'<div class="ca-metric" style="color:#fff"><div class="ca-metric-l" style="color:#fff">Filas crudas</div><div class="ca-metric-v">{c["raw_count"]}</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="ca-metric" style="color:#fff"><div class="ca-metric-l" style="color:#fff">Total eliminadas</div><div class="ca-metric-v ca-warn">{c["totals_removed"]}</div></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="ca-metric" style="color:#fff"><div class="ca-metric-l" style="color:#fff">Con SFE</div><div class="ca-metric-v ca-ok">{c["with_sfe"]}</div></div>', unsafe_allow_html=True)
        m4.markdown(f'<div class="ca-metric" style="color:#fff"><div class="ca-metric-l" style="color:#fff">Sin SFE</div><div class="ca-metric-v ca-err">{c["without_sfe"]}</div></div>', unsafe_allow_html=True)
        st.dataframe(_df_cont_preview(c), use_container_width=True, hide_index=True, height=220)

    st.markdown(
        '<div class="ca-step" style="background:#171B1E;color:#fff">'
        '<div class="ca-step-h" style="color:#fff"><span class="ca-num" style="color:#FFAD03">03</span> Cruce, informe Excel y archivo mensual</div></div>',
        unsafe_allow_html=True,
    )
    ready = st.session_state.cmp_via and st.session_state.cmp_cont
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("🔄 Cruzar archivos por SFE", type="primary", disabled=not ready, key="btn_cross"):
            st.session_state.cmp_cross = cruzar(st.session_state.cmp_via, st.session_state.cmp_cont)
            st.rerun()
    with b2:
        if st.button("💾 Guardar en historial mensual", disabled=not st.session_state.cmp_cross, key="btn_save"):
            try:
                r = guardar_cruce(
                    titulo or f"Cruce {periodo}",
                    st.session_state.cmp_via,
                    st.session_state.cmp_cont,
                    st.session_state.cmp_cross,
                    periodo,
                )
                st.success(f"Guardado · Consolidado: `{r['ruta_consolidado']}`")
            except Exception as e:
                st.error(str(e))
    with b3:
        if st.session_state.cmp_cross:
            informe_bytes, informe_name = generar_informe_excel_bytes(
                st.session_state.cmp_via,
                st.session_state.cmp_cont,
                st.session_state.cmp_cross,
                titulo or f"Cruce {periodo}",
                periodo,
            )
            st.download_button(
                "⬇️ Descargar informe Excel completo",
                informe_bytes,
                file_name=informe_name,
                mime=MIME_XLSX,
                type="primary",
                key="dl_informe_cruce",
            )

    if st.session_state.cmp_cross:
        x = st.session_state.cmp_cross
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("En ambos", len(x["both"]))
        m2.metric("Solo VIA", len(x["onlyVia"]))
        m3.metric("Solo Contab.", len(x["onlyCont"]))
        m4.metric("Sin SFE", len(x["noSfe"]))

        tab = st.radio(
            "Ver resultados",
            ["Coincidencias", "Solo VIA", "Solo Contabilidad", "Sin SFE"],
            horizontal=True,
            key="cmp_tab_res",
        )
        if tab == "Coincidencias":
            st.dataframe(pd.DataFrame(x["both"]), use_container_width=True, hide_index=True, height=360)
        elif tab == "Solo VIA":
            st.dataframe(pd.DataFrame(x["onlyVia"]), use_container_width=True, hide_index=True, height=360)
        elif tab == "Solo Contabilidad":
            st.dataframe(pd.DataFrame(x["onlyCont"]), use_container_width=True, hide_index=True, height=360)
        else:
            st.dataframe(pd.DataFrame(x["noSfe"]), use_container_width=True, hide_index=True, height=360)

        if len(x["both"]) == 0:
            st.warning(
                "Sin coincidencias por SFE. Verifique que ambos archivos cubran el mismo periodo "
                "(VIA = facturación; Contabilidad = pagos recaudados)."
            )

        st.caption(
            "El informe Excel incluye: **Resumen**, **VIA Limpio**, **Contabilidad Limpia**, "
            "**En Ambos**, **Solo VIA**, **Solo Contabilidad** y **Sin SFE**."
        )

    html_path = _html_path()
    with st.expander("🌐 Vista HTML completa (standalone en navegador)"):
        if html_path.is_file():
            st.caption(f"Archivo: `{html_path}` — procesamiento 100% en el navegador.")
            if st.button("Abrir comparador HTML", key="open_html"):
                if os.name == "nt":
                    os.startfile(str(html_path))  # noqa: S606
            with open(html_path, encoding="utf-8") as f:
                components.html(f.read(), height=900, scrolling=True)
        else:
            st.info("Use el flujo de arriba; el HTML standalone se genera en dashboard/static/.")


def render_historial() -> None:
    cmp = _cmp()
    listar_periodos = cmp.listar_periodos
    listar_historial = cmp.listar_historial
    carpeta_comisiones = cmp.carpeta_comisiones
    query_resumen_periodo = cmp.query_resumen_periodo

    st.markdown("## Histórico mensual — Cruces VIA × Contabilidad")
    periodos = listar_periodos()
    if not periodos:
        st.info("Aún no hay cruzes guardados. Use el Comparador y pulse **Guardar cruce en historial mensual**.")
        return

    sel_periodo = st.selectbox("Periodo", periodos, key="hist_periodo")
    df = listar_historial(sel_periodo)
    if not df.empty:
        show = df[
            ["id", "titulo", "fecha_cruce", "coincidencias", "solo_via", "solo_cont", "sin_sfe", "ruta_excel", "ruta_consolidado"]
        ].copy()
        show.columns = ["ID", "Título", "Fecha", "Coincidencias", "Solo VIA", "Solo Cont.", "Sin SFE", "Excel", "Consolidado"]
        st.dataframe(show.drop(columns=["ID"]), use_container_width=True, hide_index=True)

        st.subheader("Descargar informes guardados")
        for _, row in df.iterrows():
            cols = st.columns([4, 2, 2])
            cols[0].write(f"**{row['titulo']}** — {str(row['fecha_cruce'])[:16]}")
            ruta = row.get("ruta_excel")
            if ruta and Path(ruta).is_file():
                with open(ruta, "rb") as f:
                    cols[1].download_button(
                        "⬇️ Informe",
                        f.read(),
                        file_name=Path(ruta).name,
                        mime=MIME_XLSX,
                        key=f"dl_hist_{row['id']}",
                    )
            cons = row.get("ruta_consolidado")
            if cons and Path(cons).is_file():
                with open(cons, "rb") as f:
                    cols[2].download_button(
                        "⬇️ Consolidado",
                        f.read(),
                        file_name=Path(cons).name,
                        mime=MIME_XLSX,
                        key=f"dl_cons_{row['id']}",
                    )

    cons_path = carpeta_comisiones() / "consolidado" / sel_periodo / f"CONSOLIDADO_{sel_periodo}.xlsx"
    if cons_path.is_file():
        st.success(f"**Archivo total del mes:** `{cons_path}`")
        with open(cons_path, "rb") as f:
            st.download_button(
                f"⬇️ Descargar CONSOLIDADO {sel_periodo}",
                f.read(),
                file_name=cons_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        resumen = query_resumen_periodo(sel_periodo)
        if resumen:
            st.subheader(f"Resumen de cruzes — {sel_periodo}")
            st.dataframe(pd.DataFrame(resumen), use_container_width=True, hide_index=True)
    else:
        st.caption("El consolidado mensual se crea al guardar el primer cruce del periodo.")

    st.subheader("Todos los periodos")
    df_all = listar_historial()
    if not df_all.empty:
        st.dataframe(
            df_all[["periodo", "titulo", "fecha_cruce", "coincidencias", "ruta_consolidado"]],
            use_container_width=True,
            hide_index=True,
        )


def _df_via_preview(via: dict) -> pd.DataFrame:
    rows = [{h: r.get(h) for h in via["clean_headers"]} for r in via["clean_rows"][:50]]
    return pd.DataFrame(rows)


def _df_cont_preview(cont: dict) -> pd.DataFrame:
    rows = [{h: r.get(h) for h in cont["clean_headers"]} for r in cont["clean_rows"][:50]]
    return pd.DataFrame(rows)
