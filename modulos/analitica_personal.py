"""
Analítica de personal — junta y limpia lo que ya hay en Shaki:
empleados_fenix (planilla y retirados), contratos_fijos_fenix, contratos_activos, vacaciones_fenix,
cumpleanos_fenix, novedades_fenix, empleados_carpetas / documentos_empleado (expedientes).

Los datos importados vienen con columnas corridas en algunas filas (p. ej. «COMPENSAR» en ciudad o
un término en la fecha de ingreso): aquí se validan y lo que no cuadra queda como «Sin dato».
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any

import pandas as pd
from dateutil.relativedelta import relativedelta

from database import get_conn

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
         "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
NO_CIUDAD = ("COMPENSAR", "COMFAMA", "COMFANDI", "COMFENALCO", "CAFAM", "COLSUBSIDIO", "EPS", "SURA", "SANITAS")


def _n(t: Any) -> str:
    s = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", s).strip()


def _q(sql: str) -> pd.DataFrame:
    conn = get_conn()
    try:
        return pd.read_sql(sql, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


def _ok(v: Any) -> bool:
    return v is not None and not (isinstance(v, float) and pd.isna(v)) and not (v is pd.NaT) and not \
        (hasattr(v, "year") and pd.isna(v))


def _fecha(v: Any) -> pd.Timestamp | None:
    if v in (None, "", "NaT") or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if re.fullmatch(r"\d{5}(\.0)?", s):  # número de serie de Excel
        return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(float(s)))
    if not re.search(r"\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2}", s):
        return None
    t = pd.to_datetime(s, errors="coerce", dayfirst=not re.match(r"\d{4}-", s))
    if pd.isna(t) or not (1940 <= t.year <= 2100):
        return None
    return t


def _retiro(obs: Any) -> pd.Timestamp | None:
    t = _n(obs).lower()
    m = re.search(r"(\d{1,2})\s*(?:de\s*)?([a-z]+)\s*(?:de\s*|del\s*)?(\d{4})", t)
    if m and m.group(2) in MESES:
        try:
            return pd.Timestamp(int(m.group(3)), MESES[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
    m = re.search(r"(\d{4}-\d{2}-\d{2})|(\d{1,2}/\d{1,2}/\d{4})", t)
    return _fecha(m.group(0)) if m else None


def _mes(v: Any) -> int | None:
    s = _n(v).lower().replace(".0", "")
    if s.isdigit() and 1 <= int(s) <= 12:
        return int(s)
    return next((n for k, n in MESES.items() if s[:3] and k.startswith(s[:3])), None)


def _dinero(v: Any) -> float | None:
    s = re.sub(r"[^\d]", "", str(v or ""))
    if len(s) < 6 or len(s) > 9:
        return None
    return float(s)


def _texto(v: Any, invalidos: tuple[str, ...] = ()) -> str:
    s = _n(v)
    if not s or s in ("NAN", "NONE", "NAT") or re.fullmatch(r"[\d .,/-]+", s) or any(x in s for x in invalidos):
        return "Sin dato"
    return s.title()


def _termino_meses(t: Any) -> int | None:
    s = _n(t)
    if "INDEFINID" in s:
        return None
    m = re.search(r"(\d+)\s*(MES|ANO)", s)
    if m:
        n = int(m.group(1))
        return n * 12 if m.group(2) == "ANO" else n
    if "UN ANO" in s or "1 ANO" in s:
        return 12
    return None


def proximo_vencimiento(inicio: pd.Timestamp | None, venc: pd.Timestamp | None, meses: int | None,
                        hoy: date | None = None) -> pd.Timestamp | None:
    """Los contratos a término fijo se renuevan solos: lleva el vencimiento al próximo futuro."""
    hoy_ts = pd.Timestamp(hoy or date.today())
    meses = None if meses is None or pd.isna(meses) else int(meses)
    venc = venc if _ok(venc) else None
    inicio = inicio if _ok(inicio) else None
    if venc is None:
        if inicio is None or not meses:
            return None
        venc = inicio + relativedelta(months=meses) - pd.Timedelta(days=1)
    if not meses:
        return venc if venc >= hoy_ts else None
    paso = max(meses, 12) if meses < 12 else meses  # tras 3 renovaciones cortas la ley lleva el plazo a 1 año
    n = 0
    while venc < hoy_ts and n < 60:
        un_dia = pd.Timedelta(days=1)
        venc = (venc + un_dia) + relativedelta(months=meses if n < 3 else paso) - un_dia
        n += 1
    return venc


def cargar(hoy: date | None = None) -> dict[str, Any]:
    hoy = hoy or date.today()
    hoy_ts = pd.Timestamp(hoy)
    emp = _q("SELECT * FROM empleados_fenix")
    out: dict[str, Any] = {"hoy": hoy}
    if not emp.empty:
        emp["nombre"] = emp["nombre_completo"].map(lambda x: _n(x).title())
        emp["activo"] = emp["activo"].astype(str).isin(["1", "True", "true"])
        emp["vinculo"] = emp["tipo_plantilla"].map({"nomina_activo": "Nómina", "prestacion_servicios": "Prestación de servicios",
                                                    "retirado": "Retirado"}).fillna("Sin dato")
        emp["ingreso"] = emp["fecha_ingreso"].map(_fecha)
        emp["nacimiento"] = emp["fecha_nacimiento"].map(_fecha)
        emp["retiro"] = emp["observaciones"].map(_retiro)
        emp["area"] = emp["departamento"].map(_texto)
        emp["cargo_n"] = emp["cargo"].map(_texto)
        emp["ciudad_n"] = emp["ciudad"].map(lambda v: _texto(v, NO_CIUDAD))
        emp["eps"] = emp["salud"].map(_texto)
        emp["caja"] = emp["caja_compensacion"].map(lambda v: _texto(v, ("HERMAN", "MAMA", "PAPA", "ESPOS", "HIJ")))
        emp["contrato"] = emp["tipo_contrato"].map(_texto)
        emp["salario"] = emp["salario_ibc"].map(_dinero)
        fin = emp["retiro"].where(~emp["activo"], hoy_ts)
        emp["antiguedad"] = [((f - i).days / 365.25) if _ok(i) and _ok(f) else None for i, f in zip(emp["ingreso"], fin)]
        emp["edad"] = [((hoy_ts - n).days / 365.25) if _ok(n) else None for n in emp["nacimiento"]]
        out["empleados"] = emp
    # vacaciones (puede haber dos hojas por persona: se toma el mayor saldo)
    vac = _q("SELECT nombre_completo, hoja_origen, dias_pendientes, dias_tomar, fecha_regreso FROM vacaciones_fenix")
    if not vac.empty:
        vac["nombre"] = vac["nombre_completo"].map(lambda x: _n(x).title())
        vac["dias"] = pd.to_numeric(vac["dias_pendientes"], errors="coerce")
        vac = vac.dropna(subset=["dias"]).sort_values("dias", ascending=False).drop_duplicates("nombre")
        out["vacaciones"] = vac[["nombre", "dias", "hoja_origen"]]
    # contratos a término fijo → próximo vencimiento y preaviso (30 días antes)
    cf = _q("SELECT nombre_completo, cargo, fecha_inicio, termino, vencimiento_contrato FROM contratos_fijos_fenix")
    if not cf.empty:
        cf["nombre"] = cf["nombre_completo"].map(lambda x: _n(x).title())
        cf["meses"] = cf["termino"].map(_termino_meses)
        cf["prox"] = [proximo_vencimiento(_fecha(i), _fecha(v), m, hoy)
                      for i, v, m in zip(cf["fecha_inicio"], cf["vencimiento_contrato"], cf["meses"])]
        cf["preaviso"] = [d - pd.Timedelta(days=30) if _ok(d) else None for d in cf["prox"]]
        if "empleados" in out:
            activos = set(out["empleados"].loc[out["empleados"]["activo"], "nombre"])
            cf = cf[cf["nombre"].isin(activos) | ~cf["nombre"].isin(set(out["empleados"]["nombre"]))]
        out["contratos"] = cf.dropna(subset=["prox"]).sort_values("prox")
    # cumpleaños (tabla propia o fecha de nacimiento de activos)
    cum = _q("SELECT nombre, dia, mes FROM cumpleanos_fenix")
    filas = []
    for _, r in cum.iterrows():
        try:
            d = int(float(r["dia"]))
            m = _mes(r["mes"])
            if m:
                filas.append({"nombre": _n(r["nombre"]).title(), "dia": d, "mes": m})
        except (TypeError, ValueError):
            continue
    if not filas and "empleados" in out:
        e = out["empleados"]
        filas = [{"nombre": n, "dia": f.day, "mes": f.month} for n, f, a in zip(e["nombre"], e["nacimiento"], e["activo"])
                 if _ok(f) and a]
    out["cumpleanos"] = pd.DataFrame(filas)
    # exámenes periódicos y dotación pendiente
    nov = _q("SELECT nombre_completo, pendiente_dotacion, examenes_periodicos FROM novedades_fenix")
    if not nov.empty:
        nov["nombre"] = nov["nombre_completo"].map(lambda x: _n(x).title())
        nov["examen"] = nov["examenes_periodicos"].map(_fecha)
        nov["prox_examen"] = [d + relativedelta(years=1) if _ok(d) else None for d in nov["examen"]]
        nov["dotacion_pend"] = nov["pendiente_dotacion"].map(lambda v: _n(v) == "SI")
        out["novedades"] = nov[["nombre", "examen", "prox_examen", "dotacion_pend"]]
    # expedientes
    car = _q("SELECT nombre_display, total_documentos, docs_faltantes, completitud_pct, activo FROM empleados_carpetas")
    if not car.empty:
        car["nombre"] = car["nombre_display"].map(lambda x: _n(x).title())
        out["expedientes"] = car
    docs = _q("SELECT categoria, COUNT(*) n FROM documentos_empleado GROUP BY categoria")
    if not docs.empty:
        out["documentos"] = docs
    ca = _q("SELECT * FROM contratos_activos")
    if not ca.empty:
        flags = [c for c in ca.columns if c.startswith("doc_") and not c.endswith("_ruta")] + \
                [c for c in ("examen_medico", "epp", "sctr") if c in ca.columns]
        ca["nombre"] = ca["nombre_completo"].map(lambda x: _n(x).title())
        out["cumplimiento"] = ca[["nombre"] + flags]
    return out


def kpis(d: dict[str, Any]) -> dict[str, Any]:
    e = d.get("empleados")
    hoy_ts = pd.Timestamp(d["hoy"])
    k: dict[str, Any] = {}
    if e is not None and not e.empty:
        act = e[e["activo"]]
        k["activos"] = len(act)
        k["nomina"] = int((act["vinculo"] == "Nómina").sum())
        k["prestacion"] = int((act["vinculo"] == "Prestación de servicios").sum())
        k["retirados"] = int((~e["activo"]).sum())
        k["antiguedad"] = float(act["antiguedad"].dropna().mean()) if act["antiguedad"].notna().any() else None
        k["edad"] = float(act["edad"].dropna().mean()) if act["edad"].notna().any() else None
        ret12 = sum(1 for r in e["retiro"] if _ok(r) and r >= hoy_ts - pd.DateOffset(years=1))
        k["retiros_12m"] = int(ret12)
        k["rotacion"] = float(ret12 / max(len(act), 1))
        k["areas"] = int(act["area"].nunique())
        k["completitud_datos"] = float(act[["ingreso", "nacimiento", "area", "cargo_n", "eps"]]
                                       .apply(lambda c: c.map(lambda v: _ok(v) and v != "Sin dato")).mean().mean())
    v = d.get("vacaciones")
    if v is not None and not v.empty:
        k["vac_dias"] = float(v["dias"].sum())
        k["vac_15"] = int((v["dias"] >= 15).sum())
    c = d.get("contratos")
    if c is not None and not c.empty:
        k["venc_60"] = int((c["prox"] <= hoy_ts + pd.Timedelta(days=60)).sum())
    cu = d.get("cumpleanos")
    if cu is not None and not cu.empty:
        k["cumple_mes"] = int((cu["mes"] == hoy_ts.month).sum())
    ex = d.get("expedientes")
    if ex is not None and not ex.empty:
        k["expedientes"] = float(pd.to_numeric(ex["completitud_pct"], errors="coerce").mean())
    return k
