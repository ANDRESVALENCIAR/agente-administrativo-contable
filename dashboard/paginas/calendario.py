"""Página Calendario Maestro — agenda centralizada del agente."""
from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from modulos.calendario_callbacks import CALLBACKS
from utils.calendario_maestro import (
    MODULOS_VALIDOS,
    agregar_tarea,
    cancelar_tarea,
    dias_habiles_entre,
    es_dia_habil,
    es_festivo,
    ejecutar_tarea_por_id,
    executor_esta_activo,
    get_festivos_colombia,
    listar_todas_activas,
    obtener_log_reciente,
    tareas_hoy,
    tareas_mes,
    tareas_semana,
    tareas_vencidas,
)


def _badge_festivo() -> None:
    hoy = date.today()
    if es_festivo(hoy):
        st.warning("🇨🇴 Hoy es **festivo** en Colombia.")
    elif not es_dia_habil(hoy):
        st.info("📅 Hoy es fin de semana.")
    else:
        st.success("✅ Hoy es día hábil.")


def render() -> None:
    st.markdown("## 📅 Calendario Maestro")
    st.caption(
        "Agenda centralizada 24/7 · Todos los módulos programan aquí · "
        f"Executor: {'🟢 activo' if executor_esta_activo() else '🟡 inactivo'}"
    )

    _badge_festivo()

    hoy = date.today()
    festivos = sorted(d for d in get_festivos_colombia(hoy.year) if d >= hoy)[:5]
    if festivos:
        st.caption(
            "Próximos festivos: "
            + ", ".join(f"{d.strftime('%d/%m')}" for d in festivos)
        )

    m1, m2, m3, m4 = st.columns(4)
    df_hoy = tareas_hoy()
    df_venc = tareas_vencidas()
    df_activas = listar_todas_activas()
    m1.metric("Tareas hoy", len(df_hoy))
    m2.metric("Vencidas", len(df_venc))
    m3.metric("Activas", len(df_activas))
    m4.metric("Días hábiles mes", dias_habiles_entre(date(hoy.year, hoy.month, 1), hoy))

    tab_hoy, tab_semana, tab_mes, tab_todas, tab_log, tab_nueva = st.tabs(
        ["Hoy", "Semana", "Mes", "Todas activas", "Log ejecuciones", "Nueva tarea"]
    )

    with tab_hoy:
        if df_hoy.empty:
            st.info("Sin tareas programadas para hoy.")
        else:
            st.dataframe(
                df_hoy.drop(columns=["es_festivo_hoy", "es_dia_habil_hoy"], errors="ignore"),
                use_container_width=True,
                hide_index=True,
            )

    with tab_semana:
        df_sem = tareas_semana()
        if df_sem.empty:
            st.info("Sin tareas en los próximos 7 días.")
        else:
            st.dataframe(df_sem, use_container_width=True, hide_index=True)

    with tab_mes:
        df_m = tareas_mes()
        festivos_mes = df_m.attrs.get("festivos_mes", [])
        if festivos_mes:
            st.caption(
                "Festivos del mes: "
                + ", ".join(d.strftime("%d/%m/%Y") for d in festivos_mes)
            )
        if df_m.empty:
            st.info("Sin tareas este mes.")
        else:
            st.dataframe(df_m, use_container_width=True, hide_index=True)

    with tab_todas:
        if not df_venc.empty:
            st.error(f"⚠️ {len(df_venc)} tarea(s) vencida(s)")
            for _, row in df_venc.iterrows():
                c1, c2 = st.columns([4, 1])
                c1.write(f"#{row['id']} {row['titulo']} — {row['modulo']}")
                if c2.button("▶ Ejecutar", key=f"run_venc_{row['id']}"):
                    ejecutar_tarea_por_id(int(row["id"]))
                    st.success("Ejecutada.")
                    st.rerun()
            st.dataframe(df_venc, use_container_width=True, hide_index=True)
        else:
            st.success("Sin tareas vencidas.")
        st.divider()
        if not df_activas.empty:
            for _, row in df_activas.head(20).iterrows():
                c1, c2 = st.columns([4, 1])
                c1.write(f"#{row['id']} {row['titulo']} — próxima: {row.get('fecha_proxima_ejecucion', '—')}")
                if row.get("funcion_callback") and c2.button("▶ Ahora", key=f"run_{row['id']}"):
                    ejecutar_tarea_por_id(int(row["id"]))
                    st.success("Ejecutada.")
                    st.rerun()
        st.dataframe(df_activas, use_container_width=True, hide_index=True)

    with tab_log:
        log = obtener_log_reciente(80)
        if log.empty:
            st.info("Sin ejecuciones registradas aún.")
        else:
            st.dataframe(log, use_container_width=True, hide_index=True)

    with tab_nueva:
        with st.form("nueva_tarea_cal"):
            titulo = st.text_input("Título *")
            descripcion = st.text_area("Descripción")
            col_a, col_b, col_c = st.columns(3)
            modulo = col_a.selectbox("Módulo", sorted(MODULOS_VALIDOS))
            tipo = col_b.selectbox(
                "Tipo",
                ["TAREA_MANUAL", "RECORDATORIO", "VENCIMIENTO", "REUNION", "ALERTA", "AUTOMATICA"],
            )
            callback_opts = [None] + sorted(CALLBACKS.keys())
            funcion_callback = col_c.selectbox(
                "Callback (opcional)",
                callback_opts,
                format_func=lambda x: "Ninguno" if x is None else x,
            )
            col_c, col_d = st.columns(2)
            prioridad = col_c.selectbox("Prioridad", ["MEDIA", "ALTA", "CRITICA", "BAJA"])
            recurrencia = col_d.selectbox(
                "Recurrencia",
                [None, "DIARIA", "DIAS_HABILES", "SEMANAL", "MENSUAL", "ANUAL"],
                format_func=lambda x: "Única vez" if x is None else x,
            )
            hora = st.text_input("Hora (HH:MM)", value="09:00")
            fecha = st.date_input("Fecha inicio", value=hoy)
            if st.form_submit_button("Agregar al calendario"):
                if not titulo.strip():
                    st.error("El título es obligatorio.")
                else:
                    h, m = map(int, hora.split(":"))
                    inicio = datetime.combine(fecha, datetime.min.time().replace(hour=h, minute=m))
                    cfg = {"hora": hora} if recurrencia else None
                    tid = agregar_tarea(
                        titulo=titulo.strip(),
                        modulo=modulo,
                        tipo=tipo,
                        fecha_inicio=inicio,
                        descripcion=descripcion or None,
                        prioridad=prioridad,
                        recurrencia=recurrencia,
                        recurrencia_config=cfg,
                        funcion_callback=funcion_callback,
                        creada_por="MANUAL",
                    )
                    st.success(f"Tarea #{tid} agregada.")
                    st.rerun()

        st.divider()
        st.caption("Desactivar tarea existente")
        if not df_activas.empty:
            opciones = {
                f"#{r['id']} · {r['titulo']}": int(r["id"])
                for _, r in df_activas.iterrows()
            }
            sel = st.selectbox("Tarea", list(opciones.keys()))
            if st.button("Cancelar tarea seleccionada"):
                cancelar_tarea(opciones[sel])
                st.success("Tarea desactivada.")
                st.rerun()
