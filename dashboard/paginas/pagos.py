"""Página Pagos — dashboard diario e historial."""
from datetime import date

import streamlit as st

from dashboard.utils.db_helper import execute, query_df
from database import aprobar_pago, obtener_pagos_pendientes, rechazar_pago
from modulos.pagos import registrar_pago_ejecutado, revisar_cxp_diario


def render() -> None:
    """Renderiza módulo pagos."""
    st.markdown("## Pagos")
    hoy = date.today().isoformat()
    if "pagos_alerta_dia" not in st.session_state:
        st.session_state.pagos_alerta_dia = ""
    if st.session_state.pagos_alerta_dia != hoy:
        urgentes = query_df(
            "SELECT * FROM pagos_pendientes WHERE estado='PENDIENTE' AND prioridad IN ('VENCIDO','HOY')"
        )
        if not urgentes.empty:
            st.warning(f"⚠️ {len(urgentes)} pago(s) urgente(s) para hoy.")
        st.session_state.pagos_alerta_dia = hoy

    t1, t2, t3 = st.tabs(["Pendientes aprobación", "Registrar pago", "Historial"])

    with t1:
        pagos = obtener_pagos_pendientes()
        if not pagos:
            st.info("No hay pagos pendientes.")
        for pago in pagos:
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            c1.write(f"**{pago[2]}** — {pago[3]} · Vence {pago[5]}")
            c2.metric("Monto", f"${pago[4]:,.0f}")
            c3.write(pago[7] or "")
            with c4:
                if st.button("✅", key=f"ap_{pago[0]}"):
                    aprobar_pago(pago[0])
                    st.rerun()
                if st.button("❌", key=f"re_{pago[0]}"):
                    rechazar_pago(pago[0])
                    st.rerun()

    with t2:
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

    with t3:
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

    st.subheader("Nómina y comisiones del período")
    st.checkbox("Nómina revisada", key="nom_ok")
    st.checkbox("Comisiones liquidadas", key="com_ok")
