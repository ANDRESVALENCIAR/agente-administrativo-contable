"""
Buzones de correo conectados a Shaki — lectura SOLO LECTURA de varias cuentas, clasificación y alertas.

- Cada buzón se registra en `correo_buzones` (correo, servidor IMAP, activo). Se pueden agregar
  más desde el panel (Correos → Buzones) sin tocar código.
- La contraseña NUNCA se guarda en la base de datos ni en git: vive en el .env del computador como
  CORREO_PASS_<CORREO_EN_MAYÚSCULAS_CON_GUIONES_BAJOS> y se escribe con scripts/configurar_buzon.ps1.
- Lectura IMAP en modo solo lectura (EXAMINE + BODY.PEEK): no marca correos como leídos, no mueve
  ni borra nada.
- Cada correo queda en `correo_bandeja`, clasificado por reglas (DIAN, Hacienda, juzgados, facturas
  electrónicas, cobros, bancos, cotizaciones, personal, publicidad). El motor de alertas convierte
  los importantes en alertas con el nivel configurado por categoría.

Servidores conocidos: viaindustrial.com → mail.viaindustrial.com:993 (el MX del dominio),
gmail.com → imap.gmail.com:993 (requiere contraseña de aplicación).
"""
from __future__ import annotations

import email
import imaplib
import json
import logging
import os
import re
import ssl
from datetime import date, datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from html import unescape
from typing import Any

from database import get_conn

logger = logging.getLogger(__name__)

SERVIDORES = {
    "gmail.com": ("imap.gmail.com", 993),
    "googlemail.com": ("imap.gmail.com", 993),
    "viaindustrial.com": ("mail.viaindustrial.com", 993),
    "outlook.com": ("outlook.office365.com", 993),
    "hotmail.com": ("outlook.office365.com", 993),
    "yahoo.com": ("imap.mail.yahoo.com", 993),
}
BUZONES_INICIALES = ["gerencia@viaindustrial.com", "gerenciafenix@viaindustrial.com",
                     "equiposindustrialesfenix@gmail.com"]
MAX_POR_LECTURA = 150
DIAS_PRIMERA_LECTURA = 7

# ───────────────────────── Categorías y nivel de alerta por defecto ─────────────────────────
# nivel: CRITICO / URGENTE / AVISO / INFO / NO (no alertar)
CATEGORIAS: dict[str, dict[str, str]] = {
    "JUDICIAL": {"nombre": "Juzgados y procesos", "nivel": "CRITICO",
                 "desc": "Notificaciones judiciales, demandas, embargos, tutelas, superintendencias, UGPP."},
    "DIAN": {"nombre": "DIAN (actuaciones)", "nivel": "CRITICO",
             "desc": "Requerimientos, emplazamientos, pliegos, sanciones, cobros o notificaciones de la DIAN."},
    "HACIENDA": {"nombre": "Hacienda Bogotá (actuaciones)", "nivel": "CRITICO",
                 "desc": "Notificaciones, requerimientos, cobro coactivo o emplazamientos de la SHD."},
    "COBRO": {"nombre": "Cobros y cartera", "nivel": "URGENTE",
              "desc": "Cuentas de cobro, facturas vencidas, recordatorios de pago, estados de cuenta en mora."},
    "BANCO_PROBLEMA": {"nombre": "Banco: problema", "nivel": "URGENTE",
                       "desc": "Pagos rechazados, fallidos, sobregiros, cuotas vencidas, bloqueos."},
    "FACTURA": {"nombre": "Facturas electrónicas recibidas", "nivel": "AVISO",
                "desc": "Facturas de proveedores (XML/ZIP o asunto de factura electrónica) por registrar y pagar."},
    "COTIZACION": {"nombre": "Solicitudes de cotización", "nivel": "AVISO",
                   "desc": "Clientes pidiendo precio, cotización u oferta."},
    "PERSONAL": {"nombre": "Personal / RRHH", "nivel": "AVISO",
                 "desc": "Incapacidades, renuncias, hojas de vida, EPS, ARL, PILA, vacaciones."},
    "DIAN_INFO": {"nombre": "DIAN / Hacienda (informativo)", "nivel": "INFO",
                  "desc": "Validaciones de factura electrónica, boletines, avisos generales."},
    "BANCO": {"nombre": "Banco: movimientos", "nivel": "INFO",
              "desc": "Transferencias, pagos exitosos, comprobantes y extractos."},
    "PUBLICIDAD": {"nombre": "Publicidad y boletines", "nivel": "NO", "desc": "Newsletters, promociones, webinars."},
    "OTRO": {"nombre": "Otros", "nivel": "NO", "desc": "Todo lo demás."},
}
NIVELES_ALERTA = ["CRITICO", "URGENTE", "AVISO", "INFO", "NO"]

_R = lambda *pal: re.compile("|".join(pal), re.I)  # noqa: E731
R_JUDICIAL = _R(r"juzgado", r"rama judicial", r"notificaci[oó]n judicial", r"\bdemanda", r"embargo", r"tutela",
                r"despacho judicial", r"proceso ejecutivo", r"mandamiento de pago", r"superintendencia",
                r"\bugpp\b", r"fiscal[ií]a", r"conciliaci[oó]n extrajudicial", r"citaci[oó]n para notificaci")
R_ACTUACION = _R(r"requerimiento", r"emplazamiento", r"pliego de cargos", r"liquidaci[oó]n oficial",
                 r"sanci[oó]n", r"cobro coactivo", r"mandamiento", r"notificaci[oó]n electr[oó]nica",
                 r"acto administrativo", r"auto de", r"resoluci[oó]n", r"inexactitud", r"omis[oó]")
R_FACTURA_ASUNTO = re.compile(r"^\s*\d{6,11}\s*;[^;]+;[^;]+;0?1\s*;", re.I)  # asunto estándar FE Colombia
R_FACTURA = _R(r"factura electr[oó]nica", r"\bfactura\b.*\b(no\.?|n[uú]mero|#)", r"documento electr[oó]nico",
               r"\bfe-?\d+", r"nota cr[eé]dito electr")
R_COBRO = _R(r"cuenta de cobro", r"estado de cuenta", r"factura vencida", r"facturas vencidas", r"recordatorio de pago",
             r"saldo pendiente", r"\bmora\b", r"en mora", r"cobro pre?jur[ií]dico", r"pago pendiente", r"vencid[ao]s?")
R_BANCO_DOM = _R(r"bancolombia", r"davivienda", r"bbva", r"bancodebogota", r"banco de bogot", r"bancodeoccidente",
                 r"occidente", r"itau", r"scotiabank", r"colpatria", r"nequi", r"daviplata", r"av villas", r"popular",
                 r"banco caja social", r"pse", r"credibanco", r"redeban")
R_BANCO_MAL = _R(r"rechazad", r"fallid", r"no exitos", r"sobregiro", r"cuota vencida", r"bloque", r"insuficiente",
                 r"reversad", r"devuelt")
R_COTIZ = _R(r"cotizaci[oó]n", r"cotizar", r"\brfq\b", r"solicitud de precio", r"precio de", r"oferta comercial",
             r"requerimos", r"necesitamos (el|un|una)")
R_PERSONAL = _R(r"incapacidad", r"hoja de vida", r"\bcv\b", r"renuncia", r"vacaciones", r"\bpila\b", r"\beps\b",
                r"\barl\b", r"liquidaci[oó]n laboral", r"certificado laboral", r"colpensiones", r"porvenir",
                r"protecci[oó]n s\.?a")
R_PUBLI = _R(r"unsubscribe", r"darse de baja", r"cancelar suscripci", r"newsletter", r"bolet[ií]n", r"webinar",
             r"promoci[oó]n", r"descuento", r"oferta especial", r"black friday", r"no-?reply@.*(news|promo|marketing)")


def clasificar(remitente: str, asunto: str, cuerpo: str, adjuntos: list[str]) -> tuple[str, str]:
    """Devuelve (categoria, motivo). Reglas en orden de gravedad."""
    rem = (remitente or "").lower()
    asu = asunto or ""
    txt = f"{asu}\n{(cuerpo or '')[:4000]}"
    adj = " ".join(adjuntos).lower()
    if R_JUDICIAL.search(txt) or rem.endswith(("ramajudicial.gov.co", "cendoj.ramajudicial.gov.co")):
        m = R_JUDICIAL.search(txt)
        return "JUDICIAL", f"menciona «{m.group(0)}»" if m else "remitente de la Rama Judicial"
    es_dian = "dian.gov.co" in rem or re.search(r"\bdian\b", asu, re.I)
    es_shd = any(d in rem for d in ("haciendabogota.gov.co", "shd.gov.co")) or re.search(
        r"hacienda (distrital|bogot)|secretar[ií]a distrital de hacienda", asu, re.I)
    if es_dian or es_shd:
        m = R_ACTUACION.search(txt)
        if m and not re.search(r"validad|aceptad|recibid[oa] por la dian", txt, re.I):
            return ("DIAN" if es_dian else "HACIENDA"), f"actuación: «{m.group(0)}»"
        return "DIAN_INFO", "informativo de entidad tributaria"
    if R_BANCO_DOM.search(rem) or (R_BANCO_DOM.search(asu) and re.search(r"transferen|pago|movimiento|extracto", asu, re.I)):
        m = R_BANCO_MAL.search(txt)
        return ("BANCO_PROBLEMA", f"«{m.group(0)}»") if m else ("BANCO", "notificación bancaria")
    if R_FACTURA_ASUNTO.search(asu) or any(a.endswith((".xml", ".zip")) for a in adjuntos) and re.search(
            r"factura|fv|fe|ad\d", asu + " " + adj, re.I) or R_FACTURA.search(asu):
        return "FACTURA", "factura electrónica recibida"
    if R_COBRO.search(asu) or (R_COBRO.search(txt) and re.search(r"pago|factura|saldo", txt, re.I)):
        m = R_COBRO.search(txt)
        return "COBRO", f"«{m.group(0)}»" if m else "cobro"
    if R_PUBLI.search(txt) or rem.startswith(("news", "marketing", "promo", "info@mail")):
        return "PUBLICIDAD", "publicidad"
    if R_COTIZ.search(asu) or (R_COTIZ.search(txt[:800]) and "?" in txt[:1500]):
        return "COTIZACION", "solicitud de cotización"
    if R_PERSONAL.search(asu):
        return "PERSONAL", "tema de personal"
    return "OTRO", ""


def emisor_factura(asunto: str) -> dict[str, str]:
    """Asunto estándar FE: 'NIT;Razón social;Número;01;...' → datos del emisor."""
    p = [x.strip() for x in (asunto or "").split(";")]
    if len(p) >= 4 and re.fullmatch(r"\d{6,11}", p[0]):
        return {"nit": p[0], "emisor": p[1], "numero": p[2]}
    return {}


# ───────────────────────── BD ─────────────────────────

def inicializar() -> None:
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS correo_buzones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            proveedor TEXT DEFAULT 'IMAP',
            imap_host TEXT,
            imap_port INTEGER DEFAULT 993,
            usuario TEXT,
            verificar_ssl INTEGER DEFAULT 1,
            activo INTEGER DEFAULT 1,
            uidvalidity TEXT,
            ultimo_uid INTEGER DEFAULT 0,
            ultima_lectura DATETIME,
            estado TEXT DEFAULT 'SIN CONFIGURAR',
            ultimo_error TEXT,
            creado_en DATETIME DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS correo_bandeja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buzon_id INTEGER NOT NULL,
            uid INTEGER,
            message_id TEXT,
            fecha DATETIME,
            remitente TEXT,
            remitente_nombre TEXT,
            asunto TEXT,
            resumen TEXT,
            adjuntos TEXT,
            categoria TEXT,
            motivo TEXT,
            datos TEXT,
            estado TEXT DEFAULT 'NUEVO',
            atendido_en DATETIME,
            leido_en DATETIME DEFAULT (datetime('now','localtime')),
            UNIQUE(buzon_id, message_id)
        );
        CREATE INDEX IF NOT EXISTS idx_bandeja_estado ON correo_bandeja(estado, categoria);
        CREATE TABLE IF NOT EXISTS correo_meta (clave TEXT PRIMARY KEY, valor TEXT);
        """
    )
    conn.commit()
    if not conn.execute("SELECT valor FROM correo_meta WHERE clave='sembrado'").fetchone():
        for e in BUZONES_INICIALES:
            h, p = servidor_para(e)
            conn.execute("INSERT OR IGNORE INTO correo_buzones (email, imap_host, imap_port, usuario) VALUES (?,?,?,?)",
                         (e, h, p, e))
        conn.execute("INSERT INTO correo_meta(clave, valor) VALUES ('sembrado', '1')")
        conn.commit()
    conn.close()


def _q(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()


def _ex(sql: str, params: tuple = ()) -> int:
    conn = get_conn()
    cur = conn.execute(sql, params)
    conn.commit()
    n = cur.lastrowid or cur.rowcount
    conn.close()
    return n


def servidor_para(correo: str) -> tuple[str, int]:
    dom = correo.split("@")[-1].lower().strip()
    return SERVIDORES.get(dom, (f"mail.{dom}", 993))


def env_clave(correo: str) -> str:
    return "CORREO_PASS_" + re.sub(r"[^A-Z0-9]", "_", correo.upper())


def tiene_clave(correo: str) -> bool:
    return bool((os.getenv(env_clave(correo)) or "").strip())


def listar_buzones() -> list[dict[str, Any]]:
    inicializar()
    filas = _q("SELECT * FROM correo_buzones ORDER BY id")
    for b in filas:
        b["tiene_clave"] = tiene_clave(b["email"])
        if not b["tiene_clave"] and b["estado"] in (None, "SIN CONFIGURAR", "OK"):
            b["estado"] = "FALTA CONTRASEÑA"
    return filas


def agregar_buzon(correo: str, host: str | None = None, puerto: int | None = None) -> int:
    inicializar()
    correo = correo.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", correo):
        raise ValueError("Correo no válido")
    h, p = servidor_para(correo)
    return _ex("INSERT OR IGNORE INTO correo_buzones (email, imap_host, imap_port, usuario) VALUES (?,?,?,?)",
               (correo, host or h, puerto or p, correo))


def actualizar_buzon(bid: int, **campos: Any) -> None:
    permitidos = {"imap_host", "imap_port", "usuario", "verificar_ssl", "activo"}
    sets = [(k, v) for k, v in campos.items() if k in permitidos]
    if sets:
        _ex(f"UPDATE correo_buzones SET {', '.join(k + '=?' for k, _ in sets)} WHERE id=?",
            tuple(v for _, v in sets) + (bid,))


def quitar_buzon(bid: int) -> None:
    _ex("UPDATE correo_buzones SET activo=0 WHERE id=?", (bid,))


# ───────────────────────── IMAP ─────────────────────────

def _dec(v: Any) -> str:
    if not v:
        return ""
    try:
        return str(make_header(decode_header(str(v))))
    except Exception:
        return str(v)


def _texto(msg: email.message.Message) -> tuple[str, list[str]]:
    texto, html, adj = "", "", []
    for parte in msg.walk():
        if parte.is_multipart():
            continue
        nombre = parte.get_filename()
        disp = str(parte.get("Content-Disposition") or "").lower()
        if nombre or "attachment" in disp:
            adj.append(_dec(nombre) or "adjunto")
            continue
        ctype = parte.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        try:
            raw = parte.get_payload(decode=True) or b""
            s = raw.decode(parte.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        if ctype == "text/plain" and not texto:
            texto = s
        elif ctype == "text/html" and not html:
            html = s
    if not texto and html:
        texto = unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", html)))
    return re.sub(r"\s+", " ", texto).strip(), adj


def _conectar(b: dict[str, Any]) -> imaplib.IMAP4_SSL:
    ctx = ssl.create_default_context()
    if not b.get("verificar_ssl", 1):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    m = imaplib.IMAP4_SSL(b["imap_host"], int(b.get("imap_port") or 993), ssl_context=ctx, timeout=30)
    m.login(b.get("usuario") or b["email"], os.getenv(env_clave(b["email"]), ""))
    return m


def nombres_certificado(host: str, port: int = 993) -> list[str]:
    """Nombres (DNS) del certificado que presenta el servidor, sin validarlo (solo para diagnóstico)."""
    from cryptography import x509

    pem = ssl.get_server_certificate((host, port), timeout=15)
    cert = x509.load_pem_x509_certificate(pem.encode())
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        return [str(n) for n in san.get_values_for_type(x509.DNSName)]
    except x509.ExtensionNotFound:
        return [a.value for a in cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)]


def _corregir_servidor(b: dict[str, Any]) -> str | None:
    """Hosting compartido: el certificado es del servidor real (p. ej. srv12.hosting.com), no de mail.<dominio>.
    Prueba esos nombres con verificación completa y, si alguno funciona, lo guarda para ese dominio."""
    try:
        nombres = [n for n in nombres_certificado(b["imap_host"], int(b.get("imap_port") or 993)) if "*" not in n]
    except Exception:
        return None
    for n in nombres:
        try:
            prueba = {**b, "imap_host": n}
            m = _conectar(prueba)
            m.logout()
        except imaplib.IMAP4.error:
            pass  # el servidor sí es ese (TLS correcto) aunque la clave falle: igual sirve el nombre
        except Exception:
            continue
        dominio = b["email"].split("@")[-1]
        _ex("UPDATE correo_buzones SET imap_host=? WHERE imap_host=? AND email LIKE ?", (n, b["imap_host"], f"%@{dominio}"))
        return n
    return None


def probar(bid: int) -> dict[str, Any]:
    b = next((x for x in listar_buzones() if x["id"] == bid), None)
    if not b:
        return {"ok": False, "error": "No existe"}
    if not b["tiene_clave"]:
        return {"ok": False, "error": f"Falta la contraseña. Ejecute scripts\\configurar_buzon.ps1 para {b['email']}."}
    try:
        m = _conectar(b)
        typ, data = m.select("INBOX", readonly=True)
        n = int(data[0]) if typ == "OK" else 0
        m.logout()
        _ex("UPDATE correo_buzones SET estado='OK', ultimo_error=NULL WHERE id=?", (bid,))
        return {"ok": True, "mensajes": n}
    except Exception as e:
        if (isinstance(e, ssl.SSLCertVerificationError) or "CERTIFICATE" in str(e).upper()) and not b.get("_reintento"):
            nuevo = _corregir_servidor(b)
            if nuevo:
                r = probar(bid)
                if r["ok"]:
                    r["servidor"] = nuevo
                return r
        err = _explicar_error(e, b)
        _ex("UPDATE correo_buzones SET estado='ERROR', ultimo_error=? WHERE id=?", (err, bid))
        return {"ok": False, "error": err}


def _explicar_error(e: Exception, b: dict[str, Any]) -> str:
    s = str(e)
    if isinstance(e, imaplib.IMAP4.error) or "AUTHENTICATIONFAILED" in s.upper() or "LOGIN" in s.upper():
        if "gmail" in b["imap_host"]:
            return ("Gmail rechazó el ingreso: use una CONTRASEÑA DE APLICACIÓN (16 letras), no la clave normal. "
                    f"Detalle: {s[:120]}")
        return f"Usuario o contraseña incorrectos para {b['email']}. Detalle: {s[:120]}"
    if isinstance(e, ssl.SSLCertVerificationError) or "CERTIFICATE" in s.upper():
        return (f"El certificado de {b['imap_host']} no coincide. Pida al proveedor del hosting el nombre exacto del "
                f"servidor IMAP o desactive 'Verificar SSL' para este buzón. Detalle: {s[:120]}")
    if isinstance(e, (TimeoutError, OSError)):
        return f"No se pudo conectar a {b['imap_host']}:{b['imap_port']} ({s[:120]})."
    return s[:300]


def leer_buzon(b: dict[str, Any]) -> dict[str, Any]:
    """Lee correos nuevos de un buzón (solo lectura) y los guarda clasificados."""
    if not b["tiene_clave"]:
        return {"buzon": b["email"], "nuevos": 0, "error": "falta contraseña"}
    nuevos = 0
    try:
        m = _conectar(b)
        typ, _ = m.select("INBOX", readonly=True)
        if typ != "OK":
            raise RuntimeError("No se pudo abrir la bandeja de entrada")
        uv = (m.response("UIDVALIDITY")[1] or [b""])[0]
        uv = uv.decode() if isinstance(uv, bytes) else str(uv or "")
        ultimo = int(b.get("ultimo_uid") or 0) if (b.get("uidvalidity") or "") == uv else 0
        if ultimo:
            typ, data = m.uid("SEARCH", None, f"UID {ultimo + 1}:*")
        else:
            desde = (date.today() - timedelta(days=DIAS_PRIMERA_LECTURA)).strftime("%d-%b-%Y")
            typ, data = m.uid("SEARCH", None, f"SINCE {desde}")
        uids = sorted(int(x) for x in (data[0] or b"").split() if int(x) > ultimo)[-MAX_POR_LECTURA:]
        maxuid = ultimo
        for uid in uids:
            typ, d = m.uid("FETCH", str(uid), "(RFC822.SIZE BODY.PEEK[])")
            if typ != "OK" or not d or not isinstance(d[0], tuple):
                continue
            msg = email.message_from_bytes(d[0][1])
            nuevos += _guardar(b, uid, msg)
            maxuid = max(maxuid, uid)
        m.logout()
        _ex("UPDATE correo_buzones SET uidvalidity=?, ultimo_uid=?, ultima_lectura=datetime('now','localtime'), "
            "estado='OK', ultimo_error=NULL WHERE id=?", (uv, maxuid, b["id"]))
        return {"buzon": b["email"], "nuevos": nuevos}
    except Exception as e:
        err = _explicar_error(e, b)
        _ex("UPDATE correo_buzones SET estado='ERROR', ultimo_error=?, ultima_lectura=datetime('now','localtime') "
            "WHERE id=?", (err, b["id"]))
        logger.warning("Buzón %s: %s", b["email"], err)
        return {"buzon": b["email"], "nuevos": nuevos, "error": err}


def _guardar(b: dict[str, Any], uid: int, msg: email.message.Message) -> int:
    nombre, rem = parseaddr(_dec(msg.get("From")))
    asunto = _dec(msg.get("Subject"))
    try:
        fecha = parsedate_to_datetime(msg.get("Date")).astimezone().replace(tzinfo=None)
    except Exception:
        fecha = datetime.now()
    cuerpo, adjuntos = _texto(msg)
    return guardar_correo(b["id"], uid, msg.get("Message-ID") or f"uid-{uid}", fecha, rem, nombre, asunto, cuerpo,
                          adjuntos)


def guardar_correo(buzon_id: int, uid: int | None, message_id: str, fecha: datetime, remitente: str, nombre: str,
                   asunto: str, cuerpo: str, adjuntos: list[str]) -> int:
    cat, motivo = clasificar(remitente, asunto, cuerpo, adjuntos)
    datos = emisor_factura(asunto) if cat == "FACTURA" else {}
    conn = get_conn()
    cur = conn.execute(
        "INSERT OR IGNORE INTO correo_bandeja (buzon_id, uid, message_id, fecha, remitente, remitente_nombre, asunto, "
        "resumen, adjuntos, categoria, motivo, datos, estado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (buzon_id, uid, message_id.strip(), fecha.isoformat(sep=" ", timespec="seconds"), remitente.lower(), nombre,
         asunto[:500], cuerpo[:1200], json.dumps(adjuntos, ensure_ascii=False), cat, motivo,
         json.dumps(datos, ensure_ascii=False), "NUEVO" if nivel_categoria(cat) != "NO" else "ARCHIVADO"))
    conn.commit()
    n = cur.rowcount
    conn.close()
    return n


def leer_todos() -> dict[str, Any]:
    """Tarea programada: lee todos los buzones activos y re-escanea alertas si hubo correos nuevos."""
    res = [leer_buzon(b) for b in listar_buzones() if b["activo"]]
    total = sum(r["nuevos"] for r in res)
    if total:
        try:
            from modulos import motor_alertas
            motor_alertas.escanear()
        except Exception as e:
            logger.warning("Alertas tras leer correos: %s", e)
    return {"nuevos": total, "buzones": res}


# ───────────────────────── Niveles por categoría (los ajusta el usuario) ─────────────────────────

def niveles() -> dict[str, str]:
    inicializar()
    r = _q("SELECT valor FROM correo_meta WHERE clave='niveles'")
    guardado = json.loads(r[0]["valor"]) if r else {}
    return {k: guardado.get(k, v["nivel"]) for k, v in CATEGORIAS.items()}


def nivel_categoria(cat: str) -> str:
    return niveles().get(cat, "NO")


def guardar_niveles(n: dict[str, str]) -> None:
    conn = get_conn()
    conn.execute("INSERT INTO correo_meta(clave, valor) VALUES ('niveles', ?) "
                 "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (json.dumps(n),))
    conn.commit()
    conn.close()


# ───────────────────────── Bandeja ─────────────────────────

def bandeja(estado: str | None = "NUEVO", categoria: str | None = None, buzon_id: int | None = None,
            dias: int = 30, limite: int = 300) -> list[dict[str, Any]]:
    inicializar()
    sql = ("SELECT c.*, b.email buzon FROM correo_bandeja c JOIN correo_buzones b ON b.id=c.buzon_id "
           "WHERE c.fecha >= ?")
    p: list[Any] = [(datetime.now() - timedelta(days=dias)).isoformat(sep=" ")]
    if estado:
        sql += " AND c.estado=?"
        p.append(estado)
    if categoria:
        sql += " AND c.categoria=?"
        p.append(categoria)
    if buzon_id:
        sql += " AND c.buzon_id=?"
        p.append(buzon_id)
    sql += " ORDER BY c.fecha DESC LIMIT ?"
    p.append(limite)
    filas = _q(sql, tuple(p))
    for f in filas:
        f["adjuntos"] = json.loads(f.get("adjuntos") or "[]")
        f["datos"] = json.loads(f.get("datos") or "{}")
    return filas


def marcar(cid: int, estado: str = "ATENDIDO") -> dict[str, Any]:
    _ex("UPDATE correo_bandeja SET estado=?, atendido_en=datetime('now','localtime') WHERE id=?", (estado, cid))
    return {"ok": True}


def reclasificar(cid: int, categoria: str) -> None:
    _ex("UPDATE correo_bandeja SET categoria=?, motivo='ajustado a mano', estado=CASE WHEN ?='NO' THEN 'ARCHIVADO' "
        "ELSE estado END WHERE id=?", (categoria, nivel_categoria(categoria), cid))


def resumen() -> dict[str, Any]:
    inicializar()
    nv = niveles()
    filas = _q("SELECT categoria, COUNT(*) n FROM correo_bandeja WHERE estado='NUEVO' GROUP BY categoria")
    por = {f["categoria"]: f["n"] for f in filas}
    return {"por_categoria": por, "importantes": sum(n for c, n in por.items() if nv.get(c) in ("CRITICO", "URGENTE")),
            "buzones": listar_buzones()}


# ───────────────────────── Regla para el motor de alertas ─────────────────────────

def alertas(hoy: date) -> list[dict[str, Any]]:
    """Condiciones vivas para modulos.motor_alertas (regla 'correos')."""
    from modulos.motor_alertas import A
    inicializar()
    nv = niveles()
    out = []
    limite = (datetime.now() - timedelta(days=15)).isoformat(sep=" ")
    for c in _q("SELECT c.*, b.email buzon FROM correo_bandeja c JOIN correo_buzones b ON b.id=c.buzon_id "
                "WHERE c.estado='NUEVO' ORDER BY c.fecha DESC LIMIT 400"):
        nivel = nv.get(c["categoria"], "NO")
        if nivel == "NO" or (nivel != "CRITICO" and str(c["fecha"]) < limite):
            continue
        cat = CATEGORIAS.get(c["categoria"], {}).get("nombre", c["categoria"])
        de = c["remitente_nombre"] or c["remitente"]
        out.append(A(f"correo:{c['id']}", nivel, "correos", f"{cat}: {c['asunto'] or '(sin asunto)'}"[:240],
                     f"De {de} → {c['buzon']} · {str(c['fecha'])[:16]} · {c['motivo'] or ''}. "
                     f"{(c['resumen'] or '')[:220]}", accion=("atender", c["id"]), ir_a="Correos"))
    for b in listar_buzones():
        if not b["activo"]:
            continue
        if not b["tiene_clave"]:
            out.append(A(f"buzon:clave:{b['id']}", "AVISO", "correos", f"Falta conectar el buzón {b['email']}",
                         "Ejecute scripts\\configurar_buzon.ps1 en el computador de Shaki y escriba la contraseña "
                         "(en Gmail, la contraseña de aplicación).", ir_a="Correos"))
        elif b["estado"] == "ERROR":
            out.append(A(f"buzon:error:{b['id']}", "URGENTE", "correos", f"No se pudo leer {b['email']}",
                         b.get("ultimo_error") or "", ir_a="Correos"))
    return out
