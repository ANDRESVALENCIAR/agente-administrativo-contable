"""
Asistente de Shaki — responde preguntas con los DATOS REALES del agente.

Herramientas (consultas de solo lectura sobre los módulos nuevos):
  hoy · pagos · impuestos · alertas · correos · revision · agenda · cartera · buscar

Dos motores:
  1. Con ANTHROPIC_API_KEY: Claude decide qué herramientas usar (tool use) y redacta la respuesta.
  2. Sin clave (modo local): un intérprete en español reconoce la pregunta (tema + fecha) y arma la
     respuesta directamente con las mismas herramientas. Nunca inventa cifras.
"""
from __future__ import annotations

import calendar
import difflib
import json
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any, Callable

from config import cfg

logger = logging.getLogger(__name__)

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _n(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t).strip()


def _p(v: Any) -> str:
    try:
        return "$" + f"{float(v):,.0f}".replace(",", ".") if v not in (None, "") else ""
    except (TypeError, ValueError):
        return ""


def _f(d: date | str | None) -> str:
    if not d:
        return "—"
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d[:10])
        except ValueError:
            return d
    hoy = date.today()
    rel = {0: "hoy", 1: "mañana", -1: "ayer"}.get((d - hoy).days)
    base = f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"
    return f"{base} ({rel})" if rel else base


# ───────────────────────── Rango de fechas en lenguaje natural ─────────────────────────

def rango(texto: str, hoy: date | None = None, defecto: int = 7) -> tuple[date, date, str]:
    t = _n(texto)
    hoy = hoy or date.today()
    if "pasado manana" in t:
        d = hoy + timedelta(days=2)
        return d, d, "pasado mañana"
    if "manana" in t:
        d = hoy + timedelta(days=1)
        return d, d, "mañana"
    if re.search(r"\bhoy\b", t):
        return hoy, hoy, "hoy"
    if "ayer" in t:
        d = hoy - timedelta(days=1)
        return d, d, "ayer"
    if "proxima semana" in t or "semana que viene" in t or "siguiente semana" in t:
        ini = hoy + timedelta(days=7 - hoy.weekday())
        return ini, ini + timedelta(days=6), "la próxima semana"
    if "semana" in t:
        if hoy.weekday() >= 5:  # fin de semana: "esta semana" = la que empieza el lunes
            ini = hoy + timedelta(days=7 - hoy.weekday())
            return hoy, ini + timedelta(days=6), "esta semana (hasta el domingo " + str((ini + timedelta(days=6)).day) + ")"
        return hoy, hoy - timedelta(days=hoy.weekday()) + timedelta(days=6), "esta semana"
    if "proximo mes" in t or "mes que viene" in t:
        a, m = (hoy.year + (hoy.month == 12), hoy.month % 12 + 1)
        return date(a, m, 1), date(a, m, calendar.monthrange(a, m)[1]), f"{MESES[m - 1]}"
    if "este mes" in t or re.search(r"\bdel mes\b|\bel mes\b", t):
        return hoy.replace(day=1), hoy.replace(day=calendar.monthrange(hoy.year, hoy.month)[1]), "este mes"
    for i, m in enumerate(MESES):
        if re.search(rf"\b{m}\b", t):
            a = hoy.year if i + 1 >= hoy.month - 2 else hoy.year + 1
            return date(a, i + 1, 1), date(a, i + 1, calendar.monthrange(a, i + 1)[1]), m
    m = re.search(r"(\d{1,3})\s*dias", t)
    if m:
        return hoy, hoy + timedelta(days=int(m.group(1))), f"los próximos {m.group(1)} días"
    if "ano" in t or "año" in texto.lower():
        return hoy, date(hoy.year, 12, 31), "lo que queda del año"
    return hoy, hoy + timedelta(days=defecto), f"los próximos {defecto} días"


# ───────────────────────── Herramientas ─────────────────────────

def h_pagos(desde: str | None = None, hasta: str | None = None, solo_vencidos: bool = False,
            texto: str | None = None) -> dict[str, Any]:
    """Pagos del control de pagos (pendientes y pagados) en un rango; o solo los vencidos sin pagar."""
    from modulos import control_pagos as cp
    cp.inicializar_tablas()
    hoy = date.today()
    if solo_vencidos:
        filas = [p for p in cp.listar(hasta=hoy - timedelta(days=1), estados=("PENDIENTE", "EN PROCESO"))]
    else:
        d = date.fromisoformat(desde) if desde else hoy
        h = date.fromisoformat(hasta) if hasta else d + timedelta(days=7)
        filas = cp.listar(desde=d, hasta=h)
    if texto:
        q = _n(texto)
        filas = [p for p in filas if q in _n(f"{p['detalle']} {p['proveedor']} {p['tipo']}")]
    filas = [p for p in filas if p["estado"] != "ANULADO"]
    pend = [p for p in filas if p["estado"] in ("PENDIENTE", "EN PROCESO")]
    return {"total": len(filas), "pendientes": len(pend), "pagados": len(filas) - len(pend),
            "valor_pendiente": sum(p["valor"] or 0 for p in pend),
            "pagos": [{"id": p["id"], "fecha": p["fecha_sugerida"], "limite": p["fecha_limite"], "detalle": p["detalle"],
                       "proveedor": p["proveedor"], "valor": p["valor"], "estado": p["estado"]} for p in filas[:60]]}


def h_impuestos(desde: str | None = None, hasta: str | None = None, solo_pendientes: bool = True) -> dict[str, Any]:
    """Declaraciones DIAN y SHD Bogotá del radar tributario en un rango (por defecto 60 días)."""
    from modulos import radar_tributario as rt
    rt.inicializar_tablas()
    hoy = date.today()
    d = date.fromisoformat(desde) if desde else hoy - timedelta(days=60)
    h = date.fromisoformat(hasta) if hasta else hoy + timedelta(days=60)
    filas = rt.listar(desde=d, hasta=h, estados=("PENDIENTE",) if solo_pendientes else None)
    return {"obligaciones": [{"id": o["id"], "impuesto": o["impuesto"], "periodo": o["periodo"], "entidad": o["entidad"],
                              "formulario": o["formulario"], "vence": o["fecha_limite"], "estado": o["estado"]}
                             for o in filas]}


def h_alertas(nivel: str | None = None) -> dict[str, Any]:
    """Alertas abiertas del centro de alertas (CRITICO, URGENTE, AVISO, INFO)."""
    from modulos import motor_alertas as ma
    filas = ma.listar()
    if nivel:
        filas = [a for a in filas if a["nivel"] == nivel.upper()]
    return {"salud": ma.salud(ma.listar()), "alertas": [
        {"nivel": a["nivel"], "modulo": a["modulo"], "titulo": a["titulo"], "detalle": (a.get("descripcion") or "")[:300],
         "valor": a.get("valor")} for a in filas[:40]]}


def h_correos(categoria: str | None = None, solo_importantes: bool = True, dias: int = 15) -> dict[str, Any]:
    """Correos leídos de los buzones conectados (sin atender), por categoría."""
    from modulos import buzones as bz
    nv = bz.niveles()
    filas = bz.bandeja(estado="NUEVO", categoria=categoria.upper() if categoria else None, dias=dias)
    if solo_importantes and not categoria:
        filas = [c for c in filas if nv.get(c["categoria"]) in ("CRITICO", "URGENTE", "AVISO")]
    return {"buzones": [{"email": b["email"], "estado": b["estado"]} for b in bz.listar_buzones()],
            "correos": [{"fecha": str(c["fecha"])[:16], "buzon": c["buzon"], "de": c["remitente_nombre"] or c["remitente"],
                         "asunto": c["asunto"], "categoria": bz.CATEGORIAS.get(c["categoria"], {}).get("nombre", c["categoria"]),
                         "nivel": nv.get(c["categoria"]), "resumen": (c["resumen"] or "")[:200], "datos": c["datos"]}
                        for c in filas[:40]]}


def h_revision(impuesto: str | None = None, periodo: str | None = None) -> dict[str, Any]:
    """Última revisión de impuestos (veredicto y hallazgos). impuesto: RET, IVA, ICA, RETEICA, RENTA…"""
    from modulos import revision_impuestos as ri
    filas = ri.listar(impuesto=impuesto.upper() if impuesto else None)
    if periodo:
        filas = [r for r in filas if r["periodo"] == periodo] or filas
    if not filas:
        return {"revision": None}
    r = ri.obtener(filas[0]["id"])
    res = r.get("resultado") or {}
    return {"revision": {"impuesto": ri.IMPUESTOS[r["impuesto"]]["nombre"], "periodo": ri.etiqueta_periodo(r["impuesto"], r["periodo"]),
                         "veredicto": r["veredicto"], "resumen": r["resumen"], "total_a_pagar": r["total_a_pagar"],
                         "hallazgos": [{k: h[k] for k in ("nivel", "titulo", "accion")} for h in res.get("hallazgos", [])
                                       if h["nivel"] != "INFO"][:12],
                         "ok": [v["titulo"] for v in res.get("verificaciones", [])][:12]}}


def h_agenda(desde: str | None = None, hasta: str | None = None) -> dict[str, Any]:
    """Todo lo que tiene fecha (pagos, impuestos, revisiones, personal, proveedores, festivos)."""
    from modulos import agenda_unificada as ag
    hoy = date.today()
    d = date.fromisoformat(desde) if desde else hoy
    h = date.fromisoformat(hasta) if hasta else hoy + timedelta(days=7)
    evs = [e for e in ag.eventos(d, h, incluir_hechos=False) if e["fuente"] != "AGENTE"]
    return {"eventos": [{"fecha": e["fecha"].isoformat(), "fuente": ag.FUENTES[e["fuente"]]["nombre"], "titulo": e["titulo"],
                         "detalle": e["sub"], "valor": e["valor"], "estado": e["nivel"]} for e in evs[:60]]}


def h_cartera() -> dict[str, Any]:
    """Clientes con cartera en mora."""
    from modulos.motor_alertas import _filas
    try:
        filas = _filas("SELECT cliente, nit, saldo, dias_mora FROM cartera_cxc WHERE dias_mora > 0 ORDER BY dias_mora DESC")
    except Exception:
        filas = []
    return {"clientes": filas[:30], "total": sum(f["saldo"] or 0 for f in filas)}


def h_buscar(texto: str) -> dict[str, Any]:
    """Busca un proveedor, cliente, impuesto o palabra en pagos, correos, alertas e impuestos."""
    from modulos.motor_alertas import _filas
    q = f"%{texto.strip()}%"
    out: dict[str, Any] = {}
    consultas = {
        "pagos": ("SELECT id, fecha_sugerida fecha, detalle, proveedor, valor, estado FROM pagos_calendario "
                  "WHERE (detalle LIKE ? OR proveedor LIKE ?) AND estado!='ANULADO' ORDER BY fecha_sugerida DESC LIMIT 12", (q, q)),
        "correos": ("SELECT fecha, remitente_nombre de, asunto, categoria FROM correo_bandeja "
                    "WHERE asunto LIKE ? OR remitente LIKE ? OR remitente_nombre LIKE ? ORDER BY fecha DESC LIMIT 10", (q, q, q)),
        "alertas": ("SELECT nivel, titulo, descripcion FROM alertas WHERE resuelto=0 AND (titulo LIKE ? OR descripcion LIKE ?) "
                    "LIMIT 10", (q, q)),
        "impuestos": ("SELECT impuesto, periodo, fecha_limite vence, estado FROM impuestos_obligaciones "
                      "WHERE (impuesto LIKE ? OR periodo LIKE ?) AND estado!='NO APLICA' ORDER BY fecha_limite LIMIT 10", (q, q)),
    }
    for k, (sql, p) in consultas.items():
        try:
            out[k] = _filas(sql, p)
        except Exception:
            out[k] = []
    if not any(out.values()):  # nombre mal escrito: sugerir el más parecido
        try:
            nombres = {r["n"] for r in _filas("SELECT DISTINCT COALESCE(proveedor, detalle) n FROM pagos_calendario") if r["n"]}
            out["parecidos"] = difflib.get_close_matches(texto.upper(), [n.upper() for n in nombres], n=3, cutoff=0.6)
        except Exception:
            pass
    return out


def h_hoy() -> dict[str, Any]:
    """Resumen del día: lo vencido, lo de hoy y lo de mañana en todos los módulos, y alertas críticas."""
    from modulos import agenda_unificada as ag
    from modulos import motor_alertas as ma
    hoy = date.today()
    evs = [e for e in ag.eventos(hoy - timedelta(days=60), hoy + timedelta(days=1), incluir_hechos=False)
           if e["fuente"] not in ("AGENTE",)]
    crit = [a for a in ma.listar() if a["nivel"] == "CRITICO"]
    return {"fecha": hoy.isoformat(),
            "vencido": [_ev(e) for e in evs if e["nivel"] == "VENCIDO"],
            "hoy": [_ev(e) for e in evs if e["fecha"] == hoy],
            "manana": [_ev(e) for e in evs if e["fecha"] == hoy + timedelta(days=1)],
            "criticas": [{"titulo": a["titulo"], "detalle": (a.get("descripcion") or "")[:220], "valor": a.get("valor")}
                         for a in crit[:8]]}


def h_persona(nombre: str, pregunta: str = "") -> dict[str, Any]:
    """Datos de un empleado o exempleado por nombre (aunque esté mal escrito): ingreso, antigüedad, edad,
    cumpleaños, cargo, área, contrato y vencimiento, vacaciones, salario."""
    from modulos import conocimiento as co
    info = co.buscar_persona(nombre)
    if not info:
        return {"encontrado": False, "nota": "No hay nadie con ese nombre en Personal."}
    return {"encontrado": True, "datos": info, "respuesta_sugerida": co.responder_persona(pregunta or nombre, info)}


def h_tercero(nombre: str, pregunta: str = "") -> dict[str, Any]:
    """Proveedor o cliente por nombre: cuánto nos facturó y le pagamos, facturas sin pago (lo que le debemos),
    cuánto le vendimos y nos debe, gasto por cuenta, pagos programados y mora. Base: auxiliar del contador."""
    from modulos import conocimiento as co
    info = co.buscar_tercero(nombre)
    if not info:
        return {"encontrado": False, "nota": "No encontré ese tercero en la contabilidad, pagos ni cartera."}
    return {"encontrado": True, "datos": info,
            "respuesta_sugerida": co.responder_tercero(pregunta or f"cuanto le debemos a {nombre}", info)}


def h_contabilidad(pregunta: str) -> dict[str, Any]:
    """Cifras del auxiliar contable: cuánto se gastó en una cuenta (arriendo, energía, publicidad…) o cuánto se
    vendió, en total o en un mes. Pase la pregunta tal cual."""
    from modulos import conocimiento as co
    r = co.responder_contable(pregunta)
    return {"respuesta": r or "No hay contabilidad cargada o no entendí la cuenta."}


def _ev(e: dict) -> dict:
    from modulos import agenda_unificada as ag
    return {"fecha": e["fecha"].isoformat(), "fuente": ag.FUENTES[e["fuente"]]["nombre"], "titulo": e["titulo"],
            "detalle": e["sub"], "valor": e["valor"]}


HERRAMIENTAS: dict[str, tuple[Callable[..., dict], dict]] = {
    "hoy": (h_hoy, {}),
    "pagos": (h_pagos, {"desde": "string (YYYY-MM-DD)", "hasta": "string (YYYY-MM-DD)", "solo_vencidos": "boolean",
                        "texto": "string (proveedor o palabra)"}),
    "impuestos": (h_impuestos, {"desde": "string", "hasta": "string", "solo_pendientes": "boolean"}),
    "alertas": (h_alertas, {"nivel": "string (CRITICO|URGENTE|AVISO|INFO)"}),
    "correos": (h_correos, {"categoria": "string (JUDICIAL|DIAN|HACIENDA|COBRO|BANCO_PROBLEMA|FACTURA|COTIZACION|PERSONAL|BANCO)",
                            "solo_importantes": "boolean", "dias": "integer"}),
    "revision": (h_revision, {"impuesto": "string (RET|IVA|ICA|RETEICA|RENTA|EXOGENA|PREDIAL)", "periodo": "string (2026-09, 2026-B5…)"}),
    "agenda": (h_agenda, {"desde": "string", "hasta": "string"}),
    "cartera": (h_cartera, {}),
    "buscar": (h_buscar, {"texto": "string"}),
    "persona": (h_persona, {"nombre": "string (nombre del empleado)", "pregunta": "string (la pregunta original)"}),
    "tercero": (h_tercero, {"nombre": "string (proveedor o cliente)", "pregunta": "string (la pregunta original)"}),
    "contabilidad": (h_contabilidad, {"pregunta": "string (la pregunta original)"}),
}


# ───────────────────────── Motor 1: Claude con herramientas ─────────────────────────

SISTEMA = (
    "Eres Shaki, el asistente administrativo y contable de EQUIPOS INDUSTRIALES FÉNIX S.A.S. (NIT 901.146.454-6) "
    "en Bogotá. Hoy es {hoy}. Responde en español colombiano, claro y directo, con viñetas cortas y montos en pesos "
    "($1.234.567). Usa SIEMPRE las herramientas para obtener datos; nunca inventes cifras ni fechas. Si una "
    "herramienta no trae datos, dilo y sugiere dónde cargarlos en Shaki. Para preguntas sobre una persona usa «persona»; "
    "sobre un proveedor o cliente (cuánto le debemos, cuánto nos debe, cuánto le pagamos) usa «tercero»; sobre cuentas "
    "contables usa «contabilidad». Aclara que las deudas se calculan con el auxiliar del periodo cargado. "
    "Termina con la acción más urgente si la hay."
)


def _tools_spec() -> list[dict]:
    out = []
    for nombre, (fn, params) in HERRAMIENTAS.items():
        props = {}
        for k, t in params.items():
            tipo = t.split(" ")[0]
            props[k] = {"type": {"string": "string", "boolean": "boolean", "integer": "integer"}.get(tipo, "string"),
                        "description": t}
        out.append({"name": nombre, "description": (fn.__doc__ or nombre).strip(),
                    "input_schema": {"type": "object", "properties": props}})
    return out


def _con_claude(pregunta: str, historial: list[dict]) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
    msgs = [{"role": m["role"], "content": m["content"]} for m in historial[-8:]] + [{"role": "user", "content": pregunta}]
    sistema = SISTEMA.format(hoy=_f(date.today()))
    for _ in range(5):
        r = client.messages.create(model=cfg.MODELO_COMPLEJO, max_tokens=1500, system=sistema, tools=_tools_spec(),
                                   messages=msgs)
        if r.stop_reason != "tool_use":
            return "".join(b.text for b in r.content if b.type == "text").strip()
        msgs.append({"role": "assistant", "content": r.content})
        resultados = []
        for b in r.content:
            if b.type == "tool_use":
                fn = HERRAMIENTAS.get(b.name, (None,))[0]
                try:
                    datos = fn(**(b.input or {})) if fn else {"error": "herramienta desconocida"}
                except Exception as e:
                    datos = {"error": str(e)}
                resultados.append({"type": "tool_result", "tool_use_id": b.id,
                                   "content": json.dumps(datos, ensure_ascii=False, default=str)[:15000]})
        msgs.append({"role": "user", "content": resultados})
    return "No alcancé a terminar la consulta. Intente con una pregunta más concreta."


# ───────────────────────── Motor 2: intérprete local ─────────────────────────

AYUDA = """Puedo responderle con los datos reales de Shaki. Pruebe, por ejemplo:

- **¿Qué tengo hoy?** · ¿Qué hay para mañana? · ¿Qué tengo esta semana?
- **Pagos**: pagos de esta semana · pagos vencidos · ¿cuánto hay que pagar este mes? · pagos de Bancolombia
- **Impuestos**: ¿qué impuestos vienen? · ¿cuándo vence la retención? · impuestos de noviembre
- **Revisión**: ¿cómo quedó la revisión de retención?
- **Alertas**: alertas críticas · ¿qué alertas hay?
- **Correos**: correos importantes · facturas que llegaron · ¿llegó algo de la DIAN?
- **Cartera**: clientes en mora
- **Personas**: ¿cuántos años lleva Andrés Valencia? · ¿cuándo cumple años Laura? · ¿cuándo vence el contrato de Juan?
- **Proveedores y clientes**: ¿cuánto le debemos a Codifer? · ¿cuánto nos debe Ecopetrol? · ¿cuánto le hemos pagado a Claro?
- **Contabilidad**: ¿cuánto gastamos en publicidad? · ¿cuánto vendimos en septiembre?
- **Buscar**: busca Codifer · ¿qué hay de Claro?"""


def _lista_pagos(d: dict, titulo: str) -> str:
    if not d["pagos"]:
        return f"No hay pagos {titulo}."
    lineas = [f"**Pagos {titulo}:** {d['pendientes']} pendiente(s)"
              + (f" por {_p(d['valor_pendiente'])}" if d["valor_pendiente"] else "")
              + (f" · {d['pagados']} ya pagado(s)" if d["pagados"] else "")]
    d["pagos"].sort(key=lambda p: (p["estado"] == "PAGADO", str(p["fecha"])))
    for p in d["pagos"][:15]:
        marca = "✓" if p["estado"] == "PAGADO" else "•"
        lineas.append(f"{marca} {_f(p['fecha'])} — {p['detalle'] or p['proveedor']}"
                      + (f" · {_p(p['valor'])}" if p["valor"] else "") + (" (pagado)" if p["estado"] == "PAGADO" else ""))
    if len(d["pagos"]) > 15:
        lineas.append(f"…y {len(d['pagos']) - 15} más en Pagos.")
    return "\n".join(lineas)


def _lista_impuestos(obl: list[dict], titulo: str) -> str:
    if not obl:
        return f"No hay declaraciones pendientes {titulo}."
    hoy = date.today()
    lineas = [f"**Declaraciones {titulo}:**"]
    for o in obl[:12]:
        dias = (date.fromisoformat(str(o["vence"])) - hoy).days
        cuando = f"VENCIDA hace {-dias} días" if dias < 0 else "vence HOY" if dias == 0 else f"en {dias} días"
        lineas.append(f"• {o['impuesto']} · {o['periodo']} ({o['entidad']}, form. {o['formulario']}) — "
                      f"{_f(o['vence'])} · {cuando}")
    return "\n".join(lineas)


def _local(pregunta: str) -> str:
    t = _n(pregunta)
    hoy = date.today()
    if not t or any(x in t for x in ("ayuda", "que puedes", "que sabes", "como funciona", "que preguntas")):
        return AYUDA
    if re.fullmatch(r"(hola|buenas|buenos dias|buenas tardes|buenas noches|hey|gracias|muchas gracias|ok|listo)[ !.]*", t):
        if t.startswith(("gracias", "muchas", "ok", "listo")):
            return "Con gusto. Aquí estoy si necesita algo más."
        return "¡Hola! Soy Shaki. Pregúnteme por pagos, impuestos, alertas, correos o «¿qué tengo hoy?». " \
               "Escriba **ayuda** para ver ejemplos."
    r = _conocimiento(pregunta, t)
    if r:
        return r
    m = re.search(r"\b(busca|buscar|encuentra|que hay de|algo de|informacion de)\s+(.+)", t)
    tema_pagos = re.search(r"\bpag(o|os|ar|ue)\b|cuota|cuanto (hay|debo|tengo)|nomina|factura[s]? (por|a) pagar", t)
    tema_imp = re.search(r"impuest|declarac|retencion|reteica|\biva\b|\bica\b|renta|exogena|predial|vehicul|dian|shd|hacienda", t)
    tema_alert = "alerta" in t or "urgente" in t or "critic" in t
    tema_corr = re.search(r"correo|email|mail|bandeja|llego|llegaron|recib", t)
    tema_rev = "revision" in t or "revisaste" in t or "como quedo" in t or "borrador" in t
    tema_cart = re.search(r"cartera|mora|me deben|cobrar|clientes", t)
    tema_agenda = re.search(r"que tengo|que hay (para|hoy|manana|esta)|agenda|pendiente|calendario|resumen", t)

    if tema_rev:
        imp = "RET" if "retencion" in t else "IVA" if re.search(r"\biva\b", t) else "RETEICA" if "reteica" in t \
            else "ICA" if re.search(r"\bica\b", t) else None
        r = h_revision(imp)["revision"]
        if not r:
            return "Todavía no hay revisiones guardadas. Súbalas en **Impuestos → Revisión de impuestos**."
        out = [f"**{r['impuesto']} · {r['periodo']}: {r['veredicto'].lower()}.**", r["resumen"]]
        if r["hallazgos"]:
            out.append("\n**Pendientes:**")
            out += [f"• [{h['nivel']}] {h['titulo']}" + (f" → {h['accion']}" if h.get("accion") else "") for h in r["hallazgos"][:8]]
        return "\n".join(out)

    if tema_corr and not tema_pagos:
        cat = ("DIAN" if "dian" in t else "HACIENDA" if re.search(r"hacienda|shd", t) else "FACTURA" if "factura" in t
               else "COTIZACION" if "cotiza" in t else "COBRO" if "cobro" in t else "JUDICIAL" if re.search(r"juzgado|demanda|embargo", t)
               else "BANCO" if "banco" in t else None)
        d = h_correos(categoria=cat, solo_importantes=cat is None)
        sin_clave = [b["email"] for b in d["buzones"] if b["estado"] in ("FALTA CONTRASEÑA", "SIN CONFIGURAR")]
        if not d["correos"]:
            msg = "No hay correos " + ("de ese tipo " if cat else "importantes ") + "sin atender en los últimos 15 días."
            if sin_clave:
                msg += f" Ojo: faltan por conectar {', '.join(sin_clave)}."
            return msg
        out = [f"**{len(d['correos'])} correo(s) {'de ese tipo' if cat else 'importantes'} sin atender:**"]
        for c in d["correos"][:12]:
            out.append(f"• [{c['categoria']}] {c['asunto']} — de {c['de']} → {c['buzon']} ({c['fecha']})")
        return "\n".join(out)

    if tema_alert:
        nivel = "CRITICO" if "critic" in t else "URGENTE" if "urgente" in t else None
        d = h_alertas(nivel)
        if not d["alertas"]:
            return "No hay alertas abiertas" + (" de ese nivel" if nivel else "") + f". Salud del sistema: {d['salud']}/100 ✓"
        out = [f"**{len(d['alertas'])} alerta(s) abiertas** · salud {d['salud']}/100"]
        for a in d["alertas"][:12]:
            out.append(f"• [{a['nivel']}] {a['titulo']}" + (f" · {_p(a['valor'])}" if a.get("valor") else ""))
        return "\n".join(out)

    if tema_imp and not tema_pagos:
        if "vencid" in t:
            obl = [o for o in h_impuestos(hoy - timedelta(days=120), hoy - timedelta(days=1))["obligaciones"]]
            return _lista_impuestos(obl, "vencidas sin marcar")
        d, h, etq = rango(t, hoy, defecto=45)
        obl = h_impuestos(d.isoformat(), h.isoformat())["obligaciones"]
        filtro = {"retencion": "Retención", "reteica": "ReteICA", "iva": "IVA", "ica": "ICA", "renta": "Renta",
                  "exogena": "exógena", "predial": "Predial", "vehicul": "Vehículos"}
        for k, v in filtro.items():
            if re.search(rf"\b{k}", t) and not (k == "ica" and "reteica" in t):
                obl = [o for o in obl if v.lower() in o["impuesto"].lower()]
                break
        return _lista_impuestos(obl, etq)

    if tema_pagos:
        if "vencid" in t or "atrasad" in t or "sin pagar" in t:
            return _lista_pagos(h_pagos(solo_vencidos=True), "vencidos sin marcar")
        d, h, etq = rango(t, hoy)
        prov = None
        mm = re.search(r"\b(de|a|con)\s+([a-z0-9][a-z0-9 .&-]{2,40})$", t)
        if mm and not re.search(r"(semana|mes|hoy|manana|dias|ano|" + "|".join(MESES) + ")", mm.group(2)):
            prov = mm.group(2).strip()
        if prov and not re.search(r"semana|mes|hoy|manana|dias|" + "|".join(MESES), t):
            d, h, etq = hoy - timedelta(days=30), hoy + timedelta(days=60), "del último mes y los próximos 2 meses"
        return _lista_pagos(h_pagos(d.isoformat(), h.isoformat(), texto=prov), etq + (f" de «{prov}»" if prov else ""))

    if tema_cart:
        d = h_cartera()
        if not d["clientes"]:
            return "No hay clientes con cartera en mora registrada."
        out = [f"**Cartera en mora: {_p(d['total'])}**"]
        out += [f"• {c['cliente']} — {c['dias_mora']} días · {_p(c['saldo'])}" for c in d["clientes"][:12]]
        return "\n".join(out)

    if m:
        return _busqueda(m.group(2))

    if tema_agenda or re.search(r"\bhoy\b|manana|semana", t):
        if re.search(r"semana|mes|dias|" + "|".join(MESES), t):
            d, h, etq = rango(t, hoy)
            evs = h_agenda(d.isoformat(), h.isoformat())["eventos"]
            if not evs:
                return f"Nada en la agenda para {etq}."
            out = [f"**Agenda de {etq}:**"]
            out += [f"• {_f(e['fecha'])} — {e['titulo']} ({e['fuente']})" + (f" · {_p(e['valor'])}" if e["valor"] else "")
                    for e in evs[:20]]
            return "\n".join(out)
        return _resumen_hoy(manana="manana" in t)

    # última opción: buscar las palabras de la pregunta
    palabras = [w for w in re.findall(r"[a-z0-9]{4,}", t) if w not in ("cual", "cuales", "donde", "como", "esta", "este",
                                                                        "tengo", "sobre", "para", "quiero", "saber")]
    if palabras:
        r = _busqueda(" ".join(palabras[-2:]))
        if not r.startswith("No encontré"):
            return r
    return "No entendí bien la pregunta. " + AYUDA


RE_PERSONA = (r"\blleva\b|antiguedad|cuantos anos|edad|cumple|nacio|vacacion|contrato|\bcargo\b|que hace|salario|sueldo|"
              r"\bgana\b|quien es|cuando (entro|ingreso)|desde cuando|trabaja")
RE_TERCERO = (r"debemos|\bdebe\b|deuda|le (hemos )?pagado|le pagamos|le compramos|nos (ha )?facturado|nos facturo|"
              r"le vendimos|le facturamos|saldo (de|con)|cuanto (le|nos)|proveedor|cliente")
RE_CONTABLE = r"cuanto (gastamos|gasto|se gasto|hemos gastado|vendimos|vendio|facturamos|ingreso)|cuanto (nos )?cuesta"


def _conocimiento(pregunta: str, t: str) -> str | None:
    """Preguntas sobre una persona, un proveedor/cliente o una cuenta contable."""
    from modulos import conocimiento as co
    try:
        if re.search(RE_PERSONA, t):
            info = co.buscar_persona(pregunta)
            if info:
                return co.responder_persona(pregunta, info)
        if re.search(RE_TERCERO, t) or re.search(RE_CONTABLE, t):
            info = co.buscar_tercero(pregunta)
            if info:
                return co.responder_tercero(pregunta, info)
        if re.search(RE_CONTABLE, t):
            r = co.responder_contable(pregunta)
            if r:
                return r
        if re.search(RE_PERSONA, t) and co.candidatos_texto(pregunta):
            return (f"No encontré a «{co.candidatos_texto(pregunta)}» en Personal. Revise que esté en el "
                    "Archivo General o en Contratos Activos.")
        if re.search(RE_TERCERO, t) and re.search(r"debe|deuda|pagado|pagamos|compramos|vendimos|facturo", t) \
                and co.candidatos_texto(pregunta):
            return (f"No encontré a «{co.candidatos_texto(pregunta)}» como proveedor ni cliente en la contabilidad, "
                    "pagos o cartera. Pruebe con otra parte del nombre (ej. «Codifer» en vez de «Codifer SAS»).")
    except Exception as e:
        logger.warning("Conocimiento: %s", e)
    return None


def _resumen_hoy(manana: bool = False) -> str:
    d = h_hoy()
    if manana:
        evs = d["manana"]
        if not evs:
            return "Mañana no tiene nada programado. ✓"
        return "**Para mañana:**\n" + "\n".join(
            f"• {e['titulo']} ({e['fuente']})" + (f" · {_p(e['valor'])}" if e["valor"] else "") for e in evs)
    out = [f"**Hoy, {_f(d['fecha']).split(' (')[0]}:**"]
    if d["vencido"]:
        out.append(f"\n🔴 **Vencido ({len(d['vencido'])}):**")
        out += [f"• {e['titulo']} ({e['fuente']}, {_f(e['fecha']).split(' (')[0]})" + (f" · {_p(e['valor'])}" if e["valor"] else "")
                for e in d["vencido"][:8]]
    out.append(f"\n🟠 **Para hoy ({len(d['hoy'])}):**" if d["hoy"] else "\n✓ Nada vence hoy.")
    out += [f"• {e['titulo']} ({e['fuente']})" + (f" · {_p(e['valor'])}" if e["valor"] else "") for e in d["hoy"][:10]]
    if d["manana"]:
        out.append(f"\n🟡 **Mañana ({len(d['manana'])}):**")
        out += [f"• {e['titulo']} ({e['fuente']})" for e in d["manana"][:6]]
    if d["criticas"]:
        out.append(f"\n⚠️ **Alertas críticas ({len(d['criticas'])}):**")
        out += [f"• {a['titulo']}" + (f" · {_p(a['valor'])}" if a.get("valor") else "") for a in d["criticas"][:6]]
    return "\n".join(out)


def _busqueda(texto: str) -> str:
    texto = texto.strip(" ?¿.")
    d = h_buscar(texto)
    out = []
    if d.get("pagos"):
        out.append(f"**Pagos ({len(d['pagos'])}):**")
        out += [f"• {_f(p['fecha'])} — {p['detalle']}" + (f" · {_p(p['valor'])}" if p["valor"] else "")
                + f" · {p['estado'].lower()}" for p in d["pagos"][:6]]
    if d.get("impuestos"):
        out.append(f"**Impuestos ({len(d['impuestos'])}):**")
        out += [f"• {o['impuesto']} {o['periodo']} — vence {_f(o['vence'])} · {o['estado'].lower()}" for o in d["impuestos"][:6]]
    if d.get("correos"):
        out.append(f"**Correos ({len(d['correos'])}):**")
        out += [f"• {str(c['fecha'])[:10]} — {c['asunto']} (de {c['de']})" for c in d["correos"][:6]]
    if d.get("alertas"):
        out.append(f"**Alertas ({len(d['alertas'])}):**")
        out += [f"• [{a['nivel']}] {a['titulo']}" for a in d["alertas"][:6]]
    if not out:
        sug = d.get("parecidos")
        return f"No encontré nada sobre «{texto}»." + (f" ¿Quiso decir: {', '.join(sug)}?" if sug else "")
    return f"Esto encontré sobre «{texto}»:\n" + "\n".join(out)


# ───────────────────────── Entrada pública ─────────────────────────

def ia_activa() -> bool:
    k = (getattr(cfg, "ANTHROPIC_API_KEY", "") or "").strip()
    return bool(k) and not k.startswith("sk-ant-xxx")


def responder(pregunta: str, historial: list[dict] | None = None) -> str:
    historial = historial or []
    if ia_activa():
        try:
            return _con_claude(pregunta, historial)
        except Exception as e:
            logger.warning("Asistente con Claude falló, uso el modo local: %s", e)
    try:
        return _local(pregunta)
    except Exception as e:
        logger.exception("Asistente local: %s", e)
        return f"Tuve un problema leyendo los datos ({e}). Intente de nuevo en un momento."
