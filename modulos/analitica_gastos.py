"""
Analítica de gastos — a partir del libro del contador (Auxiliar + Balance de prueba).

Fuente: el Excel más reciente con hoja «Auxiliar» que haya en data/contabilidad/ (subido desde
Gastos) o en data/revisiones/ (el que se sube en Revisión de impuestos). Lee cuentas 4 (ingresos),
5 (gastos) y 6-7 (costos) con fecha, tercero, detalle y valor, y deja un caché para abrir rápido.
Nada de esto se sube a git (data/ está ignorado).
"""
from __future__ import annotations

import hashlib
import logging
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent.parent / "data"
CARPETA_SUBIDAS = RAIZ / "contabilidad"
CACHE = RAIZ / "analitica"

GRUPOS = {
    "51": "Gastos de administración",
    "52": "Gastos de ventas",
    "53": "Gastos no operacionales",
    "54": "Impuesto de renta",
    "61": "Costo de ventas",
    "62": "Compras",
    "71": "Costos de producción",
    "72": "Mano de obra directa",
    "73": "Costos indirectos",
    "74": "Contratos de servicios",
}


def libros_disponibles() -> list[Path]:
    rutas: list[Path] = []
    for base in (CARPETA_SUBIDAS, RAIZ / "revisiones"):
        if base.exists():
            rutas += [p for p in base.rglob("*") if p.suffix.lower() in (".xlsx", ".xlsm") and not p.name.startswith("~$")]
    return sorted(rutas, key=lambda p: p.stat().st_mtime, reverse=True)


def guardar_subida(nombre: str, contenido: bytes) -> Path:
    CARPETA_SUBIDAS.mkdir(parents=True, exist_ok=True)
    ruta = CARPETA_SUBIDAS / Path(nombre).name
    ruta.write_bytes(contenido)
    return ruta


def _clave(ruta: Path) -> str:
    st = ruta.stat()
    return hashlib.md5(f"v2|{ruta}|{st.st_mtime}|{st.st_size}".encode()).hexdigest()[:16]


def cargar(ruta: Path | None = None) -> dict[str, Any] | None:
    """Devuelve {"mov": DataFrame, "cuentas": {cuenta: nombre}, "fuente": ruta} o None si no hay libro."""
    candidatos = [ruta] if ruta else libros_disponibles()
    for r in candidatos:
        if r is None or not r.exists():
            continue
        CACHE.mkdir(parents=True, exist_ok=True)
        cache = CACHE / f"gastos_{_clave(r)}.pkl"
        if cache.exists():
            try:
                return pd.read_pickle(cache)
            except Exception:
                pass
        try:
            datos = _leer(r)
        except Exception as e:
            logger.warning("No se pudo leer %s: %s", r, e)
            continue
        if datos is None:
            continue
        pd.to_pickle(datos, cache)
        return datos
    return None


def _leer(ruta: Path) -> dict[str, Any] | None:
    from modulos.revision_lectores import Libro

    libro = Libro(ruta)
    try:
        if not libro.hoja("Auxiliar"):
            return None
        mov = pd.DataFrame(libro.auxiliar(("4", "5", "6", "7")))
        terc = pd.DataFrame(libro.auxiliar(("1305", "1330", "2205", "2335", "2380")))
        pr = libro.prueba()
    finally:
        libro.cerrar()
    if mov.empty:
        return None
    mov["fecha"] = pd.to_datetime(mov["fecha"], errors="coerce")
    mov = mov.dropna(subset=["fecha"])
    mov["cuenta"] = mov["cuenta"].astype(str)
    mov["clase"] = mov["cuenta"].str[0]
    mov["grupo"] = mov["cuenta"].str[:2]
    mov["cuenta4"] = mov["cuenta"].str[:4]
    mov["cuenta6"] = mov["cuenta"].str[:6]
    # ingresos (clase 4) se registran crédito (negativo): se voltean para que sumen positivo
    mov["monto"] = mov.apply(lambda r: -r["valor"] if r["clase"] == "4" else r["valor"], axis=1)
    mov["tercero"] = mov["nombre"].fillna("").astype(str).str.split(" Nit:").str[0].str.strip().replace("", "Sin tercero")
    mov["mes"] = mov["fecha"].dt.to_period("M").dt.to_timestamp()
    nombres = {k: str(v.get("nombre") or "").strip().title() for k, v in pr.items()}
    for g, n in GRUPOS.items():
        nombres.setdefault(g, n)
    mov["nombre_grupo"] = mov["grupo"].map(lambda g: GRUPOS.get(g, nombres.get(g, g)))
    mov["nombre_cuenta4"] = mov["cuenta4"].map(lambda c: nombres.get(c, c))
    mov["nombre_cuenta6"] = mov["cuenta6"].map(lambda c: nombres.get(c, c))
    if not terc.empty:
        terc["fecha"] = pd.to_datetime(terc["fecha"], errors="coerce")
        terc["tercero"] = terc["nombre"].fillna("").astype(str).str.split(" Nit:").str[0].str.strip()
        terc["cuenta4"] = terc["cuenta"].astype(str).str[:4]
        terc["nombre_cuenta4"] = terc["cuenta4"].map(lambda c: nombres.get(c, c))
    return {"terceros": terc, "mov": mov[["fecha", "mes", "cuenta", "cuenta4", "cuenta6", "clase", "grupo", "nombre_grupo",
                        "nombre_cuenta4", "nombre_cuenta6", "nit", "tercero", "detalle", "comprobante", "monto"]],
            "cuentas": nombres, "fuente": str(ruta), "leido": date.today().isoformat()}


# ───────────────────────── Medidas ─────────────────────────

def gastos(mov: pd.DataFrame, incluir_costos: bool = True) -> pd.DataFrame:
    clases = ("5", "6", "7") if incluir_costos else ("5",)
    return mov[mov["clase"].isin(clases)]


def mensual(mov: pd.DataFrame, incluir_costos: bool = True) -> pd.DataFrame:
    g = gastos(mov, incluir_costos).groupby("mes")["monto"].sum().rename("gastos")
    i = mov[mov["clase"] == "4"].groupby("mes")["monto"].sum().rename("ingresos")
    df = pd.concat([i, g], axis=1).fillna(0).sort_index()
    df["resultado"] = df["ingresos"] - df["gastos"]
    df["margen"] = (df["resultado"] / df["ingresos"].where(df["ingresos"] != 0)).fillna(0)
    return df


def kpis(mov: pd.DataFrame, incluir_costos: bool = True) -> dict[str, Any]:
    m = mensual(mov, incluir_costos)
    if m.empty:
        return {}
    ult = m.iloc[-1]
    ant = m.iloc[-2] if len(m) > 1 else None
    g = gastos(mov, incluir_costos)
    top_cta = g.groupby("nombre_cuenta4")["monto"].sum().sort_values(ascending=False)
    return {
        "gasto_total": float(m["gastos"].sum()), "ingreso_total": float(m["ingresos"].sum()),
        "resultado": float(m["resultado"].sum()), "meses": len(m),
        "promedio_mes": float(m["gastos"].mean()), "ultimo_mes": m.index[-1], "gasto_ultimo": float(ult["gastos"]),
        "var_mes": (float(ult["gastos"] / ant["gastos"] - 1) if ant is not None and ant["gastos"] else None),
        "pct_ingresos": float(m["gastos"].sum() / m["ingresos"].sum()) if m["ingresos"].sum() else None,
        "terceros": int(g["tercero"].nunique()), "movimientos": int(len(g)),
        "cuenta_mayor": top_cta.index[0] if len(top_cta) else "—",
        "cuenta_mayor_valor": float(top_cta.iloc[0]) if len(top_cta) else 0,
        "mes_mayor": m["gastos"].idxmax(), "mes_mayor_valor": float(m["gastos"].max()),
    }


def anomalias(mov: pd.DataFrame, incluir_costos: bool = True) -> pd.DataFrame:
    """Cuentas cuyo último mes se sale más de 50 % de su promedio de los meses anteriores."""
    g = gastos(mov, incluir_costos)
    p = g.pivot_table(index="nombre_cuenta4", columns="mes", values="monto", aggfunc="sum").fillna(0)
    if p.shape[1] < 3:
        return pd.DataFrame()
    ult = p.iloc[:, -1]
    prom = p.iloc[:, :-1].mean(axis=1)
    df = pd.DataFrame({"cuenta": p.index, "ultimo": ult.values, "promedio": prom.values})
    df["variacion"] = (df["ultimo"] / df["promedio"].where(df["promedio"] > 0) - 1)
    df = df[(df["promedio"] > 500_000) & (df["ultimo"] > 0) & (df["variacion"].abs() > 0.5)]
    return df.sort_values("variacion", key=abs, ascending=False)
