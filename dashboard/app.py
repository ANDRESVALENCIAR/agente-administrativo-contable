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
    initial_sidebar_state="auto",
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
    try:
        from modulos import motor_alertas

        motor_alertas.escanear_si_toca(5)
    except Exception:
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

@st.cache_resource(show_spinner=False)
def _optimizar_bd() -> int:
    """Una vez por arranque del servidor: índices en las columnas más consultadas + PRAGMA optimize."""
    from database import asegurar_indices

    return asegurar_indices()


_optimizar_bd()

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
    st.session_state.chat_mensajes_ui = []

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
    pagina = st.radio("Navegación", list(PAGINAS.keys()), label_visibility="collapsed", key="nav")
    st.divider()
    st.caption(f"Costo API hoy: **${stats['costo_hoy']}**")
    st.caption(f"Costo API mes: **${stats['costo_mes']}**")
    libs_ok = sum(1 for v in librerias_disponibles().values() if v)
    st.caption(f"Librerías core: **{libs_ok}** activas")

def _chat_cuerpo(en_dialogo: bool = False) -> None:
    """Chat con Shaki: responde con los datos reales (pagos, impuestos, alertas, correos, revisión…)."""
    def _rerun() -> None:
        st.rerun(scope="fragment") if en_dialogo else st.rerun()

    def _preguntar(texto: str) -> None:
        st.session_state.chat_mensajes_ui.append({"rol": "user", "texto": texto})
        from modulos import asistente as _as
        aviso = ("Shaki está analizando con IA…" if _as.motor_para(texto, st.session_state.chat_historial) == "ia"
                 else "Shaki está consultando…")
        with st.spinner(aviso):
            r, st.session_state.chat_historial = chat_responder(texto, st.session_state.chat_historial)
        st.session_state.chat_mensajes_ui.append({"rol": "agent", "texto": r})

    caja = st.container(height=430 if en_dialogo else 520, border=False)
    with caja:
        if not st.session_state.chat_mensajes_ui:
            with st.chat_message("assistant", avatar=":material/auto_awesome:"):
                st.markdown("Hola, soy **Shaki**. Pregúnteme con sus palabras: *¿cómo vamos?*, *¿cuánta plata hay "
                            "en bancos?*, *¿cuánto le debemos a Codifer?*, *¿quién cumple años este mes?*, *¿qué tengo "
                            "hoy?*… Escriba **ayuda** para ver todo lo que sé.")
        for msg in st.session_state.chat_mensajes_ui[-20:]:
            # $ escapado (si no, Streamlit lo toma como fórmula) y saltos de línea respetados
            texto = str(msg["texto"]).replace("$", "\\$").replace("\n", "  \n")
            if msg["rol"] == "user":
                with st.chat_message("user", avatar=":material/person:"):
                    st.markdown(texto)
            else:
                with st.chat_message("assistant", avatar=":material/auto_awesome:"):
                    st.markdown(texto)
    from modulos import asistente as _as
    if _as.ia_activa():
        st.caption(f":material/psychology: IA activa · {cfg.MODELO_COMPLEJO} — lo simple se responde gratis al instante; "
                   "las preguntas abiertas las analiza la IA.")
    else:
        st.caption(":material/bolt: Modo local (gratis, sin IA). Para preguntas abiertas y análisis, active la IA con "
                   "scripts\\configurar_ia.ps1")
    preguntas = ["¿Qué tengo hoy?", "¿Cómo vamos?", "¿Cuánta plata hay en bancos?", "¿Me alcanza la plata?",
                 "¿Cuánto nos deben los clientes?", "Pagos de esta semana", "¿Qué impuestos vienen?",
                 "¿Quién cumple años este mes?"]
    n = st.session_state.get("chat_sug_n", 0)
    elegida = st.pills("Sugerencias", preguntas, key=f"sug_{int(en_dialogo)}_{n}", label_visibility="collapsed")
    if elegida:
        st.session_state.chat_sug_n = n + 1
        _preguntar(elegida)
        _rerun()
    with st.form(f"chat_form_{int(en_dialogo)}", clear_on_submit=True, border=False):
        c1, c2 = st.columns([5, 1])
        user_input = c1.text_input("Mensaje", placeholder="Escriba su pregunta…", label_visibility="collapsed")
        if c2.form_submit_button("Enviar", width="stretch", type="primary") and user_input.strip():
            _preguntar(user_input.strip())
            _rerun()


@st.dialog("Pregúntale a Shaki", width="large")
def _chat_dialogo() -> None:
    _chat_cuerpo(en_dialogo=True)


# Por defecto el tablero usa todo el ancho (celular, portátil de 13" y TV); el chat se abre en una
# ventana emergente. Quien prefiera el chat fijo a la derecha lo activa en la barra lateral.
with st.sidebar:
    chat_lado = st.toggle("Chat fijo a la derecha", value=False, key="chat_lado",
                          help="Recomendado solo en pantallas grandes")

if chat_lado:
    col_dashboard, col_chat = st.columns([2.4, 1], gap="large")
else:
    col_dashboard, col_chat = st.container(), None

def _nav_movil() -> None:
    st.session_state["nav"] = st.session_state["nav_movil"]


with col_dashboard:
    # Celular: menú arriba (la barra lateral queda oculta); en pantallas grandes este bloque no se ve
    with st.container(key="nav_movil_box"):
        m1, m2 = st.columns([3, 1.2])
        st.session_state["nav_movil"] = pagina
        m1.selectbox("Ir a", list(PAGINAS.keys()), key="nav_movil", on_change=_nav_movil,
                     label_visibility="collapsed")
        if m2.button("Shaki", key="abrir_chat_movil", width="stretch", icon=":material/chat:"):
            _chat_dialogo()
    if not chat_lado:
        c_btn = st.container(key="chat_btn_box")
        if c_btn.button("Pregúntale a Shaki", key="abrir_chat", width="stretch", icon=":material/chat:"):
            _chat_dialogo()
    PAGINAS[pagina]()

if col_chat is not None:
    with col_chat:
        st.markdown(
            f'<div class="sk-chat-h"><div class="sk-logo" style="width:26px;height:26px;border-radius:8px">{LOGO_SVG}</div>'
            '<span>Pregúntale a Shaki</span></div>',
            unsafe_allow_html=True,
        )
        _chat_cuerpo()
