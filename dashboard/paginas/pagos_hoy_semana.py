"""Tableros "Hoy" y "Semana" del control de pagos."""
from __future__ import annotations

from datetime import date, timedelta
from html import escape

import streamlit as st

from database import get_conn
from modulos import control_pagos as cp

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_L = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
           "octubre", "noviembre", "diciembre"]

CSS = """
<style>
.hs-hero { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:28px; padding:8px 0 22px 0; }
.hs-eyebrow { font-size:12px; color:#8B8B93; letter-spacing:.1em; text-transform:uppercase; font-family:'Geist Mono',monospace; }
.hs-day { font-size:clamp(40px,5vw,64px); font-weight:300; letter-spacing:-.04em; color:#FFFFFF; line-height:1; margin:10px 0 12px 0; }
.hs-sub { font-size:15px; color:#A1A1AA; }
.hs-sub b { color:#FFFFFF; font-weight:500; }
.hs-ring { position:relative; width:150px; height:150px; flex:none; }
.hs-ring-c { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; }
.hs-ring-c b { font-size:34px; font-weight:300; color:#FFFFFF; letter-spacing:-.03em; }
.hs-ring-c span { font-size:10.5px; color:#8B8B93; font-family:'Geist Mono',monospace; letter-spacing:.06em; }
.hs-sec { display:flex; align-items:baseline; justify-content:space-between; margin:26px 0 10px 0; }
.hs-sec .hs-h { margin:0; font-size:18px; font-weight:500; color:#FFFFFF; letter-spacing:-.01em; font-family:inherit; }
.hs-sec .hs-n { font-size:11px; color:#8B8B93; font-family:'Geist Mono',monospace; letter-spacing:.06em; }
.hs-card { background:#0F1012; border:1px solid #1F2024; border-radius:16px; padding:16px 18px; }
.hs-card.acc { border-color:#5A2A1B; background:linear-gradient(180deg,#1A110E 0%,#0F1012 70%); }
.hs-card.ok { opacity:.62; }
.hs-tag { display:inline-block; font-size:10px; font-family:'Geist Mono',monospace; letter-spacing:.05em; padding:3px 7px;
          border-radius:6px; font-weight:500; margin-bottom:10px; }
.t-VENCIDO, .t-HOY { background:#FF6A3D; color:#0A0B0D; }
.t-MAÑANA { background:#F5C542; color:#0A0B0D; }
.t-PRÓXIMO { border:1px solid #F5C542; color:#F5C542; }
.t-AL-DÍA { border:1px solid #3F3F46; color:#C4C4CC; }
.t-PAGADO { background:#14321F; color:#4ADE80; }
.t-ANULADO { border:1px dashed #3F3F46; color:#71717A; }
.hs-t { font-size:15px; color:#FFFFFF; line-height:1.3; font-weight:500; }
.hs-s { font-size:12.5px; color:#8B8B93; margin-top:4px; line-height:1.45; }
.hs-m { font-size:20px; color:#FFFFFF; font-weight:300; margin-top:10px; letter-spacing:-.02em; }
.hs-empty { border:1px dashed #26272C; border-radius:16px; padding:22px; text-align:center; color:#8B8B93; font-size:14px; }
.hs-sent { font-size:10.5px; font-family:'Geist Mono',monospace; color:#4ADE80; margin-top:8px; }
.hs-sent.no { color:#F5C542; }
/* Semana */
.wk-col { min-height:120px; }
.wk-h { padding:9px 8px 7px 8px; border-radius:12px 12px 0 0; border:1px solid #1F2024; border-bottom:none; background:#0F1012; }
.wk-h.today { background:#F4F4F5; }
.wk-h.today .wk-d, .wk-h.today .wk-n, .wk-h.today .wk-c { color:#0A0B0D !important; }
.wk-d { font-size:11px; color:#8B8B93; font-family:'Geist Mono',monospace; letter-spacing:.06em; }
.wk-n { font-size:26px; font-weight:300; color:#FFFFFF; line-height:1.1; }
.wk-c { font-size:10.5px; color:#8B8B93; font-family:'Geist Mono',monospace; }
.wk-body { border:1px solid #1F2024; border-top:none; border-radius:0 0 12px 12px; padding:8px; min-height:60px; margin-bottom:8px; }
.wk-card { border-radius:9px; padding:7px 7px; margin-bottom:6px; background:#141518; border-left:3px solid #3F3F46; }
.wk-card.c-VENCIDO, .wk-card.c-HOY { border-left-color:#FF6A3D; }
.wk-card.c-MAÑANA, .wk-card.c-PRÓXIMO { border-left-color:#F5C542; }
.wk-card.c-PAGADO { border-left-color:#4ADE80; opacity:.55; }
.wk-card.c-ANULADO { opacity:.4; }
.wk-ct { font-size:11.5px; color:#E8E8EA; line-height:1.25; overflow:hidden; display:-webkit-box; -webkit-line-clamp:3; word-break:break-word; -webkit-box-orient:vertical; }
.wk-cs { font-size:10.5px; color:#8B8B93; margin-top:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.wk-free { font-size:11px; color:#52525B; text-align:center; padding:14px 0; }
.wk-bar { display:flex; height:8px; border-radius:999px; overflow:hidden; gap:2px; margin:6px 0 4px 0; }
</style>
"""


def _miles(v) -> str:
    return f"${float(v):,.0f}".replace(",", ".") if v else ""


def _anillo(pct: int, centro: str, pie: str, color: str = "#4ADE80") -> str:
    r, c = 62, 2 * 3.14159 * 62
    lleno = c * max(0, min(pct, 100)) / 100
    return (
        f'<div class="hs-ring"><svg width="150" height="150" viewBox="0 0 150 150" role="img" '
        f'aria-label="{pct}% {escape(pie)}">'
        f'<circle cx="75" cy="75" r="{r}" fill="none" stroke="#1F2024" stroke-width="10"></circle>'
        f'<circle cx="75" cy="75" r="{r}" fill="none" stroke="{color}" stroke-width="10" stroke-linecap="round" '
        f'stroke-dasharray="{lleno:.1f} {c:.1f}" transform="rotate(-90 75 75)"></circle></svg>'
        f'<div class="hs-ring-c"><b>{escape(centro)}</b><span>{escape(pie)}</span></div></div>'
    )


def _pagados_en(desde: date, hasta: date) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        f"SELECT {', '.join(cp.COLUMNAS)} FROM pagos_calendario WHERE estado='PAGADO' "
        "AND fecha_pago_real BETWEEN ? AND ? ORDER BY actualizado_en DESC",
        (desde.isoformat(), hasta.isoformat()),
    ).fetchall()
    conn.close()
    return [dict(zip(cp.COLUMNAS, r)) for r in rows]


def _proxima_ronda() -> str:
    from datetime import datetime

    ahora = datetime.now()
    if (ahora.hour, ahora.minute) < (8, 0):
        return "SALE 08:00"
    if (ahora.hour, ahora.minute) < (16, 30):
        return "SALE 16:30"
    return "REVISAR CANALES"


def _tarjeta(p: dict, hoy: date, clave: str, mostrar_alerta: bool = False) -> None:
    sem = cp.semaforo(p, hoy)
    clase = "acc" if sem in ("VENCIDO", "HOY") else "ok" if sem in ("PAGADO", "ANULADO") else ""
    fecha = date.fromisoformat(str(p["fecha_sugerida"]))
    extra = []
    if sem == "VENCIDO":
        extra.append(f"venció hace {(hoy - fecha).days} día(s)")
    if p.get("referencia"):
        extra.append(escape(str(p["referencia"])))
    extra.append(escape(p.get("centro_costos") or ""))
    alerta = ""
    if mostrar_alerta and p["estado"] in cp.ABIERTOS:
        alerta = (f'<div class="hs-sent">✓ ALERTA ENVIADA {str(p["alerta_24h_enviada"])[11:16]}</div>'
                  if p.get("alerta_24h_enviada") else f'<div class="hs-sent no">○ ALERTA PENDIENTE ({_proxima_ronda()})</div>')
    st.markdown(
        f'<div class="hs-card {clase}"><span class="hs-tag t-{sem.replace(" ", "-")}">{sem}</span>'
        f'<div class="hs-t">{escape(p["detalle"] or "")}</div>'
        f'<div class="hs-s">{escape(p["proveedor"] or "")} · {" · ".join(x for x in extra if x)}</div>'
        f'{"<div class=hs-m>" + _miles(p.get("valor")) + "</div>" if p.get("valor") else ""}{alerta}</div>',
        unsafe_allow_html=True,
    )
    if p["estado"] in cp.ABIERTOS:
        if st.button("Ya lo pagué" if p["tipo"] == "PAGO" else "Ya lo hice", key=f"{clave}_{p['id']}",
                     type="primary", width="stretch"):
            cp.marcar_pagado(p["id"], por="dashboard")
            st.rerun()


def _grilla(filas: list[dict], hoy: date, clave: str, columnas: int = 3, alerta: bool = False) -> None:
    for i in range(0, len(filas), columnas):
        cols = st.columns(columnas, gap="medium")
        for col, p in zip(cols, filas[i:i + columnas]):
            with col:
                _tarjeta(p, hoy, clave, alerta)
        st.write("")


# ───────────────────────── HOY ─────────────────────────

def render_hoy() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    if not cp.hay_datos():
        st.info("Cargue el Excel en la pestaña Control de pagos.")
        return
    hoy = date.today()
    manana = hoy + timedelta(days=1)
    de_hoy = cp.listar(hoy, hoy)
    vencidos = cp.listar(date(hoy.year, 1, 1), hoy - timedelta(days=1), cp.ABIERTOS)
    de_manana = cp.listar(manana, manana, cp.ABIERTOS)
    pagados_hoy = _pagados_en(hoy, hoy)

    abiertos_hoy = [p for p in de_hoy if p["estado"] in cp.ABIERTOS]
    total_hoy = len([p for p in de_hoy if p["estado"] != "ANULADO"])
    listos_hoy = len([p for p in de_hoy if p["estado"] == "PAGADO"])
    pct = round(100 * listos_hoy / total_hoy) if total_hoy else 100
    urgentes = len(abiertos_hoy) + len(vencidos)

    if urgentes:
        frase = f"Tienes <b>{urgentes}</b> pago(s) por resolver hoy"
    elif de_manana:
        frase = f"Hoy estás al día · mañana vencen <b>{len(de_manana)}</b>"
    else:
        frase = "Todo al día. Nada vence hoy ni mañana."
    centro = f"{listos_hoy}/{total_hoy}" if total_hoy else "✓"
    st.markdown(
        f'<div class="hs-hero"><div><div class="hs-eyebrow">Hoy · {DIAS[hoy.weekday()]}</div>'
        f'<div class="hs-day">{hoy.day} de {MESES_L[hoy.month - 1]}</div>'
        f'<div class="hs-sub">{frase}</div></div>'
        f'{_anillo(pct, centro, "PAGADOS HOY" if total_hoy else "DÍA LIBRE", "#4ADE80" if not urgentes else "#FF6A3D")}'
        f'</div>',
        unsafe_allow_html=True,
    )

    if vencidos:
        st.markdown(f'<div class="hs-sec"><div class="hs-h">Vencidos sin pagar</div><div class="hs-n">{len(vencidos)} CUOTA(S)</div></div>',
                    unsafe_allow_html=True)
        _grilla(vencidos[:9], hoy, "hv")
        if len(vencidos) > 9:
            st.caption(f"Y {len(vencidos) - 9} más en Control de pagos → Vencidos sin pagar.")

    st.markdown(f'<div class="hs-sec"><div class="hs-h">Para pagar hoy</div><div class="hs-n">{len(abiertos_hoy)} PENDIENTE(S)</div></div>',
                unsafe_allow_html=True)
    if abiertos_hoy:
        _grilla(abiertos_hoy, hoy, "hh")
    else:
        st.markdown('<div class="hs-empty">No hay pagos pendientes para hoy.</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="hs-sec"><div class="hs-h">Mañana · reciben alerta 24h</div><div class="hs-n">{len(de_manana)} CUOTA(S)</div></div>',
                unsafe_allow_html=True)
    if de_manana:
        _grilla(de_manana, hoy, "hm", alerta=True)
    else:
        st.markdown(f'<div class="hs-empty">Nada vence el {DIAS[manana.weekday()].lower()}.</div>',
                    unsafe_allow_html=True)

    if pagados_hoy:
        st.markdown(f'<div class="hs-sec"><div class="hs-h">Pagado hoy</div><div class="hs-n">{len(pagados_hoy)} LISTO(S)</div></div>',
                    unsafe_allow_html=True)
        filas = "".join(
            f'<div class="sk-log"><b>{escape(p["detalle"] or "")}</b> · {escape(p["proveedor"] or "")} · '
            f'<span style="color:#4ADE80">{escape(p.get("confirmado_por") or "Excel")}</span></div>'
            for p in pagados_hoy
        )
        st.markdown(filas, unsafe_allow_html=True)


# ───────────────────────── SEMANA ─────────────────────────

def render_semana() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    if not cp.hay_datos():
        st.info("Cargue el Excel en la pestaña Control de pagos.")
        return
    hoy = date.today()
    off = st.session_state.get("wk_off", 0)
    lunes = hoy - timedelta(days=hoy.weekday()) + timedelta(weeks=off)
    domingo = lunes + timedelta(days=6)
    filas = cp.listar(lunes, domingo)
    vivas = [p for p in filas if p["estado"] != "ANULADO"]
    pagadas = [p for p in vivas if p["estado"] == "PAGADO"]
    abiertas = [p for p in vivas if p["estado"] in cp.ABIERTOS]
    vencidas = [p for p in abiertas if cp.semaforo(p, hoy) == "VENCIDO"]
    pct = round(100 * len(pagadas) / len(vivas)) if vivas else 100
    valor = sum(p["valor"] or 0 for p in abiertas)

    rango = (f"{lunes.day} {MESES[lunes.month - 1]} – {domingo.day} {MESES[domingo.month - 1]}")
    etiqueta = "Esta semana" if off == 0 else "Semana siguiente" if off == 1 else "Semana anterior" if off == -1 \
        else f"Semana {'+' if off > 0 else ''}{off}"
    c1, c2, c3, c4 = st.columns([4, 1, 1, 1], vertical_alignment="center")
    c1.markdown(f'<div class="hs-eyebrow">{etiqueta}</div><div class="hs-day" style="font-size:44px">{rango}</div>',
                unsafe_allow_html=True)
    if c2.button("‹ Anterior", key="wk_prev", width="stretch"):
        st.session_state.wk_off = off - 1
        st.rerun()
    if c3.button("Hoy", key="wk_today", width="stretch", disabled=off == 0):
        st.session_state.wk_off = 0
        st.rerun()
    if c4.button("Siguiente ›", key="wk_next", width="stretch"):
        st.session_state.wk_off = off + 1
        st.rerun()

    kpis = [
        ("Cuotas", len(vivas), "EN LA SEMANA"),
        ("Pagadas", len(pagadas), f"{pct}% AL DÍA"),
        ("Pendientes", len(abiertas), _miles(valor) or "VALOR POR DEFINIR"),
        ("Vencidas", len(vencidas), "SIN PAGAR"),
    ]
    html = "".join(
        f'<div class="sk-kpi"><span class="sk-kpi-l">{l}</span>'
        f'<span class="sk-kpi-v" style="{"color:#FF6A3D" if l == "Vencidas" and v else ""}">{v}</span>'
        f'<span class="sk-kpi-f">{f}</span></div>' for l, v, f in kpis
    )
    st.markdown(
        f'<div class="sk-kpis" style="grid-template-columns:repeat(4,minmax(0,1fr));margin:14px 0 6px 0">{html}</div>'
        f'<div class="wk-bar"><div style="flex:{max(pct, 1)} 1 0;background:#4ADE80"></div>'
        f'<div style="flex:{max(100 - pct, 0)} 1 0;background:#26272C"></div></div>',
        unsafe_allow_html=True,
    )
    st.write("")

    cols = st.columns(7, gap="small")
    for i, col in enumerate(cols):
        d = lunes + timedelta(days=i)
        del_dia = [p for p in filas if str(p["fecha_sugerida"]) == d.isoformat()]
        n_ab = len([p for p in del_dia if p["estado"] in cp.ABIERTOS])
        with col:
            st.markdown(
                f'<div class="wk-h {"today" if d == hoy else ""}"><div class="wk-d">{DIAS[i][:3].upper()}</div>'
                f'<div class="wk-n">{d.day}</div>'
                f'<div class="wk-c">{len(del_dia) or "—"}{" · " + str(n_ab) + " ⧗" if n_ab else ""}</div></div>',
                unsafe_allow_html=True,
            )
            if not del_dia:
                st.markdown('<div class="wk-body"><div class="wk-free">Libre</div></div>', unsafe_allow_html=True)
                continue
            tarjetas = "".join(
                f'<div class="wk-card c-{cp.semaforo(p, hoy).replace(" ", "-")}" title="{escape(p["detalle"] or "")}">'
                f'<div class="wk-ct">{escape(p["detalle"] or "")}</div>'
                f'<div class="wk-cs">{"✓ " if p["estado"] == "PAGADO" else ""}{escape(p["proveedor"] or "")}</div></div>'
                for p in del_dia
            )
            st.markdown(f'<div class="wk-body">{tarjetas}</div>', unsafe_allow_html=True)
            abiertas_dia = [p for p in del_dia if p["estado"] in cp.ABIERTOS]
            if abiertas_dia:
                with st.popover(f"✓ {len(abiertas_dia)}", width="stretch", help="Marcar como pagado"):
                    for p in abiertas_dia:
                        if st.button(f"✓ {p['detalle']}", key=f"wk_ok_{p['id']}", width="stretch"):
                            cp.marcar_pagado(p["id"], por="dashboard")
                            st.rerun()

    # Resumen por centro de costos
    if vivas:
        por_centro: dict[str, list[int]] = {}
        for p in vivas:
            k = p.get("centro_costos") or "Sin centro"
            por_centro.setdefault(k, [0, 0])
            por_centro[k][0] += 1
            por_centro[k][1] += p["estado"] == "PAGADO"
        filas_c = "".join(
            f'<div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-top:1px solid #1F2024">'
            f'<span style="width:110px;font-size:13px;color:#E8E8EA">{escape(k)}</span>'
            f'<div class="wk-bar" style="flex:1;margin:0"><div style="flex:{v[1] or 0.001} 1 0;background:#4ADE80"></div>'
            f'<div style="flex:{(v[0] - v[1]) or 0.001} 1 0;background:#3F3F46"></div></div>'
            f'<span style="width:70px;text-align:right;font-size:12px;color:#8B8B93;font-family:Geist Mono,monospace">'
            f'{v[1]}/{v[0]}</span></div>'
            for k, v in sorted(por_centro.items(), key=lambda kv: -kv[1][0])
        )
        st.markdown(f'<div class="hs-sec"><div class="hs-h">Por centro de costos</div><div class="hs-n">PAGADAS / TOTAL</div></div>{filas_c}',
                    unsafe_allow_html=True)
