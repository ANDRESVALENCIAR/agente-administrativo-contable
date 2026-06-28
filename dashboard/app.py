"""
Dashboard AGENTE ADMIN SHAKI — EIF SAS
Ejecutar: streamlit run dashboard/app.py
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import cfg, en_modo_demo
from dashboard.chat import chat_responder
from dashboard.estilos import CSS
from dashboard.paginas import (
    alertas,
    comisiones,
    contabilidad,
    correos,
    creditos,
    cxp_cxc,
    documentos,
    estadisticas,
    impuestos,
    inicio,
    juridico,
    pagos,
    personal,
    presupuesto,
)
from dashboard.utils.alertas_globales import verificar_alertas_globales
from core.db_sqlalchemy import get_engine
from core.registro_libs import librerias_disponibles
from database import cargar_datos_demo, inicializar_db, obtener_estadisticas_hoy

PAGINAS = {
    "🏠 Inicio": inicio.render,
    "🔔 Alertas": alertas.render,
    "📒 Contabilidad": contabilidad.render,
    "🧾 Impuestos": impuestos.render,
    "📋 CXP/CXC": cxp_cxc.render,
    "💳 Pagos": pagos.render,
    "📧 Correos": correos.render,
    "🤝 Créditos": creditos.render,
    "💰 Comisiones": comisiones.render,
    "👤 Personal": personal.render,
    "📊 Presupuesto": presupuesto.render,
    "⚖️ Jurídico": juridico.render,
    "📄 Documentos": documentos.render,
    "📈 Estadísticas": estadisticas.render,
}

st.set_page_config(
    page_title=f"AGENTE ADMIN SHAKI · {cfg.NOMBRE_EMPRESA}",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(CSS, unsafe_allow_html=True)
inicializar_db()
get_engine()
if en_modo_demo():
    cargar_datos_demo()

if "alertas_verificadas" not in st.session_state:
    verificar_alertas_globales()
    st.session_state.alertas_verificadas = True

if "chat_historial" not in st.session_state:
    st.session_state.chat_historial = []
if "chat_mensajes_ui" not in st.session_state:
    st.session_state.chat_mensajes_ui = [
        {
            "rol": "agent",
            "texto": (
                f"Buenos días. Soy AGENTE ADMIN SHAKI de {cfg.NOMBRE_EMPRESA}. "
                "Puedo ayudarte con alertas, pagos, impuestos, créditos y más. ¿En qué te ayudo?"
            ),
        }
    ]

stats = obtener_estadisticas_hoy()

with st.sidebar:
    st.markdown("### 🤖 AGENTE ADMIN SHAKI")
    st.markdown(f"**{cfg.NOMBRE_EMPRESA}**")
    modo = "Demo" if en_modo_demo() else "Producción"
    st.markdown(f'<p class="status-active">● Activo · {modo}</p>', unsafe_allow_html=True)
    st.divider()
    pagina = st.radio("Navegación", list(PAGINAS.keys()), label_visibility="collapsed")
    st.divider()
    st.caption(f"Costo API hoy: **${stats['costo_hoy']}**")
    st.caption(f"Costo API mes: **${stats['costo_mes']}**")
    libs_ok = sum(1 for v in librerias_disponibles().values() if v)
    st.caption(f"Librerías core: **{libs_ok}** activas")

col_dashboard, col_chat = st.columns([2, 1])

with col_dashboard:
    PAGINAS[pagina]()

with col_chat:
    st.markdown("### 💬 Chat — AGENTE ADMIN SHAKI")
    for msg in st.session_state.chat_mensajes_ui[-15:]:
        css = "chat-msg-user" if msg["rol"] == "user" else "chat-msg-agent"
        st.markdown(f'<div class="{css}">{msg["texto"]}</div>', unsafe_allow_html=True)

    st.divider()
    preguntas = [
        "¿Qué alertas hay hoy?",
        "Pagos pendientes",
        "Verificar alertas",
        "Procesar correos",
        "Cartera en mora",
        "Impuestos próximos",
        "¿Qué puedes hacer?",
    ]
    q1, q2, q3 = st.columns(3)
    cols = [q1, q2, q3]
    for i, p in enumerate(preguntas):
        col = cols[i % 3]
        if col.button(p, key=f"qr_{i}", use_container_width=True):
            st.session_state.chat_mensajes_ui.append({"rol": "user", "texto": p})
            with st.spinner("Consultando..."):
                r, st.session_state.chat_historial = chat_responder(p, st.session_state.chat_historial)
            st.session_state.chat_mensajes_ui.append({"rol": "agent", "texto": r})
            st.rerun()

    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("Mensaje", placeholder="Escribe aquí...", label_visibility="collapsed")
        if st.form_submit_button("Enviar →", use_container_width=True) and user_input.strip():
            st.session_state.chat_mensajes_ui.append({"rol": "user", "texto": user_input})
            with st.spinner("Consultando..."):
                r, st.session_state.chat_historial = chat_responder(user_input, st.session_state.chat_historial)
            st.session_state.chat_mensajes_ui.append({"rol": "agent", "texto": r})
            st.rerun()
