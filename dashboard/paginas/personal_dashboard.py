"""Personal — tablero interactivo de la planta: quiénes son, dónde están, qué vence y qué falta."""
from __future__ import annotations

from datetime import date
from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.estilos import OTROS, PLOTLY_LAYOUT, SERIES
from modulos import analitica_personal as ap
from dashboard.utils.pestanas import abierta, pestanas

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MESES_L = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
           "noviembre", "diciembre"]

CSS = """
<style>
.pd-hero{border:1px solid #1F2024;border-radius:22px;padding:22px 24px;margin-bottom:12px;
 background:radial-gradient(120% 160% at 0% 0%,#0F1620 0%,#0A0B0D 60%)}
.pd-eb{font-family:'Geist Mono',monospace;font-size:11px;letter-spacing:.14em;color:#8B8B93;text-transform:uppercase}
.pd-big{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-top:6px}
.pd-big b{font-size:52px;font-weight:300;color:#fff;letter-spacing:-.03em;line-height:1}
.pd-big span{color:#A1A1AA;font-size:14px}
.pd-k{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-top:16px}
.pd-k div{background:#0F1012;border:1px solid #1F2024;border-radius:14px;padding:11px 13px}
.pd-k b{display:block;color:#fff;font-size:20px;font-weight:500}
.pd-k span{font-size:10px;color:#8B8B93;font-family:'Geist Mono',monospace;letter-spacing:.08em;text-transform:uppercase}
.pd-h{color:#fff;font-size:16px;font-weight:500;margin:14px 0 2px}.pd-c{color:#8B8B93;font-size:12.5px;margin-bottom:4px}
.pd-ev{display:flex;gap:12px;align-items:center;padding:9px 2px;border-top:1px solid #17181C}
.pd-d{min-width:46px;text-align:center;font-family:'Geist Mono',monospace}.pd-d b{display:block;color:#fff;font-size:20px;font-weight:400}
.pd-d span{font-size:10px;color:#8B8B93}.pd-t{color:#E4E4E7;font-size:14px}.pd-s{color:#8B8B93;font-size:12px}
.pd-tag{font-family:'Geist Mono',monospace;font-size:9.5px;padding:2px 7px;border-radius:6px;margin-left:6px}
</style>
"""


def _layout(fig: go.Figure, alto: int = 300, leyenda: bool = False) -> go.Figure:
    fig.update_layout(**PLOTLY_LAYOUT, height=alto, showlegend=leyenda,
                      legend=dict(orientation="h", y=-0.2, x=0, title_text="", font=dict(size=11)),
                      hoverlabel=dict(bgcolor="#141519", bordercolor="#2A2B30", font=dict(color="#E8E8EA")))
    fig.update_xaxes(showgrid=False, linecolor="#26272C", tickfont=dict(color="#8B8B93"))
    fig.update_yaxes(gridcolor="#1A1B1F", zeroline=False, tickfont=dict(color="#8B8B93"))
    return fig


def _num(v, dec: int = 1, suf: str = "") -> str:
    return "—" if v is None or (isinstance(v, float) and pd.isna(v)) else f"{v:.{dec}f}".replace(".", ",") + suf


@st.cache_data(ttl=300, show_spinner=False)
def _datos(_dia: str) -> dict:
    return ap.cargar()


def render() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    d = _datos(date.today().isoformat())
    e: pd.DataFrame | None = d.get("empleados")
    if e is None or e.empty:
        st.info("No hay personal cargado. Use la pestaña «Archivo General» para importar el Excel de personal.")
        return
    k = ap.kpis(d)
    hoy = pd.Timestamp(d["hoy"])

    st.markdown(
        f'<div class="pd-hero"><div class="pd-eb">Equipo · {hoy.day} de {MESES_L[hoy.month - 1]} de {hoy.year}</div>'
        f'<div class="pd-big"><b>{k.get("activos", 0)}</b><span>personas activas · {k.get("nomina", 0)} en nómina · '
        f'{k.get("prestacion", 0)} por prestación de servicios · {k.get("areas", 0)} áreas</span></div>'
        f'<div class="pd-k">'
        f'<div><b>{_num(k.get("antiguedad"), 1, " años")}</b><span>Antigüedad prom.</span></div>'
        f'<div><b>{_num(k.get("edad"), 0, " años")}</b><span>Edad promedio</span></div>'
        f'<div><b>{k.get("retiros_12m", 0)}</b><span>Retiros 12 meses · {_num(k.get("rotacion", 0) * 100, 0, "%")} rotación</span></div>'
        f'<div><b style="color:{"#d95926" if k.get("venc_60") else "#fff"}">{k.get("venc_60", 0)}</b><span>Contratos vencen 60 días</span></div>'
        f'<div><b>{_num(k.get("vac_dias"), 0)}</b><span>Días de vacaciones pend. · {k.get("vac_15", 0)} con 15+</span></div>'
        f'<div><b>{k.get("cumple_mes", 0)}</b><span>Cumpleaños este mes</span></div>'
        f'<div><b>{_num(k.get("expedientes"), 0, "%")}</b><span>Expedientes completos</span></div>'
        f'<div><b>{_num(k.get("completitud_datos", 0) * 100, 0, "%")}</b><span>Datos completos</span></div>'
        f'</div></div>', unsafe_allow_html=True)

    act = e[e["activo"]].copy()
    f1, f2, f3 = st.columns([2, 2, 1.2])
    areas = sorted(act["area"].unique())
    sel_areas = f1.multiselect("Área", areas, default=[], placeholder="Todas las áreas", key="pd_area")
    vinc = sorted(act["vinculo"].unique())
    sel_v = f2.multiselect("Vinculación", vinc, default=[], placeholder="Todas", key="pd_vinc")
    ver_sal = f3.toggle("Mostrar salarios", value=False, key="pd_sal", help="Oculto por defecto (útil en TV o reuniones)")
    if sel_areas:
        act = act[act["area"].isin(sel_areas)]
    if sel_v:
        act = act[act["vinculo"].isin(sel_v)]

    nov = d.get("novedades")
    t1, t2, t3, t4, t5 = pestanas(["Equipo", "Historia", "Lo que vence", "Vacaciones y bienestar", "Expedientes y datos"],
                                  key="pd_tabs")

    with t1:
        if abierta(t1):
            c1, c2 = st.columns([1.4, 1])
            with c1:
                st.markdown('<div class="pd-h">Personas por área</div><div class="pd-c">Haga clic en una barra para filtrar '
                            'el directorio. Si falta el área, se toma de Contratos Activos o se deduce del cargo.</div>', unsafe_allow_html=True)
                pa = act.groupby(["area", "vinculo"]).size().reset_index(name="personas")
                orden = pa.groupby("area")["personas"].sum().sort_values().index.tolist()
                colv = {"Nómina": SERIES[0], "Prestación de servicios": SERIES[1], "Sin dato": OTROS}
                fig = px.bar(pa, y="area", x="personas", color="vinculo", orientation="h", color_discrete_map=colv,
                             category_orders={"area": orden[::-1]}, labels={"area": "", "personas": "", "vinculo": ""})
                fig.update_traces(marker_line_color="#0A0B0D", marker_line_width=2,
                                  hovertemplate="%{y}<br>%{fullData.name}: %{x}<extra></extra>")
                ev = st.plotly_chart(_layout(fig, max(240, 34 * len(orden) + 60), True), width="stretch",
                                     on_select="rerun", selection_mode="points", key="pd_bar_area")
            with c2:
                st.markdown('<div class="pd-h">Cargos</div><div class="pd-c">Cuántas personas por cargo</div>',
                            unsafe_allow_html=True)
                pc = act["cargo_n"].value_counts().head(10).iloc[::-1]
                fig = px.bar(x=pc.values, y=pc.index, orientation="h", labels={"x": "", "y": ""})
                fig.update_traces(marker_color=SERIES[0], hovertemplate="%{y}: %{x}<extra></extra>")
                st.plotly_chart(_layout(fig, max(240, 30 * len(pc) + 60)), width="stretch")
            c3, c4, c5 = st.columns(3)
            for col, campo, tit in ((c3, "ciudad_n", "Ciudad / sede"), (c4, "eps", "EPS"), (c5, "caja", "Caja de compensación")):
                with col:
                    st.markdown(f'<div class="pd-h">{tit}</div>', unsafe_allow_html=True)
                    v = act[campo].value_counts()
                    top = v.head(5)
                    if len(v) > 5:
                        top = pd.concat([top, pd.Series({"Otras": v.iloc[5:].sum()})])
                    fig = go.Figure(go.Pie(labels=top.index, values=top.values, hole=0.62, sort=False,
                                           marker=dict(colors=[SERIES[i] if n not in ("Otras", "Sin dato") else OTROS
                                                               for i, n in enumerate(top.index)],
                                                       line=dict(color="#0A0B0D", width=2)),
                                           textinfo="none", hovertemplate="%{label}: %{value} (%{percent})<extra></extra>"))
                    st.plotly_chart(_layout(fig, 230, True), width="stretch")
            filtro = None
            try:
                pts = ev.selection.points if ev else []
                filtro = pts[0]["y"] if pts else None
            except Exception:
                filtro = None
            st.markdown(f'<div class="pd-h">Directorio{" · " + escape(filtro) if filtro else ""}</div>', unsafe_allow_html=True)
            q = st.text_input("Buscar persona o cargo", key="pd_q", placeholder="Nombre, cargo…", label_visibility="collapsed")
            dirc = act if not filtro else act[act["area"] == filtro]
            if q:
                dirc = dirc[dirc["nombre"].str.contains(q, case=False) | dirc["cargo_n"].str.contains(q, case=False)]
            cols = ["nombre", "cargo_n", "area", "vinculo", "contrato", "ingreso", "antiguedad", "edad", "ciudad_n", "eps"]
            if ver_sal:
                cols.append("salario")
            vista = dirc[cols].copy()
            vista["ingreso"] = pd.to_datetime(vista["ingreso"], errors="coerce")
            st.dataframe(vista.sort_values("nombre"), width="stretch", hide_index=True,
                         column_config={"nombre": "Nombre", "cargo_n": "Cargo", "area": "Área", "vinculo": "Vinculación",
                                        "contrato": "Contrato", "ingreso": st.column_config.DateColumn("Ingreso", format="DD/MM/YYYY"),
                                        "antiguedad": st.column_config.NumberColumn("Antigüedad (años)", format="%.1f"),
                                        "edad": st.column_config.NumberColumn("Edad", format="%.0f"),
                                        "ciudad_n": "Ciudad", "eps": "EPS",
                                        "salario": st.column_config.NumberColumn("Salario", format="$ %,.0f")})

    with t2:
        if abierta(t2):
            c1, c2 = st.columns([1.4, 1])
            with c1:
                st.markdown('<div class="pd-h">Ingresos y retiros por año</div><div class="pd-c">Barras: personas que '
                            'entraron y salieron. Línea: planta al cierre de cada año.</div>', unsafe_allow_html=True)
                ing = e["ingreso"].map(lambda x: x.year if ap._ok(x) else None).dropna().astype(int).value_counts()
                ret = e["retiro"].map(lambda x: x.year if ap._ok(x) else None).dropna().astype(int).value_counts()
                anios = list(range(int(min(ing.index.min(), ret.index.min() if len(ret) else 9999)), hoy.year + 1)) if len(ing) else []
                planta, acum = [], 0
                for a in anios:
                    acum += int(ing.get(a, 0)) - int(ret.get(a, 0))
                    planta.append(acum)
                fig = go.Figure()
                fig.add_bar(x=anios, y=[int(ing.get(a, 0)) for a in anios], name="Ingresos", marker_color=SERIES[2],
                            hovertemplate="%{x}: %{y} ingresos<extra></extra>")
                fig.add_bar(x=anios, y=[-int(ret.get(a, 0)) for a in anios], name="Retiros", marker_color=SERIES[1],
                            hovertemplate="%{x}: %{customdata} retiros<extra></extra>",
                            customdata=[int(ret.get(a, 0)) for a in anios])
                fig.add_scatter(x=anios, y=planta, name="Planta estimada", mode="lines+markers",
                                line=dict(color="#E8E8EA", width=2), marker=dict(size=8),
                                hovertemplate="%{x}: %{y} personas<extra></extra>")
                fig.update_layout(barmode="relative", bargap=0.35)
                st.plotly_chart(_layout(fig, 340, True), width="stretch")
                st.caption("Los retiros se leen de la columna Observaciones (p. ej. «RETIRO 31 JULIO DE 2025»); "
                           "los que no tienen fecha no aparecen.")
            with c2:
                st.markdown('<div class="pd-h">Antigüedad de la planta</div><div class="pd-c">Años en la empresa</div>',
                            unsafe_allow_html=True)
                an = act["antiguedad"].dropna()
                if len(an):
                    cortes = pd.cut(an, [0, 1, 2, 3, 5, 8, 50], right=False,
                                    labels=["<1", "1–2", "2–3", "3–5", "5–8", "8+"]).value_counts().sort_index()
                    fig = px.bar(x=cortes.index.astype(str), y=cortes.values, labels={"x": "Años", "y": ""})
                    fig.update_traces(marker_color=SERIES[0], hovertemplate="%{x} años: %{y} personas<extra></extra>")
                    st.plotly_chart(_layout(fig, 165), width="stretch")
                st.markdown('<div class="pd-h">Edades</div>', unsafe_allow_html=True)
                ed = act["edad"].dropna()
                if len(ed):
                    cortes = pd.cut(ed, [18, 25, 35, 45, 55, 65, 90], right=False,
                                    labels=["18–24", "25–34", "35–44", "45–54", "55–64", "65+"]).value_counts().sort_index()
                    fig = px.bar(x=cortes.index.astype(str), y=cortes.values, labels={"x": "Años", "y": ""})
                    fig.update_traces(marker_color=SERIES[6], hovertemplate="%{x}: %{y} personas<extra></extra>")
                    st.plotly_chart(_layout(fig, 165), width="stretch")

    with t3:
        if abierta(t3):
            eventos = []
            for _, r in (d.get("contratos") if d.get("contratos") is not None else pd.DataFrame()).iterrows():
                eventos.append({"fecha": r["prox"], "tipo": "Vence contrato", "persona": r["nombre"],
                                "detalle": f"{int(r['meses'])} meses" if ap._ok(r["meses"]) else "término fijo"})
                if ap._ok(r["preaviso"]):
                    eventos.append({"fecha": r["preaviso"], "tipo": "Preaviso (30 días)", "persona": r["nombre"],
                                    "detalle": "último día para avisar si no se renueva"})
            if nov is not None:
                for _, r in nov.iterrows():
                    if ap._ok(r["prox_examen"]):
                        eventos.append({"fecha": r["prox_examen"], "tipo": "Examen periódico", "persona": r["nombre"],
                                        "detalle": "un año después del último"})
            cu = d.get("cumpleanos")
            if cu is not None and not cu.empty:
                for _, r in cu.iterrows():
                    try:
                        f = pd.Timestamp(hoy.year, int(r["mes"]), int(r["dia"]))
                        if f < hoy.normalize():
                            f = pd.Timestamp(hoy.year + 1, int(r["mes"]), int(r["dia"]))
                        eventos.append({"fecha": f, "tipo": "Cumpleaños", "persona": r["nombre"], "detalle": "🎂"})
                    except ValueError:
                        continue
            evd = pd.DataFrame(eventos)
            if evd.empty:
                st.info("No hay fechas de contratos, exámenes ni cumpleaños cargadas.")
            else:
                evd["fecha"] = pd.to_datetime(evd["fecha"])
                horizonte = st.select_slider("Horizonte", options=[30, 60, 90, 180, 365], value=90,
                                             format_func=lambda x: f"{x} días", key="pd_hz")
                ve = evd[(evd["fecha"] >= hoy.normalize() - pd.Timedelta(days=30)) &
                         (evd["fecha"] <= hoy + pd.Timedelta(days=horizonte))].sort_values("fecha")
                colt = {"Vence contrato": SERIES[1], "Preaviso (30 días)": SERIES[3], "Examen periódico": SERIES[2],
                        "Cumpleaños": SERIES[4]}
                st.markdown('<div class="pd-h">Línea de tiempo</div><div class="pd-c">Cada punto es una fecha; pase el '
                            'cursor para ver la persona.</div>', unsafe_allow_html=True)
                fig = px.scatter(ve, x="fecha", y="tipo", color="tipo", color_discrete_map=colt, hover_name="persona",
                                 custom_data=["detalle"], labels={"fecha": "", "tipo": ""})
                fig.update_traces(marker=dict(size=13, line=dict(color="#0A0B0D", width=2)),
                                  hovertemplate="<b>%{hovertext}</b><br>%{x|%d %b %Y}<br>%{customdata[0]}<extra></extra>")
                fig.add_vline(x=hoy, line_color="#FF6A3D", line_dash="dot")
                st.plotly_chart(_layout(fig, 260), width="stretch")
                html = []
                for _, r in ve.head(40).iterrows():
                    dias = (r["fecha"].normalize() - hoy.normalize()).days
                    c = colt.get(r["tipo"], OTROS)
                    cuando = "vencido" if dias < 0 else "hoy" if dias == 0 else f"en {dias} días"
                    html.append(f'<div class="pd-ev"><div class="pd-d"><b>{r["fecha"].day:02d}</b><span>'
                                f'{MESES[r["fecha"].month - 1].upper()}</span></div><div><div class="pd-t">{escape(r["persona"])}'
                                f'<span class="pd-tag" style="color:{c};border:1px solid {c}66">{escape(r["tipo"])}</span></div>'
                                f'<div class="pd-s">{escape(str(r["detalle"]))} · {cuando}</div></div></div>')
                st.markdown("".join(html) or '<div class="pd-c">Nada en este horizonte.</div>', unsafe_allow_html=True)

    with t4:
        if abierta(t4):
            c1, c2 = st.columns([1.4, 1])
            vac = d.get("vacaciones")
            with c1:
                st.markdown('<div class="pd-h">Días de vacaciones pendientes</div><div class="pd-c">Rojo: 15 días o más '
                            '(conviene programarlas; la ley permite acumular hasta 2 periodos).</div>', unsafe_allow_html=True)
                if vac is not None and not vac.empty:
                    v = vac[vac["dias"] > 0].sort_values("dias")
                    fig = px.bar(v, x="dias", y="nombre", orientation="h", labels={"dias": "", "nombre": ""})
                    fig.update_traces(marker_color=[SERIES[7] if x >= 15 else SERIES[0] for x in v["dias"]],
                                      hovertemplate="%{y}: %{x} días<extra></extra>")
                    st.plotly_chart(_layout(fig, max(260, 24 * len(v) + 60)), width="stretch")
                else:
                    st.info("Sin datos de vacaciones.")
            with c2:
                st.markdown('<div class="pd-h">Cumpleaños por mes</div>', unsafe_allow_html=True)
                cu = d.get("cumpleanos")
                if cu is not None and not cu.empty:
                    cm = cu["mes"].value_counts().reindex(range(1, 13), fill_value=0)
                    fig = px.bar(x=MESES, y=cm.values, labels={"x": "", "y": ""})
                    fig.update_traces(marker_color=[SERIES[4] if i + 1 == hoy.month else "#2A2B30" for i in range(12)],
                                      hovertemplate="%{x}: %{y}<extra></extra>")
                    st.plotly_chart(_layout(fig, 200), width="stretch")
                    este = cu[cu["mes"] == hoy.month].sort_values("dia")
                    if not este.empty:
                        st.markdown("**Este mes:** " + " · ".join(f"{escape(r['nombre'])} ({r['dia']})"
                                                                  for _, r in este.iterrows()))
                if nov is not None:
                    pend = nov[nov["dotacion_pend"]]
                    st.markdown(f'<div class="pd-h">Dotación pendiente: {len(pend)}</div>', unsafe_allow_html=True)
                    if len(pend):
                        st.caption(", ".join(pend["nombre"].tolist()))

    with t5:
        if abierta(t5):
            c1, c2 = st.columns([1.3, 1])
            exp = d.get("expedientes")
            with c1:
                st.markdown('<div class="pd-h">Completitud del expediente por persona</div>', unsafe_allow_html=True)
                if exp is not None and not exp.empty:
                    x = exp.assign(pct=pd.to_numeric(exp["completitud_pct"], errors="coerce")).sort_values("pct")
                    fig = px.bar(x, x="pct", y="nombre", orientation="h", range_x=[0, 100], labels={"pct": "", "nombre": ""},
                                 custom_data=["total_documentos", "docs_faltantes"])
                    fig.update_traces(marker_color=[SERIES[2] if p >= 80 else SERIES[3] if p >= 50 else SERIES[7] for p in x["pct"]],
                                      hovertemplate="%{y}: %{x:.0f}%<br>%{customdata[0]} documentos · faltan %{customdata[1]}<extra></extra>")
                    fig.update_xaxes(ticksuffix="%")
                    st.plotly_chart(_layout(fig, max(260, 24 * len(x) + 60)), width="stretch")
            with c2:
                docs = d.get("documentos")
                st.markdown('<div class="pd-h">Documentos en los expedientes</div>', unsafe_allow_html=True)
                if docs is not None and not docs.empty:
                    docs = docs.sort_values("n", ascending=False)
                    fig = px.treemap(docs, path=["categoria"], values="n")
                    fig.update_traces(marker=dict(colors=[SERIES[i % 3] for i in range(len(docs))], line=dict(color="#0A0B0D", width=2)),
                                      hovertemplate="%{label}: %{value}<extra></extra>", texttemplate="%{label}<br>%{value}")
                    st.plotly_chart(_layout(fig, 300), width="stretch")
                st.markdown('<div class="pd-h">Calidad de los datos (activos)</div><div class="pd-c">Qué tan completa está la '
                            'ficha de cada campo</div>', unsafe_allow_html=True)
                act_all = e[e["activo"]]
                campos = {"Fecha de ingreso": "ingreso", "Fecha de nacimiento": "nacimiento", "Área": "area", "Cargo": "cargo_n",
                          "EPS": "eps", "Ciudad": "ciudad_n", "Caja": "caja", "Salario": "salario"}
                for et, c in campos.items():
                    pct = act_all[c].map(lambda v: ap._ok(v) and v != "Sin dato").mean() if len(act_all) else 0
                    st.markdown(f'<div style="display:flex;justify-content:space-between;color:#A1A1AA;font-size:13px">'
                                f'<span>{et}</span><b style="color:#fff">{pct * 100:.0f}%</b></div>', unsafe_allow_html=True)
                    st.progress(float(pct))
            cumpl = d.get("cumplimiento")
            if cumpl is not None and not cumpl.empty:
                st.markdown('<div class="pd-h">Documentos de contratación por persona</div><div class="pd-c">Verde = lo tiene · '
                            'gris = falta</div>', unsafe_allow_html=True)
                cols = [c for c in cumpl.columns if c != "nombre"]
                z = cumpl[cols].apply(lambda c: c.map(lambda v: 1 if str(v).upper() == "SI" else 0))
                etiquetas = [c.replace("doc_", "").replace("_", " ").title() for c in cols]
                fig = go.Figure(go.Heatmap(z=z.values, x=etiquetas, y=cumpl["nombre"], colorscale=[[0, "#1F2024"], [1, "#199e70"]],
                                           showscale=False, xgap=3, ygap=3,
                                           hovertemplate="%{y}<br>%{x}: %{z}<extra></extra>"))
                st.plotly_chart(_layout(fig, 40 + 24 * len(cumpl)), width="stretch")
