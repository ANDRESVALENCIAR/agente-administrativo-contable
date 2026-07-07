"""Página CXP/CXC — cuentas por pagar y cobrar."""
from datetime import date

import streamlit as st

from dashboard.utils.db_helper import execute, query_df
from dashboard.utils.reportes import generar_reporte
from modulos.cxp_cxc import preparar_reunion_semanal, sincronizar_cartera_desde_excel


def render() -> None:
    """Renderiza módulo CXP/CXC."""
    st.markdown("## CXP / CXC")
    t1, t2, t3, t4 = st.tabs(["CXC Cobros", "CXP Pagos", "Incapacidades", "Reunión semanal"])

    with t1:
        if st.button("Sincronizar cartera desde Excel"):
            n = sincronizar_cartera_desde_excel()
            st.success(f"{n} cliente(s) sincronizado(s).")
            st.rerun()
        df = query_df("SELECT * FROM cartera_cxc ORDER BY dias_mora DESC")
        if df.empty:
            st.info("Sin cartera. Sincronice desde Excel o agregue un cliente.")
            with st.form("cxc_new"):
                cli = st.text_input("Cliente")
                nit = st.text_input("NIT")
                saldo = st.number_input("Saldo", min_value=0.0)
                dias = st.number_input("Días mora", min_value=0, value=0)
                if st.form_submit_button("Agregar cliente"):
                    execute(
                        "INSERT INTO cartera_cxc (cliente,nit,saldo,dias_mora) VALUES (?,?,?,?)",
                        (cli, nit, saldo, int(dias)),
                    )
                    st.rerun()
        else:
            for _, r in df.iterrows():
                dias = r["dias_mora"]
                sem = "🟢" if dias < 30 else "🟡" if dias < 60 else "🔴"
                c1, c2 = st.columns([4, 1])
                c1.write(f"{sem} {r['cliente']} — ${r['saldo']:,.0f} — {dias}d")
                if c2.button("Gestionar", key=f"gc_{r['id']}"):
                    execute(
                        "UPDATE cartera_cxc SET ultima_gestion=?, notas=? WHERE id=?",
                        (date.today().isoformat(), "Gestión registrada desde dashboard", r["id"]),
                    )
                    st.success("Gestión registrada.")
                    st.rerun()

    with t2:
        df = query_df("SELECT * FROM cxp_programados ORDER BY fecha_pago")
        st.dataframe(df, use_container_width=True, hide_index=True)
        with st.form("cxp_new"):
            prov = st.text_input("Proveedor")
            conc = st.text_input("Concepto")
            monto = st.number_input("Monto", min_value=0.0)
            fp = st.date_input("Fecha pago", date.today())
            pp = st.checkbox("PP confirmado en VIA")
            if st.form_submit_button("Agregar CXP"):
                execute(
                    "INSERT INTO cxp_programados (proveedor,concepto,monto,fecha_pago,pp_via_confirmado) VALUES (?,?,?,?,?)",
                    (prov, conc, monto, fp.isoformat(), 1 if pp else 0),
                )
                st.rerun()

    with t3:
        with st.form("incap"):
            emp = st.text_input("Empleado")
            fi = st.date_input("Fecha inicio", date.today())
            dias = st.number_input("Días", min_value=1, value=1)
            if st.form_submit_button("Registrar"):
                execute(
                    "INSERT INTO incapacidades (empleado,fecha_inicio,dias) VALUES (?,?,?)",
                    (emp, fi.isoformat(), int(dias)),
                )
                st.rerun()
        st.dataframe(query_df("SELECT * FROM incapacidades ORDER BY id DESC"), use_container_width=True)

    with t4:
        if st.button("Generar agenda semanal"):
            preparar_reunion_semanal()
            st.success("Agenda generada y enviada (modo demo si aplica).")
        resumen = query_df(
            "SELECT 'CXP' as tipo, proveedor as nombre, monto as valor FROM cxp_programados "
            "UNION ALL SELECT 'CXC', cliente, saldo FROM cartera_cxc"
        )
        if not resumen.empty and st.button("Exportar resumen Excel"):
            data, nombre = generar_reporte("cxp_cxc", resumen, "excel")
            st.download_button("Descargar", data, nombre)
