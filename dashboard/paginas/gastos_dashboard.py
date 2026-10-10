"""Gastos — tablero interactivo con la contabilidad real (auxiliar del contador) y los compromisos recurrentes."""
from __future__ import annotations

from datetime import date, timedelta
from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.estilos import OTROS, PLOTLY_LAYOUT, SECUENCIAL, SERIES
from modulos import analitica_gastos as ag

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

CSS = """
<style>
.gd-hero{border:1px solid #1F2024;border-radius:22px;padding:22px 24px;margin-bottom:12px;
 background:radial-gradient(120% 160% at 100% 0%,#1A1310 0%,#0A0B0D 60%)}
.gd-eb{font-family:'Geist Mono',monospace;font-size:11px;letter-spacing:.14em;color:#8B8B93;text-transform:uppercase}
.gd-big{font-size:46px;font-weight:300;color:#fff;letter-spacing:-.03em;line-height:1.05;margin-top:6px}
.gd-sub{color:#A1A1AA;font-size:13.5px;margin-top:4px}.gd-sub b{color:#fff;font-weight:500}
.gd-k{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:16px}
.gd-k div{background:#0F1012;border:1px solid #1F2024;border-radius:14px;padding:11px 13px}
.gd-k b{display:block;color:#fff;font-size:19px;font-weight:500}
.gd-k span{font-size:10px;color:#8B8B93;font-family:'Geist Mono',monospace;letter-spacing:.08em;text-transform:uppercase}
.gd-h{color:#fff;font-size:16px;font-weight:500;margin:14px 0 2px}.gd-c{color:#8B8B93;font-size:12.5px;margin-bottom:4px}
.gd-an{border-left:3px solid #c98500;background:#121317;border-radius:0 12px 12px 0;padding:8px 12px;margin:6px 0;
 color:#E4E4E7;font-size:13.5px}.gd-an small{color:#8B8B93}
</style>
"""


def _p(v: float | None, corto: bool = False) -> str:
    if v is None:
        return "—"
    if corto and abs(v) >= 1e6:
        return f"${v / 1e6:,.1f} M".replace(",", "X").replace(".", ",").replace("X", ".")
    return "$" + f"{v:,.0f}".replace(",", ".")


def _layout(fig: go.Figure, alto: int = 320, leyenda: bool = True) -> go.Figure:
    fig.update_layout(**PLOTLY_LAYOUT, height=alto, showlegend=leyenda, hovermode="closest",
                      legend=dict(orientation="h", y=-0.18, x=0, title_text="", font=dict(size=11)),
                      hoverlabel=dict(bgcolor="#141519", bordercolor="#2A2B30", font=dict(color="#E8E8EA")))
    fig.update_xaxes(showgrid=False, linecolor="#26272C", tickfont=dict(color="#8B8B93"))
    fig.update_yaxes(gridcolor="#1A1B1F", zeroline=False, tickfont=dict(color="#8B8B93"))
    return fig


def _mes(ts: pd.Timestamp) -> str:
    return f"{MESES[ts.month - 1]} {str(ts.year)[2:]}"


def _cargar_ui() -> dict | None:
    with st.expander("Fuente de datos · subir el auxiliar del contador", expanded=False):
        libros = ag.libros_disponibles()
        if libros:
            st.caption("Se usa el más reciente: " + escape(libros[0].name))
        sub = st.file_uploader("Libro del contador (.xlsx / .xlsm con hojas Auxiliar y Prueba)", type=["xlsx", "xlsm"],
                               key="gd_up")
        if sub is not None and st.button("Usar este archivo", type="primary"):
            ag.guardar_subida(sub.name, sub.getvalue())
            st.cache_data.clear()
            st.rerun()
    return _datos()


@st.cache_data(show_spinner="Leyendo la contabilidad…", ttl=3600)
def _datos_cache(_firma: str) -> dict | None:
    return ag.cargar()


def _datos() -> dict | None:
    libros = ag.libros_disponibles()
    firma = f"{libros[0]}|{libros[0].stat().st_mtime}" if libros else "ninguno"
    return _datos_cache(firma)


def render() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    datos = _cargar_ui()
    if not datos:
        st.info("Aún no hay contabilidad cargada. Suba el libro del contador (el mismo Excel de la liquidación de "
                "retención, con hojas **Auxiliar** y **Prueba**) en «Fuente de datos». También se toma solo el que "
                "suba en Impuestos → Revisión de impuestos.")
        return
    mov: pd.DataFrame = datos["mov"]

    # ── Filtros (una fila) ──
    meses = sorted(mov["mes"].unique())
    f1, f2, f3 = st.columns([2.2, 2, 1.1])
    if len(meses) > 1:
        r = f1.select_slider("Periodo", options=meses, value=(meses[0], meses[-1]), format_func=_mes, key="gd_rng")
    else:
        r = (meses[0], meses[0])
    grupos_all = sorted(mov.loc[mov["clase"] != "4", "nombre_grupo"].unique())
    grupos = f2.multiselect("Tipo de gasto", grupos_all, default=grupos_all, key="gd_grp")
    costos = f3.toggle("Incluir costo de ventas", value=True, key="gd_cost",
                       help="Cuentas 6 y 7: el costo de la mercancía vendida")
    m = mov[(mov["mes"] >= r[0]) & (mov["mes"] <= r[1])]
    m = m[(m["clase"] == "4") | m["nombre_grupo"].isin(grupos)]
    g = ag.gastos(m, costos)
    k = ag.kpis(m, costos)
    if not k:
        st.warning("No hay movimientos en ese periodo.")
        return

    var = k["var_mes"]
    var_txt = (f'<b style="color:{"#e66767" if var > 0 else "#4ADE80"}">{var * 100:+.0f}%</b> vs mes anterior'
               if var is not None else "")
    pct_html = (f'<div><b>{k["pct_ingresos"] * 100:.0f}%</b><span>Gasto / ingreso</span></div>'
                if k["pct_ingresos"] else "")
    st.markdown(
        f'<div class="gd-hero"><div class="gd-eb">Gastos {"y costos " if costos else ""}· {_mes(r[0])} – {_mes(r[1])} · '
        f'fuente: contabilidad</div><div class="gd-big">{_p(k["gasto_total"])}</div>'
        f'<div class="gd-sub">Último mes ({_mes(k["ultimo_mes"])}): <b>{_p(k["gasto_ultimo"])}</b> {var_txt} · '
        f'promedio mensual <b>{_p(k["promedio_mes"])}</b></div>'
        f'<div class="gd-k">'
        f'<div><b>{_p(k["ingreso_total"], True)}</b><span>Ingresos</span></div>'
        f'<div><b style="color:{"#4ADE80" if k["resultado"] >= 0 else "#e66767"}">{_p(k["resultado"], True)}</b><span>Resultado</span></div>'
        f'{pct_html}'
        f'<div><b>{escape(str(k["cuenta_mayor"]))[:22]}</b><span>Cuenta más alta · {_p(k["cuenta_mayor_valor"], True)}</span></div>'
        f'<div><b>{_mes(k["mes_mayor"])}</b><span>Mes más alto · {_p(k["mes_mayor_valor"], True)}</span></div>'
        f'<div><b>{k["terceros"]:,}</b><span>Terceros · {k["movimientos"]:,} mov.</span></div>'
        f'</div></div>', unsafe_allow_html=True)

    t1, t2, t3, t4, t5 = st.tabs(["Evolución", "¿En qué se gasta?", "Proveedores", "Detalle", "Compromisos recurrentes"])

    with t1:
        mens = ag.mensual(m, costos)
        c1, c2 = st.columns([1.35, 1])
        with c1:
            st.markdown('<div class="gd-h">Gasto mensual por tipo</div><div class="gd-c">Pase el cursor para ver '
                        'el valor; haga clic en la leyenda para ocultar un tipo.</div>', unsafe_allow_html=True)
            pm = g.groupby(["mes", "nombre_grupo"])["monto"].sum().reset_index()
            orden = pm.groupby("nombre_grupo")["monto"].sum().sort_values(ascending=False).index.tolist()
            colores = {n: (SERIES[i] if i < len(SERIES) else OTROS) for i, n in enumerate(sorted(grupos_all))}
            fig = px.bar(pm, x="mes", y="monto", color="nombre_grupo", category_orders={"nombre_grupo": orden},
                         color_discrete_map=colores, labels={"monto": "", "mes": "", "nombre_grupo": ""})
            fig.update_traces(marker_line_color="#0A0B0D", marker_line_width=2,
                              hovertemplate="%{x|%b %Y}<br>%{fullData.name}: $%{y:,.0f}<extra></extra>")
            fig.update_layout(bargap=0.35)
            fig.update_xaxes(tickformat="%b %y", dtick="M1")
            fig.update_yaxes(tickformat="~s", tickprefix="$")
            st.plotly_chart(_layout(fig, 360), use_container_width=True)
        with c2:
            st.markdown('<div class="gd-h">Ingresos vs. gastos</div><div class="gd-c">Resultado del mes = ingresos − '
                        'gastos</div>', unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_bar(x=mens.index, y=mens["ingresos"], name="Ingresos", marker_color=SERIES[2],
                        hovertemplate="%{x|%b %Y}<br>Ingresos $%{y:,.0f}<extra></extra>")
            fig.add_bar(x=mens.index, y=mens["gastos"], name="Gastos", marker_color=SERIES[1],
                        hovertemplate="%{x|%b %Y}<br>Gastos $%{y:,.0f}<extra></extra>")
            fig.add_scatter(x=mens.index, y=mens["resultado"], name="Resultado", mode="lines+markers",
                            line=dict(color="#E8E8EA", width=2), marker=dict(size=8),
                            hovertemplate="%{x|%b %Y}<br>Resultado $%{y:,.0f}<extra></extra>")
            fig.update_layout(barmode="group", bargap=0.3)
            fig.update_xaxes(tickformat="%b %y", dtick="M1")
            fig.update_yaxes(tickformat="~s", tickprefix="$")
            st.plotly_chart(_layout(fig, 360), use_container_width=True)
        an = ag.anomalias(m, costos)
        if not an.empty:
            st.markdown('<div class="gd-h">Lo que se salió de lo normal en el último mes</div>', unsafe_allow_html=True)
            for _, a in an.head(6).iterrows():
                st.markdown(f'<div class="gd-an"><b>{escape(str(a["cuenta"]))}</b>: {_p(a["ultimo"])} '
                            f'<small>vs. promedio {_p(a["promedio"])} ({a["variacion"] * 100:+.0f}%)</small></div>',
                            unsafe_allow_html=True)

    with t2:
        c1, c2 = st.columns([1.4, 1])
        with c1:
            st.markdown('<div class="gd-h">Mapa de gastos</div><div class="gd-c">Clic en un bloque para entrar; '
                        'clic arriba para volver.</div>', unsafe_allow_html=True)
            tm = g.groupby(["nombre_grupo", "nombre_cuenta4", "nombre_cuenta6"])["monto"].sum().reset_index()
            tm = tm[tm["monto"] > 0]
            fig = px.treemap(tm, path=[px.Constant("Total"), "nombre_grupo", "nombre_cuenta4", "nombre_cuenta6"],
                             values="monto", color="nombre_grupo", color_discrete_map={**colores, "(?)": OTROS})
            fig.update_traces(hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percentRoot:.1%} del total<extra></extra>",
                              texttemplate="%{label}<br>%{percentRoot:.0%}", marker_line_color="#0A0B0D",
                              marker_line_width=2, root_color="#0F1012")
            st.plotly_chart(_layout(fig, 460, False), use_container_width=True)
        with c2:
            st.markdown('<div class="gd-h">Top cuentas</div>', unsafe_allow_html=True)
            top = g.groupby("nombre_cuenta4")["monto"].sum().sort_values(ascending=True).tail(12).reset_index()
            top["nombre_cuenta4"] = top["nombre_cuenta4"].str.slice(0, 28)
            fig = px.bar(top, x="monto", y="nombre_cuenta4", orientation="h", labels={"monto": "", "nombre_cuenta4": ""})
            fig.update_traces(marker_color=SERIES[0], hovertemplate="%{y}<br>$%{x:,.0f}<extra></extra>")
            fig.update_xaxes(tickformat="~s", tickprefix="$")
            st.plotly_chart(_layout(fig, 460, False), use_container_width=True)
        st.markdown('<div class="gd-h">Mapa de calor: cuenta × mes</div><div class="gd-c">Cada fila se compara con su '
                    'propio mes más alto (más claro = más gasto en esa cuenta). Sirve para ver estacionalidad.</div>', unsafe_allow_html=True)
        hm = g.pivot_table(index="nombre_cuenta4", columns="mes", values="monto", aggfunc="sum").fillna(0)
        hm = hm.loc[hm.sum(axis=1).sort_values(ascending=False).index[:15]]
        rel = hm.div(hm.max(axis=1).where(hm.max(axis=1) > 0), axis=0).fillna(0)  # cada cuenta contra su mes más alto
        fig = go.Figure(go.Heatmap(z=rel.values, x=[_mes(c) for c in hm.columns], y=[str(i)[:30] for i in hm.index],
                                   customdata=hm.values, zmin=0, zmax=1,
                                   colorscale=[[i / (len(SECUENCIAL) - 1), c] for i, c in enumerate(SECUENCIAL)],
                                   xgap=2, ygap=2, hovertemplate="%{y}<br>%{x}: $%{customdata:,.0f}<extra></extra>",
                                   colorbar=dict(tickvals=[0, 1], ticktext=["bajo", "su mes más alto"], outlinewidth=0)))
        st.plotly_chart(_layout(fig, 40 + 26 * len(hm), False), use_container_width=True)

    with t3:
        propio = g["nit"].astype(str).str.replace(r"\D", "", regex=True).str.startswith("901146454")
        g_ext = g[~propio]
        st.caption(f"Sin contar movimientos internos de la empresa ({_p(g[propio]['monto'].sum())}: costo de ventas, "
                   "cierres y autorretenciones).")
        terc = g_ext.groupby("tercero").agg(total=("monto", "sum"), movimientos=("monto", "size"),
                                         ultimo=("fecha", "max"), meses=("mes", "nunique")).reset_index()
        terc = terc[terc["total"] > 0].sort_values("total", ascending=False)
        c1, c2 = st.columns([1.3, 1])
        with c1:
            st.markdown('<div class="gd-h">Top 15 terceros</div><div class="gd-c">Seleccione una barra para ver sus '
                        'movimientos abajo.</div>', unsafe_allow_html=True)
            t15 = terc.head(15).iloc[::-1]
            fig = px.bar(t15, x="total", y="tercero", orientation="h", labels={"total": "", "tercero": ""},
                         custom_data=["movimientos", "meses"])
            fig.update_traces(marker_color=SERIES[0],
                              hovertemplate="%{y}<br>$%{x:,.0f}<br>%{customdata[0]} movimientos · %{customdata[1]} meses<extra></extra>")
            fig.update_xaxes(tickformat="~s", tickprefix="$")
            ev = st.plotly_chart(_layout(fig, 500, False), use_container_width=True, on_select="rerun",
                                 selection_mode="points", key="gd_terc")
        with c2:
            st.markdown('<div class="gd-h">Concentración</div><div class="gd-c">Cuánto del gasto se va en los '
                        'principales terceros</div>', unsafe_allow_html=True)
            tot = terc["total"].sum()
            filas = [(f"Top {n}", terc.head(n)["total"].sum() / tot if tot else 0) for n in (1, 5, 10, 20)]
            for et, v in filas:
                st.markdown(f'<div style="display:flex;justify-content:space-between;color:#A1A1AA;font-size:13px">'
                            f'<span>{et}</span><b style="color:#fff">{v * 100:.0f}%</b></div>', unsafe_allow_html=True)
                st.progress(min(1.0, v))
            st.markdown(f'<div class="gd-c" style="margin-top:10px">{len(terc):,} terceros con gasto en el periodo.</div>',
                        unsafe_allow_html=True)
        sel = None
        try:
            pts = ev.selection.points if ev else []
            sel = pts[0]["y"] if pts else None
        except Exception:
            sel = None
        busca = st.text_input("Buscar tercero", value=sel or "", key="gd_tq", placeholder="Nombre del proveedor…")
        if busca:
            d = g_ext[g_ext["tercero"].str.contains(busca, case=False, na=False)]
            st.markdown(f'<div class="gd-h">{escape(busca)}: {_p(d["monto"].sum())} en {len(d)} movimientos</div>',
                        unsafe_allow_html=True)
            serie = d.groupby("mes")["monto"].sum()
            if len(serie) > 1:
                fig = px.area(serie.reset_index(), x="mes", y="monto", labels={"monto": "", "mes": ""})
                fig.update_traces(line_color=SERIES[0], fillcolor="rgba(57,135,229,.18)",
                                  hovertemplate="%{x|%b %Y}: $%{y:,.0f}<extra></extra>")
                fig.update_yaxes(tickformat="~s", tickprefix="$")
                st.plotly_chart(_layout(fig, 220, False), use_container_width=True)
            st.dataframe(d.sort_values("fecha", ascending=False)[["fecha", "nombre_cuenta6", "detalle", "comprobante", "monto"]],
                         use_container_width=True, hide_index=True,
                         column_config={"fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                                        "nombre_cuenta6": "Cuenta", "detalle": "Detalle", "comprobante": "Comprobante",
                                        "monto": st.column_config.NumberColumn("Valor", format="$ %,.0f")})
        else:
            st.dataframe(terc.head(100), use_container_width=True, hide_index=True,
                         column_config={"tercero": "Tercero", "total": st.column_config.NumberColumn("Total", format="$ %,.0f"),
                                        "movimientos": "Movimientos", "meses": "Meses con gasto",
                                        "ultimo": st.column_config.DateColumn("Último", format="DD/MM/YYYY")})

    with t4:
        c1, c2 = st.columns([1, 1])
        cuentas = ["Todas"] + sorted(g["nombre_cuenta4"].unique())
        cta = c1.selectbox("Cuenta", cuentas, key="gd_cta")
        txt = c2.text_input("Buscar en el detalle", key="gd_txt", placeholder="arriendo, flete, DHL…")
        d = g if cta == "Todas" else g[g["nombre_cuenta4"] == cta]
        if txt:
            d = d[d["detalle"].str.contains(txt, case=False, na=False) | d["tercero"].str.contains(txt, case=False, na=False)]
        st.markdown(f'<div class="gd-h">{len(d):,} movimientos · {_p(d["monto"].sum())}</div>', unsafe_allow_html=True)
        vista = d.sort_values("fecha", ascending=False)[["fecha", "nombre_cuenta4", "nombre_cuenta6", "tercero", "detalle",
                                                         "comprobante", "monto"]]
        st.dataframe(vista.head(2000), use_container_width=True, hide_index=True, height=480,
                     column_config={"fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                                    "nombre_cuenta4": "Cuenta", "nombre_cuenta6": "Subcuenta", "tercero": "Tercero",
                                    "detalle": "Detalle", "comprobante": "Comprobante",
                                    "monto": st.column_config.NumberColumn("Valor", format="$ %,.0f")})
        st.download_button("Descargar (CSV)", vista.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"gastos_{date.today()}.csv", mime="text/csv")

    with t5:
        _compromisos()


def _compromisos() -> None:
    from modulos.motor_alertas import _filas
    try:
        cat = pd.DataFrame(_filas("SELECT categoria, periodicidad_std, centro_costos, proveedor_limpio FROM gastos_maestro"))
    except Exception:
        cat = pd.DataFrame()
    try:
        hoy = date.today()
        prox = pd.DataFrame(_filas(
            "SELECT fecha_sugerida, detalle, proveedor, centro_costos, valor, estado FROM pagos_calendario "
            "WHERE estado IN ('PENDIENTE','EN PROCESO') AND fecha_sugerida BETWEEN ? AND ? ORDER BY fecha_sugerida",
            (hoy.isoformat(), (hoy + timedelta(days=30)).isoformat())))
    except Exception:
        prox = pd.DataFrame()
    if cat.empty and prox.empty:
        st.info("No hay compromisos cargados. Use Pagos → Control de pagos y la estandarización de gastos.")
        return
    c1, c2 = st.columns([1.2, 1])
    if not cat.empty:
        with c1:
            st.markdown(f'<div class="gd-h">Compromisos por categoría y frecuencia</div><div class="gd-c">{len(cat):,} '
                        'registros del catálogo de gastos. Clic para entrar.</div>', unsafe_allow_html=True)
            sb = cat.fillna("SIN DATO").groupby(["categoria", "periodicidad_std"]).size().reset_index(name="n")
            sb["categoria"] = sb["categoria"].str.replace("_", " ").str.title()
            top = sb.groupby("categoria")["n"].sum().sort_values(ascending=False).index[:8].tolist()
            sb.loc[~sb["categoria"].isin(top), "categoria"] = "Otras"
            colores = {c: SERIES[i] for i, c in enumerate(top)}
            colores["Otras"] = OTROS
            fig = px.sunburst(sb, path=["categoria", "periodicidad_std"], values="n", color="categoria",
                              color_discrete_map=colores)
            fig.update_traces(hovertemplate="%{label}: %{value} registros<extra></extra>", marker_line_color="#0A0B0D",
                              marker_line_width=2, insidetextorientation="radial")
            st.plotly_chart(_layout(fig, 430, False), use_container_width=True)
    with c2:
        st.markdown(f'<div class="gd-h">Próximos 30 días</div><div class="gd-c">{len(prox)} pagos programados '
                    '(Control de pagos)</div>', unsafe_allow_html=True)
        if not prox.empty:
            prox["fecha_sugerida"] = pd.to_datetime(prox["fecha_sugerida"])
            por_sem = prox.groupby(prox["fecha_sugerida"].dt.to_period("W").dt.start_time).size().reset_index(name="pagos")
            fig = px.bar(por_sem, x="fecha_sugerida", y="pagos", labels={"fecha_sugerida": "Semana", "pagos": ""})
            fig.update_traces(marker_color=SERIES[0], hovertemplate="Semana del %{x|%d %b}: %{y} pagos<extra></extra>")
            st.plotly_chart(_layout(fig, 200, False), use_container_width=True)
            st.dataframe(prox, use_container_width=True, hide_index=True, height=230,
                         column_config={"fecha_sugerida": st.column_config.DateColumn("Fecha", format="DD/MM"),
                                        "detalle": "Pago", "proveedor": "Proveedor", "centro_costos": "Centro",
                                        "valor": st.column_config.NumberColumn("Valor", format="$ %,.0f"),
                                        "estado": "Estado"})
