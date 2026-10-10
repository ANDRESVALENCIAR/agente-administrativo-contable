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
from dashboard.estilos import CSS, LOGO_SVG
from dashboard.paginas import (
    alertas,
    calendario,
    comisiones,
    contabilidad,
    correos,
    creditos,
    cxp_cxc,
    documentos,
    estadisticas,
    gastos,
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
    "Inicio": inicio.render,
    "Calendario": calendario.render,
    "Alertas": alertas.render,
    "Contabilidad": contabilidad.render,
    "Impuestos": impuestos.render,
    "CXP / CXC": cxp_cxc.render,
    "Pagos": pagos.render,
    "Gastos": gastos.render,
    "Correos": correos.render,
    "Créditos": creditos.render,
    "Comisiones": comisiones.render,
    "Personal": personal.render,
    "Presupuesto": presupuesto.render,
    "Jurídico": juridico.render,
    "Documentos": documentos.render,
    "Estadísticas": estadisticas.render,
}

st.set_page_config(
    page_title=f"AGENTE ADMIN SHAKI · {cfg.NOMBRE_EMPRESA}",
    page_icon="◼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(CSS, unsafe_allow_html=True)

# Evitar re-inicializar BD y sync pesado en cada rerun de Streamlit
if "db_ready" not in st.session_state:
    inicializar_db()
    get_engine()
    st.session_state.db_ready = True

# Enlace "Ya lo pagué" de las alertas 24h (correo / WhatsApp): pantalla propia y nada más
_token_pago = st.query_params.get("pagar")
if _token_pago:
    from dashboard.paginas import confirmar_pago

    confirmar_pago.render(_token_pago)
    st.stop()
_token_imp = st.query_params.get("presentar")
if _token_imp:
    from dashboard.paginas import confirmar_impuesto

    confirmar_impuesto.render(_token_imp)
    st.stop()

if "rrhh_watcher_on" not in st.session_state:
    try:
        from modulos.watcher_carpetas import iniciar_watcher

        iniciar_watcher()
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Watcher carpetas RRHH: %s", exc)
    st.session_state.rrhh_watcher_on = True
if "calendario_executor_on" not in st.session_state:
    try:
        from utils.calendario_maestro import iniciar_executor

        iniciar_executor()
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Calendario maestro: %s", exc)
    st.session_state.calendario_executor_on = True
if en_modo_demo() and "demo_loaded" not in st.session_state:
    cargar_datos_demo()
    st.session_state.demo_loaded = True

if "alertas_verificadas" not in st.session_state:
    verificar_alertas_globales()
    st.session_state.alertas_verificadas = True

if "pagos_sync" not in st.session_state:
    try:
        from utils.sync_pagos import actualizar_estados_pagos, importar_excel_a_sqlite
        from database import get_conn

        # Solo importar Excel completo si la tabla pagos está vacía (evita ~20-30s cada sesión)
        conn = get_conn()
        n_pagos = conn.execute("SELECT COUNT(*) FROM pagos").fetchone()[0]
        conn.close()
        if n_pagos == 0:
            st.session_state.pagos_sync = importar_excel_a_sqlite()
        else:
            actualizar_estados_pagos()
            st.session_state.pagos_sync = {"skipped": True, "registros": n_pagos}
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Sync CONTROL DE PAGOS al arrancar: %s", exc)
        st.session_state.pagos_sync = {"error": str(exc)}

if "radar_tributario_sync" not in st.session_state:
    try:
        from modulos.radar_tributario import inicializar_y_cargar as _radar_init

        _radar_init()
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Radar tributario al arrancar: %s", exc)
    st.session_state.radar_tributario_sync = True

if "control_pagos_sync" not in st.session_state:
    try:
        from modulos.control_pagos import inicializar_y_cargar

        inicializar_y_cargar()
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Control de pagos al arrancar: %s", exc)
    st.session_state.control_pagos_sync = True

if "gastos_std" not in st.session_state:
    try:
        from utils.estandarizar_gastos import estandarizar_todos, gastos_maestro_vacio

        if gastos_maestro_vacio():
            st.session_state.gastos_std = estandarizar_todos()
        else:
            st.session_state.gastos_std = {"skipped": True}
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Estandarizar gastos al arrancar: %s", exc)
        st.session_state.gastos_std = {"error": str(exc)}

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

# Contador urgentes CONTROL DE PAGOS para sidebar (cacheado por sesión)
if "pagos_urgentes_n" not in st.session_state:
    _pagos_urgentes = 0
    try:
        from modulos import control_pagos as _cp

        if _cp.hay_datos():
            _rc = _cp.resumen()
            _pagos_urgentes = int(_rc["vencidos"]) + int(_rc["hoy"])
        else:
            from utils.alertas_pagos import resumen_pagos_widget

            _rw = resumen_pagos_widget()
            _pagos_urgentes = int(_rw.get("vencidos", 0)) + int(_rw.get("hoy", 0))
    except Exception:
        pass
    st.session_state.pagos_urgentes_n = _pagos_urgentes
_pagos_urgentes = st.session_state.pagos_urgentes_n

with st.sidebar:
    modo = "Demo" if en_modo_demo() else "Producción"
    st.markdown(
        f'''<div class="sk-brand"><div class="sk-logo">{LOGO_SVG}</div>
        <div><div class="sk-brand-name">Shaki</div><div class="sk-brand-sub">{cfg.NOMBRE_EMPRESA}</div></div></div>
        <span class="sk-pill"><span class="sk-dot"></span>Agente activo · {modo}</span>''',
        unsafe_allow_html=True,
    )
    if _pagos_urgentes:
        st.markdown(
            f'<div class="sk-urgent"><b>{_pagos_urgentes:,}</b>pagos urgentes</div>'.replace(",", "."),
            unsafe_allow_html=True,
        )
    st.write("")
    pagina = st.radio("Navegación", list(PAGINAS.keys()), label_visibility="collapsed")
    st.divider()
    st.caption(f"Costo API hoy: **${stats['costo_hoy']}**")
    st.caption(f"Costo API mes: **${stats['costo_mes']}**")
    libs_ok = sum(1 for v in librerias_disponibles().values() if v)
    st.caption(f"Librerías core: **{libs_ok}** activas")

col_dashboard, col_chat = st.columns([2, 1], gap="large")

with col_dashboard:
    PAGINAS[pagina]()

with col_chat:
    st.markdown(
        f'<div class="sk-chat-h"><div class="sk-logo" style="width:26px;height:26px;border-radius:8px">{LOGO_SVG}</div>'
        '<span>Pregúntale a Shaki</span></div>',
        unsafe_allow_html=True,
    )
    for msg in st.session_state.chat_mensajes_ui[-15:]:
        css = "chat-msg-user" if msg["rol"] == "user" else "chat-msg-agent"
        st.markdown(f'<div class="{css}">{msg["texto"]}</div>', unsafe_allow_html=True)

    preguntas = [
        "¿Qué alertas hay hoy?",
        "Pagos pendientes",
        "Verificar alertas",
        "Procesar correos",
        "Cartera en mora",
        "Impuestos próximos",
        "¿Qué puedes hacer?",
    ]
    cols = st.columns(2)
    for i, p in enumerate(preguntas):
        col = cols[i % 2]
        if col.button(p, key=f"qr_{i}", use_container_width=True):
            st.session_state.chat_mensajes_ui.append({"rol": "user", "texto": p})
            with st.spinner("Consultando..."):
                r, st.session_state.chat_historial = chat_responder(p, st.session_state.chat_historial)
            st.session_state.chat_mensajes_ui.append({"rol": "agent", "texto": r})
            st.rerun()

    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "Mensaje", placeholder="¿Qué pagos vencen esta semana?", label_visibility="collapsed"
        )
        if st.form_submit_button("Enviar", use_container_width=True) and user_input.strip():
            st.session_state.chat_mensajes_ui.append({"rol": "user", "texto": user_input})
            with st.spinner("Consultando..."):
                r, st.session_state.chat_historial = chat_responder(user_input, st.session_state.chat_historial)
            st.session_state.chat_mensajes_ui.append({"rol": "agent", "texto": r})
            st.rerun()
