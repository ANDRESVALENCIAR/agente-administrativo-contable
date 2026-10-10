"""Pantalla que abre el botón "Ya lo pagué" del correo / WhatsApp (?pagar=<token>)."""
from datetime import date
from html import escape

import streamlit as st

from dashboard.estilos import LOGO_SVG
from modulos import control_pagos as cp

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]
_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

CSS = """
<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] { display: none !important; }
.cf-card { background: #0F1012; border: 1px solid #1F2024; border-radius: 22px; padding: 28px; }
.cf-eyebrow { font-size: 11px; letter-spacing: .1em; color: #FF6A3D; font-family: 'Geist Mono', monospace; }
.cf-title { font-size: 26px; font-weight: 500; color: #FFFFFF; margin: 8px 0 6px 0; letter-spacing: -0.02em; }
.cf-sub { font-size: 14px; color: #A1A1AA; line-height: 1.6; }
.cf-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; background: #1F2024;
           border: 1px solid #1F2024; border-radius: 14px; overflow: hidden; margin: 18px 0 6px 0; }
.cf-grid div { background: #0A0B0D; padding: 12px 14px; }
.cf-grid span { display: block; font-size: 11px; color: #8B8B93; margin-bottom: 4px; }
.cf-grid b { font-size: 14px; color: #E8E8EA; font-weight: 500; }
.cf-ok { text-align: center; padding: 18px 0 6px 0; }
.cf-check { width: 64px; height: 64px; border-radius: 50%; background: #4ADE80; display: inline-flex;
            align-items: center; justify-content: center; margin-bottom: 14px; }
</style>
"""


def _fecha(d: str) -> str:
    f = date.fromisoformat(str(d))
    return f"{_DIAS[f.weekday()].capitalize()} {f.day} de {_MESES[f.month - 1]}"


def _marca() -> None:
    st.markdown(
        f'<div class="sk-brand" style="justify-content:center"><div class="sk-logo">{LOGO_SVG}</div>'
        f'<div><div class="sk-brand-name">Shaki</div><div class="sk-brand-sub">Control de pagos</div></div></div>',
        unsafe_allow_html=True,
    )


def _check() -> str:
    return ('<div class="cf-check"><svg aria-hidden="true" width="30" height="30" viewBox="0 0 24 24" fill="none" '
            'stroke="#0A0B0D" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M5 12.5l4.5 4.5L19 7.5"></path></svg></div>')


def render(token: str) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    cp.inicializar_tablas()
    _, centro, _ = st.columns([1, 2.2, 1])
    with centro:
        st.write("")
        _marca()
        pid = cp.verificar_token(token)
        p = cp.obtener(pid) if pid else None
        if not p:
            st.error("Este enlace no es válido o ya no existe. Abra el panel de Shaki para revisar el pago.")
            return

        hecho = st.session_state.get(f"cf_ok_{pid}") or p["estado"] == "PAGADO"
        verbo = "pagado" if p["tipo"] == "PAGO" else "hecho"
        if hecho:
            st.markdown(
                f'<div class="cf-card cf-ok">{_check()}'
                f'<div class="cf-title">¡Listo, quedó al día!</div>'
                f'<div class="cf-sub"><b style="color:#fff">{escape(p["detalle"] or "")}</b><br>'
                f'Marcado como {verbo} el {_fecha(p["fecha_pago_real"] or date.today().isoformat())}. '
                f'Ya no recibirás más avisos de esta cuota.</div></div>',
                unsafe_allow_html=True,
            )
            if p.get("excel_pendiente"):
                st.caption("El Excel estaba abierto; el agente lo actualizará apenas se cierre.")
            return

        sem = cp.semaforo(p)
        etiqueta = {"VENCIDO": "VENCIDO · PENDIENTE DE PAGO", "HOY": "VENCE HOY · PENDIENTE DE PAGO",
                    "MAÑANA": "VENCE MAÑANA · PENDIENTE DE PAGO"}.get(sem, "PENDIENTE DE PAGO")
        valor = f"${p['valor']:,.0f}".replace(",", ".") if p.get("valor") else "Por definir"
        st.markdown(
            f'<div class="cf-card"><div class="cf-eyebrow">{etiqueta}</div>'
            f'<div class="cf-title">{escape(p["detalle"] or "")}</div>'
            f'<div class="cf-sub">{escape(p["proveedor"] or "")}</div>'
            f'<div class="cf-grid">'
            f'<div><span>Fecha de pago</span><b>{_fecha(p["fecha_sugerida"])}</b></div>'
            f'<div><span>Valor</span><b>{valor}</b></div>'
            f'<div><span>Referencia</span><b>{escape(p["referencia"] or "—")}</b></div>'
            f'<div><span>Centro de costos</span><b>{escape(p["centro_costos"] or "—")}</b></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        with st.form("cf_form"):
            c1, c2 = st.columns(2)
            monto = c1.number_input("Valor pagado (opcional)", min_value=0.0, step=1000.0,
                                    value=float(p["valor"] or 0), format="%.0f")
            ref = c2.text_input("Referencia / comprobante (opcional)")
            enviar = st.form_submit_button(
                "Confirmar: ya lo pagué" if p["tipo"] == "PAGO" else "Confirmar: ya lo hice",
                width="stretch",
            )
        if enviar:
            res = cp.marcar_pagado(pid, por="enlace de alerta", valor=monto or None, referencia=ref or None)
            if res.get("ok"):
                st.session_state[f"cf_ok_{pid}"] = True
                st.rerun()
            st.error("No se pudo registrar el pago. Intente de nuevo o márquelo en el panel.")
        st.caption("Al confirmar, el agente lo marca PAGADO en el panel y en el Excel de control de pagos.")
