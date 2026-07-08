"""
Importación y gestión del ARCHIVO GENERAL PERSONAL FÉNIX 2026.
Alimenta SQLite, sincroniza carpetas PERSONAL ACTIVO y tabla empleados.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from config import cfg
from database import get_conn, registrar_accion

logger = logging.getLogger(__name__)

_DEFAULT_ARCHIVO = (
    r"C:\Users\micro\OneDrive - viaindustrial.com\0. TRABAJANDO HOY"
    r"\Agente ADmin Shaki\ARCHIVO GENERAL PERSONAL FENIX 2026.xlsx"
)

HOJAS_PERSONAL = {
    "PERSONAL EIF NOMINA ACT": "nomina_activo",
    "PERSONAL PRESTACION DE SERV": "prestacion_servicios",
    "PERSONAL EIF RETIRADOS": "retirado",
}

MESES = [
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
]


def ruta_archivo_general() -> Path:
    env = os.getenv("RRHH_ARCHIVO_GENERAL", "").strip()
    if env:
        return Path(env)
    cfg_path = getattr(cfg, "RRHH_ARCHIVO_GENERAL", None)
    if cfg_path and Path(cfg_path).is_file():
        return Path(cfg_path)
    return Path(_DEFAULT_ARCHIVO)


def normalizar_nombre(nombre: str) -> str:
    return re.sub(r"\s+", " ", str(nombre or "").upper().strip())


def _serializar(val: Any) -> Any:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (datetime, date)):
        return val.date().isoformat() if hasattr(val, "date") else str(val)[:10]
    if isinstance(val, pd.Timestamp):
        return val.date().isoformat()
    if isinstance(val, str):
        return val.strip() or None
    if isinstance(val, (int, float)):
        return val
    return str(val)


def _limpiar_cedula(val: Any) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = re.sub(r"[^\d]", "", str(val))
    return s or None


def _buscar_col(df: pd.DataFrame, *candidatos: str) -> str | None:
    cols = {str(c).upper().strip(): c for c in df.columns}
    for cand in candidatos:
        key = cand.upper().strip()
        if key in cols:
            return cols[key]
        for k, orig in cols.items():
            if key in k:
                return orig
    return None


def _fila_dict(row: pd.Series) -> dict[str, Any]:
    return {str(k): _serializar(v) for k, v in row.items()}


def _extraer_campos(row: pd.Series, tipo: str) -> dict[str, Any]:
    datos = _fila_dict(row)
    nombre = datos.get("NOMBRE COMPLETO") or datos.get("NOMBRE")
    cedula = _limpiar_cedula(datos.get("CEDULA"))
    cargo = datos.get("CARGO")
    dept = datos.get("DEPARTAMENTO  C/COSTO") or datos.get("DEPARTAMENTO")
    return {
        "nombre_completo": nombre,
        "cedula": cedula,
        "tipo_plantilla": tipo,
        "activo": 0 if tipo == "retirado" else 1,
        "cargo": cargo,
        "departamento": dept,
        "jefe_inmediato": datos.get("JEFE INMEDIATO"),
        "lugar_labor": datos.get("LUGAR DONDE DESEMPEÑA LAS LABORES")
        or datos.get("LUGAR DONDE DESEMPEA LAS LABORES"),
        "tipo_contrato": datos.get("TIPO DE CONTRATO"),
        "termino": datos.get("TÉRMINO") or datos.get("TERMINO"),
        "fecha_ingreso": datos.get("FECHA INICIO DE CONTRATO"),
        "vencimiento_contrato": datos.get("FECHA DE VENCIMIENTO CONTRATO")
        or datos.get("Vencimiento Contrato"),
        "fecha_preaviso": datos.get("FECHA PLAZO PREAVISO"),
        "fecha_nacimiento": datos.get("FECHA DE NACIMIENTO"),
        "telefono": datos.get("TELEFONO"),
        "email_corporativo": datos.get("CORREO CORPORATIVO"),
        "email_personal": datos.get("CORREO PERSONAL"),
        "direccion": datos.get("DIRECCIÓN") or datos.get("DIRECCION"),
        "barrio": datos.get("BARRIO"),
        "ciudad": datos.get("CIUDAD"),
        "salario_ibc": datos.get("VALOR CONTRATO /IBC Actualizado a 2026")
        or datos.get("VALOR CONTRATO /IBC 2020"),
        "salud": datos.get("SALUD"),
        "pension": datos.get("PENSION"),
        "cesantias": datos.get("CESANTIAS"),
        "caja_compensacion": datos.get("CAJA DE COMPENSACION FAMILIAR"),
        "ref_emergencia": datos.get("EN CASO DE EMERGENCIA LLAMAR A "),
        "parentesco_emergencia": datos.get("PARENTESCO"),
        "tel_emergencia": datos.get("CEL / TEL"),
        "observaciones": datos.get("OBSERVACIONES"),
        "datos_json": json.dumps(datos, ensure_ascii=False),
    }


def _mejor_carpeta(nombre: str, carpetas: list[str]) -> str | None:
    norm = normalizar_nombre(nombre)
    for c in carpetas:
        if normalizar_nombre(c) == norm:
            return c
    tokens = set(norm.split())
    mejor, score_max = None, 0.0
    for c in carpetas:
        ct = set(normalizar_nombre(c).split())
        if not ct:
            continue
        score = len(tokens & ct) / max(len(tokens), 1)
        if score > score_max and score >= 0.55:
            mejor, score_max = c, score
    return mejor


def _upsert_empleado_fenix(c, campos: dict[str, Any], origen: str = "import") -> int:
    cedula = campos.get("cedula")
    nombre = campos.get("nombre_completo")
    if not nombre:
        return 0

    if cedula:
        c.execute("SELECT id FROM empleados_fenix WHERE cedula=?", (cedula,))
        row = c.fetchone()
        if row:
            emp_id = row[0]
            c.execute(
                """UPDATE empleados_fenix SET
                   nombre_completo=?, tipo_plantilla=?, activo=?, cargo=?, departamento=?,
                   jefe_inmediato=?, lugar_labor=?, tipo_contrato=?, termino=?,
                   fecha_ingreso=?, vencimiento_contrato=?, fecha_preaviso=?,
                   fecha_nacimiento=?, telefono=?, email_corporativo=?, email_personal=?,
                   direccion=?, barrio=?, ciudad=?, salario_ibc=?, salud=?, pension=?,
                   cesantias=?, caja_compensacion=?, ref_emergencia=?, parentesco_emergencia=?,
                   tel_emergencia=?, observaciones=?, datos_json=?, origen=?,
                   fecha_actualizacion=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (
                    nombre, campos.get("tipo_plantilla"), campos.get("activo", 1),
                    campos.get("cargo"), campos.get("departamento"), campos.get("jefe_inmediato"),
                    campos.get("lugar_labor"), campos.get("tipo_contrato"), campos.get("termino"),
                    campos.get("fecha_ingreso"), campos.get("vencimiento_contrato"),
                    campos.get("fecha_preaviso"), campos.get("fecha_nacimiento"),
                    campos.get("telefono"), campos.get("email_corporativo"),
                    campos.get("email_personal"), campos.get("direccion"), campos.get("barrio"),
                    campos.get("ciudad"), campos.get("salario_ibc"), campos.get("salud"),
                    campos.get("pension"), campos.get("cesantias"), campos.get("caja_compensacion"),
                    campos.get("ref_emergencia"), campos.get("parentesco_emergencia"),
                    campos.get("tel_emergencia"), campos.get("observaciones"),
                    campos.get("datos_json"), origen, emp_id,
                ),
            )
            return emp_id

    c.execute("SELECT id FROM empleados_fenix WHERE UPPER(nombre_completo)=?", (nombre.upper(),))
    row = c.fetchone()
    if row:
        emp_id = row[0]
        c.execute(
            """UPDATE empleados_fenix SET cedula=COALESCE(?, cedula), tipo_plantilla=?, activo=?,
               cargo=?, departamento=?, datos_json=?, origen=?, fecha_actualizacion=CURRENT_TIMESTAMP
               WHERE id=?""",
            (cedula, campos.get("tipo_plantilla"), campos.get("activo", 1),
             campos.get("cargo"), campos.get("departamento"), campos.get("datos_json"),
             origen, emp_id),
        )
        return emp_id

    c.execute(
        """INSERT INTO empleados_fenix
           (nombre_completo, cedula, tipo_plantilla, activo, cargo, departamento,
            jefe_inmediato, lugar_labor, tipo_contrato, termino, fecha_ingreso,
            vencimiento_contrato, fecha_preaviso, fecha_nacimiento, telefono,
            email_corporativo, email_personal, direccion, barrio, ciudad, salario_ibc,
            salud, pension, cesantias, caja_compensacion, ref_emergencia,
            parentesco_emergencia, tel_emergencia, observaciones, datos_json, origen)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            nombre, cedula, campos.get("tipo_plantilla"), campos.get("activo", 1),
            campos.get("cargo"), campos.get("departamento"), campos.get("jefe_inmediato"),
            campos.get("lugar_labor"), campos.get("tipo_contrato"), campos.get("termino"),
            campos.get("fecha_ingreso"), campos.get("vencimiento_contrato"),
            campos.get("fecha_preaviso"), campos.get("fecha_nacimiento"),
            campos.get("telefono"), campos.get("email_corporativo"),
            campos.get("email_personal"), campos.get("direccion"), campos.get("barrio"),
            campos.get("ciudad"), campos.get("salario_ibc"), campos.get("salud"),
            campos.get("pension"), campos.get("cesantias"), campos.get("caja_compensacion"),
            campos.get("ref_emergencia"), campos.get("parentesco_emergencia"),
            campos.get("tel_emergencia"), campos.get("observaciones"),
            campos.get("datos_json"), origen,
        ),
    )
    return c.lastrowid


def _importar_hojas_personal(c, path: Path) -> int:
    total = 0
    for hoja, tipo in HOJAS_PERSONAL.items():
        try:
            df = pd.read_excel(path, sheet_name=hoja, header=1)
        except Exception as e:
            logger.warning("Hoja %s omitida: %s", hoja, e)
            continue
        col_nom = _buscar_col(df, "NOMBRE COMPLETO")
        if not col_nom:
            continue
        for _, row in df.iterrows():
            if pd.isna(row.get(col_nom)):
                continue
            campos = _extraer_campos(row, tipo)
            if _upsert_empleado_fenix(c, campos):
                total += 1
    return total


def _importar_novedades(c, path: Path) -> int:
    try:
        df = pd.read_excel(path, sheet_name="NOVEDADES 2025", header=5)
    except Exception as e:
        logger.warning("Novedades omitidas: %s", e)
        return 0

    col_nom = _buscar_col(df, "NOMBRE COMPLETO")
    if not col_nom:
        return 0

    col_ced = _buscar_col(df, "CEDULA")
    col_fi = _buscar_col(df, "FECHA DE INGRESO")
    col_dot = _buscar_col(df, "PENDIENTE DOTACIÓN", "PENDIENTE DOTACION")
    col_exam = _buscar_col(df, "EXÁMENES MEDICOS", "EXAMENES MEDICOS")

    c.execute("DELETE FROM novedades_fenix")
    count = 0
    for _, row in df.iterrows():
        nombre = _serializar(row.get(col_nom))
        if not nombre:
            continue
        meses = {}
        for mes in MESES:
            col = _buscar_col(df, mes)
            if col:
                val = _serializar(row.get(col))
                if val:
                    meses[mes] = val
        cedula = _limpiar_cedula(row.get(col_ced)) if col_ced else None
        c.execute("SELECT id FROM empleados_fenix WHERE cedula=? OR UPPER(nombre_completo)=?",
                    (cedula, nombre.upper()))
        emp_row = c.fetchone()
        emp_id = emp_row[0] if emp_row else None

        c.execute(
            """INSERT INTO novedades_fenix
               (empleado_id, nombre_completo, cedula, fecha_ingreso, pendiente_dotacion,
                examenes_periodicos, meses_json)
               VALUES (?,?,?,?,?,?,?)""",
            (
                emp_id, nombre, cedula,
                _serializar(row.get(col_fi)) if col_fi else None,
                _serializar(row.get(col_dot)) if col_dot else None,
                _serializar(row.get(col_exam)) if col_exam else None,
                json.dumps(meses, ensure_ascii=False),
            ),
        )
        count += 1
    return count


def _importar_vacaciones(c, path: Path) -> int:
    c.execute("DELETE FROM vacaciones_fenix")
    count = 0
    hojas = ["VACACIONES 2025-2026", "VACACIONES AFVR 2025-2026"]
    for hoja in hojas:
        try:
            df = pd.read_excel(path, sheet_name=hoja, header=2)
        except Exception:
            continue
        col_nom = _buscar_col(df, "NOMBRE")
        if not col_nom:
            continue
        for _, row in df.iterrows():
            nombre = _serializar(row.get(col_nom))
            if not nombre:
                continue
            c.execute("SELECT id FROM empleados_fenix WHERE UPPER(nombre_completo) LIKE ?",
                        (f"%{nombre.upper()[:20]}%",))
            emp_row = c.fetchone()
            c.execute(
                """INSERT INTO vacaciones_fenix
                   (empleado_id, nombre_completo, hoja_origen, dias_pendientes, dias_tomar,
                    dias_pendientes_2025, fecha_regreso, observaciones, datos_json)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    emp_row[0] if emp_row else None,
                    nombre, hoja,
                    _serializar(row.get(_buscar_col(df, "DIAS PENDIENTES DE VACACIONES", "DIAS PENDIENTES") or "")),
                    _serializar(row.get(_buscar_col(df, "DIAS A TOMARSE") or "")),
                    _serializar(row.get(_buscar_col(df, "DIAS PENDIENTES POR TOMARSE EN 2025") or "")),
                    _serializar(row.get(_buscar_col(df, "DIA DE REGRESO A LABORAR") or "")),
                    _serializar(row.get(_buscar_col(df, "OBSERVACIONES") or "")),
                    json.dumps(_fila_dict(row), ensure_ascii=False),
                ),
            )
            count += 1
    return count


def _importar_cumpleanos(c, path: Path) -> int:
    try:
        df = pd.read_excel(path, sheet_name="CUMPLEAÑOS ", header=1)
    except Exception:
        try:
            df = pd.read_excel(path, sheet_name="CUMPLEAÑOS", header=1)
        except Exception as e:
            logger.warning("Cumpleaños omitidos: %s", e)
            return 0

    c.execute("DELETE FROM cumpleanos_fenix")
    count = 0
    col_nom = _buscar_col(df, "NOMBRE")
    col_dia = _buscar_col(df, "DIA")
    col_mes = _buscar_col(df, "MES")
    for _, row in df.iterrows():
        nombre = _serializar(row.get(col_nom or ""))
        if not nombre:
            continue
        c.execute(
            """INSERT INTO cumpleanos_fenix (nombre, dia, mes) VALUES (?,?,?)""",
            (nombre, _serializar(row.get(col_dia or "")), _serializar(row.get(col_mes or ""))),
        )
        count += 1
    return count


def _importar_contratos_fijos(c, path: Path) -> int:
    try:
        df = pd.read_excel(path, sheet_name=" CONTRATOS FIJOS PREAVISOS", header=1)
    except Exception as e:
        logger.warning("Contratos fijos omitidos: %s", e)
        return 0

    c.execute("DELETE FROM contratos_fijos_fenix")
    count = 0
    col_nom = _buscar_col(df, "NOMBRE COMPLETO")
    for _, row in df.iterrows():
        nombre = _serializar(row.get(col_nom or ""))
        if not nombre:
            continue
        cedula = _limpiar_cedula(row.get(_buscar_col(df, "CEDULA") or ""))
        c.execute("SELECT id FROM empleados_fenix WHERE cedula=? OR UPPER(nombre_completo)=?",
                    (cedula, nombre.upper()))
        emp_row = c.fetchone()
        c.execute(
            """INSERT INTO contratos_fijos_fenix
               (empleado_id, nombre_completo, cedula, cargo, fecha_inicio, termino,
                vencimiento_contrato, fecha_preaviso, datos_json)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                emp_row[0] if emp_row else None, nombre, cedula,
                _serializar(row.get(_buscar_col(df, "CARGO") or "")),
                _serializar(row.get(_buscar_col(df, "FECHA INICIO DE CONTRATO") or "")),
                _serializar(row.get(_buscar_col(df, "TÉRMINO", "TERMINO") or "")),
                _serializar(row.get(_buscar_col(df, "FECHA DE VENCIMIENTO") or "")),
                _serializar(row.get(_buscar_col(df, "FECHA PLAZO", "PREAVISO") or "")),
                json.dumps(_fila_dict(row), ensure_ascii=False),
            ),
        )
        count += 1
    return count


def vincular_carpetas() -> dict[str, int]:
    """Vincula empleados_fenix con empleados_carpetas y actualiza empleados."""
    from modulos.carpetas_rrhh import ruta_personal_activo

    base = ruta_personal_activo()
    carpetas = [p.name for p in base.iterdir() if p.is_dir()] if base.is_dir() else []

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, nombre_completo, cedula FROM empleados_fenix WHERE activo=1")
    empleados = c.fetchall()

    vinculados = 0
    sync_empleados = 0
    for emp_id, nombre, cedula in empleados:
        carpeta = _mejor_carpeta(nombre, carpetas)
        if carpeta:
            c.execute(
                "UPDATE empleados_fenix SET carpeta_vinculada=? WHERE id=?",
                (carpeta, emp_id),
            )
            vinculados += 1
            ruta = str((base / carpeta).resolve())
            c.execute("SELECT id FROM empleados_carpetas WHERE nombre_carpeta=?", (carpeta,))
            if not c.fetchone():
                c.execute(
                    """INSERT INTO empleados_carpetas
                       (nombre_carpeta, nombre_display, ruta_carpeta, activo)
                       VALUES (?,?,?,1)""",
                    (carpeta, carpeta.title(), ruta),
                )

        c.execute("SELECT id FROM empleados WHERE cedula=?", (cedula,))
        emp_legacy = c.fetchone()
        c.execute(
            """SELECT cargo, fecha_ingreso, salario_ibc, tipo_contrato FROM empleados_fenix WHERE id=?""",
            (emp_id,),
        )
        row = c.fetchone()
        if row:
            cargo, fi, sal, tc = row
            sal_num = None
            try:
                sal_num = float(re.sub(r"[^\d.]", "", str(sal or "")) or 0) or None
            except ValueError:
                pass
            if emp_legacy:
                c.execute(
                    """UPDATE empleados SET nombre=?, cargo=?, fecha_ingreso=?, salario=?,
                       tipo_contrato=?, cedula=?, activo=1 WHERE id=?""",
                    (nombre, cargo, fi, sal_num, tc, cedula, emp_legacy[0]),
                )
            else:
                c.execute(
                    """INSERT INTO empleados (nombre, cargo, fecha_ingreso, salario, tipo_contrato, cedula, activo)
                       VALUES (?,?,?,?,?,?,1)""",
                    (nombre, cargo, fi, sal_num, tc, cedula),
                )
            sync_empleados += 1

    c.execute(
        """INSERT OR REPLACE INTO personal_fenix_sync (id, ruta_archivo, ultima_importacion, empleados, vinculados)
           VALUES (1, ?, CURRENT_TIMESTAMP, ?, ?)""",
        (str(ruta_archivo_general()), len(empleados), vinculados),
    )
    conn.commit()
    conn.close()
    return {"vinculados": vinculados, "empleados_sync": sync_empleados}


def importar_archivo_general(ruta: str | Path | None = None) -> dict[str, Any]:
    """Importa el Excel ARCHIVO GENERAL a SQLite y sincroniza carpetas."""
    path = Path(ruta) if ruta else ruta_archivo_general()
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")

    conn = get_conn()
    c = conn.cursor()
    resultado = {
        "archivo": str(path),
        "empleados": _importar_hojas_personal(c, path),
        "novedades": _importar_novedades(c, path),
        "vacaciones": _importar_vacaciones(c, path),
        "cumpleanos": _importar_cumpleanos(c, path),
        "contratos_fijos": _importar_contratos_fijos(c, path),
    }
    conn.commit()
    conn.close()

    resultado.update(vincular_carpetas())
    registrar_accion(
        "personal", "importar_archivo_fenix",
        f"{resultado['empleados']} empleados importados", "EXITOSO",
    )
    logger.info("Importación Fénix completada: %s", resultado)
    return resultado


def guardar_empleado_manual(datos: dict[str, Any]) -> int:
    """Alta o edición manual de empleado en memoria SQLite."""
    conn = get_conn()
    c = conn.cursor()
    campos = {
        "nombre_completo": datos.get("nombre_completo"),
        "cedula": _limpiar_cedula(datos.get("cedula")),
        "tipo_plantilla": datos.get("tipo_plantilla", "nomina_activo"),
        "activo": int(datos.get("activo", 1)),
        "cargo": datos.get("cargo"),
        "departamento": datos.get("departamento"),
        "fecha_ingreso": datos.get("fecha_ingreso"),
        "telefono": datos.get("telefono"),
        "email_corporativo": datos.get("email_corporativo"),
        "salario_ibc": datos.get("salario_ibc"),
        "tipo_contrato": datos.get("tipo_contrato"),
        "observaciones": datos.get("observaciones"),
        "datos_json": json.dumps(datos, ensure_ascii=False),
    }
    emp_id = datos.get("id")
    if emp_id:
        c.execute(
            """UPDATE empleados_fenix SET nombre_completo=?, cedula=?, tipo_plantilla=?, activo=?,
               cargo=?, departamento=?, fecha_ingreso=?, telefono=?, email_corporativo=?,
               salario_ibc=?, tipo_contrato=?, observaciones=?, datos_json=?, origen='manual',
               fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?""",
            (
                campos["nombre_completo"], campos["cedula"], campos["tipo_plantilla"],
                campos["activo"], campos["cargo"], campos["departamento"],
                campos["fecha_ingreso"], campos["telefono"], campos["email_corporativo"],
                campos["salario_ibc"], campos["tipo_contrato"], campos["observaciones"],
                campos["datos_json"], emp_id,
            ),
        )
    else:
        emp_id = _upsert_empleado_fenix(c, campos, origen="manual")
    conn.commit()
    conn.close()
    vincular_carpetas()
    return int(emp_id)


def obtener_estado_importacion() -> dict[str, Any]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM personal_fenix_sync WHERE id=1")
    row = c.fetchone()
    cols = [d[0] for d in c.description] if c.description else []
    sync = dict(zip(cols, row)) if row else {}
    c.execute("SELECT COUNT(*) FROM empleados_fenix WHERE activo=1")
    activos = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM empleados_fenix WHERE activo=0")
    retirados = c.fetchone()[0]
    conn.close()
    return {"sync": sync, "activos": activos, "retirados": retirados, "ruta_default": str(ruta_archivo_general())}
