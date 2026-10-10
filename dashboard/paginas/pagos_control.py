"""Pestaña principal de Pagos: libro "Control de pagos" + alertas 24h con botón "Ya lo pagué"."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from config import cfg
from dashboard.estilos import ACCENT, PLOTLY_LAYOUT
from database import get_conn
from modulos import control_pagos as cp

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

CSS = """
<style>
.cp-head { display:flex; flex-wrap:wrap; justify-content:space-between; align-items:flex-end; gap:12px; margin-bottom:6px; }
.cp-src { font-size:12px; color:#8B8B93; font-family:'Geist Mono',monospace; }
.cp-day { display:flex; align-items:baseline; gap:10px; margin:22px 0 4px 0; padding-bottom:8px; border-bottom:1px solid #1F2024; }
.cp-day b { font-size:15px; color:#FFFFFF; font-weight:500; }
.cp-day span { font-size:12px; color:#8B8B93; font-family:'Geist Mono',monospace; }
.cp-row-t { font-size:15px; color:#E8E8EA; line-height:1.35; }
.cp-row-s { font-size:12.5px; color:#8B8B93; margin-top:3px; line-height:1.45; }
.cp-tag { font-size:10.5px; font-family:'Geist Mono',monospace; padding:3px 8px; border-radius:6px; white-space:nowrap;
          font-weight:500; letter-spacing:.03em; display:inline-block; }
.cp-VENCIDO, .cp-HOY { background:#FF6A3D; color:#0A0B0D; }
.cp-MAÑANA { background:#F5C542; color:#0A0B0D; }
.cp-PRÓXIMO { border:1px solid #F5C542; color:#F5C542; }
.cp-AL-DÍA { border:1px solid #3F3F46; color:#C4C4CC; }
.cp-PAGADO { background:#14321F; color:#4ADE80; }
.cp-ANULADO { border:1px dashed #3F3F46; color:#71717A; }
.cp-enproc { font-size:10.5px; color:#7DD3FC; font-family:'Geist Mono',monospace; margin-left:6px; }
.cp-sent { font-size:11px; color:#8B8B93; font-family:'Geist Mono',monospace; }
.cp-money { font-size:15px; color:#FFFFFF; font-weight:300; text-align:right; white-space:nowrap; }
.cp-card { background:#0F1012; border:1px solid #1F2024; border-radius:18px; padding:18px 20px; }
.cp-card h4 { margin:0 0 8px 0; font-size:16px; font-weight:500; color:#FFFFFF; }
.cp-kv { font-size:13px; color:#A1A1AA; line-height:1.9; }
.cp-kv b { color:#E8E8EA; font-weight:500; }
.cp-warn { color:#F5C542; }
</style>
"""


def _fecha_corta(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d.day} {MESES[d.month - 1][:3].lower()}"


def _miles(v) -> str:
    return f"${float(v):,.0f}".replace(",", ".") if v else "—"


# ───────────────────────── Carga del libro ─────────────────────────

def _guardar_subido(archivo) -> Path:
    destino = cp.ruta_excel()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(archivo.getbuffer())
    return destino


def _panel_carga(vacio: bool) -> None:
    archivo = st.file_uploader(
        "Suba el Excel de control de pagos (hojas Maestro de Pagos, Calendario Anual y Festivos)",
        type=["xlsx"], key="cp_upload", label_visibility="collapsed" if not vacio else "visible",
    )
    if archivo is not None and st.button("Cargar este archivo", key="cp_upload_btn", type="primary"):
        try:
            ruta = _guardar_subido(archivo)
            res = cp.importar_excel(ruta)
            st.success(f"Listo: {res['total']} cuotas cargadas ({res['nuevos']} nuevas). Guardado en {ruta}.")
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudo leer el archivo: {exc}")


# ───────────────────────── Bloques ─────────────────────────

def _indicadores(r: dict) -> None:
    pct = r["al_dia_pct"]
    items = [
        ("Vencidos", r["vencidos"], "SIN PAGAR", r["vencidos"] > 0),
        ("Vencen hoy", r["hoy"], "FECHA SUGERIDA", r["hoy"] > 0),
        ("Mañana", r["manana"], "RECIBEN ALERTA 24H", False),
        ("Próximos 7 días", r["semana"], "PENDIENTES", False),
        ("Al día este mes", f"{pct}%", f"{r['mes_pagados']} DE {r['mes_total']} PAGADOS", False),
    ]
    html = "".join(
        f'<div class="sk-kpi"><span class="sk-kpi-l">{l}</span>'
        f'<span class="sk-kpi-v" style="{"color:" + ACCENT if alerta else ""}">{v}</span>'
        f'<span class="sk-kpi-f">{f}</span></div>'
        for l, v, f, alerta in items
    )
    st.markdown(f'<div class="sk-kpis" style="margin:18px 0 8px 0">{html}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sk-bar" style="margin:14px 0 6px 0"><div style="flex:{max(pct, 1)} 1 0;background:#4ADE80"></div>'
        f'<div style="flex:{max(100 - pct, 0)} 1 0;background:#26272C"></div></div>'
        f'<div class="sk-legend"><span style="color:#4ADE80">■ PAGADO {pct}%</span>'
        f'<span>■ PENDIENTE {100 - pct}% · {r["mes_pendientes"]} CUOTAS</span></div>',
        unsafe_allow_html=True,
    )


def _estado_auto() -> tuple[bool, list[tuple[bool, str, str]]]:
    """Lista de chequeo para que la alerta salga sola."""
    e = cp.estado_canales()
    try:
        from utils.calendario_maestro import executor_esta_activo

        prog = executor_esta_activo()
    except Exception:
        prog = False
    items = [
        (prog, "Agente encendido", "Programador activo: revisa cada 2 min" if prog
         else "Inicie el agente (scripts/iniciar_shaki_24x7.ps1)"),
        (bool(e["correo"] and e["destinos_correo"]), "Correo",
         f'{e["correo"]} → {", ".join(e["destinos_correo"])}' if e["correo"] and e["destinos_correo"]
         else ("Falta SMTP_HOST/SMTP_USER/SMTP_PASSWORD" if not e["correo"] else "Falta PAGOS_ALERTA_EMAILS")),
        (bool(e["whatsapp"] and e["destinos_whatsapp"]), "WhatsApp",
         f'{e["whatsapp"]} → {", ".join(e["destinos_whatsapp"])}' if e["whatsapp"] and e["destinos_whatsapp"]
         else ("Falta TWILIO_ACCOUNT_SID/TOKEN/FROM" if not e["whatsapp"] else "Falta PAGOS_ALERTA_WHATSAPP")),
        (e["url_publica"], 'Botón "Ya lo pagué"',
         e["url"] if e["url_publica"] else f'{e["url"]} solo abre en este PC · configure NGROK_DOMAIN o APP_PUBLIC_URL'),
    ]
    listo = items[0][0] and (items[1][0] or items[2][0]) and items[3][0]
    return listo, items


def _panel_alertas() -> None:
    listo, items = _estado_auto()
    pendientes = cp.pagos_para_alerta()
    filas = "".join(
        f'<div style="display:flex;gap:10px;align-items:flex-start;padding:7px 0;border-top:1px solid #1F2024">'
        f'<span style="color:{"#4ADE80" if ok else "#F5C542"};font-family:Geist Mono,monospace;font-size:12px;'
        f'min-width:16px">{"●" if ok else "○"}</span>'
        f'<div><b style="color:#E8E8EA;font-weight:500">{escape(t)}</b>'
        f'<div style="font-size:12px;color:#8B8B93">{escape(d)}</div></div></div>'
        for ok, t, d in items
    )
    estado = ('<span style="color:#4ADE80">AUTOMÁTICO · ACTIVO</span>' if listo
              else '<span style="color:#F5C542">FALTA CONFIGURAR</span>')
    st.markdown(
        f'<div class="cp-card"><h4>Alerta 24 horas</h4>'
        f'<div class="sk-kpi-f" style="margin-bottom:6px">{estado} · 08:00 Y 16:30 · '
        f'{len(pendientes)} POR AVISAR</div>{filas}</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    if c1.button("Enviar ahora", key="cp_send_now", use_container_width=True, disabled=not pendientes):
        res = cp.enviar_alerta(pendientes)
        if res["sin_canal"]:
            st.error("No salió: configure correo (SMTP) o WhatsApp (Twilio).")
        else:
            st.success(f"Enviado: {res['pagos']} pago(s) · {res['correos']} correo(s) · {res['whatsapp']} WhatsApp.")
    if c2.button("Probar envío", key="cp_test", use_container_width=True,
                 help="Manda un mensaje de prueba a los destinatarios, sin marcar nada como avisado"):
        muestra = cp.listar(date.today(), date.today() + timedelta(days=31), estados=cp.ABIERTOS)[:1]
        if not muestra:
            st.info("No hay cuotas pendientes para usar de ejemplo.")
        else:
            res = cp.enviar_alerta(muestra, marcar=False)
            if res["sin_canal"]:
                st.error("No hay canal configurado todavía.")
            else:
                st.success(f"Prueba: {res['correos']} correo(s) · {res['whatsapp']} WhatsApp. Revise el historial.")
    with c3.popover("Ver ejemplo", use_container_width=True):
        muestra = pendientes or cp.listar(date.today(), date.today() + timedelta(days=31), estados=cp.ABIERTOS)[:1]
        if muestra:
            components.html(cp.html_correo(muestra[:2]), height=520, scrolling=True)
            st.code(cp.texto_whatsapp(muestra[0]), language=None)
        else:
            st.caption("No hay cuotas pendientes para mostrar.")


def _grafica_anual(anio: int) -> None:
    conn = get_conn()
    df = pd.read_sql(
        """SELECT CAST(strftime('%m', fecha_sugerida) AS INTEGER) AS mes, estado, COUNT(*) AS n
           FROM pagos_calendario WHERE anio=? AND estado!='ANULADO' GROUP BY mes, estado""",
        conn, params=(anio,),
    )
    conn.close()
    if df.empty:
        return
    piv = df.pivot_table(index="mes", columns="estado", values="n", aggfunc="sum", fill_value=0).reindex(
        range(1, 13), fill_value=0)
    pag = piv.get("PAGADO", pd.Series(0, index=piv.index))
    pend = piv.drop(columns=[c for c in piv.columns if c == "PAGADO"]).sum(axis=1)
    x = [m[:3] for m in MESES]
    fig = go.Figure()
    fig.add_bar(x=x, y=pag.values, name="Pagadas", marker_color="#4ADE80")
    fig.add_bar(x=x, y=pend.values, name="Pendientes", marker_color="#3F3F46")
    fig.update_layout(**PLOTLY_LAYOUT, barmode="stack", height=230, title=f"Cuotas por mes · {anio}",
                      legend=dict(orientation="h", y=1.15, x=1, xanchor="right"))
    fig.update_yaxes(gridcolor="#1F2024")
    st.plotly_chart(fig, use_container_width=True)


def _filtros(anio: int) -> tuple[date, date, tuple[str, ...] | None, str | None, str | None]:
    hoy = date.today()
    c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1])
    vista = c1.selectbox(
        "Ver", ["Próximos 7 días", "Vencidos sin pagar", "Este mes", "Mes siguiente", "Todo el año"],
        key="cp_vista",
    )
    conn = get_conn()
    centros = [r[0] for r in conn.execute(
        "SELECT DISTINCT centro_costos FROM pagos_calendario WHERE centro_costos IS NOT NULL ORDER BY 1").fetchall()]
    conn.close()
    centro = c2.selectbox("Centro de costos", ["Todos"] + centros, key="cp_centro")
    tipo = c3.selectbox("Tipo", ["Todos", "PAGO", "TAREA"], key="cp_tipo")
    estado = c4.selectbox("Estado", ["Abiertos", "Todos", "PAGADO", "ANULADO"], key="cp_estado")

    estados: tuple[str, ...] | None = {
        "Abiertos": cp.ABIERTOS, "Todos": None, "PAGADO": ("PAGADO",), "ANULADO": ("ANULADO",)}[estado]
    if vista == "Próximos 7 días":
        desde, hasta = hoy, hoy + timedelta(days=7)
    elif vista == "Vencidos sin pagar":
        desde, hasta, estados = date(anio, 1, 1), hoy - timedelta(days=1), cp.ABIERTOS
    elif vista == "Este mes":
        desde, hasta = hoy.replace(day=1), hoy.replace(day=calendar.monthrange(hoy.year, hoy.month)[1])
    elif vista == "Mes siguiente":
        sig = (hoy.replace(day=28) + timedelta(days=4)).replace(day=1)
        desde, hasta = sig, sig.replace(day=calendar.monthrange(sig.year, sig.month)[1])
    else:
        desde, hasta = date(anio, 1, 1), date(anio, 12, 31)
    return desde, hasta, estados, None if centro == "Todos" else centro, None if tipo == "Todos" else tipo


def _fila(p: dict) -> None:
    sem = cp.semaforo(p)
    c1, c2, c3, c4 = st.columns([0.95, 3.6, 0.9, 2.1], vertical_alignment="center")
    c1.markdown(f'<span class="cp-tag cp-{sem.replace(" ", "-")}">{sem}</span>', unsafe_allow_html=True)
    extra = []
    if p.get("referencia"):
        extra.append(escape(str(p["referencia"])))
    extra.append(escape(p.get("centro_costos") or ""))
    if p["tipo"] == "TAREA":
        extra.append("TAREA")
    if str(p["fecha_limite"]) != str(p["fecha_sugerida"]):
        lim = date.fromisoformat(str(p["fecha_limite"]))
        extra.append(f"límite {lim.day}/{lim.month} no hábil, se adelanta")
    enproc = '<span class="cp-enproc">EN PROCESO</span>' if p["estado"] == "EN PROCESO" else ""
    sent = ""
    if p.get("alerta_24h_enviada"):
        sent = f' · <span class="cp-sent">ALERTA ENVIADA {str(p["alerta_24h_enviada"])[5:16]}</span>'
    if p["estado"] == "PAGADO" and p.get("fecha_pago_real"):
        sent = f' · <span class="cp-sent">PAGADO {str(p["fecha_pago_real"])[:10]}</span>'
    c2.markdown(
        f'<div class="cp-row-t">{escape(p["detalle"] or "")}{enproc}</div>'
        f'<div class="cp-row-s">{escape(p["proveedor"] or "")} · {" · ".join(x for x in extra if x)}{sent}</div>',
        unsafe_allow_html=True,
    )
    c3.markdown(f'<div class="cp-money">{_miles(p.get("valor"))}</div>', unsafe_allow_html=True)
    with c4:
        if p["estado"] in cp.ABIERTOS:
            b1, b2 = st.columns([1.25, 1])
            if b1.button("Pagado" if p["tipo"] == "PAGO" else "Hecho", key=f"cp_ok_{p['id']}",
                         type="primary", use_container_width=True):
                cp.marcar_pagado(p["id"], por="dashboard")
                st.rerun()
            with b2.popover("Más", use_container_width=True):
                st.caption(f"{p['id_pago']} · cuota {p['ocurrencia']}")
                if st.button("Enviar alerta ahora", key=f"cp_al_{p['id']}", use_container_width=True):
                    r = cp.enviar_alerta([p], marcar=False)
                    if r["sin_canal"]:
                        st.error("Sin canal configurado")
                    else:
                        st.success(f"{r['correos']} correo(s) · {r['whatsapp']} WhatsApp")
                if p["estado"] != "EN PROCESO" and st.button("En proceso", key=f"cp_ep_{p['id']}",
                                                             use_container_width=True):
                    cp.cambiar_estado(p["id"], "EN PROCESO")
                    st.rerun()
                if st.button("Anular", key=f"cp_an_{p['id']}", use_container_width=True):
                    cp.cambiar_estado(p["id"], "ANULADO")
                    st.rerun()
        elif st.button("Reabrir", key=f"cp_re_{p['id']}", use_container_width=True):
            cp.cambiar_estado(p["id"], "PENDIENTE")
            st.rerun()


def _agenda(anio: int) -> None:
    desde, hasta, estados, centro, tipo = _filtros(anio)
    filas = cp.listar(desde, hasta, estados, centro)
    if tipo:
        filas = [f for f in filas if f["tipo"] == tipo]
    if not filas:
        st.markdown('<div class="sk-row"><span class="sk-row-s">Nada pendiente en esta vista. Todo al día.</span></div>',
                    unsafe_allow_html=True)
        return
    limite = 80
    if len(filas) > limite:
        st.caption(f"Mostrando {limite} de {len(filas)} cuotas. Afine el filtro para ver el resto.")
    dia_actual = None
    for p in filas[:limite]:
        d = date.fromisoformat(str(p["fecha_sugerida"]))
        if d != dia_actual:
            dia_actual = d
            del_dia = [f for f in filas if f["fecha_sugerida"] == p["fecha_sugerida"]]
            st.markdown(
                f'<div class="cp-day"><b>{_fecha_corta(d)}</b><span>{len(del_dia)} CUOTA(S)</span></div>',
                unsafe_allow_html=True,
            )
        _fila(p)


def _historial_alertas() -> None:
    conn = get_conn()
    df = pd.read_sql(
        """SELECT a.enviado_en AS enviado, a.canal, a.destino, CASE a.ok WHEN 1 THEN 'OK' ELSE 'FALLÓ' END AS resultado,
                  p.detalle, p.fecha_sugerida AS fecha_pago, p.estado
           FROM pagos_calendario_alertas a JOIN pagos_calendario p ON p.id=a.pago_id
           ORDER BY a.id DESC LIMIT 50""",
        conn,
    )
    conn.close()
    if df.empty:
        st.caption("Aún no se han enviado alertas.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


# ───────────────────────── Página ─────────────────────────

def render() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    cp.inicializar_tablas()
    ruta = cp.ruta_excel()

    if not cp.hay_datos():
        st.markdown(
            '<div class="cp-card"><h4>Cargue su control de pagos</h4><div class="cp-kv">'
            'Suba el libro con las hojas <b>Maestro de Pagos</b>, <b>Calendario Anual</b> y <b>Festivos</b>. '
            f'Quedará guardado en <b>{escape(str(ruta))}</b> y el agente lo leerá cada mañana.</div></div>',
            unsafe_allow_html=True,
        )
        _panel_carga(vacio=True)
        return

    ultima = (cp._meta("ultima_importacion") or "")[:16].replace("T", " ")
    conn = get_conn()
    anio = conn.execute("SELECT MAX(anio) FROM pagos_calendario").fetchone()[0] or date.today().year
    conn.close()
    r = cp.resumen()

    c1, c2 = st.columns([3, 1.2], vertical_alignment="bottom")
    c1.markdown(
        f'<div class="sk-eyebrow">Control de pagos · {anio}</div>'
        f'<div class="cp-src">{escape(ruta.name)} · leído {escape(ultima)}'
        f'{" · " + str(r["excel_pendiente"]) + " CAMBIO(S) POR ESCRIBIR EN EXCEL (¿ARCHIVO ABIERTO?)" if r["excel_pendiente"] else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )
    if c2.button("Releer Excel", key="cp_reload", use_container_width=True):
        try:
            res = cp.importar_si_existe()
            st.toast(f"Excel leído: {res['total']} cuotas" if res else "No se encontró el archivo")
        except Exception as exc:
            st.error(f"No se pudo leer: {exc}")
        st.rerun()

    _indicadores(r)

    izq, der = st.columns([1, 1.25], gap="large")
    with izq:
        _panel_alertas()
    with der:
        _grafica_anual(anio)

    st.markdown('<div class="sk-card-h" style="margin-top:18px"><h4>Agenda de pagos</h4></div>',
                unsafe_allow_html=True)
    _agenda(anio)

    st.write("")
    with st.expander("Historial de alertas enviadas"):
        _historial_alertas()
    with st.expander("Reemplazar el Excel"):
        _panel_carga(vacio=False)
