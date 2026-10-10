"""Revisión de impuestos — el contador sube los insumos y Shaki entrega el informe escrito."""
from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path

import streamlit as st
from dashboard.utils import incrustar

from modulos import revision_impuestos as ri

COL = {"CORRECTO": "#4ADE80", "CORRECTO CON OBSERVACIONES": "#F5C542",
       "FORMULARIO CORRECTO · CON ALERTAS": "#FF6A3D", "CON DIFERENCIAS": "#E5484D"}
NIVEL_COL = {"CRITICO": "#E5484D", "ALTO": "#FF6A3D", "MEDIO": "#F5C542", "INFO": "#8B8B93"}

CSS = """
<style>
.rv-hero{position:relative;overflow:hidden;background:radial-gradient(120% 160% at 0% 0%,#17181C 0%,#0A0B0D 65%);
 border:1px solid #1F2024;border-radius:22px;padding:22px 24px;margin-bottom:14px}
.rv-hero:after{content:"";position:absolute;right:-90px;top:-110px;width:300px;height:300px;border-radius:50%;
 background:radial-gradient(circle,#7DD3FC22,transparent 70%)}
.rv-eb{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#8B8B93;font-family:'Geist Mono',monospace}
.rv-h{font-size:26px;color:#fff;font-weight:600;letter-spacing:-.02em;margin:6px 0 2px}
.rv-s{color:#A1A1AA;font-size:13.5px}
.rv-grid{display:grid;grid-template-columns:150px 1fr;gap:8px 14px;margin-top:18px;align-items:center}
.rv-imp{color:#E4E4E7;font-size:13px}.rv-imp span{display:block;color:#71717A;font-size:10.5px;font-family:'Geist Mono',monospace}
.rv-cells{display:flex;gap:5px;flex-wrap:nowrap}
.rv-c{flex:1 1 0;min-width:0;overflow:hidden;height:30px;border-radius:9px;border:1px solid #26272C;background:#111215;
 display:flex;align-items:center;justify-content:center;font-size:10px;color:#71717A;font-family:'Geist Mono',monospace}
.rv-c.on{color:#0A0B0D;font-weight:700;border-color:transparent}
.rv-ley{display:flex;gap:16px;flex-wrap:wrap;margin-top:14px;font-size:11px;color:#8B8B93}
.rv-ley i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.rv-card{background:#0F1012;border:1px solid #1F2024;border-radius:18px;padding:18px 20px;margin-top:6px}
.rv-ver{display:inline-block;padding:6px 12px;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:.06em}
.rv-k{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:14px}
.rv-k div{background:#141519;border:1px solid #1F2024;border-radius:14px;padding:10px 12px}
.rv-k b{display:block;color:#fff;font-size:20px;font-weight:600}.rv-k span{font-size:10px;color:#8B8B93;letter-spacing:.08em;text-transform:uppercase}
.rv-f{border-left:3px solid;padding:8px 12px;margin:8px 0;background:#121317;border-radius:0 12px 12px 0}
.rv-f b{color:#fff;font-weight:600;font-size:14px}.rv-f div{color:#A1A1AA;font-size:12.5px;margin-top:3px}
.rv-tag{font-size:10px;font-weight:700;letter-spacing:.06em;margin-right:8px}
@media(max-width:700px){.rv-grid{grid-template-columns:1fr}.rv-k{grid-template-columns:repeat(2,1fr)}}
</style>
"""


def _mapa(anio: int) -> None:
    ult = ri.ultima_por_periodo(anio)
    filas = []
    for imp, info in ri.IMPUESTOS.items():
        celdas = []
        for cod, etq in ri.periodos(imp, anio):
            r = ult.get((imp, cod))
            corto = cod[5:] if len(cod) > 4 else str(anio)
            corto = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"][
                int(corto) - 1] if corto.isdigit() and len(corto) == 2 else corto
            if r:
                c = COL.get(r["veredicto"], "#8B8B93")
                celdas.append(f'<div class="rv-c on" style="background:{c}" title="{escape(etq)} · '
                              f'{escape(r["veredicto"])}">{escape(corto)}</div>')
            else:
                celdas.append(f'<div class="rv-c" title="{escape(etq)} · sin revisar">{escape(corto)}</div>')
        filas.append(f'<div class="rv-imp">{escape(info["corto"])}<span>{escape(info["entidad"])} · '
                     f'{escape(info["form"])}</span></div><div class="rv-cells">{"".join(celdas)}</div>')
    n = sum(1 for k in ult if k[0])
    ley = "".join(f'<span><i style="background:{c}"></i>{escape(v.capitalize())}</span>' for v, c in COL.items())
    st.markdown(
        f'<div class="rv-hero"><div class="rv-eb">Revisión de impuestos · {anio}</div>'
        f'<div class="rv-h">El año tributario, revisado declaración por declaración</div>'
        f'<div class="rv-s">{n} periodo(s) revisados. Suba en cada impuesto el borrador y la liquidación del contador; '
        f'Shaki los cruza con la contabilidad y la norma vigente y deja el informe guardado.</div>'
        f'<div class="rv-grid">{"".join(filas)}</div><div class="rv-ley">{ley}'
        f'<span><i style="background:#111215;border:1px solid #26272C"></i>Sin revisar</span></div></div>',
        unsafe_allow_html=True,
    )


def _pesos(v) -> str:
    return "—" if not v else "$" + f"{v:,.0f}".replace(",", ".")


def _mostrar(rev: dict, clave: str) -> None:
    c = COL.get(rev["veredicto"], "#8B8B93")
    res = rev.get("resultado") or {}
    venc = ri.vencimiento(rev["impuesto"], rev["periodo"])
    st.markdown(
        f'<div class="rv-card"><div class="rv-eb">{escape(ri.IMPUESTOS[rev["impuesto"]]["nombre"])} · '
        f'{escape(ri.etiqueta_periodo(rev["impuesto"], rev["periodo"]))} · revisado {escape(str(rev["creado_en"])[:16])}</div>'
        f'<div style="margin-top:10px"><span class="rv-ver" style="background:{c}22;color:{c};border:1px solid {c}66">'
        f'{escape(rev["veredicto"])}</span></div>'
        f'<div class="rv-s" style="margin-top:10px">{escape(rev.get("resumen") or "")}</div>'
        f'<div class="rv-k"><div><b>{_pesos(rev.get("total_a_pagar"))}</b><span>Total a pagar</span></div>'
        f'<div><b>{venc.strftime("%d/%m/%Y") if venc else "—"}</b><span>Vence</span></div>'
        f'<div><b style="color:#E5484D">{rev.get("n_criticos", 0)}</b><span>Críticos</span></div>'
        f'<div><b style="color:#4ADE80">{len(res.get("verificaciones", []))}</b><span>Verificaciones OK</span></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    hall = [h for h in res.get("hallazgos", []) if h["nivel"] != "INFO"]
    if hall:
        st.markdown("".join(
            f'<div class="rv-f" style="border-color:{NIVEL_COL[h["nivel"]]}"><b><span class="rv-tag" '
            f'style="color:{NIVEL_COL[h["nivel"]]}">{h["nivel"]}</span>{escape(h["titulo"])}</b>'
            f'<div>{escape(h.get("accion") or h.get("detalle") or "")}</div></div>' for h in hall[:8]),
            unsafe_allow_html=True)
    ruta = rev.get("informe_path")
    if ruta and Path(ruta).exists():
        html = Path(ruta).read_text(encoding="utf-8")
        st.download_button("Descargar informe escrito", html.encode("utf-8"), file_name=Path(ruta).name,
                           mime="text/html", width="stretch", key=f"dl_{clave}_{rev['id']}")
        ver = st.toggle("Ver informe completo aquí", key=f"ver_{clave}_{rev['id']}")
        if ver:
            incrustar.html(html, height=1200, scrolling=True)
        st.caption("El informe se abre en el navegador; para PDF use Imprimir → Guardar como PDF.")


def _tab_impuesto(imp: str, anio: int) -> None:
    info = ri.IMPUESTOS[imp]
    pers = ri.periodos(imp, anio)
    codigos = [c for c, _ in pers]
    sug = ri.periodo_sugerido(imp)
    idx = codigos.index(sug) if sug in codigos else 0
    izq, der = st.columns([1, 1.25], gap="large")
    with izq:
        st.markdown(f"**Subir insumos · {info['nombre']}**")
        cod = st.selectbox("Periodo", codigos, index=idx, format_func=lambda c: dict(pers)[c], key=f"per_{imp}")
        ayuda = ("Borrador del formulario 350 en PDF + la liquidación del contador (.xlsm/.xlsx con Prueba, Auxiliar, "
                 "RetenciónHT, AutorrentaHT y formatos 383)." if imp == "RET" else
                 f"Borrador del formulario {info['form']} en PDF + la liquidación en Excel y los soportes.")
        archivos = st.file_uploader("Archivos del contador", type=["pdf", "xlsx", "xlsm", "xls", "csv"],
                                    accept_multiple_files=True, key=f"up_{imp}_{cod}", help=ayuda)
        st.caption(ayuda)
        con_ia = False
        if ri.ia_disponible():
            con_ia = st.toggle("Agregar concepto de Claude (IA)", value=False, key=f"ia_{imp}")
        if st.button("Revisar ahora", type="primary", width="stretch", key=f"btn_{imp}",
                     disabled=not archivos):
            with st.spinner("Leyendo el borrador, cruzando con la contabilidad y la norma…"):
                try:
                    guard = ri.guardar_archivos(imp, cod, [(a.name, a.getvalue()) for a in archivos])
                    rev = ri.revisar(imp, cod, guard, con_ia=con_ia)
                    st.session_state[f"rv_sel_{imp}"] = rev["id"]
                    st.toast(f"Revisión lista: {rev['veredicto']}")
                except Exception as e:  # nunca romper la página por un archivo raro
                    st.error(f"No se pudo revisar: {e}")
    with der:
        hist = ri.listar(anio, imp)
        if not hist:
            st.markdown(f'<div class="rv-card"><div class="rv-eb">Historial {anio}</div>'
                        f'<div class="rv-s" style="margin-top:8px">Aún no hay revisiones de {escape(info["nombre"])} '
                        f'en {anio}. Suba los archivos del periodo y presione «Revisar ahora».</div></div>',
                        unsafe_allow_html=True)
            return
        ids = [h["id"] for h in hist]
        sel = st.session_state.get(f"rv_sel_{imp}")
        elegido = st.selectbox(
            f"Historial {anio}", ids, index=ids.index(sel) if sel in ids else 0, key=f"hist_{imp}",
            format_func=lambda i: next(f"{ri.etiqueta_periodo(imp, h['periodo'])} · {h['veredicto'].lower()} · "
                                       f"{str(h['creado_en'])[:16]}" for h in hist if h["id"] == i))
        rev = ri.obtener(elegido)
        if rev:
            _mostrar(rev, imp)


def render() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    ri.inicializar_tablas()
    hoy = date.today()
    anios = list(range(hoy.year, 2024, -1))
    _, c = st.columns([4, 1])
    with c:
        anio = st.selectbox("Año", anios, index=0, key="rv_anio", label_visibility="collapsed")
    _mapa(anio)
    tabs = st.tabs([v["corto"] for v in ri.IMPUESTOS.values()])
    for t, imp in zip(tabs, ri.IMPUESTOS):
        with t:
            _tab_impuesto(imp, anio)
