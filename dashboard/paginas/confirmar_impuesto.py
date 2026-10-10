"""Pantalla que abre el botón "Ya lo presenté" del correo de impuestos (?presentar=<token>)."""
from datetime import date
from html import escape

import streamlit as st

from dashboard.paginas.confirmar_pago import CSS, _check, _fecha
from dashboard.estilos import LOGO_SVG
from modulos import radar_tributario as rt


def render(token: str) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    rt.inicializar_tablas()
    _, centro, _ = st.columns([1, 2.2, 1])
    with centro:
        st.write("")
        st.markdown(
            f'<div class="sk-brand" style="justify-content:center"><div class="sk-logo">{LOGO_SVG}</div>'
            f'<div><div class="sk-brand-name">Shaki</div><div class="sk-brand-sub">Radar tributario</div></div></div>',
            unsafe_allow_html=True,
        )
        oid = rt.verificar_token(token)
        o = rt.obtener(oid) if oid else None
        if not o:
            st.error("Este enlace no es válido. Abra el panel de Shaki → Impuestos para revisar la declaración.")
            return
        if st.session_state.get(f"ri_ok_{oid}") or o["estado"] == "PRESENTADO":
            st.markdown(
                f'<div class="cf-card cf-ok">{_check()}<div class="cf-title">¡Listo, quedó presentada!</div>'
                f'<div class="cf-sub"><b style="color:#fff">{escape(o["impuesto"])} · {escape(o["periodo"] or "")}</b><br>'
                f'Registrada el {_fecha(str(o["presentado_en"] or date.today().isoformat())[:10])}. '
                f'No recibirás más avisos de esta declaración.</div></div>',
                unsafe_allow_html=True,
            )
            return
        sem = rt.semaforo(o)
        st.markdown(
            f'<div class="cf-card"><div class="cf-eyebrow">PENDIENTE DE PRESENTACIÓN · {sem} · {escape(o["entidad"])}</div>'
            f'<div class="cf-title">{escape(o["impuesto"])}</div>'
            f'<div class="cf-sub">{escape(o["periodo"] or "")}</div>'
            f'<div class="cf-grid">'
            f'<div><span>Vence</span><b>{_fecha(o["fecha_limite"])}</b></div>'
            f'<div><span>Formulario</span><b>{escape(o["formulario"] or "—")}</b></div>'
            f'<div><span>Tipo</span><b>{escape(o["tipo"] or "—")}</b></div>'
            f'<div><span>NIT</span><b>{escape(rt.cfg.NIT_EMPRESA)}</b></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        with st.form("ri_form"):
            ref = st.text_input("Número de formulario o radicado (opcional)")
            ok = st.form_submit_button("Confirmar: ya lo presenté", width="stretch")
        if ok:
            if rt.marcar_presentado(oid, por="enlace de alerta", referencia=ref or None).get("ok"):
                st.session_state[f"ri_ok_{oid}"] = True
                st.rerun()
            st.error("No se pudo registrar. Intente de nuevo o márquelo en el panel.")
        st.caption("Al confirmar, el agente la marca PRESENTADA en el radar tributario.")
