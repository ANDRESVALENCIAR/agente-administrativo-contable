"""Contabilidad → Revisión contable: sube los archivos del contador y Shaki los revisa con reglas fijas (sin IA)."""
from __future__ import annotations

import hashlib
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.paginas.gastos_dashboard import CSS as CSS_GD
from modulos import auditoria_contable as au
from modulos import auditoria_informe as ai

CARPETA = Path(__file__).resolve().parents[2] / "data" / "contabilidad" / "revision_contable"
COLOR = ai.COLOR

CSS = CSS_GD + """
<style>
.rc-h{border-left:3px solid;background:#101114;border-radius:0 12px 12px 0;padding:10px 14px;margin:8px 0}
.rc-h b{color:#fff;font-weight:500}.rc-h p{color:#A1A1AA;font-size:13px;margin:4px 0 0}
.rc-h .rec{color:#E4E4E7}.rc-chip{font-size:10.5px;font-family:'Geist Mono',monospace;letter-spacing:.08em;padding:2px 8px;
border-radius:99px;margin-right:8px;text-transform:uppercase}
</style>
"""


@st.cache_data(show_spinner=False, max_entries=8)
def _revisar(firma: str, rutas: tuple[str, ...], otro: str | None = None) -> dict:
    return au.revisar_archivos(list(rutas), otro_balance=otro)


def _guardar(archivos) -> list[Path]:
    CARPETA.mkdir(parents=True, exist_ok=True)
    rutas = []
    for a in archivos:
        ruta = CARPETA / Path(a.name).name
        if ruta.exists() and ruta.read_bytes() != a.getvalue():  # mismo nombre, otro contenido: no se pisa
            ruta = CARPETA / f"{ruta.stem}_{hashlib.md5(a.getvalue()).hexdigest()[:6]}{ruta.suffix}"
        ruta.write_bytes(a.getvalue())
        rutas.append(ruta)
    return rutas


def _firma(rutas: list[Path]) -> str:
    h = hashlib.md5()
    for r in sorted(rutas):
        st_ = r.stat()
        h.update(f"{r.name}|{st_.st_size}|{st_.st_mtime_ns}".encode())
    return h.hexdigest()


def render() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="gd-h">Revisión contable automática</div><div class="gd-c">Suba los archivos del cierre en '
                'su casilla y presione «Generar informe». Shaki los revisa con más de 40 reglas contables fijas —sin '
                'inteligencia artificial— y arma un informe verificable cifra por cifra.</div>', unsafe_allow_html=True)
    tipos = ["xlsx", "xlsm"]
    c1, c2 = st.columns(2)
    f_bal = c1.file_uploader("1 · Balance de prueba del mes (obligatorio)", type=tipos, key="rc_bal",
                             help="El Excel de World Office con el balance del mes; si trae auxiliar y terceros, también "
                                  "se revisan.")
    f_eeff = c2.file_uploader("2 · Estados financieros NIIF (opcional)", type=tipos, key="rc_eeff")
    c3, c4 = st.columns(2)
    f_otro = c3.file_uploader("3 · Otro balance de prueba para comparar (opcional)", type=tipos, key="rc_otro",
                              help="El del mes anterior o el siguiente: Shaki verifica que los saldos empalmen y muestra "
                                   "las variaciones grandes.")
    f_conc = c4.file_uploader("4 · Conciliación bancaria (opcional)", type=tipos, key="rc_conc")
    b1, b2 = st.columns([1, 2.4])
    if b1.button("Generar informe", type="primary", width="stretch", disabled=f_bal is None):
        rol = {}
        for clave, f in (("balance", f_bal), ("eeff", f_eeff), ("otro", f_otro), ("conciliacion", f_conc)):
            if f is not None:
                rol[clave] = str(_guardar([f])[0])
        st.session_state["rc_roles"] = rol
    if f_bal is None and not st.session_state.get("rc_roles"):
        b2.caption("Suba al menos el balance de prueba para generar el informe.")
    roles = {k: v for k, v in st.session_state.get("rc_roles", {}).items() if Path(v).exists()}
    if "balance" not in roles:
        return
    rutas = [Path(roles[k]) for k in ("balance", "eeff", "conciliacion") if k in roles]
    otro = roles.get("otro")
    with st.spinner("Revisando cifra por cifra…"):
        r = _revisar(_firma(rutas + ([Path(otro)] if otro else [])), tuple(str(x) for x in rutas), otro)

    color = {"Confiable": "#4ADE80", "Confiable con salvedades": "#c98500"}.get(r["veredicto"], "#e66767")
    cn = r["conteo"]
    st.markdown(
        f'<div class="gd-hero"><div class="gd-eb">Revisión contable · corte {escape(ai._fecha(r["corte"]))}</div>'
        f'<div class="gd-big" style="color:{color}">{r["puntaje"]}<span style="font-size:20px;color:#8B8B93"> / 100</span></div>'
        f'<div class="gd-sub"><b style="color:{color}">{escape(r["veredicto"])}</b> · confiabilidad del registro contable. '
        f'Riesgos de pago vencidos (impuestos y prestaciones): <b>{au._p(r["riesgos_total"])}</b></div>'
        f'<div class="gd-k"><div><b style="color:#e66767">{cn["CRITICO"]}</b><span>Críticos</span></div>'
        f'<div><b style="color:#F76B15">{cn["ALTO"]}</b><span>Altos</span></div>'
        f'<div><b style="color:#c98500">{cn["MEDIO"]}</b><span>Medios</span></div>'
        f'<div><b>{cn["BAJO"]}</b><span>Bajos</span></div>'
        f'<div><b style="color:#4ADE80">{cn["OK"]}</b><span>Revisiones OK</span></div></div></div>',
        unsafe_allow_html=True)
    st.caption("Archivos: " + " · ".join(r["fuentes"]))

    html = ai.generar_html(r)
    corte = r["corte"].strftime("%Y-%m") if r.get("corte") else "corte"
    st.download_button("Descargar informe (HTML para imprimir o guardar como PDF)", html.encode("utf-8"),
                       file_name=f"Revision_contable_{corte}.html", mime="text/html", icon=":material/download:")

    filtro = st.pills("Mostrar", ["Errores de registro", "Riesgos de pago", "Todo lo verificado"],
                      default="Errores de registro", key="rc_filtro", label_visibility="collapsed")
    hall = r["hallazgos"]
    if filtro == "Errores de registro":
        hall = [h for h in hall if h["tipo"] == "registro" and h["nivel"] != "OK"]
    elif filtro == "Riesgos de pago":
        hall = [h for h in hall if h["tipo"] == "riesgo" and h["nivel"] != "OK"]
    for h in hall:
        c = COLOR[h["nivel"]]
        valor = (f' · {au._p(h["valor"])}' if isinstance(h.get("valor"), (int, float)) and abs(h["valor"]) >= 1
                 and h["codigo"] not in ("G8", "D3") else "")
        st.markdown(
            f'<div class="rc-h" style="border-color:{c}"><span class="rc-chip" style="color:{c};background:{c}22">'
            f'{ai.NOMBRE[h["nivel"]]}</span><b>{escape(h["titulo"])}{valor}</b>'
            f'<p>{escape(h["detalle"])}</p>'
            + (f'<p class="rec">→ {escape(h["recomendacion"])}</p>' if h.get("recomendacion") else "")
            + f'<p style="font-size:11px">Regla {h["codigo"]} · {escape(au.AREAS.get(h["area"], h["area"]))}</p></div>',
            unsafe_allow_html=True)
        if h.get("evidencia"):
            with st.expander(f"Evidencia ({len(h['evidencia'])})"):
                df = pd.DataFrame(h["evidencia"]).rename(columns=ai.ETIQUETAS)
                cfg = {ai.ETIQUETAS.get(k, k): st.column_config.NumberColumn(format="$%,.0f")
                       for k in h["evidencia"][0] if k in ai.MONEDA}
                st.dataframe(df, hide_index=True, width="stretch", column_config=cfg)
    if not hall:
        st.success("Nada que mostrar en este filtro.")
