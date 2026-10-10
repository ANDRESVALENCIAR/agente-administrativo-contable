"""Página Pagos — CONTROL DE PAGOS (Excel) + aprobación + historial."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from config import en_modo_demo
from database_modulos import (
    guardar_checklist_pagos_periodo,
    obtener_checklist_pagos_periodo,
)
from modulos.pagos import (
    aprobar_pago_control,
    actualizar_valor_a_pagar,
    crear_pago_manual,
    exportar_pagos_filtrados_excel,
    listar_proveedores,
    marcar_pago_ejecutado,
    query_pagos,
    rechazar_pago_control,
    revision_nomina,
)
from core.formato_col import dia_semana_es
from utils.sync_pagos import (
    CENTROS_COSTO,
    PERIODICIDADES,
    programar_tareas_calendario_pagos,
    ruta_excel_pagos,
    sincronizar_bidireccional,
)

COLORES_ESTADO = {
    "PENDIENTE": "#8E8E93",
    "URGENTE": "#FF9F0A",
    "HOY": "#FF9F0A",
    "VENCIDO": "#FF453A",
    "APROBADO": "#0071E3",
    "PAGADO": "#30D158",
    "RECHAZADO": "#8E8E93",
}

CSS = """
<style>
.pg-card{border:1px solid #1F2024;border-radius:16px;padding:16px 18px;margin-bottom:10px;background:#0F1012;color:#E8E8EA}
.pg-badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:700;color:#fff;margin-left:6px}
.pg-chip{display:inline-block;background:#1F2024;color:#C4C4CC;padding:2px 8px;border-radius:999px;font-size:11px;margin-right:4px}
.pg-muted{color:#8B8B93;font-size:13px}
.pg-money{font-size:22px;font-weight:300;letter-spacing:-0.02em;color:#FFFFFF}
</style>
"""


def _periodo_actual() -> str:
    return date.today().strftime("%Y-%m")


def _fmt_money(v) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return "—"
    try:
        return f"${float(v):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def _badge(estado: str) -> str:
    color = COLORES_ESTADO.get(estado, "#8E8E93")
    return f'<span class="pg-badge" style="background:{color}">{estado}</span>'


def _enrich(detalle: str) -> dict:
    try:
        from utils.estandarizar_gastos import lookup_gasto_por_detalle

        return lookup_gasto_por_detalle(detalle) or {}
    except Exception:
        return {}


def _tarjeta_html(num: int, row: dict) -> str:
    prov = row.get("proveedor") or "Sin proveedor"
    det = row.get("detalle") or ""
    fl = row.get("fecha_limite") or ""
    estado = row.get("estado") or "PENDIENTE"
    centro = row.get("centro_costos") or ""
    per = row.get("periodicidad") or ""
    obs = row.get("observaciones") or ""
    monto = _fmt_money(row.get("valor_a_pagar"))
    obs_html = f'<div class="pg-muted">{obs}</div>' if obs else ""
    info = _enrich(det)
    cat_chip = ""
    per_chip = f'<span class="pg-chip">{per}</span>' if per else ""
    if info:
        color = info.get("categoria_color") or "#AEAEB2"
        cat_chip = (
            f'<span class="pg-chip" style="background:{color};color:#fff">'
            f'{info.get("categoria_icono","")} {info.get("categoria_label") or info.get("categoria")}</span>'
        )
        per_chip = (
            f'<span class="pg-chip">{info.get("periodicidad_icono","")} '
            f'{info.get("periodicidad_label") or info.get("periodicidad_std") or per}</span>'
        )
    return f"""
    <div class="pg-card">
      <div><strong>#{num}</strong> <strong>{prov}</strong> {_badge(estado)}</div>
      <div class="pg-muted">{det}</div>
      <div style="margin-top:6px">Vence <strong>{fl}</strong>
        <span class="pg-chip">{centro}</span>
        {cat_chip}
        {per_chip}
      </div>
      <div class="pg-money" style="margin-top:6px">{monto}</div>
      {obs_html}
    </div>
    """


def render() -> None:
    from dashboard.paginas import pagos_control, pagos_hoy_semana

    st.markdown("## Pagos")
    t_hoy, t_semana, t_control, t_anterior = st.tabs(
        ["Hoy", "Semana", "Control de pagos", "Archivo anterior (CONTROL DE PAGOS)"]
    )
    with t_hoy:
        pagos_hoy_semana.render_hoy()
    with t_semana:
        pagos_hoy_semana.render_semana()
    with t_control:
        pagos_control.render()
    with t_anterior:
        _render_anterior()


def _render_anterior() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    excel_path = ruta_excel_pagos()
    st.caption(f"Fuente: `{excel_path.name}` · hoja CONTROL DE PAGOS")

    periodo = _periodo_actual()
    hoy = date.today()

    # Banner urgentes
    urg = query_pagos(estados=["VENCIDO", "HOY", "URGENTE"])
    n_hoy_venc = len(urg[urg["estado"].isin(["HOY", "VENCIDO"])]) if not urg.empty else 0
    if n_hoy_venc:
        st.warning(f"⚠️ {n_hoy_venc} pago(s) urgente(s) para hoy / vencidos")

    t1, t2, t3, t4 = st.tabs(
        [
            "Pendientes aprobación",
            "Aprobados (por pagar)",
            "Registrar pago",
            "Historial",
        ]
    )

    with t1:
        _tab_pendientes(hoy)

    with t2:
        _tab_aprobados()

    with t3:
        _tab_registrar()

    with t4:
        _tab_historial()

    st.divider()
    st.subheader(f"Nómina y comisiones — período {periodo}")
    checklist = obtener_checklist_pagos_periodo(periodo)
    c1, c2, c3, c4 = st.columns(4)
    nom_ok = c1.checkbox("Nómina revisada", value=checklist.get("nomina_revisada", False), key="pg_nom")
    com_ok = c2.checkbox(
        "Comisiones liquidadas", value=checklist.get("comisiones_liquidadas", False), key="pg_com"
    )
    ss_ok = c3.checkbox(
        "Aportes seguridad social pagados",
        value=checklist.get("aportes_ss_pagados", False),
        key="pg_ss",
    )
    ret_ok = c4.checkbox(
        "Retención en la fuente calculada",
        value=checklist.get("retencion_fuente_calculada", False),
        key="pg_ret",
    )
    b1, b2 = st.columns(2)
    if b1.button("Guardar checklist del período", key="pg_chk_save"):
        guardar_checklist_pagos_periodo(
            nom_ok,
            com_ok,
            periodo,
            aportes_ss_pagados=ss_ok,
            retencion_fuente_calculada=ret_ok,
        )
        st.success(f"Checklist {periodo} guardado.")
    if b2.button("Ejecutar revisión de nómina (IA)", key="pg_nom_ia"):
        if en_modo_demo():
            st.info("Active la API key para usar esta función")
        else:
            with st.spinner("Revisando nómina..."):
                msg = revision_nomina()
            if msg == "Active la API key para usar esta función":
                st.info(msg)
            else:
                st.success("Revisión de nómina ejecutada.")
                st.write(msg)


def _tab_pendientes(hoy: date) -> None:
    from datetime import timedelta

    df_u = query_pagos(estados=["VENCIDO", "HOY", "URGENTE"])
    df_p = query_pagos(estados=["PENDIENTE"], proximos_dias=7)

    # Vencidos históricos: solo últimos 90 días en tarjetas (el resto va a tabla)
    corte = (hoy - timedelta(days=90)).isoformat()
    if not df_u.empty:
        urg_hoy = df_u[df_u["estado"].isin(["HOY", "URGENTE"])]
        venc = df_u[df_u["estado"] == "VENCIDO"]
        venc_recientes = venc[venc["fecha_limite"] >= corte] if not venc.empty else venc
        venc_viejos = venc[venc["fecha_limite"] < corte] if not venc.empty else venc
        df_cards = pd_concat_unique(urg_hoy, venc_recientes)
        df_cards = pd_concat_unique(df_cards, df_p)
    else:
        df_cards = df_p
        venc_viejos = df_u

    n_venc_total = 0 if df_u.empty else int((df_u["estado"] == "VENCIDO").sum())
    st.caption(
        f"Tarjetas: urgentes / hoy / vencidos ≤90 días / pendientes 7d. "
        f"Vencidos históricos totales: {n_venc_total}."
    )

    if df_cards.empty and (venc_viejos is None or getattr(venc_viejos, "empty", True)):
        st.info("No hay pagos pendientes de aprobación en la ventana urgente / 7 días.")
        return

    max_cards = 40
    for i, (_, row) in enumerate(df_cards.head(max_cards).iterrows(), start=1):
        r = row.to_dict()
        pid = int(r["id"])
        st.markdown(_tarjeta_html(i, r), unsafe_allow_html=True)
        cols = st.columns([2, 1, 1, 2])
        val = r.get("valor_a_pagar")
        if val is None or (isinstance(val, float) and pd.isna(val)):
            nuevo_val = cols[0].number_input(
                "Valor a pagar",
                min_value=0.0,
                step=1000.0,
                key=f"val_{pid}",
                label_visibility="collapsed",
            )
            if cols[0].button("💾 Guardar valor", key=f"sv_{pid}"):
                actualizar_valor_a_pagar(pid, float(nuevo_val))
                st.rerun()
        if cols[1].button("✅ APROBAR", key=f"ap_{pid}"):
            aprobar_pago_control(pid)
            st.rerun()
        motivo = cols[3].text_input(
            "Motivo rechazo",
            key=f"mot_{pid}",
            label_visibility="collapsed",
            placeholder="Motivo (si rechaza)",
        )
        if cols[2].button("❌ RECHAZAR", key=f"re_{pid}"):
            rechazar_pago_control(pid, comentario=motivo or "")
            st.rerun()

    if len(df_cards) > max_cards:
        st.info(f"Mostrando {max_cards} de {len(df_cards)} en tarjetas. Use Historial para el resto.")

    if venc_viejos is not None and not getattr(venc_viejos, "empty", True):
        with st.expander(f"Vencidos históricos (>90 días): {len(venc_viejos)}"):
            st.dataframe(
                venc_viejos[
                    [
                        c
                        for c in [
                            "fecha_limite",
                            "detalle",
                            "proveedor",
                            "centro_costos",
                            "valor_a_pagar",
                            "estado",
                        ]
                        if c in venc_viejos.columns
                    ]
                ].head(500),
                use_container_width=True,
                hide_index=True,
            )


def pd_concat_unique(a, b):
    import pandas as pd

    if a.empty:
        return b
    if b.empty:
        return a
    out = pd.concat([a, b], ignore_index=True)
    return out.drop_duplicates(subset=["id"]).sort_values(["fecha_limite", "prioridad"])


def _tab_aprobados() -> None:
    df = query_pagos(estados=["APROBADO"])
    if df.empty:
        st.info("No hay pagos aprobados pendientes de ejecución.")
        return
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        r = row.to_dict()
        pid = int(r["id"])
        st.markdown(_tarjeta_html(i, r), unsafe_allow_html=True)
        with st.expander(f"Marcar como PAGADO — #{pid}", expanded=False):
            with st.form(f"pay_{pid}"):
                fp = st.date_input("Fecha de pago", date.today(), key=f"fp_{pid}")
                default_val = float(r["valor_a_pagar"] or 0)
                vp = st.number_input("Valor pagado", min_value=0.0, value=default_val, step=1000.0)
                cta = st.text_input("Cuenta origen/destino", value=r.get("cuenta_origen_destino") or "")
                ref = st.text_input("Referencia / Pago total", value=r.get("pago_total") or "")
                if st.form_submit_button("✅ Marcar como PAGADO", type="primary"):
                    ok = marcar_pago_ejecutado(
                        pid,
                        fp.isoformat(),
                        valor_pagado=vp,
                        cuenta=cta or None,
                        referencia=ref or None,
                    )
                    if ok:
                        st.success("Pago marcado y sincronizado al Excel.")
                        st.rerun()
                    else:
                        st.error("No se pudo marcar el pago.")


def _tab_registrar() -> None:
    proveedores = listar_proveedores()
    with st.form("reg_pago_nuevo"):
        detalle = st.text_input("Detalle *")
        prov_sel = st.selectbox("Proveedor (existente)", ["(nuevo)"] + proveedores)
        prov_nuevo = st.text_input("Proveedor nuevo (si aplica)")
        proveedor = prov_nuevo.strip() if prov_sel == "(nuevo)" else prov_sel
        centro = st.selectbox("Centro de costos", CENTROS_COSTO)
        fl = st.date_input("Fecha límite", date.today())
        valor = st.number_input("Valor a pagar (COP)", min_value=0.0, step=1000.0)
        periodicidad = st.selectbox("Periodicidad", PERIODICIDADES)
        periodo = st.text_input("Período", placeholder="Ej: JULIO 2026")
        observaciones = st.text_area("Observaciones")
        cuenta = st.text_input("Cuenta origen/destino")
        prioridad = st.radio("Prioridad", [1, 4], format_func=lambda x: "1 = Alta" if x == 1 else "4 = Normal", horizontal=True)
        c1, c2 = st.columns(2)
        guardar = c1.form_submit_button("GUARDAR")
        guardar_ap = c2.form_submit_button("GUARDAR Y APROBAR", type="primary")
        if guardar or guardar_ap:
            if not detalle.strip():
                st.error("Detalle es obligatorio.")
            else:
                pid = crear_pago_manual(
                    {
                        "detalle": detalle.strip(),
                        "proveedor": proveedor or None,
                        "centro_costos": centro,
                        "fecha_limite": fl,
                        "valor_a_pagar": valor or None,
                        "periodicidad": periodicidad,
                        "periodo": periodo or None,
                        "anio": fl.year,
                        "observaciones": observaciones or None,
                        "cuenta_origen_destino": cuenta or None,
                        "prioridad": prioridad,
                        "dia_semana": dia_semana_es(fl).upper(),
                    },
                    aprobar=bool(guardar_ap),
                )
                st.success(f"Pago #{pid} registrado" + (" y aprobado." if guardar_ap else "."))


def _tab_historial() -> None:
    from modulos.catalogos_gastos import CATEGORIAS_GASTO, PERIODICIDADES_STD
    from utils.estandarizar_gastos import lookup_gasto_por_detalle

    cats_std = [c[0] for c in CATEGORIAS_GASTO]
    pers_std = [p[0] for p in PERIODICIDADES_STD]

    c1, c2, c3, c4, c5 = st.columns(5)
    centros = c1.multiselect("Centro de costos", CENTROS_COSTO, key="hist_cc")
    estados = c2.multiselect(
        "Estado",
        ["PAGADO", "PENDIENTE", "VENCIDO", "HOY", "URGENTE", "APROBADO", "RECHAZADO"],
        key="hist_est",
    )
    pers = c3.multiselect("Periodicidad Excel", PERIODICIDADES, key="hist_per")
    rango = c4.date_input("Rango fechas", value=[], key="hist_rango")
    prov = c5.text_input("Proveedor", key="hist_prov")

    c6, c7 = st.columns(2)
    cat_f = c6.multiselect("Categoría (estándar)", cats_std, key="hist_cat_std")
    per_std_f = c7.multiselect("Periodicidad estándar", pers_std, key="hist_per_std")

    fecha_desde = fecha_hasta = None
    if isinstance(rango, (list, tuple)) and len(rango) == 2:
        fecha_desde, fecha_hasta = rango[0].isoformat(), rango[1].isoformat()

    df = query_pagos(
        estados=estados or None,
        centros=centros or None,
        periodicidades=pers or None,
        proveedor=prov or None,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    if not df.empty:
        enrich_rows = []
        for _, r in df.iterrows():
            info = lookup_gasto_por_detalle(r.get("detalle") or "") or {}
            enrich_rows.append(
                {
                    "categoria_std": info.get("categoria"),
                    "periodicidad_std": info.get("periodicidad_std"),
                }
            )
        enr = pd.DataFrame(enrich_rows)
        df = pd.concat([df.reset_index(drop=True), enr], axis=1)
        if cat_f:
            df = df[df["categoria_std"].isin(cat_f)]
        if per_std_f:
            df = df[df["periodicidad_std"].isin(per_std_f)]

    show_cols = [
        "fecha_limite",
        "detalle",
        "proveedor",
        "centro_costos",
        "valor_a_pagar",
        "valor_pagado",
        "fecha_pago",
        "estado",
        "periodicidad",
        "categoria_std",
        "periodicidad_std",
    ]
    if not df.empty:
        st.dataframe(df[[c for c in show_cols if c in df.columns]], use_container_width=True, hide_index=True)
        total_apagar = float(df["valor_a_pagar"].fillna(0).sum())
        total_pagado = float(df["valor_pagado"].fillna(0).sum())
        m1, m2, m3 = st.columns(3)
        m1.metric("Total valor a pagar", _fmt_money(total_apagar))
        m2.metric("Total valor pagado", _fmt_money(total_pagado))
        m3.metric("Diferencia (pendiente)", _fmt_money(total_apagar - total_pagado))
    else:
        st.info("Sin registros con los filtros actuales.")

    b1, b2 = st.columns(2)
    if b1.button("Exportar Excel", key="hist_exp"):
        data = exportar_pagos_filtrados_excel(df if not df.empty else df)
        st.download_button(
            "⬇️ Descargar filtrado",
            data,
            file_name=f"pagos_filtrados_{date.today().isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="hist_dl",
        )
    if b2.button("Sincronizar CXP desde Excel/agente", key="hist_sync"):
        with st.spinner("Sincronizando CONTROL DE PAGOS..."):
            try:
                res = sincronizar_bidireccional()
                programar_tareas_calendario_pagos()
                st.success(
                    f"Sync OK · nuevos={res.get('nuevos',0)} · "
                    f"actualizados={res.get('actualizados',0)} · "
                    f"exportados={res.get('exportados',0)}"
                )
                st.rerun()
            except Exception as e:
                st.error(str(e))
