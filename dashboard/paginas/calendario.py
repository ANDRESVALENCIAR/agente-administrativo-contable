"""Calendario Maestro — centro de mando: todo lo que tiene fecha en Shaki en una sola vista."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from html import escape

import pandas as pd
import streamlit as st

from modulos import agenda_unificada as ag
from modulos.calendario_callbacks import CALLBACKS
from utils.calendario_maestro import (
    MODULOS_VALIDOS,
    agregar_tarea,
    cancelar_tarea,
    ejecutar_tarea_por_id,
    es_dia_habil,
    es_festivo,
    executor_esta_activo,
    listar_todas_activas,
    obtener_log_reciente,
    tareas_vencidas,
)

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
DIAS_C = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"]
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
         "Noviembre", "Diciembre"]
NIV_COL = {"VENCIDO": "#E5484D", "HOY": "#FF6A3D", "MAÑANA": "#F5C542", "PRONTO": "#F5C542",
           "PROGRAMADO": "#52525B", "HECHO": "#2FB36D"}
NIV_TXT = {"VENCIDO": "VENCIDO", "HOY": "HOY", "MAÑANA": "MAÑANA", "PRONTO": "PRONTO", "PROGRAMADO": "",
           "HECHO": "HECHO"}
BOTON = {"pagar": "Pagué ✓", "presentar": "Presenté ✓", "ejecutar": "Ejecutar"}

CSS = """
<style>
.cm-hero{position:relative;overflow:hidden;border:1px solid #1F2024;border-radius:24px;padding:24px 26px 18px;
 background:radial-gradient(120% 160% at 100% 0%,#1A1420 0%,#0A0B0D 55%)}
.cm-hero:before{content:"";position:absolute;left:-120px;bottom:-160px;width:360px;height:360px;border-radius:50%;
 background:radial-gradient(circle,#7DD3FC1f,transparent 70%)}
.cm-top{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;position:relative}
.cm-eb{font-family:'Geist Mono',monospace;font-size:11px;letter-spacing:.14em;color:#8B8B93;text-transform:uppercase}
.cm-day{font-size:44px;line-height:1.05;color:#fff;font-weight:600;letter-spacing:-.03em;margin-top:6px}
.cm-sub{color:#A1A1AA;font-size:14px;margin-top:6px}.cm-sub b{color:#fff}
.cm-state{text-align:right;font-family:'Geist Mono',monospace;font-size:11px;color:#8B8B93;line-height:1.9}
.cm-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;box-shadow:0 0 10px currentColor}
.cm-pulse{display:grid;grid-template-columns:repeat(30,1fr);gap:4px;margin-top:22px;position:relative}
.cm-pd{display:flex;flex-direction:column;align-items:center;gap:3px}
.cm-bar{width:100%;height:58px;border-radius:7px;background:#121317;border:1px solid #1C1D21;display:flex;
 flex-direction:column-reverse;overflow:hidden}
.cm-bar.hoy{border-color:#FF6A3D;box-shadow:0 0 0 1px #FF6A3D55,0 0 18px #FF6A3D33}
.cm-bar.fest{background:repeating-linear-gradient(135deg,#121317 0 4px,#1a1420 4px 8px)}
.cm-seg{width:100%}
.cm-pn{font-family:'Geist Mono',monospace;font-size:9.5px;color:#71717A}.cm-pn.w{color:#3F3F46}
.cm-leg{display:flex;flex-wrap:wrap;gap:14px;margin-top:12px;font-size:11px;color:#8B8B93}
.cm-leg i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.cm-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:14px 0 6px}
.cm-k{background:#0F1012;border:1px solid #1F2024;border-radius:16px;padding:12px 14px}
.cm-k b{display:block;font-size:24px;color:#fff;font-weight:500;line-height:1.1}
.cm-k span{font-size:10px;color:#8B8B93;font-family:'Geist Mono',monospace;letter-spacing:.08em;text-transform:uppercase}
.cm-row{display:flex;gap:12px;align-items:flex-start;padding:10px 4px;border-bottom:1px solid #17181C}
.cm-bul{width:4px;align-self:stretch;border-radius:4px;flex:0 0 4px}
.cm-t{color:#fff;font-size:14.5px;font-weight:500;line-height:1.3}.cm-s{color:#8B8B93;font-size:12.5px;margin-top:2px}
.cm-tag{font-family:'Geist Mono',monospace;font-size:9.5px;letter-spacing:.06em;padding:2px 7px;border-radius:6px;
 margin-left:8px;vertical-align:1px}
.cm-src{font-family:'Geist Mono',monospace;font-size:10px;letter-spacing:.08em}
.cm-val{margin-left:auto;text-align:right;color:#E4E4E7;font-family:'Geist Mono',monospace;font-size:13px;white-space:nowrap}
.cm-h{display:flex;justify-content:space-between;align-items:baseline;margin:6px 0 4px}
.cm-h b{color:#fff;font-size:16px;font-weight:500}.cm-h span{color:#8B8B93;font-size:11px;font-family:'Geist Mono',monospace}
.cm-week{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px}
.cm-col{background:#0F1012;border:1px solid #1F2024;border-radius:16px;padding:10px;min-height:280px}
.cm-col.hoy{border-color:#FF6A3D88;background:linear-gradient(180deg,#1A120E 0%,#0F1012 40%)}
.cm-col.fest{background:repeating-linear-gradient(135deg,#0F1012 0 6px,#140F18 6px 12px)}
.cm-ch{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}
.cm-ch b{font-size:22px;color:#fff;font-weight:500}.cm-ch span{font-family:'Geist Mono',monospace;font-size:10px;color:#8B8B93}
.cm-chip{border-radius:10px;padding:6px 8px;margin-bottom:6px;background:#141519;border-left:3px solid;font-size:12px;
 color:#E4E4E7;line-height:1.3}.cm-chip small{display:block;color:#8B8B93;font-size:10.5px;margin-top:2px}
.cm-chip.done{opacity:.45;text-decoration:line-through}
.cm-month{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px}
.cm-mh{font-family:'Geist Mono',monospace;font-size:10px;color:#71717A;text-align:center;padding-bottom:4px}
.cm-md{background:#0F1012;border:1px solid #1C1D21;border-radius:12px;min-height:104px;padding:6px 7px}
.cm-md.out{opacity:.3}.cm-md.hoy{border-color:#FF6A3D;box-shadow:0 0 16px #FF6A3D33}
.cm-md.fest{background:repeating-linear-gradient(135deg,#0F1012 0 5px,#160F19 5px 10px)}
.cm-mn{font-size:13px;color:#C4C4CC;font-family:'Geist Mono',monospace}
.cm-mc{display:block;font-size:10.5px;color:#E4E4E7;border-radius:6px;padding:2px 5px;margin-top:3px;white-space:nowrap;
 overflow:hidden;text-overflow:ellipsis}
.cm-more{font-size:10px;color:#8B8B93;margin-top:3px;font-family:'Geist Mono',monospace}
@media(max-width:900px){.cm-kpis{grid-template-columns:repeat(3,1fr)}.cm-week{grid-template-columns:1fr}
 .cm-pulse{grid-template-columns:repeat(15,1fr)}.cm-day{font-size:32px}}
</style>
"""


def _pesos(v) -> str:
    return "" if not v else "$" + f"{float(v):,.0f}".replace(",", ".")


def _col(fuente: str) -> str:
    return ag.FUENTES.get(fuente, {}).get("color", "#8B8B93")


# ───────────────────────── Hero ─────────────────────────

def _hero(hoy: date, evs30: list[dict], r: dict) -> None:
    por_dia: dict[date, list[dict]] = {}
    for e in evs30:
        if not e["hecho"]:
            por_dia.setdefault(e["fecha"], []).append(e)
    maxn = max([len([x for x in v if x["fuente"] not in ("FESTIVO", "AGENTE")]) for v in por_dia.values()] + [4])
    cols = []
    for i in range(30):
        d = hoy + timedelta(days=i)
        evs = [e for e in por_dia.get(d, []) if e["fuente"] not in ("FESTIVO", "AGENTE")]
        fest = any(e["fuente"] == "FESTIVO" for e in por_dia.get(d, []))
        segs = "".join(
            f'<div class="cm-seg" style="height:{max(6, 100 * sum(1 for e in evs if e["fuente"] == f) / maxn):.0f}%;'
            f'background:{_col(f)}"></div>'
            for f in ag.FUENTES if any(e["fuente"] == f for e in evs))
        clase = "hoy" if i == 0 else "fest" if fest else ""
        tip = escape(f"{DIAS[d.weekday()]} {d:%d/%m}: " + ("; ".join(e["titulo"] for e in evs[:6]) or "libre")
                     + (" · festivo" if fest else ""))
        cols.append(f'<div class="cm-pd" title="{tip}"><div class="cm-bar {clase}">{segs}</div>'
                    f'<span class="cm-pn{" w" if d.weekday() >= 5 else ""}">{d.day}</span></div>')
    estado_dia = ("Festivo en Colombia" if es_festivo(hoy) else "Día hábil" if es_dia_habil(hoy) else "Fin de semana")
    exe = executor_esta_activo()
    ley = "".join(f'<span><i style="background:{v["color"]}"></i>{escape(v["nombre"])}</span>'
                  for k, v in ag.FUENTES.items() if k != "AGENTE")
    pend_hoy = r["hoy"] + r["vencidos"]
    st.markdown(
        f'<div class="cm-hero"><div class="cm-top"><div>'
        f'<div class="cm-eb">Centro de mando · {escape(estado_dia)}</div>'
        f'<div class="cm-day">{DIAS[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1].lower()}</div>'
        f'<div class="cm-sub">'
        + (f'Tienes <b>{pend_hoy}</b> asunto(s) para hoy' + (f', <b style="color:#E5484D">{r["vencidos"]} vencido(s)</b>'
                                                            if r["vencidos"] else "")
           if pend_hoy else "Nada pendiente para hoy")
        + f' · <b>{r["semana"]}</b> en los próximos 7 días.</div></div>'
        f'<div class="cm-state"><span class="cm-dot" style="color:{"#4ADE80" if exe else "#F5C542"};'
        f'background:currentColor"></span>Agente {"activo 24/7" if exe else "en pausa"}<br>'
        f'{r["automatizaciones_hoy"]} automatizaciones hoy'
        + (f'<br><span style="color:#E5484D">{r["fallas_24h"]} falla(s) en 24 h</span>' if r["fallas_24h"] else "")
        + f'</div></div><div class="cm-pulse">{"".join(cols)}</div><div class="cm-leg">{ley}</div></div>',
        unsafe_allow_html=True,
    )
    k = [(r["vencidos"], "Vencidos", "#E5484D" if r["vencidos"] else "#fff"), (r["hoy"], "Para hoy", "#fff"),
         (r["semana"], "Próx. 7 días", "#fff"), (_pesos(r["valor_semana"]) or "$0", "Pagos 7 días", "#fff"),
         (r["impuestos_30"], "Declaraciones 30 d", "#7DD3FC"), (r["revisiones_pend"], "Revisiones pend.", "#C4B5FD")]
    st.markdown('<div class="cm-kpis">' + "".join(
        f'<div class="cm-k"><b style="color:{c}">{v}</b><span>{t}</span></div>' for v, t, c in k) + "</div>",
        unsafe_allow_html=True)


# ───────────────────────── Listas ─────────────────────────

def _fila(e: dict, mostrar_fecha: bool = False) -> str:
    c = NIV_COL[e["nivel"]]
    tag = NIV_TXT[e["nivel"]]
    tag_html = f'<span class="cm-tag" style="color:{c};border:1px solid {c}66">{tag}</span>' if tag else ""
    cuando = []
    if mostrar_fecha:
        cuando.append(f'{DIAS_C[e["fecha"].weekday()]} {e["fecha"]:%d/%m}')
    if e["hora"]:
        cuando.append(e["hora"])
    src = ag.FUENTES[e["fuente"]]
    return (f'<div class="cm-row"><div class="cm-bul" style="background:{src["color"]}"></div><div>'
            f'<div class="cm-t">{escape(e["titulo"])}{tag_html}</div>'
            f'<div class="cm-s"><span class="cm-src" style="color:{src["color"]}">{escape(src["nombre"].upper())}</span>'
            f'{" · " + escape(" · ".join(cuando)) if cuando else ""}{" · " + escape(e["sub"]) if e["sub"] else ""}</div>'
            f'</div><div class="cm-val">{_pesos(e["valor"])}</div></div>')


def _lista_con_acciones(evs: list[dict], clave: str, mostrar_fecha: bool = False, limite: int = 40) -> None:
    if not evs:
        st.markdown('<div class="cm-s" style="padding:14px 4px">Nada aquí. Todo al día.</div>', unsafe_allow_html=True)
        return
    for e in evs[:limite]:
        if e["accion"] and not e["hecho"]:
            c1, c2 = st.columns([4, 1.5], vertical_alignment="center")
            c1.markdown(_fila(e, mostrar_fecha), unsafe_allow_html=True)
            if c2.button(BOTON[e["accion"][0]], key=f"{clave}_{e['uid']}", use_container_width=True):
                res = ag.ejecutar_accion(e["accion"], por="calendario maestro")
                if res.get("ok", True):
                    st.toast(f"Listo: {e['titulo']}")
                else:
                    st.error(f"No se pudo: {res}")
                st.rerun()
        else:
            st.markdown(_fila(e, mostrar_fecha), unsafe_allow_html=True)
    if len(evs) > limite:
        st.caption(f"…y {len(evs) - limite} más en la pestaña Agenda.")


def _tab_hoy(hoy: date, fuentes: tuple[str, ...]) -> None:
    evs = ag.eventos(hoy - timedelta(days=90), hoy + timedelta(days=3), fuentes=fuentes)
    urgentes = [e for e in evs if not e["hecho"] and e["fuente"] not in ("AGENTE", "FESTIVO")
                and e["fecha"] <= hoy]
    proximos = [e for e in evs if not e["hecho"] and e["fuente"] != "AGENTE" and hoy < e["fecha"] <= hoy + timedelta(days=3)]
    shaki = [e for e in ag.eventos(hoy, hoy, fuentes=("AGENTE",)) if e["fecha"] <= hoy]
    izq, der = st.columns([1.5, 1], gap="large")
    with izq:
        st.markdown(f'<div class="cm-h"><b>Para hoy y vencido</b><span>{len(urgentes)} asunto(s)</span></div>',
                    unsafe_allow_html=True)
        _lista_con_acciones(urgentes, "hoy", mostrar_fecha=True)
        st.markdown(f'<div class="cm-h" style="margin-top:18px"><b>Próximos 3 días</b><span>{len(proximos)}</span></div>',
                    unsafe_allow_html=True)
        _lista_con_acciones(proximos, "prox", mostrar_fecha=True)
    with der:
        st.markdown(f'<div class="cm-h"><b>Lo que Shaki hace hoy</b><span>{len(shaki)} tarea(s)</span></div>',
                    unsafe_allow_html=True)
        st.markdown("".join(_fila(e) for e in shaki) or '<div class="cm-s">Sin automatizaciones hoy.</div>',
                    unsafe_allow_html=True)


def _tab_semana(hoy: date, fuentes: tuple[str, ...]) -> None:
    c1, c2, c3 = st.columns([1, 3, 1])
    off = st.session_state.get("cm_sem", 0)
    if c1.button("← Semana anterior", use_container_width=True):
        st.session_state.cm_sem = off - 1
        st.rerun()
    if c3.button("Semana siguiente →", use_container_width=True):
        st.session_state.cm_sem = off + 1
        st.rerun()
    lunes = hoy - timedelta(days=hoy.weekday()) + timedelta(weeks=off)
    domingo = lunes + timedelta(days=6)
    c2.markdown(f'<div style="text-align:center" class="cm-eb">{lunes:%d/%m} — {domingo:%d/%m/%Y}'
                f'{"  ·  esta semana" if off == 0 else ""}</div>', unsafe_allow_html=True)
    evs = [e for e in ag.eventos(lunes, domingo, fuentes=fuentes) if lunes <= e["fecha"] <= domingo]
    cols = []
    for i in range(7):
        d = lunes + timedelta(days=i)
        del_dia = [e for e in evs if e["fecha"] == d]
        fest = any(e["fuente"] == "FESTIVO" for e in del_dia)
        chips = "".join(
            f'<div class="cm-chip" style="border-color:{_col(e["fuente"])}">'
            f'{escape(e["titulo"])}<small>{escape((e["hora"] + " · ") if e["hora"] else "")}'
            f'{escape(ag.FUENTES[e["fuente"]]["nombre"])}{(" · " + _pesos(e["valor"])) if e["valor"] else ""}</small></div>'
            for e in del_dia if not e["hecho"])
        hechos = sum(1 for e in del_dia if e["hecho"])
        if hechos:
            chips += f'<div class="cm-more" style="color:#2FB36D">✓ {hechos} hecho(s)</div>'
        clase = "hoy" if d == hoy else "fest" if fest else ""
        cols.append(f'<div class="cm-col {clase}"><div class="cm-ch"><b>{d.day}</b><span>{DIAS_C[i]}</span></div>'
                    f'{chips or "<div class=cm-s>—</div>"}</div>')
    st.markdown(f'<div class="cm-week">{"".join(cols)}</div>', unsafe_allow_html=True)


def _tab_mes(hoy: date, fuentes: tuple[str, ...]) -> None:
    c1, c2 = st.columns([1, 1])
    anio = c1.selectbox("Año", [hoy.year - 1, hoy.year, hoy.year + 1], index=1, key="cm_mes_anio")
    mes = c2.selectbox("Mes", list(range(1, 13)), index=hoy.month - 1, format_func=lambda m: MESES[m - 1],
                       key="cm_mes_mes")
    cal = calendar.Calendar(firstweekday=0).monthdatescalendar(anio, mes)
    evs = ag.eventos(cal[0][0], cal[-1][-1], fuentes=fuentes)
    celdas = ["".join(f'<div class="cm-mh">{d}</div>' for d in DIAS_C)]
    for semana in cal:
        for d in semana:
            del_dia = [e for e in evs if e["fecha"] == d]
            fest = any(e["fuente"] == "FESTIVO" for e in del_dia)
            visibles = [e for e in del_dia if e["fuente"] != "FESTIVO"]
            chips = "".join(
                f'<span class="cm-mc" style="background:{_col(e["fuente"])}22;border-left:2px solid {_col(e["fuente"])}'
                f'{";opacity:.5;text-decoration:line-through" if e["hecho"] else ""}" title="{escape(e["titulo"])}">'
                f'{escape(e["titulo"])}</span>' for e in visibles[:3])
            mas = f'<div class="cm-more">+{len(visibles) - 3} más</div>' if len(visibles) > 3 else ""
            clase = " ".join(x for x in ["out" if d.month != mes else "", "hoy" if d == hoy else "",
                                         "fest" if fest else ""] if x)
            celdas.append(f'<div class="cm-md {clase}"><div class="cm-mn">{d.day}</div>{chips}{mas}</div>')
    st.markdown(f'<div class="cm-month">{"".join(celdas)}</div>', unsafe_allow_html=True)


def _tab_agenda(hoy: date, fuentes: tuple[str, ...]) -> None:
    c1, c2 = st.columns([1, 1])
    dias = c1.segmented_control("Horizonte", [7, 30, 60, 90], default=30, format_func=lambda d: f"{d} días",
                                key="cm_hz") or 30
    ver_hechos = c2.toggle("Mostrar lo ya hecho", value=False, key="cm_hechos")
    evs = ag.eventos(hoy - timedelta(days=90), hoy + timedelta(days=dias), fuentes=fuentes, incluir_hechos=ver_hechos)
    evs = [e for e in evs if e["fecha"] >= hoy or not e["hecho"]]
    if not evs:
        st.info("Sin eventos en este rango.")
        return
    actual = None
    for e in evs[:200]:
        f = max(e["fecha"], hoy) if e["nivel"] == "VENCIDO" else e["fecha"]
        grupo = "Vencido" if e["nivel"] == "VENCIDO" else f"{DIAS[f.weekday()]} {f.day} de {MESES[f.month - 1].lower()}"
        if grupo != actual:
            actual = grupo
            st.markdown(f'<div class="cm-h" style="margin-top:14px"><b>{escape(grupo)}</b></div>', unsafe_allow_html=True)
        _lista_con_acciones([e], "ag", mostrar_fecha=e["nivel"] == "VENCIDO")
    df = pd.DataFrame([{"fecha": e["fecha"], "hora": e["hora"], "fuente": ag.FUENTES[e["fuente"]]["nombre"],
                        "asunto": e["titulo"], "detalle": e["sub"], "valor": e["valor"], "estado": e["nivel"]}
                       for e in evs])
    st.download_button("Descargar agenda (CSV)", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"agenda_shaki_{hoy}.csv", mime="text/csv")


# ───────────────────────── Automatizaciones (antes: todo el calendario) ─────────────────────────

def _tab_automatizaciones(hoy: date) -> None:
    df_venc = tareas_vencidas()
    df_activas = listar_todas_activas()
    t1, t2, t3 = st.tabs(["Tareas activas", "Registro de ejecuciones", "Nueva tarea"])
    with t1:
        if not df_venc.empty:
            st.error(f"{len(df_venc)} tarea(s) atrasada(s)")
            for _, row in df_venc.iterrows():
                c1, c2 = st.columns([4, 1])
                c1.write(f"#{row['id']} {row['titulo']} — {row['modulo']}")
                if c2.button("Ejecutar", key=f"run_venc_{row['id']}"):
                    ejecutar_tarea_por_id(int(row["id"]))
                    st.rerun()
        st.dataframe(df_activas, use_container_width=True, hide_index=True)
    with t2:
        log = obtener_log_reciente(80)
        if log.empty:
            st.info("Sin ejecuciones registradas aún.")
        else:
            st.dataframe(log, use_container_width=True, hide_index=True)
    with t3:
        with st.form("nueva_tarea_cal"):
            titulo = st.text_input("Título *")
            descripcion = st.text_area("Descripción")
            col_a, col_b, col_c = st.columns(3)
            modulo = col_a.selectbox("Módulo", sorted(MODULOS_VALIDOS))
            tipo = col_b.selectbox("Tipo", ["TAREA_MANUAL", "RECORDATORIO", "VENCIMIENTO", "REUNION", "ALERTA",
                                            "AUTOMATICA"])
            callback_opts = [None] + sorted(CALLBACKS.keys())
            funcion_callback = col_c.selectbox("Acción automática (opcional)", callback_opts,
                                               format_func=lambda x: "Ninguna" if x is None else x)
            col_d, col_e = st.columns(2)
            prioridad = col_d.selectbox("Prioridad", ["MEDIA", "ALTA", "CRITICA", "BAJA"])
            recurrencia = col_e.selectbox("Recurrencia", [None, "DIARIA", "DIAS_HABILES", "SEMANAL", "MENSUAL", "ANUAL"],
                                          format_func=lambda x: "Única vez" if x is None else x)
            hora = st.text_input("Hora (HH:MM)", value="09:00")
            fecha = st.date_input("Fecha", value=hoy)
            if st.form_submit_button("Agregar al calendario"):
                if not titulo.strip():
                    st.error("El título es obligatorio.")
                else:
                    try:
                        h, m = map(int, hora.split(":"))
                    except ValueError:
                        h, m = 9, 0
                    inicio = datetime.combine(fecha, datetime.min.time().replace(hour=h, minute=m))
                    tid = agregar_tarea(titulo=titulo.strip(), modulo=modulo, tipo=tipo, fecha_inicio=inicio,
                                        descripcion=descripcion or None, prioridad=prioridad, recurrencia=recurrencia,
                                        recurrencia_config={"hora": hora} if recurrencia else None,
                                        funcion_callback=funcion_callback, creada_por="MANUAL")
                    st.success(f"Tarea #{tid} agregada.")
                    st.rerun()
        if not df_activas.empty:
            st.divider()
            opciones = {f"#{r['id']} · {r['titulo']}": int(r["id"]) for _, r in df_activas.iterrows()}
            sel = st.selectbox("Desactivar una tarea", list(opciones.keys()))
            if st.button("Desactivar tarea seleccionada"):
                cancelar_tarea(opciones[sel])
                st.rerun()


# ───────────────────────── Página ─────────────────────────

def render() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    hoy = date.today()
    st.markdown("## Calendario Maestro")
    r = ag.resumen(hoy)
    _hero(hoy, ag.eventos(hoy, hoy + timedelta(days=29)), r)
    opciones = list(ag.FUENTES)
    sel = st.pills("Mostrar", opciones, selection_mode="multi", default=[f for f in opciones if f != "AGENTE"],
                   format_func=lambda f: ag.FUENTES[f]["nombre"], key="cm_fuentes", label_visibility="collapsed")
    fuentes = tuple(sel or opciones)
    t_hoy, t_sem, t_mes, t_ag, t_auto = st.tabs(["Hoy", "Semana", "Mes", "Agenda", "Automatizaciones"])
    with t_hoy:
        _tab_hoy(hoy, fuentes)
    with t_sem:
        _tab_semana(hoy, fuentes)
    with t_mes:
        _tab_mes(hoy, fuentes)
    with t_ag:
        _tab_agenda(hoy, fuentes)
    with t_auto:
        _tab_automatizaciones(hoy)
