"""Centro de alertas — alertas vivas: se crean, se actualizan y se cierran solas; acciones en un clic."""
from __future__ import annotations

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

from database import crear_alerta
from modulos import motor_alertas as ma

BOTON = {"pagar": "Pagué ✓", "presentar": "Presenté ✓", "ejecutar": "Reintentar"}

CSS = """
<style>
.al-hero{position:relative;overflow:hidden;border:1px solid #1F2024;border-radius:24px;padding:24px 26px;
 background:radial-gradient(120% 160% at 0% 0%,#1B1012 0%,#0A0B0D 58%);display:flex;gap:28px;align-items:center;flex-wrap:wrap}
.al-hero:after{content:"";position:absolute;right:-100px;top:-120px;width:320px;height:320px;border-radius:50%;
 background:radial-gradient(circle,#E5484D22,transparent 70%)}
.al-ring{position:relative;width:132px;height:132px;flex:0 0 132px}
.al-ring b{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;flex-direction:column;
 font-size:34px;color:#fff;font-weight:600;letter-spacing:-.02em}
.al-ring b span{font-size:9.5px;color:#8B8B93;font-family:'Geist Mono',monospace;letter-spacing:.12em;font-weight:400}
.al-eb{font-family:'Geist Mono',monospace;font-size:11px;letter-spacing:.14em;color:#8B8B93;text-transform:uppercase}
.al-h{font-size:30px;color:#fff;font-weight:600;letter-spacing:-.02em;margin:4px 0}
.al-sub{color:#A1A1AA;font-size:13.5px;line-height:1.6}.al-sub b{color:#fff}
.al-n{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
.al-n div{border:1px solid #26272C;border-radius:14px;padding:8px 14px;min-width:92px;background:#0F1012}
.al-n div b{display:block;font-size:22px;font-weight:500}.al-n div span{font-size:10px;color:#8B8B93;
 font-family:'Geist Mono',monospace;letter-spacing:.08em;text-transform:uppercase}
.al-ch{margin-left:auto;font-family:'Geist Mono',monospace;font-size:11px;color:#8B8B93;line-height:2;text-align:right;
 position:relative;z-index:1}
.al-ch i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px}
.al-sec{display:flex;align-items:baseline;gap:10px;margin:18px 0 4px}
.al-sec b{font-size:15px;color:#fff;font-weight:500}.al-sec span{font-family:'Geist Mono',monospace;font-size:11px;color:#8B8B93}
.al-card{display:flex;gap:12px;padding:12px 4px 4px;border-top:1px solid #17181C}
.al-bar{width:4px;border-radius:4px;flex:0 0 4px;align-self:stretch}
.al-t{color:#fff;font-size:15px;font-weight:500;line-height:1.3}
.al-d{color:#A1A1AA;font-size:13px;margin-top:3px;line-height:1.45}
.al-m{color:#71717A;font-size:11px;margin-top:5px;font-family:'Geist Mono',monospace;letter-spacing:.03em}
.al-v{margin-left:auto;color:#fff;font-family:'Geist Mono',monospace;font-size:14px;white-space:nowrap;padding-left:12px}
.al-new{font-family:'Geist Mono',monospace;font-size:9.5px;color:#0A0B0D;background:#FF6A3D;border-radius:5px;
 padding:1px 6px;margin-left:8px;vertical-align:2px}
.al-ok{border:1px solid #14321F;background:linear-gradient(135deg,#0D1A12,#0A0B0D);border-radius:18px;padding:22px;
 color:#4ADE80;font-size:15px}
</style>
"""


def _hace(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        d = datetime.now() - datetime.fromisoformat(str(ts)[:19])
    except ValueError:
        return str(ts)[:16]
    m = int(d.total_seconds() // 60)
    return "ahora" if m < 1 else f"hace {m} min" if m < 60 else f"hace {m // 60} h" if m < 1440 else f"hace {m // 1440} d"


def _ring(score: int) -> str:
    c = "#4ADE80" if score >= 80 else "#F5C542" if score >= 50 else "#E5484D"
    r, L = 56, 2 * 3.14159 * 56
    return (f'<div class="al-ring"><svg width="132" height="132" viewBox="0 0 132 132">'
            f'<circle cx="66" cy="66" r="{r}" fill="none" stroke="#1F2024" stroke-width="10"/>'
            f'<circle cx="66" cy="66" r="{r}" fill="none" stroke="{c}" stroke-width="10" stroke-linecap="round" '
            f'stroke-dasharray="{L * score / 100:.1f} {L:.1f}" transform="rotate(-90 66 66)" '
            f'style="filter:drop-shadow(0 0 8px {c}88)"/></svg><b>{score}<span>SALUD</span></b></div>')


def _hero(activas: list[dict], pospuestas: int) -> None:
    n = {k: sum(1 for a in activas if a["nivel"] == k) for k in ma.NIVELES}
    score = ma.salud(activas)
    try:
        from conexiones.notificador import canal_correo, canal_whatsapp
        correo, wa = canal_correo(), canal_whatsapp()
    except Exception:
        correo, wa = None, None
    dest = ma.destinos()
    frase = ("Todo en orden." if not activas else
             f'<b style="color:#E5484D">{n["CRITICO"]} crítica(s)</b> requieren atención hoy.' if n["CRITICO"] else
             f'<b>{n["URGENTE"]}</b> urgente(s) para resolver pronto.' if n["URGENTE"] else
             "Solo avisos menores.")
    cajas = "".join(f'<div><b style="color:{ma.COLOR[k]}">{n[k]}</b><span>{ma.NOMBRE_NIVEL[k]}s</span></div>'
                    for k in ("CRITICO", "URGENTE", "AVISO"))
    cajas += f'<div><b style="color:#A1A1AA">{pospuestas}</b><span>Pospuestas</span></div>'
    st.markdown(
        f'<div class="al-hero">{_ring(score)}<div style="position:relative;z-index:1">'
        f'<div class="al-eb">Centro de alertas · en vivo</div><div class="al-h">{len(activas)} alerta(s) abiertas</div>'
        f'<div class="al-sub">{frase} Se cierran solas cuando el problema se resuelve.</div>'
        f'<div class="al-n">{cajas}</div></div>'
        f'<div class="al-ch">Último escaneo · {_hace(ma.meta("ultimo_escaneo"))}<br>'
        f'<i style="background:{"#4ADE80" if correo else "#E5484D"}"></i>Correo · '
        f'{escape(correo or "sin configurar")}<br>'
        f'<i style="background:{"#4ADE80" if wa else "#52525B"}"></i>WhatsApp · {escape(wa or "no configurado")}<br>'
        f'Resumen 06:55 → {escape(", ".join(d.split("@")[0] for d in dest) or "—")}</div></div>',
        unsafe_allow_html=True,
    )


def _ir(pagina: str) -> None:
    st.session_state["nav"] = pagina


def _tarjeta(a: dict, clave: str, historial: bool = False) -> None:
    c = ma.COLOR.get(a["nivel"], "#8B8B93")
    nueva = (not historial and a.get("timestamp") and
             (datetime.now() - datetime.fromisoformat(str(a["timestamp"])[:19])).total_seconds() < 6 * 3600)
    meta = [ma.MODULOS.get(str(a["modulo"]).lower(), str(a["modulo"]).capitalize()),
            f'abierta {_hace(a.get("timestamp"))}']
    if a.get("origen") == "MOTOR" and (a.get("veces") or 1) > 1 and not historial:
        meta.append(f'confirmada {a["veces"]} veces')
    if a.get("notificada_en"):
        meta.append("avisada por correo")
    if historial:
        meta = [f'cerrada {_hace(a.get("fecha_resolucion"))}', escape(str(a.get("resuelta_por") or "usuario"))]
    if a.get("pospuesta_hasta") and not historial:
        meta.append(f'pospuesta hasta {str(a["pospuesta_hasta"])[:16]}')
    valor = ma._p(a["valor"]) if a.get("valor") else ""
    st.markdown(
        f'<div class="al-card"><div class="al-bar" style="background:{c}"></div><div style="flex:1">'
        f'<div class="al-t">{escape(a["titulo"])}{"<span class=al-new>NUEVA</span>" if nueva else ""}</div>'
        f'<div class="al-d">{escape(a.get("descripcion") or "")}</div>'
        f'<div class="al-m">{" · ".join(escape(str(x)) for x in meta)}</div></div>'
        f'<div class="al-v">{valor}</div></div>',
        unsafe_allow_html=True,
    )
    if historial:
        return
    cols = st.columns([1.3, 1.3, 1, 1, 1])
    acc = a.get("accion")
    if acc and acc[0] in BOTON:
        if cols[0].button(BOTON[acc[0]], key=f"{clave}_acc_{a['id']}", type="primary", use_container_width=True):
            r = ma.ejecutar_accion(a)
            st.toast("Listo ✓" if r.get("ok", True) else f"No se pudo: {r}")
            st.rerun()
    if a.get("ir_a"):
        cols[1].button(f"Ir a {a['ir_a']}", key=f"{clave}_ir_{a['id']}", on_click=_ir, args=(a["ir_a"],),
                       use_container_width=True)
    if a.get("pospuesta_hasta"):
        if cols[2].button("Reactivar", key=f"{clave}_re_{a['id']}", use_container_width=True):
            ma.reactivar(a["id"])
            st.rerun()
    else:
        if cols[2].button("Mañana", key=f"{clave}_p1_{a['id']}", use_container_width=True, help="Posponer 24 horas"):
            ma.posponer(a["id"], 24)
            st.rerun()
        if cols[3].button("1 semana", key=f"{clave}_p7_{a['id']}", use_container_width=True, help="Posponer 7 días"):
            ma.posponer(a["id"], 24 * 7)
            st.rerun()
    if cols[4].button("Resolver", key=f"{clave}_ok_{a['id']}", use_container_width=True,
                      help="Se cierra y no vuelve en 7 días, salvo que empeore"):
        ma.resolver(a["id"], por="usuario")
        st.rerun()


def _filtrar(alertas: list[dict], niveles: list[str], modulos: list[str], texto: str) -> list[dict]:
    t = texto.strip().lower()
    out = []
    for a in alertas:
        mod = ma.MODULOS.get(str(a["modulo"]).lower(), str(a["modulo"]).capitalize())
        if niveles and a["nivel"] not in niveles:
            continue
        if modulos and mod not in modulos:
            continue
        if t and t not in (a["titulo"] + " " + (a.get("descripcion") or "")).lower():
            continue
        out.append(a)
    return out


def _lista(alertas: list[dict], clave: str, historial: bool = False) -> None:
    if not alertas:
        st.markdown('<div class="al-ok">✓ Nada por aquí. Shaki sigue vigilando.</div>', unsafe_allow_html=True)
        return
    if historial:
        for a in alertas[:150]:
            _tarjeta(a, clave, historial=True)
        return
    for nivel in ma.NIVELES:
        grupo = [a for a in alertas if a["nivel"] == nivel]
        if not grupo:
            continue
        st.markdown(f'<div class="al-sec"><b style="color:{ma.COLOR[nivel]}">{ma.NOMBRE_NIVEL[nivel]}s</b>'
                    f'<span>{len(grupo)}</span></div>', unsafe_allow_html=True)
        for a in grupo[:60]:
            _tarjeta(a, clave)
        if len(grupo) > 60:
            st.caption(f"…y {len(grupo) - 60} más. Use los filtros.")


def _tab_reglas() -> None:
    st.markdown("**Reglas que vigila Shaki**")
    actual = ma.reglas_activas()
    nuevo = {}
    for k, r in ma.REGLAS.items():
        nuevo[k] = st.toggle(r["nombre"], value=actual[k], key=f"regla_{k}", help=r["desc"])
        st.caption(r["desc"])
    if nuevo != actual:
        ma.guardar_reglas(nuevo)
        ma.escanear(notificar=False)
        st.rerun()
    st.divider()
    st.markdown("**Avisos por correo**")
    st.markdown(
        f"- **Crítica nueva** → correo inmediato a: {', '.join(ma.destinos()) or '—'}\n"
        "- **Resumen diario 06:55** con todo lo abierto (crítico, urgente y avisos).\n"
        "- Se escanea cada 30 minutos y cada vez que abre Shaki.")
    if st.button("Enviarme el resumen ahora"):
        r = ma.enviar_resumen_diario()
        if r["alertas"] == 0:
            st.info("No hay alertas abiertas: no se envió nada.")
        elif r["correos"]:
            st.success(f"Resumen enviado ({r['alertas']} alertas) a {r['correos']} destinatario(s).")
        else:
            st.error("No se pudo enviar: revise la configuración de correo.")
    envios = ma._filas("SELECT enviado_en, tipo, destino, n_alertas, ok FROM alertas_envios ORDER BY id DESC LIMIT 30")
    if envios:
        st.dataframe(pd.DataFrame(envios), use_container_width=True, hide_index=True)
    st.divider()
    with st.expander("Crear alerta manual"):
        with st.form("alerta_manual"):
            nivel = st.selectbox("Nivel", ["AVISO", "URGENTE", "CRITICO", "INFO"],
                                 format_func=lambda x: ma.NOMBRE_NIVEL[x])
            titulo = st.text_input("Título")
            descripcion = st.text_area("Descripción")
            if st.form_submit_button("Registrar alerta"):
                if titulo.strip():
                    crear_alerta(nivel, "manual", titulo.strip(), descripcion or "")
                    st.rerun()
                else:
                    st.error("El título es obligatorio.")


def render() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    ma.inicializar()
    top = st.columns([4, 1])
    top[0].markdown("## Alertas")
    if top[1].button("Escanear ahora", use_container_width=True, type="primary"):
        r = ma.escanear()
        st.toast(f"{r['nuevas']} nueva(s) · {r['resueltas']} se cerraron solas · {r['vivas']} vivas")
    activas = ma.listar("ACTIVAS")
    pospuestas = ma.listar("POSPUESTAS")
    _hero(activas, len(pospuestas))

    f1, f2, f3 = st.columns([1.2, 2, 1.2])
    niveles = f1.pills("Nivel", list(ma.NIVELES), selection_mode="multi", default=[],
                       format_func=lambda k: ma.NOMBRE_NIVEL[k], key="al_niv")
    mods = sorted({ma.MODULOS.get(str(a["modulo"]).lower(), str(a["modulo"]).capitalize()) for a in activas})
    modulos = f2.pills("Módulo", mods, selection_mode="multi", default=[], key="al_mod")
    texto = f3.text_input("Buscar", key="al_txt", placeholder="Proveedor, impuesto…")

    t1, t2, t3, t4 = st.tabs([f"Activas ({len(activas)})", f"Pospuestas ({len(pospuestas)})", "Historial 30 días",
                              "Reglas y avisos"])
    with t1:
        _lista(_filtrar(activas, niveles, modulos, texto), "act")
    with t2:
        _lista(_filtrar(pospuestas, niveles, modulos, texto), "pos")
    with t3:
        _lista(_filtrar(ma.listar("HISTORIAL"), niveles, modulos, texto), "his", historial=True)
    with t4:
        _tab_reglas()
