"""
Dashboard principal del Agente Administrativo.
Ejecutar con: streamlit run dashboard/app.py
Interfaz web con dashboard de métricas + chat conversacional en tiempo real.
"""
import os
import sqlite3
import sys
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import cfg, en_modo_demo
from dashboard.chat import chat_responder
from dashboard.estilos import CSS
from database import (
    aprobar_pago,
    cargar_datos_demo,
    inicializar_db,
    marcar_alerta_resuelta,
    obtener_alertas_activas,
    obtener_correos_ultimos_dias,
    obtener_estadisticas_hoy,
    obtener_pagos_pendientes,
    rechazar_pago,
)

st.set_page_config(
    page_title=f"Agente Admin · {cfg.NOMBRE_EMPRESA}",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(CSS, unsafe_allow_html=True)

inicializar_db()
if en_modo_demo():
    cargar_datos_demo()

if "chat_historial" not in st.session_state:
    st.session_state.chat_historial = []
if "chat_mensajes_ui" not in st.session_state:
    st.session_state.chat_mensajes_ui = [
        {
            "rol": "agent",
            "texto": (
                f"Buenos días. Soy tu asistente administrativo de {cfg.NOMBRE_EMPRESA}. "
                "Puedo ayudarte a revisar alertas, aprobar pagos, consultar impuestos, "
                "generar documentos y mucho más. ¿En qué te ayudo hoy?"
            ),
        }
    ]

with st.sidebar:
    st.markdown("### 🤖 Agente Admin")
    st.markdown(f"**{cfg.NOMBRE_EMPRESA}**")
    modo = "Demo" if en_modo_demo() else "Producción"
    st.markdown(f'<p class="status-active">● Activo · {modo}</p>', unsafe_allow_html=True)
    st.caption(f"Última ejecución: {datetime.now().strftime('%H:%M')}")
    st.divider()

    pagina = st.radio(
        "Navegación",
        [
            "🏠 Inicio",
            "🔔 Alertas",
            "💳 Pagos",
            "📧 Correos",
            "🤝 Créditos",
            "💰 Comisiones",
            "👤 Personal",
            "📊 Presupuesto",
            "📄 Documentos",
            "📈 Estadísticas",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    stats = obtener_estadisticas_hoy()
    st.caption(f"Costo API hoy: **${stats['costo_hoy']}**")
    st.caption(f"Costo API mes: **${stats['costo_mes']}**")

col_dashboard, col_chat = st.columns([2, 1])

with col_dashboard:
    if "Inicio" in pagina:
        st.markdown("## Panel principal")
        st.caption(datetime.now().strftime("%A %d de %B de %Y · %H:%M"))

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Alertas activas", stats["alertas_activas"])
        with m2:
            st.metric("Pagos por aprobar", stats["pagos_pendientes"])
        with m3:
            st.metric("Correos hoy", stats["correos_hoy"])
        with m4:
            st.metric("Costo API hoy", f"${stats['costo_hoy']}")

        st.divider()
        st.markdown('<p class="section-title">Alertas activas</p>', unsafe_allow_html=True)
        alertas = obtener_alertas_activas()
        if alertas:
            for alerta in alertas[:5]:
                nivel_css = {
                    "CRITICO": "alert-critico",
                    "URGENTE": "alert-urgente",
                    "AVISO": "alert-aviso",
                }.get(alerta[3], "alert-aviso")
                col_a, col_b = st.columns([5, 1])
                with col_a:
                    st.markdown(
                        f'<div class="{nivel_css}"><strong>[{alerta[3]}]</strong> {alerta[4]}'
                        f"<br><small>{alerta[5]}</small></div>",
                        unsafe_allow_html=True,
                    )
                with col_b:
                    if st.button("Resolver", key=f"alerta_{alerta[0]}"):
                        marcar_alerta_resuelta(alerta[0])
                        st.rerun()
        else:
            st.success("Sin alertas activas. Todo en orden.")

        st.divider()
        st.markdown('<p class="section-title">Últimas acciones del agente</p>', unsafe_allow_html=True)
        if stats["ultimas_acciones"]:
            for acc in stats["ultimas_acciones"]:
                icono = "✅" if acc[3] == "EXITOSO" else "❌"
                st.caption(f"{icono} **{acc[0]}** · {acc[2]} · `{acc[4]}`")
        else:
            st.caption("Sin acciones registradas hoy.")

        st.divider()
        st.markdown('<p class="section-title">Correos procesados — últimos 7 días</p>', unsafe_allow_html=True)
        datos_correos = obtener_correos_ultimos_dias(7)
        if datos_correos:
            df_correos = pd.DataFrame(datos_correos, columns=["fecha", "total", "categoria"])
            fig = px.bar(
                df_correos,
                x="fecha",
                y="total",
                color="categoria",
                color_discrete_sequence=px.colors.qualitative.Set3,
                height=200,
            )
            fig.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="h", y=-0.3),
                showlegend=True,
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)

    elif "Alertas" in pagina:
        st.markdown("## Alertas del sistema")
        alertas = obtener_alertas_activas()
        if not alertas:
            st.success("Sin alertas activas en este momento.")
        for alerta in alertas:
            with st.expander(f"[{alerta[3]}] {alerta[4]} · {alerta[1]}", expanded=alerta[3] == "CRITICO"):
                st.write(alerta[5])
                st.caption(f"Módulo: {alerta[2]} · {alerta[1]}")
                if st.button("Marcar como resuelta", key=f"res_{alerta[0]}"):
                    marcar_alerta_resuelta(alerta[0])
                    st.rerun()

    elif "Pagos" in pagina:
        st.markdown("## Pagos pendientes de aprobación")
        pagos = obtener_pagos_pendientes()
        if not pagos:
            st.info("No hay pagos pendientes de aprobación.")
        for pago in pagos:
            with st.container():
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                c1.write(f"**{pago[2]}** — {pago[3]}")
                c1.caption(f"Vence: {pago[5]} · {pago[7] or ''}")
                c2.metric("Monto", f"${pago[4]:,.0f}")
                prioridad_color = {
                    "VENCIDO": "🔴",
                    "HOY": "🟠",
                    "URGENTE": "🟡",
                    "PROXIMO": "🔵",
                    "NORMAL": "⚪",
                }.get(pago[7], "⚪")
                c3.write(f"{prioridad_color} {pago[7]}")
                with c4:
                    if st.button("✅ Aprobar", key=f"ap_{pago[0]}"):
                        aprobar_pago(pago[0])
                        st.success("Pago aprobado.")
                        st.rerun()
                    if st.button("❌ Rechazar", key=f"re_{pago[0]}"):
                        rechazar_pago(pago[0])
                        st.rerun()
                st.divider()

    elif "Correos" in pagina:
        st.markdown("## Correos procesados")
        conn = sqlite3.connect(cfg.DATABASE_PATH)
        df = pd.read_sql(
            """SELECT timestamp, origen, remitente, asunto, categoria, accion
               FROM correos_procesados ORDER BY id DESC LIMIT 100""",
            conn,
        )
        conn.close()
        if df.empty:
            st.info("No hay correos procesados aún.")
        else:
            col_f1, col_f2 = st.columns(2)
            cat_filter = col_f1.selectbox("Filtrar por categoría", ["Todas"] + df["categoria"].unique().tolist())
            orig_filter = col_f2.selectbox("Origen", ["Todos", "GMAIL", "OUTLOOK"])
            if cat_filter != "Todas":
                df = df[df["categoria"] == cat_filter]
            if orig_filter != "Todos":
                df = df[df["origen"] == orig_filter]
            st.dataframe(df, use_container_width=True, hide_index=True)

    elif "Créditos" in pagina:
        st.markdown("## Créditos analizados")
        conn = sqlite3.connect(cfg.DATABASE_PATH)
        df = pd.read_sql("SELECT * FROM creditos_analizados ORDER BY id DESC", conn)
        conn.close()
        if df.empty:
            st.info("No hay créditos analizados. Usa el chat para analizar una solicitud.")
        else:
            st.dataframe(
                df[["timestamp", "cliente", "cupo_solicitado", "cupo_aprobado", "decision", "estado_habilitacion"]],
                use_container_width=True,
            )

    elif "Documentos" in pagina:
        st.markdown("## Documentos generados")
        conn = sqlite3.connect(cfg.DATABASE_PATH)
        df = pd.read_sql("SELECT * FROM documentos_generados ORDER BY id DESC", conn)
        conn.close()
        if df.empty:
            st.info("No hay documentos generados aún.")
        else:
            for _, row in df.iterrows():
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{row['nombre_archivo']}** — {row['descripcion']}")
                c1.caption(f"{row['tipo']} · {row['timestamp']}")
                if row["path_local"] and os.path.exists(row["path_local"]):
                    with open(row["path_local"], "rb") as f:
                        c2.download_button(
                            "Descargar",
                            f.read(),
                            file_name=row["nombre_archivo"],
                            key=f"doc_{row['id']}",
                        )

    elif "Estadísticas" in pagina:
        st.markdown("## Estadísticas del sistema")
        conn = sqlite3.connect(cfg.DATABASE_PATH)
        df_tokens = pd.read_sql(
            """SELECT fecha,
               tokens_input_sonnet + tokens_input_haiku as tokens_in,
               tokens_output_sonnet + tokens_output_haiku as tokens_out,
               costo_estimado_usd as costo
               FROM uso_tokens_diario ORDER BY fecha DESC LIMIT 30""",
            conn,
        )
        conn.close()
        if not df_tokens.empty:
            st.markdown("#### Costo API últimos 30 días")
            fig = px.area(df_tokens, x="fecha", y="costo", height=200, color_discrete_sequence=["#534AB7"])
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos de uso todavía. Se llenará al usar Claude API.")

    else:
        st.markdown(f"## {pagina}")
        st.info("Esta sección está en construcción. Usa el chat para consultar información.")

with col_chat:
    st.markdown("### 💬 Chat con el agente")

    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_mensajes_ui[-15:]:
            if msg["rol"] == "user":
                st.markdown(f'<div class="chat-msg-user">{msg["texto"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-msg-agent">{msg["texto"]}</div>', unsafe_allow_html=True)

    st.divider()
    st.caption("Preguntas frecuentes:")
    qcol1, qcol2 = st.columns(2)
    preguntas_rapidas = [
        "¿Qué alertas hay hoy?",
        "¿Qué pagos hay pendientes?",
        "Estado de impuestos",
        "¿Qué falta para cerrar el mes?",
        "Resumen de cartera vencida",
        "¿Cuánto llevamos de costo API?",
    ]
    for i, pregunta in enumerate(preguntas_rapidas):
        col = qcol1 if i % 2 == 0 else qcol2
        if col.button(pregunta, key=f"qr_{i}", use_container_width=True):
            st.session_state.chat_mensajes_ui.append({"rol": "user", "texto": pregunta})
            with st.spinner("Consultando..."):
                respuesta, st.session_state.chat_historial = chat_responder(
                    pregunta, st.session_state.chat_historial
                )
            st.session_state.chat_mensajes_ui.append({"rol": "agent", "texto": respuesta})
            st.rerun()

    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "Escribe tu mensaje...",
            placeholder="Ej: ¿Qué correos llegaron hoy?",
            label_visibility="collapsed",
        )
        enviado = st.form_submit_button("Enviar →", use_container_width=True)

    if enviado and user_input.strip():
        st.session_state.chat_mensajes_ui.append({"rol": "user", "texto": user_input})
        with st.spinner("El agente está consultando..."):
            respuesta, st.session_state.chat_historial = chat_responder(
                user_input, st.session_state.chat_historial
            )
        st.session_state.chat_mensajes_ui.append({"rol": "agent", "texto": respuesta})
        st.rerun()
