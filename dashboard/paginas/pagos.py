"""Página Pagos — dashboard diario e historial."""
from datetime import date

import streamlit as st

from dashboard.utils.db_helper import execute, query_df
from database import aprobar_pago, obtener_pagos_aprobados, obtener_pagos_pendientes, rechazar_pago
from database_modulos import (
    guardar_checklist_pagos_periodo,
    obtener_checklist_pagos_periodo,
)
from modulos.pagos import registrar_pago_ejecutado, revisar_cxp_diario, revision_nomina


def _periodo_actual() -> str:
    return date.today().strftime("%Y-%m")


def render() -> None:
    """Renderiza módulo pagos."""
    st.markdown("## Pagos")
    hoy = date.today().isoformat()
    periodo = _periodo_actual()
    if "pagos_alerta_dia" not in st.session_state:
        st.session_state.pagos_alerta_dia = ""
    if st.session_state.pagos_alerta_dia != hoy:
        urgentes = query_df(
            "SELECT * FROM pagos_pendientes WHERE estado='PENDIENTE' AND prioridad IN ('VENCIDO','HOY')"
        )
        if not urgentes.empty:
            st.warning(f"⚠️ {len(urgentes)} pago(s) urgente(s) para hoy.")
        st.session_state.pagos_alerta_dia = hoy

    t1, t2, t3, t4 = st.tabs(
        ["Pendientes aprobación", "Aprobados (por pagar)", "Registrar pago", "Historial"]
    )

    with t1:
        pagos = obtener_pagos_pendientes()
        if not pagos:
            st.info("No hay pagos pendientes.")
        for pago in pagos:
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            c1.write(f"**#{pago[0]} {pago[2]}** — {pago[3]} · Vence {pago[5]}")
            c2.metric("Monto", f"${pago[4]:,.0f}")
            c3.write(pago[7] or "")
            with c4:
                if st.button("✅", key=f"ap_{pago[0]}", help="Aprobar"):
                    aprobar_pago(pago[0])
                    st.rerun()
                if st.button("❌", key=f"re_{pago[0]}", help="Rechazar"):
                    rechazar_pago(pago[0])
                    st.rerun()

    with t2:
        aprobados = obtener_pagos_aprobados()
        if not aprobados:
            st.info("No hay pagos aprobados pendientes de ejecución bancaria.")
        for pago in aprobados:
            with st.expander(f"#{pago[0]} {pago[2]} — ${pago[4]:,.0f}", expanded=False):
                st.caption(f"{pago[3]} · Vence {pago[5]} · Prioridad {pago[7]}")
                with st.form(f"ejecutar_{pago[0]}"):
                    fp = st.date_input("Fecha pago", date.today(), key=f"fp_{pago[0]}")
                    ref = st.text_input("Referencia comprobante", key=f"ref_{pago[0]}")
                    if st.form_submit_button("Marcar como pagado"):
                        if not ref.strip():
                            st.error("Indique la referencia del comprobante.")
                        elif registrar_pago_ejecutado(pago[0], fp.isoformat(), ref.strip()):
                            st.success("Pago registrado en historial y marcado como PAGADO.")
                            st.rerun()
                        else:
                            st.error("No se pudo registrar el pago.")

    with t3:
        with st.form("reg_pago"):
            prov = st.text_input("Proveedor")
            conc = st.text_input("Concepto")
            val = st.number_input("Valor", min_value=0.0)
            fp = st.date_input("Fecha pago", date.today())
            comp = st.text_input("Referencia comprobante")
            if st.form_submit_button("Registrar pago ejecutado"):
                execute(
                    "INSERT INTO historial_pagos (proveedor,concepto,valor,fecha_pago,comprobante) VALUES (?,?,?,?,?)",
                    (prov, conc, val, fp.isoformat(), comp),
                )
                st.success("Pago registrado.")

    with t4:
        df = query_df("SELECT * FROM historial_pagos ORDER BY id DESC LIMIT 100")
        f1, f2 = st.columns(2)
        prov_f = f1.text_input("Filtrar proveedor")
        if prov_f:
            df = df[df["proveedor"].str.contains(prov_f, case=False, na=False)]
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    if st.button("Sincronizar CXP desde Excel/agente"):
        revisar_cxp_diario()
        st.success("CXP actualizado.")

    st.subheader(f"Nómina y comisiones — período {periodo}")
    checklist = obtener_checklist_pagos_periodo(periodo)
    c1, c2 = st.columns(2)
    nom_ok = c1.checkbox("Nómina revisada", value=checklist["nomina_revisada"], key="nom_ok")
    com_ok = c2.checkbox(
        "Comisiones liquidadas", value=checklist["comisiones_liquidadas"], key="com_ok"
    )
    if st.button("Guardar checklist del período"):
        guardar_checklist_pagos_periodo(nom_ok, com_ok, periodo)
        st.success(f"Checklist {periodo} guardado.")
    if st.button("Ejecutar revisión de nómina (IA)"):
        revision_nomina()
        st.success("Revisión de nómina enviada a RRHH/contabilidad.")
