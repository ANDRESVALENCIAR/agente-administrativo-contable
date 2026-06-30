"""Carpetas inteligentes RRHH — escaneo, clasificación y sync SQLite (sin IA)."""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

from database import get_conn

logger = logging.getLogger(__name__)

EXTENSIONES = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".jpg", ".jpeg", ".png", ".zip"}

DOCS_REQUERIDOS = [
    "cedula_cc",
    "contrato",
    "examen_medico",
    "arl",
    "eps",
    "certificacion_ban",
    "hoja_vida",
    "afiliacion",
]

# (categoría, regex) — orden: más específico primero
REGLAS_CATEGORIA: list[tuple[str, str]] = [
    ("certificacion_lab", r"CERTIFICACION\s*LABORAL|CERTIFICADO\s*LAB"),
    ("certificacion_ban", r"CERTIFICACION\s*BANCARIA|BANCARIA|BANCOLOMBIA"),
    ("cedula_cc", r"\bCC\b|CEDULA|CÉDULA|TARJETA\s*IDENTIDAD"),
    ("contrato", r"CONTRATO|FORMATO\s*CONTRATO"),
    ("examen_medico", r"EXAMEN|PERIODICO|RECOMENDACIONES"),
    ("arl", r"\bARL\b|CARNET\s*ARL|AFILIACION\s*ARL"),
    ("eps", r"\bEPS\b|NUEVA\s*EPS|CARNET\s*EPS"),
    ("hoja_vida", r"HOJA\s*DE\s*VIDA|CURRICULUM|CURRÍCULUM"),
    ("planilla_seguridad", r"PLANILLA|COMP\s*PAGO\s*PLANILLA"),
    ("afiliacion", r"AFILIACION|AFILIACIÓN|FORMULARIO\s*UNICO|COMFANDI|COMPENSAR|\bCAJA\b"),
    ("cesantias", r"CESANTIA|CESANTÍAS|RETIRO\s*CESANTIA"),
    ("policia_antec", r"POLICIA|POLICÍA|ANTECEDENTES"),
    ("procuraduria", r"PROCURADURIA|PROCURADURÍA"),
    ("contraloria", r"CONTRALORIA|CONTRALORÍA"),
    ("documentos_gral", r"DOCUMENTOS\s*GENERALES"),
    ("liquidacion", r"LIQUIDACION|LIQUIDACIÓN"),
    ("memorando", r"MEMORANDO"),
    ("novedad", r"NOVEDAD"),
    ("solicitud", r"SOLICITUD|ANTICIPO"),
    ("dotacion", r"DOTACION|DOTACIÓN"),
    ("colpensiones", r"COLPENSIONES|PENSIONES"),
    ("ruaf", r"\bRUAF\b"),
]

_lock = threading.Lock()
_watcher_activo = False

_DEFAULT_ONEDRIVE = (
    r"c:\Users\micro\OneDrive - viaindustrial.com\16. RRHH PERSONAL FUNCIONES\PERSONAL ACTIVO"
)


def proyecto_root() -> Path:
    return Path(__file__).resolve().parent.parent


def ruta_personal_activo() -> Path:
    env = os.getenv("RRHH_CARPETA_PERSONAL", "").strip()
    if env:
        return Path(env)
    local = proyecto_root() / "PERSONAL ACTIVO"
    if local.is_dir() and any(local.iterdir()):
        return local
    return Path(_DEFAULT_ONEDRIVE) if Path(_DEFAULT_ONEDRIVE).is_dir() else local


def ruta_personal_retirado() -> Path:
    env = os.getenv("RRHH_CARPETA_RETIRADO", "").strip()
    if env:
        return Path(env)
    return proyecto_root() / "PERSONAL RETIRADO"


def clasificar_documento(nombre_archivo: str) -> str:
    """Clasifica un archivo según palabras clave en el nombre."""
    nombre = nombre_archivo.upper()
    for cat, patron in REGLAS_CATEGORIA:
        if re.search(patron, nombre, re.IGNORECASE):
            return cat
    return "otro"


def calcular_completitud(categorias_presentes: list[str]) -> tuple[int, list[str]]:
    cats = set(categorias_presentes)
    faltantes = [d for d in DOCS_REQUERIDOS if d not in cats]
    pct = int((len(DOCS_REQUERIDOS) - len(faltantes)) / len(DOCS_REQUERIDOS) * 100)
    return pct, faltantes


def _nombre_display(nombre_carpeta: str) -> str:
    return nombre_carpeta.strip().title()


def _ignorar_archivo(path: Path) -> bool:
    if path.name.startswith("~$") or path.name.lower() == "desktop.ini":
        return True
    if path.suffix.lower() not in EXTENSIONES:
        return True
    return False


def _log_cambio(c, empleado: str, tipo: str, archivo: str | None = None, categoria: str | None = None) -> None:
    c.execute(
        """INSERT INTO log_cambios_carpetas (empleado, tipo_cambio, archivo, categoria)
           VALUES (?,?,?,?)""",
        (empleado, tipo, archivo, categoria),
    )


def _sync_empleados_legacy(c, nombre_carpeta: str, ruta: str) -> None:
    c.execute("SELECT id FROM empleados WHERE UPPER(nombre)=?", (nombre_carpeta.upper(),))
    if c.fetchone():
        c.execute(
            "UPDATE empleados SET ruta_expediente=?, activo=1 WHERE UPPER(nombre)=?",
            (ruta, nombre_carpeta.upper()),
        )
    else:
        c.execute(
            "INSERT INTO empleados (nombre, ruta_expediente, activo) VALUES (?,?,1)",
            (nombre_carpeta, ruta),
        )


def _escanear_archivos_carpeta(ruta_carpeta: Path) -> list[dict[str, Any]]:
    docs = []
    if not ruta_carpeta.is_dir():
        return docs
    for path in ruta_carpeta.rglob("*"):
        if not path.is_file() or _ignorar_archivo(path):
            continue
        stat = path.stat()
        docs.append(
            {
                "nombre_archivo": path.name,
                "ruta_archivo": str(path.resolve()),
                "categoria": clasificar_documento(path.name),
                "extension": path.suffix.lower(),
                "tamanio_kb": max(int(stat.st_size / 1024), 1),
                "fecha_archivo": datetime.fromtimestamp(stat.st_mtime).date().isoformat(),
            }
        )
    return docs


def _actualizar_completitud_empleado(c, empleado_id: int) -> None:
    c.execute(
        "SELECT DISTINCT categoria FROM documentos_empleado WHERE empleado_id=?",
        (empleado_id,),
    )
    cats = [row[0] for row in c.fetchall()]
    pct, faltantes = calcular_completitud(cats)
    c.execute(
        """UPDATE empleados_carpetas SET
           total_documentos=(SELECT COUNT(*) FROM documentos_empleado WHERE empleado_id=?),
           docs_faltantes=?,
           completitud_pct=?,
           ultima_actualizacion=CURRENT_TIMESTAMP
           WHERE id=?""",
        (empleado_id, json.dumps(faltantes, ensure_ascii=False), pct, empleado_id),
    )


def registrar_nuevo_empleado(nombre_carpeta: str) -> int:
    """Nueva carpeta en PERSONAL ACTIVO → empleado nuevo."""
    base = ruta_personal_activo()
    ruta = base / nombre_carpeta
    if not ruta.is_dir():
        ruta.mkdir(parents=True, exist_ok=True)

    with _lock:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT id FROM empleados_carpetas WHERE nombre_carpeta=?", (nombre_carpeta,))
        row = c.fetchone()
        if row:
            emp_id = row[0]
            c.execute(
                "UPDATE empleados_carpetas SET activo=1, ruta_carpeta=?, ultima_actualizacion=CURRENT_TIMESTAMP WHERE id=?",
                (str(ruta.resolve()), emp_id),
            )
        else:
            c.execute(
                """INSERT INTO empleados_carpetas
                   (nombre_carpeta, nombre_display, ruta_carpeta, activo)
                   VALUES (?,?,?,1)""",
                (nombre_carpeta, _nombre_display(nombre_carpeta), str(ruta.resolve())),
            )
            emp_id = c.lastrowid
            _log_cambio(c, nombre_carpeta, "EMPLEADO_NUEVO")

        actualizar_documentos_empleado(emp_id, ruta, c=c, conn=conn)
        _sync_empleados_legacy(c, nombre_carpeta, str(ruta.resolve()))
        conn.commit()
        conn.close()
    return emp_id or 0


def retirar_empleado(nombre_carpeta: str) -> None:
    """Carpeta eliminada de PERSONAL ACTIVO → empleado retirado (historial conservado)."""
    with _lock:
        conn = get_conn()
        c = conn.cursor()
        c.execute(
            """UPDATE empleados_carpetas SET activo=0, ultima_actualizacion=CURRENT_TIMESTAMP
               WHERE nombre_carpeta=?""",
            (nombre_carpeta,),
        )
        c.execute("UPDATE empleados SET activo=0 WHERE UPPER(nombre)=?", (nombre_carpeta.upper(),))
        _log_cambio(c, nombre_carpeta, "EMPLEADO_RETIRADO")
        conn.commit()
        conn.close()


def actualizar_documentos_empleado(
    empleado_id: int,
    ruta_carpeta: Path,
    c=None,
    conn=None,
) -> dict[str, int]:
    """Escaneo recursivo; detecta altas y bajas de archivos."""
    close = False
    if c is None:
        conn = get_conn()
        c = conn.cursor()
        close = True

    c.execute("SELECT nombre_carpeta FROM empleados_carpetas WHERE id=?", (empleado_id,))
    row = c.fetchone()
    nombre_emp = row[0] if row else ruta_carpeta.name

    en_disco = _escanear_archivos_carpeta(ruta_carpeta)
    rutas_disco = {d["ruta_archivo"] for d in en_disco}

    c.execute("SELECT id, ruta_archivo, nombre_archivo FROM documentos_empleado WHERE empleado_id=?", (empleado_id,))
    en_bd = {r[1]: (r[0], r[2]) for r in c.fetchall()}

    nuevos = 0
    eliminados = 0

    for ruta, (doc_id, nom) in list(en_bd.items()):
        if ruta not in rutas_disco:
            c.execute("DELETE FROM documentos_empleado WHERE id=?", (doc_id,))
            _log_cambio(c, nombre_emp, "ARCHIVO_ELIMINADO", nom)
            eliminados += 1

    for doc in en_disco:
        if doc["ruta_archivo"] in en_bd:
            c.execute(
                """UPDATE documentos_empleado SET categoria=?, tamanio_kb=?, fecha_archivo=?
                   WHERE empleado_id=? AND ruta_archivo=?""",
                (doc["categoria"], doc["tamanio_kb"], doc["fecha_archivo"], empleado_id, doc["ruta_archivo"]),
            )
        else:
            c.execute(
                """INSERT INTO documentos_empleado
                   (empleado_id, nombre_archivo, ruta_archivo, categoria, extension, tamanio_kb, fecha_archivo)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    empleado_id,
                    doc["nombre_archivo"],
                    doc["ruta_archivo"],
                    doc["categoria"],
                    doc["extension"],
                    doc["tamanio_kb"],
                    doc["fecha_archivo"],
                ),
            )
            _log_cambio(c, nombre_emp, "ARCHIVO_NUEVO", doc["nombre_archivo"], doc["categoria"])
            nuevos += 1

    _actualizar_completitud_empleado(c, empleado_id)

    if close:
        conn.commit()
        conn.close()

    return {"nuevos": nuevos, "eliminados": eliminados}


def escanear_carpetas_personal() -> dict[str, Any]:
    """Escaneo completo de PERSONAL ACTIVO/."""
    base = ruta_personal_activo()
    base.mkdir(parents=True, exist_ok=True)

    resumen = {
        "empleados_nuevos": 0,
        "empleados_retirados": 0,
        "archivos_nuevos": 0,
        "archivos_eliminados": 0,
        "total_empleados": 0,
        "total_documentos": 0,
        "ruta": str(base.resolve()),
    }

    with _lock:
        conn = get_conn()
        c = conn.cursor()

        carpetas_disco = {
            p.name: p for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")
        }

        c.execute("SELECT id, nombre_carpeta, ruta_carpeta FROM empleados_carpetas")
        en_bd = {row[1]: (row[0], row[2]) for row in c.fetchall()}

        for nombre, carpeta in carpetas_disco.items():
            if nombre not in en_bd:
                c.execute(
                    """INSERT INTO empleados_carpetas
                       (nombre_carpeta, nombre_display, ruta_carpeta, activo)
                       VALUES (?,?,?,1)""",
                    (nombre, _nombre_display(nombre), str(carpeta.resolve())),
                )
                emp_id = c.lastrowid
                _log_cambio(c, nombre, "EMPLEADO_NUEVO")
                resumen["empleados_nuevos"] += 1
            else:
                emp_id = en_bd[nombre][0]
                c.execute(
                    "UPDATE empleados_carpetas SET ruta_carpeta=?, activo=1 WHERE id=?",
                    (str(carpeta.resolve()), emp_id),
                )

            stats = actualizar_documentos_empleado(emp_id, carpeta, c=c, conn=conn)
            resumen["archivos_nuevos"] += stats["nuevos"]
            resumen["archivos_eliminados"] += stats["eliminados"]
            _sync_empleados_legacy(c, nombre, str(carpeta.resolve()))

        for nombre in en_bd:
            if nombre not in carpetas_disco:
                c.execute("UPDATE empleados_carpetas SET activo=0 WHERE nombre_carpeta=?", (nombre,))
                c.execute("UPDATE empleados SET activo=0 WHERE UPPER(nombre)=?", (nombre.upper(),))
                _log_cambio(c, nombre, "EMPLEADO_RETIRADO")
                resumen["empleados_retirados"] += 1

        c.execute("SELECT COUNT(*) FROM empleados_carpetas WHERE activo=1")
        resumen["total_empleados"] = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM documentos_empleado")
        resumen["total_documentos"] = c.fetchone()[0]

        c.execute(
            """INSERT INTO expediente_sync (id, ultima_sync, archivos_total, empleados_total, carpeta_base)
               VALUES (1, CURRENT_TIMESTAMP, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 ultima_sync=CURRENT_TIMESTAMP,
                 archivos_total=excluded.archivos_total,
                 empleados_total=excluded.empleados_total,
                 carpeta_base=excluded.carpeta_base""",
            (resumen["total_documentos"], resumen["total_empleados"], str(base.resolve())),
        )

        conn.commit()
        conn.close()

    logger.info("Escaneo PERSONAL ACTIVO: %s", resumen)
    return resumen


def archivar_empleado(nombre_carpeta: str) -> str:
    """Mueve carpeta a PERSONAL RETIRADO/ y marca inactivo en BD."""
    origen = ruta_personal_activo() / nombre_carpeta
    if not origen.is_dir():
        raise FileNotFoundError(f"No existe carpeta activa: {origen}")

    dest_base = ruta_personal_retirado()
    dest_base.mkdir(parents=True, exist_ok=True)
    destino = dest_base / nombre_carpeta
    if destino.exists():
        destino = dest_base / f"{nombre_carpeta}_{date.today().isoformat()}"

    shutil.move(str(origen), str(destino))
    retirar_empleado(nombre_carpeta)
    return str(destino.resolve())


def obtener_empleado_por_carpeta(nombre_carpeta: str) -> dict | None:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM empleados_carpetas WHERE nombre_carpeta=?", (nombre_carpeta,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    cols = [d[0] for d in c.description]
    conn.close()
    return dict(zip(cols, row))


def obtener_id_empleado_carpeta(nombre_carpeta: str) -> int | None:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM empleados_carpetas WHERE nombre_carpeta=?", (nombre_carpeta,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def procesar_archivo_nuevo(ruta: Path) -> None:
    """Handler watcher: archivo creado."""
    if _ignorar_archivo(ruta):
        return
    base = ruta_personal_activo()
    try:
        rel = ruta.relative_to(base)
    except ValueError:
        return
    if len(rel.parts) < 2:
        return
    nombre_carpeta = rel.parts[0]
    emp_id = obtener_id_empleado_carpeta(nombre_carpeta)
    if not emp_id:
        emp_id = registrar_nuevo_empleado(nombre_carpeta)
    else:
        actualizar_documentos_empleado(emp_id, base / nombre_carpeta)


def procesar_archivo_eliminado(ruta: Path) -> None:
    if _ignorar_archivo(ruta):
        return
    base = ruta_personal_activo()
    try:
        rel = ruta.relative_to(base)
    except ValueError:
        return
    if len(rel.parts) < 2:
        return
    nombre_carpeta = rel.parts[0]
    emp_id = obtener_id_empleado_carpeta(nombre_carpeta)
    if emp_id:
        actualizar_documentos_empleado(emp_id, base / nombre_carpeta)


def guardar_certificacion_en_carpeta(nombre_empleado: str, pdf_local: str) -> str:
    """Copia certificación PDF a la carpeta del empleado."""
    origen = Path(pdf_local)
    if not origen.is_file():
        raise FileNotFoundError(pdf_local)

    base = ruta_personal_activo()
    carpeta = base / nombre_empleado.upper()
    if not carpeta.is_dir():
        for p in base.iterdir():
            if p.is_dir() and p.name.upper() == nombre_empleado.upper():
                carpeta = p
                break
        else:
            carpeta.mkdir(parents=True)
            registrar_nuevo_empleado(carpeta.name)

    hoy = date.today().isoformat()
    dest = carpeta / f"CERTIFICACION LABORAL {carpeta.name} {hoy}.pdf"
    shutil.copy2(origen, dest)

    emp_id = obtener_id_empleado_carpeta(carpeta.name)
    if emp_id:
        actualizar_documentos_empleado(emp_id, carpeta)
    return str(dest.resolve())


def watcher_esta_activo() -> bool:
    return _watcher_activo


def marcar_watcher_activo(valor: bool = True) -> None:
    global _watcher_activo
    _watcher_activo = valor


def generar_alertas_carpetas() -> int:
    """Crea alertas dashboard desde log y completitud de expedientes."""
    from database import crear_alerta

    nuevas = 0
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        """SELECT empleado, tipo_cambio, archivo, categoria FROM log_cambios_carpetas
           WHERE procesado=0 ORDER BY id"""
    )
    for emp, tipo, arch, cat in c.fetchall():
        if tipo == "EMPLEADO_NUEVO":
            titulo = f"Nuevo empleado detectado: {emp}"
            if not _alerta_existe(c, "personal", titulo):
                crear_alerta("URGENTE", "personal", titulo, "Carpeta nueva en PERSONAL ACTIVO")
                nuevas += 1
        elif tipo == "EMPLEADO_RETIRADO":
            titulo = f"Empleado retirado: {emp}"
            if not _alerta_existe(c, "personal", titulo):
                crear_alerta("URGENTE", "personal", titulo, "Carpeta eliminada de PERSONAL ACTIVO")
                nuevas += 1
        elif tipo == "ARCHIVO_NUEVO" and arch:
            titulo = f"Doc. nuevo: {emp}"
            if not _alerta_existe(c, "personal", titulo):
                crear_alerta("AVISO", "personal", titulo, f"{arch} ({cat or 'otro'})")
                nuevas += 1

    c.execute(
        """SELECT nombre_display, docs_faltantes, completitud_pct FROM empleados_carpetas
           WHERE activo=1 AND completitud_pct < 50"""
    )
    for nom, falt, pct in c.fetchall():
        titulo = f"Expediente incompleto: {nom}"
        if not _alerta_existe(c, "personal", titulo):
            crear_alerta("AVISO", "personal", titulo, f"{pct}% — falta: {falt}")
            nuevas += 1

    c.execute("UPDATE log_cambios_carpetas SET procesado=1 WHERE procesado=0")
    conn.commit()
    conn.close()
    return nuevas


def _alerta_existe(c, modulo: str, titulo: str) -> bool:
    c.execute(
        "SELECT 1 FROM alertas WHERE modulo=? AND titulo=? AND resuelto=0 LIMIT 1",
        (modulo, titulo),
    )
    return c.fetchone() is not None


# Compatibilidad con módulo expediente anterior
def carpeta_personal_base() -> Path:
    return ruta_personal_activo()


def sincronizar_expediente(empleado: str | None = None) -> dict[str, Any]:
    if empleado:
        emp_id = obtener_id_empleado_carpeta(empleado)
        if emp_id:
            actualizar_documentos_empleado(emp_id, ruta_personal_activo() / empleado)
        return {"ok": True, "empleado": empleado}
    r = escanear_carpetas_personal()
    return {
        "ok": True,
        "carpeta": r["ruta"],
        "empleados": r["total_empleados"],
        "archivos": r["total_documentos"],
        "ultima_sync": datetime.now().isoformat(timespec="seconds"),
        **r,
    }


def crear_carpeta_empleado(nombre: str) -> Path:
    base = ruta_personal_activo()
    base.mkdir(parents=True, exist_ok=True)
    carpeta = base / nombre.strip().upper()
    carpeta.mkdir(exist_ok=True)
    (carpeta / "OTROS DOCUMENTOS").mkdir(exist_ok=True)
    registrar_nuevo_empleado(carpeta.name)
    return carpeta


def obtener_estado_sync() -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT ultima_sync, archivos_total, empleados_total, carpeta_base FROM expediente_sync WHERE id=1")
    row = c.fetchone()
    conn.close()
    base = ruta_personal_activo()
    if not row:
        return {
            "ultima_sync": None,
            "archivos_total": 0,
            "empleados_total": 0,
            "carpeta_base": str(base.resolve()),
            "vigilancia_activa": watcher_esta_activo(),
        }
    return {
        "ultima_sync": row[0],
        "archivos_total": row[1],
        "empleados_total": row[2],
        "carpeta_base": row[3] or str(base.resolve()),
        "vigilancia_activa": watcher_esta_activo(),
    }
