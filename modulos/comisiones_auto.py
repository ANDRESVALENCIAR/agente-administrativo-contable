"""Liquidación automática de comisiones VIA × Contabilidad.

Cada mes llegan por correo dos archivos (RECAUDO_VIA_<MES>_<AÑO>.xlsx y RECAUDO_CONTABILIDAD_<MES>_<AÑO>.xlsx)
y luego un correo que dice «liquidar comisiones». Shaki:
  1. guarda los adjuntos en data/comisiones/entrada/<periodo>/  (también sirve dejarlos ahí a mano),
  2. al recibir «liquidar comisiones» carga el de VIA en «Cargar Comisión VIA» y el de contabilidad en
     «Cargar Comisiones Contabilidad», cruza por SFE y guarda el cruce en el histórico mensual,
  3. avisa por correo «Ya liquidé las comisiones de <mes>» con el resumen por asesor.
Si el mismo par de archivos ya se liquidó, no lo repite."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Any

from config import cfg
from database import get_conn, registrar_accion

logger = logging.getLogger(__name__)

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
R_LIQUIDAR = re.compile(r"liquid(ar|e|en|ación|acion)\w*\s+(las\s+|de\s+)?comisi[oó]n", re.I)
R_VIA = re.compile(r"recaudo[\s_-]*via|\bvia\b", re.I)
R_CONT = re.compile(r"contab|conta\b", re.I)


def carpeta_entrada() -> Path:
    p = Path(cfg.COMISIONES_ENTRADA) if cfg.COMISIONES_ENTRADA else (
        Path(__file__).resolve().parent.parent / "data" / "comisiones" / "entrada")
    p.mkdir(parents=True, exist_ok=True)
    return p


def inicializar() -> None:
    conn = get_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS comisiones_liquidacion_auto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        periodo TEXT NOT NULL,
        huella TEXT NOT NULL UNIQUE,
        archivo_via TEXT, archivo_cont TEXT,
        fecha TIMESTAMP DEFAULT (datetime('now','localtime')),
        origen TEXT,
        resumen_json TEXT,
        aviso TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS comisiones_orden_pendiente (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TIMESTAMP DEFAULT (datetime('now','localtime')),
        remitente TEXT, asunto TEXT, message_id TEXT UNIQUE, atendida INTEGER DEFAULT 0)""")
    conn.commit()
    conn.close()


# ───────────────────────── Identificar archivos y periodo ─────────────────────────

def tipo_archivo(nombre: str) -> str | None:
    """'via', 'cont' o None según el nombre del archivo."""
    n = Path(nombre).stem.replace("_", " ")
    if not nombre.lower().endswith((".xlsx", ".xlsm", ".xls")):
        return None
    if R_CONT.search(n):
        return "cont"
    if R_VIA.search(n):
        return "via"
    return None


def periodo_de(texto: str, ref: date | None = None) -> str | None:
    """'RECAUDO_VIA_SEPTIEMBRE_2026' → '2026-09'. Sin año usa el del correo (o el mes anterior en enero)."""
    t = texto.lower().replace("_", " ")
    for i, m in enumerate(MESES, 1):
        if re.search(rf"\b({m}|{m[:3]})\b", t) or (m == "septiembre" and re.search(r"\bsetiembre\b", t)):
            y = re.search(r"\b(20\d{2})\b", t)
            ref = ref or date.today()
            anio = int(y.group(1)) if y else (ref.year - 1 if i > ref.month else ref.year)
            return f"{anio}-{i:02d}"
    return None


def nombre_periodo(periodo: str) -> str:
    a, m = periodo.split("-")
    return f"{MESES[int(m) - 1]} {a}"


def es_orden_liquidar(asunto: str, cuerpo: str = "") -> bool:
    return bool(R_LIQUIDAR.search(asunto or "") or R_LIQUIDAR.search((cuerpo or "")[:600]))


def remitente_autorizado(remitente: str) -> bool:
    """Solo personas de la empresa (dominios de los buzones conectados) o las listadas en COMISIONES_REMITENTES."""
    rem = (remitente or "").lower().strip()
    lista = {e.strip().lower() for e in (cfg.COMISIONES_REMITENTES or "").replace(";", ",").split(",") if e.strip()}
    if rem in lista:
        return True
    publicos = {"gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "live.com", "icloud.com", "hotmail.es",
                "yahoo.es", "outlook.es", "msn.com", "protonmail.com", "proton.me"}
    dominios: set[str] = set()
    try:
        from modulos import buzones
        for b in buzones.listar_buzones():
            correo = b["email"].lower()
            if correo == rem:
                return True
            if correo.split("@")[-1] not in publicos:
                dominios.add(correo.split("@")[-1])
    except Exception:
        pass
    dominios |= {d.strip().lower() for d in (cfg.COMISIONES_DOMINIOS or "").split(",") if d.strip()}
    return "@" in rem and rem.split("@")[-1] in dominios


# ───────────────────────── Recibir (correo o carpeta) ─────────────────────────

def guardar_adjunto(nombre: str, contenido: bytes, ref: date | None = None) -> Path | None:
    """Guarda un adjunto RECAUDO_* en la carpeta de entrada del periodo. Devuelve la ruta o None si no aplica."""
    if not tipo_archivo(nombre) or not contenido:
        return None
    periodo = periodo_de(nombre, ref) or "sin_periodo"
    destino = carpeta_entrada() / periodo
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / Path(nombre).name
    if ruta.exists() and ruta.read_bytes() != contenido:
        ruta = destino / f"{ruta.stem}_{hashlib.md5(contenido).hexdigest()[:6]}{ruta.suffix}"
    ruta.write_bytes(contenido)
    return ruta


def registrar_orden(remitente: str, asunto: str, message_id: str) -> None:
    inicializar()
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO comisiones_orden_pendiente (remitente, asunto, message_id) VALUES (?,?,?)",
                 (remitente.lower(), asunto[:300], (message_id or f"{remitente}-{asunto}").strip()))
    conn.commit()
    conn.close()


def pares_disponibles() -> dict[str, dict[str, Path]]:
    """{periodo: {'via': ruta, 'cont': ruta}} con el archivo más reciente de cada tipo."""
    pares: dict[str, dict[str, Path]] = {}
    base = carpeta_entrada()
    for f in sorted(base.rglob("*"), key=lambda p: p.stat().st_mtime if p.is_file() else 0):
        if not f.is_file() or "procesados" in f.parts:
            continue
        t = tipo_archivo(f.name)
        if not t:
            continue
        periodo = periodo_de(f.name) or (f.parent.name if re.match(r"\d{4}-\d{2}$", f.parent.name) else None)
        if periodo:
            pares.setdefault(periodo, {})[t] = f
    return pares


# ───────────────────────── Liquidar ─────────────────────────

def _huella(*rutas: Path) -> str:
    h = hashlib.sha256()
    for r in rutas:
        h.update(r.read_bytes())
    return h.hexdigest()


def ya_liquidado(huella: str) -> dict | None:
    inicializar()
    conn = get_conn()
    fila = conn.execute("SELECT periodo, fecha FROM comisiones_liquidacion_auto WHERE huella=?", (huella,)).fetchone()
    conn.close()
    return {"periodo": fila[0], "fecha": fila[1]} if fila else None


def _num(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def resumen_cruce(via: dict, cont: dict, cross: dict) -> dict[str, Any]:
    """Totales sin duplicar: lo recaudado sale de contabilidad (una vez por recibo), agrupado por vendedor."""
    recibos: dict[str, dict] = {}
    for r in cont["clean_rows"]:
        clave = f"{r.get('Doc Num')}|{r.get('_SFE_KEY')}|{r.get('Saldo')}"
        recibos.setdefault(clave, r)
    sfe_via = {r["_SFE_KEY"] for r in via["clean_rows"]}
    por_vendedor: dict[str, dict[str, float]] = {}
    for r in recibos.values():
        v = str(r.get("Vendedor") or "Sin vendedor").strip().title()
        d = por_vendedor.setdefault(v, {"recibos": 0, "recaudo": 0.0, "cruzado": 0.0, "sin_cruce": 0.0})
        d["recibos"] += 1
        d["recaudo"] += _num(r.get("Saldo"))
        if r.get("_SFE_KEY") and r["_SFE_KEY"] in sfe_via:
            d["cruzado"] += _num(r.get("Saldo"))
        else:
            d["sin_cruce"] += _num(r.get("Saldo"))
    asesores = sorted(({"vendedor": k, **v} for k, v in por_vendedor.items()), key=lambda x: -x["recaudo"])
    return {
        "recaudo_total": sum(a["recaudo"] for a in asesores),
        "recaudo_cruzado": sum(a["cruzado"] for a in asesores),
        "recibos": len(recibos),
        "sfe_via": len(sfe_via),
        "abono_via": via["sum_abono"],
        "coincidencias": len({r["SFE"] for r in cross["both"]}),
        "solo_via": len({r["SFE"] for r in cross["onlyVia"]}),
        "solo_cont": len(cross["onlyCont"]),
        "sin_sfe": len(cross["noSfe"]),
        "asesores": asesores,
    }


def liquidar(ruta_via: Path, ruta_cont: Path, periodo: str, origen: str = "manual",
             forzar: bool = False, avisar: bool = True, destinos_extra: list[str] | None = None) -> dict[str, Any]:
    """Carga VIA y Contabilidad en el comparador, cruza por SFE, guarda en el histórico y avisa."""
    import modulos.comparador_comisiones as cmp

    inicializar()
    huella = _huella(ruta_via, ruta_cont)
    previo = ya_liquidado(huella)
    if previo and not forzar:
        _archivar(ruta_via, ruta_cont, previo["periodo"])
        return {"estado": "repetido", "periodo": previo["periodo"], "fecha": previo["fecha"],
                "mensaje": f"Las comisiones de {nombre_periodo(previo['periodo'])} con estos mismos archivos ya "
                           f"estaban liquidadas ({str(previo['fecha'])[:16]}). No las repetí."}

    via = cmp.process_via(str(ruta_via))         # 01 · Cargar Comisión VIA
    cont = cmp.process_cont(str(ruta_cont))      # 02 · Cargar Comisiones Contabilidad
    cross = cmp.cruzar(via, cont)                # 03 · Cruce por SFE
    titulo = f"Comisiones {nombre_periodo(periodo).capitalize()} – liquidación automática"
    guardado = cmp.guardar_cruce(titulo, via, cont, cross, periodo)
    res = resumen_cruce(via, cont, cross)

    mensaje = (f"Ya liquidé las comisiones de {nombre_periodo(periodo)}: recaudo de {_pesos(res['recaudo_total'])} en "
               f"{res['recibos']} recibos de {len(res['asesores'])} asesores; {res['coincidencias']} facturas (SFE) "
               f"cruzan entre VIA y contabilidad, {res['solo_via']} están solo en VIA y {res['sin_sfe']} recibo(s) "
               f"no traen SFE.")
    aviso = enviar_aviso(periodo, res, guardado, destinos_extra) if avisar else "sin aviso"

    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO comisiones_liquidacion_auto (periodo, huella, archivo_via, archivo_cont, "
                 "origen, resumen_json, aviso) VALUES (?,?,?,?,?,?,?)",
                 (periodo, huella, str(ruta_via), str(ruta_cont), origen,
                  json.dumps({**res, "ruta_excel": guardado["ruta_excel"]}, ensure_ascii=False, default=str), aviso))
    conn.execute("UPDATE comisiones_orden_pendiente SET atendida=1 WHERE atendida=0")
    conn.commit()
    conn.close()
    registrar_accion("comisiones", "liquidacion_automatica", mensaje[:480], "EXITOSO")

    _archivar(ruta_via, ruta_cont, periodo)
    return {"estado": "liquidado", "periodo": periodo, "mensaje": mensaje, "resumen": res,
            "ruta_excel": guardado["ruta_excel"], "aviso": aviso}


def _pesos(v: float) -> str:
    return "$" + f"{v:,.0f}".replace(",", ".")


def _archivar(ruta_via: Path, ruta_cont: Path, periodo: str) -> None:
    """Los archivos ya usados pasan a entrada/procesados/<periodo> (si estaban en la carpeta de entrada)."""
    entrada = carpeta_entrada().resolve()
    destino = entrada / "procesados" / periodo
    destino.mkdir(parents=True, exist_ok=True)
    for r in (ruta_via, ruta_cont):
        r = r.resolve()
        if entrada in r.parents and "procesados" not in r.parts:
            try:
                shutil.move(str(r), str(destino / r.name))
            except Exception as e:
                logger.warning("No se pudo mover %s: %s", r, e)


def _destinos(extra: list[str] | None = None) -> list[str]:
    base = cfg.COMISIONES_AVISO_EMAILS or cfg.PAGOS_ALERTA_EMAILS or cfg.EMAIL_GERENCIA or ""
    lista = [e.strip() for e in base.replace(";", ",").split(",") if e.strip()]
    for e in extra or []:
        if e and e.lower() not in {x.lower() for x in lista}:
            lista.append(e)
    return lista


def html_aviso(periodo: str, res: dict[str, Any]) -> str:
    td = "padding:6px 10px;border-bottom:1px solid #eee"
    filas = "".join(
        f"<tr><td style='{td}'>{escape(a['vendedor'])}</td><td style='{td};text-align:right'>{a['recibos']}</td>"
        f"<td style='{td};text-align:right'>{_pesos(a['recaudo'])}</td></tr>" for a in res["asesores"])
    return (
        "<div style='font-family:Arial,sans-serif;color:#111;max-width:640px'>"
        f"<h2 style='margin:0 0 6px'>Ya liquidé las comisiones de {nombre_periodo(periodo)}</h2>"
        "<p style='color:#444'>Cargué el archivo de VIA en «Cargar Comisión VIA» y el de contabilidad en «Cargar "
        "Comisiones Contabilidad», los crucé por SFE y guardé el resultado en Shaki → Comisiones → Histórico mensual.</p>"
        f"<p><b>Recaudo del mes:</b> {_pesos(res['recaudo_total'])} · {res['recibos']} recibos<br>"
        f"<b>Facturas que cruzan:</b> {res['coincidencias']} · <b>Solo en VIA:</b> {res['solo_via']} · "
        f"<b>Recibos sin SFE:</b> {res['sin_sfe']}</p>"
        "<table style='border-collapse:collapse;width:100%;font-size:14px'><tr style='background:#f4f4f5'>"
        "<th style='padding:6px 10px;text-align:left'>Asesor</th><th style='padding:6px 10px;text-align:right'>Recibos</th>"
        "<th style='padding:6px 10px;text-align:right'>Recaudo</th></tr>" + filas + "</table>"
        "<p style='color:#888;font-size:12px;margin-top:16px'>Aviso automático de Shaki · EIF SAS. El informe Excel "
        "completo queda en Comisiones → Histórico mensual.</p></div>")


def enviar_aviso(periodo: str, res: dict[str, Any], guardado: dict, extra: list[str] | None = None) -> str:
    from conexiones.notificador import enviar_email

    destinos = _destinos(extra)
    if not destinos:
        return "sin destinatarios (configure COMISIONES_AVISO_EMAILS)"
    asunto = f"Comisiones de {nombre_periodo(periodo)} liquidadas · Shaki"
    html = html_aviso(periodo, res)
    enviados = [d for d in destinos if enviar_email(d, asunto, html)]
    return f"enviado a {', '.join(enviados)}" if enviados else "no se pudo enviar el correo"


def procesar_pendientes(solo_con_orden: bool = True) -> list[dict[str, Any]]:
    """Liquida los pares completos de la carpeta de entrada. Por correo, solo si llegó la orden «liquidar comisiones»."""
    inicializar()
    conn = get_conn()
    ordenes = conn.execute("SELECT remitente FROM comisiones_orden_pendiente WHERE atendida=0").fetchall()
    conn.close()
    if solo_con_orden and not ordenes:
        return []
    extra = sorted({o[0] for o in ordenes if remitente_autorizado(o[0])})
    resultados = []
    pares = pares_disponibles()
    completos = {p: d for p, d in pares.items() if "via" in d and "cont" in d}
    for periodo, d in sorted(completos.items()):
        try:
            resultados.append(liquidar(d["via"], d["cont"], periodo, origen="correo" if ordenes else "carpeta",
                                       destinos_extra=extra))
        except Exception as e:
            logger.exception("Liquidación automática %s", periodo)
            registrar_accion("comisiones", "liquidacion_automatica", f"Falló {periodo}", "ERROR", str(e))
            resultados.append({"estado": "error", "periodo": periodo, "mensaje": f"No pude liquidar {periodo}: {e}"})
    if ordenes and not completos:
        faltan = {p: [t for t in ("via", "cont") if t not in d] for p, d in pares.items()}
        txt = "; ".join(f"{nombre_periodo(p) if p != 'sin_periodo' else 'sin mes'}: falta "
                        f"{' y '.join('el de VIA' if t == 'via' else 'el de contabilidad' for t in f)}"
                        for p, f in faltan.items()) or "no ha llegado ningún archivo RECAUDO_VIA ni RECAUDO_CONTABILIDAD"
        resultados.append({"estado": "faltan_archivos", "mensaje": f"Recibí la orden de liquidar comisiones pero {txt}."})
    return resultados


def ultimas(n: int = 6) -> list[dict[str, Any]]:
    inicializar()
    conn = get_conn()
    filas = conn.execute("SELECT periodo, fecha, origen, resumen_json, aviso FROM comisiones_liquidacion_auto "
                         "ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    conn.close()
    return [{"periodo": f[0], "fecha": f[1], "origen": f[2], "resumen": json.loads(f[3] or "{}"), "aviso": f[4]}
            for f in filas]
