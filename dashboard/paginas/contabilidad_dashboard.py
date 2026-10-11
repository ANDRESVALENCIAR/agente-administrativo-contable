"""Contabilidad — tablero gerencial con el libro real del contador (Auxiliar + Prueba).

Mismo lenguaje visual que Gastos y Personal: héroe con la cifra principal, indicadores en tarjetas y pestañas
perezosas con gráficos interactivos."""
from __future__ import annotations

from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.estilos import SERIES
from dashboard.paginas.gastos_dashboard import CSS as CSS_GD, _cargar_ui, _layout, _mes, _p
from dashboard.utils.pestanas import abierta, pestanas
from modulos import analitica_contable as ac

VERDE, ROJO, AMBAR = "#4ADE80", "#e66767", "#c98500"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]

CSS = CSS_GD + """
<style>
.cd-ok{display:inline-block;font-size:11px;font-family:'Geist Mono',monospace;letter-spacing:.06em;padding:3px 9px;
 border-radius:99px;margin-left:8px;vertical-align:middle}
.cd-pl{display:table!important;width:100%!important;border-collapse:collapse!important;border:0!important;
 font-size:13.5px;margin-top:6px;background:transparent!important}
.cd-pl tr,.cd-pl tbody{border:0!important;background:transparent!important}
.cd-pl td{padding:7px 4px!important;border:0!important;border-bottom:1px solid #18191D!important;color:#D4D4D8;
 background:transparent!important}
.cd-pl td:last-child,.cd-pl td.n{text-align:right;font-variant-numeric:tabular-nums}
.cd-pl tr.t td{color:#fff;font-weight:600;border-bottom:1px solid #2A2B30}
.cd-pl td.p{color:#8B8B93;font-size:12px;width:60px}
.cd-ind{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-top:8px}
.cd-ind div{background:#0F1012;border:1px solid #1F2024;border-radius:14px;padding:13px 15px;border-top:3px solid #52525B}
.cd-ind b{display:block;color:#fff;font-size:24px;font-weight:400;letter-spacing:-.02em}
.cd-ind span{display:block;font-size:10.5px;color:#8B8B93;font-family:'Geist Mono',monospace;letter-spacing:.08em;
 text-transform:uppercase;margin:2px 0 6px}
.cd-ind p{color:#A1A1AA;font-size:12.5px;margin:0;line-height:1.35}
.cd-ind .bien{border-top-color:#4ADE80}.cd-ind .ojo{border-top-color:#c98500}.cd-ind .mal{border-top-color:#e66767}
</style>
"""


def _fecha(ts) -> str:
    return f"{ts.day} de {MESES[ts.month - 1]} de {ts.year}" if ts is not None and pd.notna(ts) else "—"


def _pct(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v * 100:.1f}%".replace(".", ",")


def _color(v: float) -> str:
    return VERDE if v >= 0 else ROJO


def _fmt_ind(i: dict) -> str:
    v = i["valor"]
    if v is None or pd.isna(v):
        return "—"
    if i["fmt"] == "%":
        return _pct(v)
    if i["fmt"] == "x":
        return f"{v:.2f}".replace(".", ",")
    if i["fmt"] == "d":
        return f"{v:.0f} días"
    return _p(v, True)


@st.cache_data(show_spinner=False, ttl=3600)
def _abiertas(_datos: dict, fuente: str, cuentas: tuple, deuda: bool, corte: pd.Timestamp) -> pd.DataFrame:
    return ac.abiertas(_datos["terceros"], cuentas, deuda, corte)


def render() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    datos = _cargar_ui()
    if not datos or "prueba" not in datos:
        st.info("Aún no hay contabilidad cargada. Suba el libro del contador (Excel con hojas **Auxiliar** y "
                "**Prueba**) en «Fuente de datos». Es el mismo archivo que se usa en Gastos y en Revisión de impuestos.")
        return
    mov: pd.DataFrame = datos["mov"]
    pr: dict = datos["prueba"]
    corte = ac.corte(datos)

    meses = sorted(mov["mes"].unique())
    f1, f2 = st.columns([2.4, 1.6])
    r = (f1.select_slider("Periodo del estado de resultados", options=meses, value=(meses[0], meses[-1]),
                          format_func=_mes, key="cd_rng") if len(meses) > 1 else (meses[0], meses[0]))
    m = mov[(mov["mes"] >= r[0]) & (mov["mes"] <= r[1])]
    e = ac.estado_resultados(m)
    b = ac.balance(pr)
    dias = max(1, (m["fecha"].max() - m["fecha"].min()).days + 1)
    f2.markdown(f'<div class="gd-c" style="margin-top:30px">Balance con corte al <b style="color:#fff">'
                f'{_fecha(corte)}</b> · fuente: {escape(str(datos.get("fuente", "")).split("/")[-1].split(chr(92))[-1])}'
                f'</div>', unsafe_allow_html=True)

    # ── Héroe ──
    cuadra = (f'<span class="cd-ok" style="background:#0F2A1A;color:{VERDE}">BALANCE CUADRA ✓</span>' if b["cuadra"]
              else f'<span class="cd-ok" style="background:#2A1212;color:{ROJO}">BALANCE NO CUADRA</span>')
    st.markdown(
        f'<div class="gd-hero"><div class="gd-eb">Resultado neto · {_mes(r[0])} – {_mes(r[1])}{cuadra}</div>'
        f'<div class="gd-big" style="color:{_color(e["neta"])}">{"−" if e["neta"] < 0 else ""}{_p(abs(e["neta"]))}</div>'
        f'<div class="gd-sub">Ventas <b>{_p(e["ingresos"])}</b> · margen bruto <b>{_pct(e["margen_bruto"])}</b> · '
        f'margen operacional <b>{_pct(e["margen_operacional"])}</b> · margen neto '
        f'<b style="color:{_color(e["neta"])}">{_pct(e["margen_neto"])}</b></div>'
        f'<div class="gd-k">'
        f'<div><b>{_p(b["activo"], True)}</b><span>Activo</span></div>'
        f'<div><b>{_p(b["pasivo"], True)}</b><span>Pasivo · {_pct(b["pasivo"] / b["activo"] if b["activo"] else None)}</span></div>'
        f'<div><b style="color:{_color(b["patrimonio_total"])}">{_p(b["patrimonio_total"], True)}</b><span>Patrimonio con resultado</span></div>'
        f'<div><b>{_p(b["disponible"], True)}</b><span>Caja y bancos</span></div>'
        f'<div><b>{_p(b["clientes"], True)}</b><span>Clientes nos deben</span></div>'
        f'<div><b>{_p(b["proveedores"], True)}</b><span>Debemos a proveedores</span></div>'
        f'<div><b>{_p(b["bancos_deuda"], True)}</b><span>Deuda con bancos</span></div>'
        f'<div><b>{_p(b["impuestos"], True)}</b><span>Impuestos por pagar</span></div>'
        f'</div></div>', unsafe_allow_html=True)

    inds = ac.indicadores(b, e, dias)
    malos = [i for i in inds if i["semaforo"] == "mal"]
    for i in malos[:4]:
        st.markdown(f'<div class="gd-an"><b>{i["nombre"]}: {_fmt_ind(i)}</b> <small>— {i["que"]}</small></div>',
                    unsafe_allow_html=True)

    t1, t2, t3, t4, t5 = pestanas(["Resultados", "Balance", "Caja y bancos", "Cartera y proveedores", "Indicadores"],
                                  key="cd_tabs")

    with t1:
        if abierta(t1):
            _tab_resultados(m, e)
    with t2:
        if abierta(t2):
            _tab_balance(b)
    with t3:
        if abierta(t3):
            _tab_caja(datos, b)
    with t4:
        if abierta(t4):
            _tab_cartera(datos, b, corte)
    with t5:
        if abierta(t5):
            st.markdown('<div class="gd-h">Indicadores financieros</div><div class="gd-c">Verde: sano · ámbar: vigilar · '
                        f'rojo: atender. Calculados con el balance al {_fecha(corte)} y las ventas del periodo elegido '
                        f'({dias} días).</div>', unsafe_allow_html=True)
            st.markdown('<div class="cd-ind">' + "".join(
                f'<div class="{i["semaforo"]}"><b>{_fmt_ind(i)}</b><span>{i["nombre"]}</span><p>{i["que"]}</p></div>'
                for i in inds) + '</div>', unsafe_allow_html=True)


# ───────────────────────── Pestañas ─────────────────────────

def _tab_resultados(m: pd.DataFrame, e: dict) -> None:
    c1, c2 = st.columns([1.25, 1])
    with c1:
        st.markdown('<div class="gd-h">De las ventas a la utilidad</div><div class="gd-c">Cómo se va quedando la plata '
                    'en cada paso. Pase el cursor para ver el valor.</div>', unsafe_allow_html=True)
        pasos = [("Ventas", e["ingresos"], "absolute"), ("Costo<br>de ventas", -e["costo"], "relative"),
                 ("Utilidad<br>bruta", 0, "total"), ("Adminis-<br>tración", -e["admin"], "relative"),
                 ("Gastos de<br>ventas", -e["ventas"], "relative"), ("Utilidad<br>operacional", 0, "total"),
                 ("Otros<br>ingresos", e["otros_ingresos"], "relative"),
                 ("Financieros<br>y otros", -e["otros_gastos"], "relative")]
        if e["renta"]:
            pasos.append(("Impuesto<br>de renta", -e["renta"], "relative"))
        pasos.append(("Utilidad<br>neta", 0, "total"))
        fig = go.Figure(go.Waterfall(
            x=[p[0] for p in pasos], y=[p[1] for p in pasos], measure=[p[2] for p in pasos],
            increasing=dict(marker=dict(color=SERIES[0])), decreasing=dict(marker=dict(color=SERIES[1])),
            totals=dict(marker=dict(color="#A1A1AA")), connector=dict(line=dict(color="#2A2B30", width=1)),
            hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>"))
        fig.update_yaxes(tickformat="~s", tickprefix="$")
        fig.update_xaxes(tickangle=0, tickfont=dict(size=10.5))
        st.plotly_chart(_layout(fig, 400, False), width="stretch")
    with c2:
        st.markdown('<div class="gd-h">Estado de resultados</div>', unsafe_allow_html=True)
        base = e["ingresos"] or 1
        filas = [("Ventas", e["ingresos"], False), ("Costo de ventas", -e["costo"], False),
                 ("Utilidad bruta", e["bruta"], True), ("Gastos de administración", -e["admin"], False),
                 ("Gastos de ventas", -e["ventas"], False), ("Utilidad operacional", e["operacional"], True),
                 ("Otros ingresos", e["otros_ingresos"], False), ("Gastos no operacionales", -e["otros_gastos"], False),
                 ("Impuesto de renta", -e["renta"], False), ("Utilidad neta", e["neta"], True)]
        html = "".join(
            f'<tr class="{"t" if tot else ""}"><td>{n}</td><td class="p">{round(v / base * 100) or 0:.0f}%</td>'
            f'<td style="color:{(_color(v) if tot else "#D4D4D8")}">{"−" if v < 0 else ""}{_p(abs(v))}</td></tr>'
            for n, v, tot in filas)
        st.markdown(f'<table class="cd-pl">{html}</table>', unsafe_allow_html=True)

    mm = ac.resultados_mensuales(m)
    if not mm.empty:
        st.markdown('<div class="gd-h">Mes a mes</div><div class="gd-c">Barras: ingresos frente a costos y gastos. '
                    'Línea: utilidad del mes. Clic en la leyenda para ocultar una serie.</div>', unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_bar(x=mm["mes"], y=mm["ingresos"], name="Ingresos", marker_color=SERIES[2],
                    hovertemplate="%{x|%b %Y}<br>Ingresos $%{y:,.0f}<extra></extra>")
        fig.add_bar(x=mm["mes"], y=mm["costo"], name="Costo de ventas", marker_color=SERIES[3],
                    hovertemplate="%{x|%b %Y}<br>Costo $%{y:,.0f}<extra></extra>")
        fig.add_bar(x=mm["mes"], y=mm["gastos"], name="Gastos", marker_color=SERIES[1],
                    hovertemplate="%{x|%b %Y}<br>Gastos $%{y:,.0f}<extra></extra>")
        fig.add_scatter(x=mm["mes"], y=mm["utilidad"], name="Utilidad", mode="lines+markers",
                        line=dict(color="#E8E8EA", width=2), marker=dict(size=8, color=[_color(v) for v in mm["utilidad"]]),
                        hovertemplate="%{x|%b %Y}<br>Utilidad $%{y:,.0f}<extra></extra>")
        fig.update_layout(barmode="group", bargap=0.25)
        fig.update_xaxes(tickformat="%b %y", dtick="M1")
        fig.update_yaxes(tickformat="~s", tickprefix="$")
        st.plotly_chart(_layout(fig, 360), width="stretch")
        positivos = int((mm["utilidad"] > 0).sum())
        st.markdown(f'<div class="gd-c">{positivos} de {len(mm)} meses con utilidad · mejor mes: '
                    f'<b style="color:#fff">{_mes(mm.loc[mm["utilidad"].idxmax(), "mes"])}</b> '
                    f'({_p(mm["utilidad"].max())}) · peor: <b style="color:#fff">'
                    f'{_mes(mm.loc[mm["utilidad"].idxmin(), "mes"])}</b> ({_p(mm["utilidad"].min())})</div>',
                    unsafe_allow_html=True)


def _tab_balance(b: dict) -> None:
    st.markdown('<div class="gd-h">Lo que tiene la empresa y cómo se financia</div><div class="gd-c">Arriba: activos. '
                'Abajo: deudas y patrimonio. Las dos barras miden lo mismo cuando el balance cuadra.</div>',
                unsafe_allow_html=True)
    azules = ["#3987e5", "#2a6bc0", "#7fb0f0", "#1d4d8a", "#c4dcfa", "#15325a"]
    naranjas = ["#d95926", "#c98500", "#e66767", "#d55181", "#f08a4b", "#9c3d17", "#e8b04a", "#b8475f"]
    verdes = ["#199e70", "#4ADE80", "#0f6b4c"]
    filas, colores = [], {}
    for i, g in enumerate(b["grupos_activo"]):
        filas.append(("Activo", g["nombre"], g["saldo"]))
        colores[g["nombre"]] = azules[i % len(azules)]
    for i, g in enumerate(b["grupos_pasivo"]):
        filas.append(("Pasivo + patrimonio", g["nombre"], g["saldo"]))
        colores[g["nombre"]] = naranjas[i % len(naranjas)]
    if b["resultado"] >= 0:
        pat = b["grupos_patrimonio"] + [{"nombre": "Utilidad del año", "saldo": b["resultado"]}]
    else:  # la pérdida se descuenta del patrimonio para que las dos barras midan lo mismo
        pat = [{"nombre": "Patrimonio (después de la pérdida del año)", "saldo": b["patrimonio_total"]}]
    for i, g in enumerate(pat):
        filas.append(("Pasivo + patrimonio", g["nombre"], g["saldo"]))
        colores[g["nombre"]] = verdes[i % len(verdes)]
    df = pd.DataFrame(filas, columns=["lado", "grupo", "saldo"])
    orden = df["grupo"].tolist()
    fig = px.bar(df, x="saldo", y="lado", color="grupo", orientation="h", color_discrete_map=colores,
                 category_orders={"lado": ["Activo", "Pasivo + patrimonio"], "grupo": orden},
                 labels={"saldo": "", "lado": "", "grupo": ""})
    fig.update_traces(marker_line_color="#0A0B0D", marker_line_width=2,
                      hovertemplate="%{fullData.name}<br>$%{x:,.0f}<extra></extra>")
    fig.update_layout(barmode="relative", bargap=0.35)
    fig.update_xaxes(tickformat="~s", tickprefix="$")
    st.plotly_chart(_layout(fig, 320), width="stretch")
    st.markdown('<div class="gd-c">Azul: lo que tiene · naranja: lo que debe · verde: lo de los socios'
                + (f' (ya descontada la pérdida del año de {_p(-b["resultado"])})' if b["resultado"] < 0 else "")
                + '.</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    for col, titulo, grupos in ((c1, "Activos", b["grupos_activo"]),
                                (c2, "Pasivos y patrimonio", b["grupos_pasivo"] + b["grupos_patrimonio"])):
        with col:
            st.markdown(f'<div class="gd-h">{titulo}</div><div class="gd-c">Saldo al corte y cambio frente al mes '
                        'anterior.</div>', unsafe_allow_html=True)
            html = "".join(
                f'<tr><td>{escape(g["nombre"])}</td><td class="n">{_p(g["saldo"])}</td>'
                f'<td class="p" style="color:{"#8B8B93" if abs(g["saldo"] - g["anterior"]) < 1 else (VERDE if g["saldo"] > g["anterior"] else ROJO)}">'
                f'{"" if abs(g["saldo"] - g["anterior"]) < 1 else ("+" if g["saldo"] > g["anterior"] else "−") + _p(abs(g["saldo"] - g["anterior"]), True)}</td></tr>'
                for g in grupos)
            st.markdown(f'<table class="cd-pl">{html}</table>', unsafe_allow_html=True)


def _tab_caja(datos: dict, b: dict) -> None:
    f = ac.flujo_caja(datos.get("caja"), b["disponible"])
    c1, c2 = st.columns([1.4, 1])
    with c1:
        st.markdown('<div class="gd-h">Entradas, salidas y saldo</div><div class="gd-c">Todo lo que entró y salió de '
                    'cajas y bancos cada mes; la línea es el saldo al cierre.</div>', unsafe_allow_html=True)
        if f.empty:
            st.caption("El auxiliar no trae movimientos de caja y bancos (cuentas 11).")
        else:
            fig = go.Figure()
            fig.add_bar(x=f["mes"], y=f["entradas"], name="Entradas", marker_color=SERIES[2],
                        hovertemplate="%{x|%b %Y}<br>Entradas $%{y:,.0f}<extra></extra>")
            fig.add_bar(x=f["mes"], y=-f["salidas"], name="Salidas", marker_color=SERIES[1],
                        customdata=f["salidas"], hovertemplate="%{x|%b %Y}<br>Salidas $%{customdata:,.0f}<extra></extra>")
            fig.add_scatter(x=f["mes"], y=f["saldo"], name="Saldo al cierre", mode="lines+markers",
                            line=dict(color="#E8E8EA", width=2), marker=dict(size=8),
                            hovertemplate="%{x|%b %Y}<br>Saldo $%{y:,.0f}<extra></extra>")
            fig.update_layout(barmode="relative", bargap=0.3)
            fig.update_xaxes(tickformat="%b %y", dtick="M1")
            fig.update_yaxes(tickformat="~s", tickprefix="$")
            st.plotly_chart(_layout(fig, 360), width="stretch")
            st.markdown(f'<div class="gd-c">Saldo al empezar el año: <b style="color:#fff">{_p(f.attrs.get("inicial"))}</b>'
                        f' · entró {_p(f["entradas"].sum(), True)} · salió {_p(f["salidas"].sum(), True)}</div>',
                        unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="gd-h">¿Dónde está la plata?</div><div class="gd-c">Saldo de cada caja y cuenta al '
                    'corte.</div>', unsafe_allow_html=True)
        cu = pd.DataFrame(ac.cuentas_disponible(datos["prueba"]))
        if not cu.empty:
            cu = cu.sort_values("saldo")
            fig = px.bar(cu, x="saldo", y="nombre", orientation="h", color="grupo",
                         color_discrete_sequence=SERIES, labels={"saldo": "", "nombre": "", "grupo": ""})
            fig.update_traces(hovertemplate="%{y}<br>$%{x:,.0f}<extra></extra>")
            fig.update_xaxes(tickformat="~s", tickprefix="$")
            st.plotly_chart(_layout(fig, 360), width="stretch")
    ent, sal = ac.mayores_movimientos_caja(datos.get("caja"))
    if not ent.empty:
        c1, c2 = st.columns(2)
        for col, titulo, df, campo in ((c1, "Quién trajo más plata", ent, "entradas"),
                                       (c2, "A quién se le pagó más", sal, "salidas")):
            with col:
                st.markdown(f'<div class="gd-h">{titulo}</div>', unsafe_allow_html=True)
                html = "".join(f'<tr><td>{escape(str(r["tercero"]) or "Sin tercero")[:42]}</td>'
                               f'<td>{_p(r[campo])}</td></tr>' for _, r in df.iterrows())
                st.markdown(f'<table class="cd-pl">{html}</table>', unsafe_allow_html=True)


def _tab_cartera(datos: dict, b: dict, corte) -> None:
    fuente = str(datos.get("fuente"))
    st.markdown('<div class="gd-c">Facturas del año sin pago registrado, por antigüedad al corte. Los proveedores se '
                'cruzan por número de factura; en clientes los pagos sin número se aplican a las facturas más '
                'antiguas. Haga clic en una barra para ver solo esas facturas.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    for col, titulo, cuentas, deuda, saldo, k in (
            (c1, "Clientes · nos deben", ("1305",), False, b["clientes"], "cli"),
            (c2, "Proveedores · les debemos", ("2205",), True, b["proveedores"], "pro")):
        with col:
            ab = _abiertas(datos, fuente, cuentas, deuda, corte)
            total = float(ab["valor"].sum()) if not ab.empty else 0.0
            st.markdown(f'<div class="gd-h">{titulo}</div><div class="gd-c">Saldo contable <b style="color:#fff">'
                        f'{_p(saldo)}</b> · facturas identificadas {_p(total)} '
                        f'({total / saldo * 100 if saldo else 0:.0f}%)</div>', unsafe_allow_html=True)
            if ab.empty:
                st.caption("Sin facturas abiertas en el auxiliar.")
                continue
            ed = ab.groupby("edad", observed=False)["valor"].sum().reset_index()
            ed["edad"] = ed["edad"].astype(str)
            colores = [SERIES[2], SERIES[0], SERIES[3], SERIES[1], ROJO]
            fig = go.Figure(go.Bar(x=ed["edad"], y=ed["valor"], marker_color=colores[:len(ed)],
                                   hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>"))
            fig.update_yaxes(tickformat="~s", tickprefix="$")
            ev = st.plotly_chart(_layout(fig, 260, False), width="stretch", on_select="rerun",
                                 selection_mode="points", key=f"cd_edad_{k}")
            sel = [p["x"] for p in (ev.selection.points if ev and ev.selection else [])]
            vista = ab[ab["edad"].astype(str).isin(sel)] if sel else ab
            top = vista.groupby("tercero")["valor"].sum().sort_values(ascending=False).head(10)
            html = "".join(f'<tr><td>{escape(n)[:40]}</td><td>{_p(v)}</td></tr>' for n, v in top.items())
            st.markdown(f'<div class="gd-c" style="margin-top:4px">{"Solo " + ", ".join(sel) if sel else "Top 10"}'
                        f'</div><table class="cd-pl">{html}</table>', unsafe_allow_html=True)
            with st.expander(f"Ver las {len(vista)} facturas"):
                st.dataframe(vista[["tercero", "fecha", "factura", "valor", "dias"]].rename(columns={
                    "tercero": "Tercero", "fecha": "Fecha", "factura": "Factura", "valor": "Valor", "dias": "Días"}),
                    hide_index=True, width="stretch",
                    column_config={"Valor": st.column_config.NumberColumn(format="$%,.0f"),
                                   "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY")})
