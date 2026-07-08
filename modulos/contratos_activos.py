"""
Módulo Contratos Activos — alimentado por carpetas PERSONAL ACTIVO,
Archivo General Fénix y edición manual.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime
from typing import Any

from database import get_conn, registrar_accion

logger = logging.getLogger(__name__)

CAMPOS_DOC = [
    ("doc_foto", "doc_foto_ruta", ("foto",)),
    ("doc_cv", "doc_cv_ruta", ("hoja_vida",)),
    ("doc_antecedentes", "doc_antecedentes_ruta", ("policia_antec", "procuraduria", "contraloria")),
    ("doc_contrato", "doc_contrato_ruta", ("contrato",)),
    ("doc_dni", "doc_dni_ruta", ("cedula_cc",)),
    ("doc_recibo_servicios", "doc_recibo_ruta", ("documentos_gral", "otro")),
    ("doc_croquis", "doc_croquis_ruta", ("otro",)),
    ("doc_declaracion", "doc_declaracion_ruta", ("solicitud", "otro")),
    ("doc_certificados", "doc_certificados_ruta", ("certificacion_ban", "certificacion_lab", "afiliacion")),
]

COLUMNAS_INFORME = [
    ("nombre_completo", "NOMBRES Y APELLIDOS"),
    ("cedula", "DNI"),
    ("fecha_ingreso", "FECHA DE INGRESO"),
    ("cargo", "CARGO"),
    ("sueldo_bruto", "SUELDO BRUTO"),
    ("area", "ÁREA"),
    ("modalidad_trabajo", "MODALIDAD DE TRABAJO"),
    ("tipo_contrato", "TIPO DE CONTRATO"),
    ("fecha_inicio", "FECHA INICIO"),
    ("fecha_fin", "FECHA FIN"),
    ("estado", "ESTADO"),
    ("sctr", "SCTR"),
    ("vida_ley", "VIDA LEY"),
    ("examen_medico", "EXAMEN MÉDICO"),
    ("induccion", "INDUCCIÓN"),
    ("epp", "EPP"),
    ("doc_foto", "FOTO"),
    ("doc_cv", "CV"),
    ("doc_antecedentes", "ANTECEDENTES"),
    ("doc_contrato", "CONTRATO FIRMADO"),
    ("doc_dni", "DNI ESCANEADO"),
    ("doc_recibo_servicios", "RECIBO LUZ/AGUA"),
    ("doc_croquis", "CROQUIS"),
    ("doc_declaracion", "DECLARACIÓN JURADA"),
    ("doc_certificados", "CERTIFICADOS"),
]


def _estado_doc(encontrado: bool, nombre: str = "") -> str:
    if encontrado:
        return "SI"
    if nombre and any(k in nombre.upper() for k in ("PENDIENTE", "SOLICIT")):
        return "PENDIENTE"
    return "NO"


def _buscar_doc_carpeta(docs: list[dict], categorias: tuple[str, ...], patron_nombre: str = "") -> tuple[str, str | None]:
    for d in docs:
        cat = (d.get("categoria") or "").lower()
        nombre = (d.get("nombre_archivo") or "").upper()
        if cat in categorias:
            return "SI", d.get("ruta_archivo")
        if patron_nombre and re.search(patron_nombre, nombre, re.I):
            return "SI", d.get("ruta_archivo")
    for d in docs:
        nombre = (d.get("nombre_archivo") or "").upper()
        if patron_nombre and re.search(patron_nombre, nombre, re.I):
            return "SI", d.get("ruta_archivo")
    return "NO", None


def _docs_empleado(c, empleado_carpeta_id: int | None) -> list[dict]:
    if not empleado_carpeta_id:
        return []
    c.execute(
        """SELECT nombre_archivo, ruta_archivo, categoria FROM documentos_empleado
           WHERE empleado_id=?""",
        (empleado_carpeta_id,),
    )
    return [
        {"nombre_archivo": r[0], "ruta_archivo": r[1], "categoria": r[2]}
        for r in c.fetchall()
    ]


def _datos_desde_fenix(c, nombre: str) -> dict[str, Any]:
    c.execute(
        """SELECT nombre_completo, cedula, cargo, departamento, lugar_labor, tipo_contrato,
                  termino, fecha_ingreso, vencimiento_contrato, salario_ibc, salud, carpeta_vinculada
           FROM empleados_fenix WHERE activo=1 AND (
               UPPER(nombre_completo)=? OR UPPER(carpeta_vinculada)=?
           ) LIMIT 1""",
        (nombre.upper(), nombre.upper()),
    )
    row = c.fetchone()
    if not row:
        return {}
    return {
        "nombre_completo": row[0],
        "cedula": row[1],
        "cargo": row[2],
        "area": row[3],
        "modalidad_trabajo": row[4],
        "tipo_contrato": f"{row[5] or ''} {row[6] or ''}".strip(),
        "fecha_ingreso": row[7],
        "fecha_inicio": row[7],
        "fecha_fin": row[8],
        "sueldo_bruto": row[9],
        "sctr": row[10],
        "estado": "ACTIVO",
    }


def sincronizar_contratos_activos() -> dict[str, int]:
    """Sincroniza contratos activos desde carpetas y Archivo General Fénix."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """SELECT id, nombre_carpeta, nombre_display FROM empleados_carpetas WHERE activo=1
           ORDER BY nombre_display"""
    )
    carpetas = c.fetchall()

    if not carpetas:
        c.execute(
            """SELECT id, nombre_completo, carpeta_vinculada FROM empleados_fenix
               WHERE activo=1 AND tipo_plantilla IN ('nomina_activo','prestacion_servicios')"""
        )
        for _, nombre, carpeta in c.fetchall():
            nom = carpeta or nombre
            carpetas.append((None, nom, nombre))

    creados, actualizados = 0, 0
    for emp_id, nombre_carpeta, nombre_display in carpetas:
        nombre_final = nombre_display or nombre_carpeta
        docs = _docs_empleado(c, emp_id)
        fenix = _datos_desde_fenix(c, nombre_carpeta) or _datos_desde_fenix(c, nombre_final)

        campos_doc = {}
        for campo_est, campo_ruta, cats in CAMPOS_DOC:
            patron = ""
            if campo_est == "doc_foto":
                patron = r"FOTO|FOTOCHECK"
            elif campo_est == "doc_recibo_servicios":
                patron = r"RECIBO|LUZ|AGUA|SERVICIO"
            elif campo_est == "doc_croquis":
                patron = r"CROQUIS"
            elif campo_est == "doc_declaracion":
                patron = r"DECLARACION|JURADA"
            est, ruta = _buscar_doc_carpeta(docs, cats, patron)
            campos_doc[campo_est] = est
            campos_doc[campo_ruta] = ruta

        examen = "SI" if any(d.get("categoria") == "examen_medico" for d in docs) else "NO"
        epp = "SI" if any(d.get("categoria") == "dotacion" for d in docs) else "NO"
        arl = "SI" if any(d.get("categoria") == "arl" for d in docs) else fenix.get("sctr", "NO")

        registro = {
            "empleado_carpeta_id": emp_id,
            "nombre_completo": fenix.get("nombre_completo") or nombre_final,
            "cedula": fenix.get("cedula"),
            "fecha_ingreso": fenix.get("fecha_ingreso"),
            "cargo": fenix.get("cargo"),
            "sueldo_bruto": fenix.get("sueldo_bruto"),
            "area": fenix.get("area"),
            "modalidad_trabajo": fenix.get("modalidad_trabajo"),
            "tipo_contrato": fenix.get("tipo_contrato"),
            "fecha_inicio": fenix.get("fecha_inicio"),
            "fecha_fin": fenix.get("fecha_fin"),
            "estado": fenix.get("estado", "ACTIVO"),
            "sctr": arl,
            "examen_medico": examen,
            "epp": epp,
            **campos_doc,
            "origen": "sync",
        }

        c.execute("SELECT id FROM contratos_activos WHERE UPPER(nombre_completo)=?",
                  (registro["nombre_completo"].upper(),))
        existe = c.fetchone()
        if existe:
            c.execute(
                """UPDATE contratos_activos SET
                   empleado_carpeta_id=?, cedula=?, fecha_ingreso=?, cargo=?, sueldo_bruto=?,
                   area=?, modalidad_trabajo=?, tipo_contrato=?, fecha_inicio=?, fecha_fin=?,
                   estado=?, sctr=?, examen_medico=?, epp=?,
                   doc_foto=?, doc_foto_ruta=?, doc_cv=?, doc_cv_ruta=?,
                   doc_antecedentes=?, doc_antecedentes_ruta=?, doc_contrato=?, doc_contrato_ruta=?,
                   doc_dni=?, doc_dni_ruta=?, doc_recibo_servicios=?, doc_recibo_ruta=?,
                   doc_croquis=?, doc_croquis_ruta=?, doc_declaracion=?, doc_declaracion_ruta=?,
                   doc_certificados=?, doc_certificados_ruta=?, origen='sync',
                   fecha_actualizacion=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (
                    registro["empleado_carpeta_id"], registro["cedula"], registro["fecha_ingreso"],
                    registro["cargo"], registro["sueldo_bruto"], registro["area"],
                    registro["modalidad_trabajo"], registro["tipo_contrato"],
                    registro["fecha_inicio"], registro["fecha_fin"], registro["estado"],
                    registro["sctr"], registro["examen_medico"], registro["epp"],
                    registro["doc_foto"], registro["doc_foto_ruta"],
                    registro["doc_cv"], registro["doc_cv_ruta"],
                    registro["doc_antecedentes"], registro["doc_antecedentes_ruta"],
                    registro["doc_contrato"], registro["doc_contrato_ruta"],
                    registro["doc_dni"], registro["doc_dni_ruta"],
                    registro["doc_recibo_servicios"], registro["doc_recibo_ruta"],
                    registro["doc_croquis"], registro["doc_croquis_ruta"],
                    registro["doc_declaracion"], registro["doc_declaracion_ruta"],
                    registro["doc_certificados"], registro["doc_certificados_ruta"],
                    existe[0],
                ),
            )
            actualizados += 1
        else:
            c.execute(
                """INSERT INTO contratos_activos
                   (empleado_carpeta_id, nombre_completo, cedula, fecha_ingreso, cargo, sueldo_bruto,
                    area, modalidad_trabajo, tipo_contrato, fecha_inicio, fecha_fin, estado,
                    sctr, examen_medico, epp, doc_foto, doc_foto_ruta, doc_cv, doc_cv_ruta,
                    doc_antecedentes, doc_antecedentes_ruta, doc_contrato, doc_contrato_ruta,
                    doc_dni, doc_dni_ruta, doc_recibo_servicios, doc_recibo_ruta,
                    doc_croquis, doc_croquis_ruta, doc_declaracion, doc_declaracion_ruta,
                    doc_certificados, doc_certificados_ruta, origen)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    registro["empleado_carpeta_id"], registro["nombre_completo"], registro["cedula"],
                    registro["fecha_ingreso"], registro["cargo"], registro["sueldo_bruto"],
                    registro["area"], registro["modalidad_trabajo"], registro["tipo_contrato"],
                    registro["fecha_inicio"], registro["fecha_fin"], registro["estado"],
                    registro["sctr"], registro["examen_medico"], registro["epp"],
                    registro["doc_foto"], registro["doc_foto_ruta"],
                    registro["doc_cv"], registro["doc_cv_ruta"],
                    registro["doc_antecedentes"], registro["doc_antecedentes_ruta"],
                    registro["doc_contrato"], registro["doc_contrato_ruta"],
                    registro["doc_dni"], registro["doc_dni_ruta"],
                    registro["doc_recibo_servicios"], registro["doc_recibo_ruta"],
                    registro["doc_croquis"], registro["doc_croquis_ruta"],
                    registro["doc_declaracion"], registro["doc_declaracion_ruta"],
                    registro["doc_certificados"], registro["doc_certificados_ruta"],
                    "sync",
                ),
            )
            creados += 1

    conn.commit()
    conn.close()
    registrar_accion(
        "personal", "sincronizar_contratos_activos",
        f"{creados} nuevos, {actualizados} actualizados", "EXITOSO",
    )
    return {"creados": creados, "actualizados": actualizados, "total": creados + actualizados}


def guardar_contrato_activo(datos: dict[str, Any]) -> int:
    """Guarda o actualiza un contrato activo manualmente."""
    conn = get_conn()
    c = conn.cursor()
    reg_id = datos.get("id")
    cols = [
        "nombre_completo", "cedula", "fecha_ingreso", "cargo", "sueldo_bruto", "area",
        "modalidad_trabajo", "tipo_contrato", "fecha_inicio", "fecha_fin", "estado",
        "sctr", "vida_ley", "examen_medico", "induccion", "epp",
        "doc_foto", "doc_cv", "doc_antecedentes", "doc_contrato", "doc_dni",
        "doc_recibo_servicios", "doc_croquis", "doc_declaracion", "doc_certificados",
        "observaciones",
    ]
    valores = [datos.get(col) for col in cols]

    if reg_id:
        sets = ", ".join(f"{col}=?" for col in cols)
        c.execute(
            f"UPDATE contratos_activos SET {sets}, origen='manual', fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?",
            (*valores, reg_id),
        )
    else:
        placeholders = ", ".join("?" * len(cols))
        c.execute(
            f"""INSERT INTO contratos_activos ({",".join(cols)}, origen)
                VALUES ({placeholders}, 'manual')""",
            valores,
        )
        reg_id = c.lastrowid
    conn.commit()
    conn.close()
    return int(reg_id)


def obtener_contrato(reg_id: int) -> dict[str, Any] | None:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM contratos_activos WHERE id=?", (reg_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    cols = [d[0] for d in c.description]
    conn.close()
    return dict(zip(cols, row))


def listar_contratos_activos() -> list[dict[str, Any]]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM contratos_activos WHERE estado='ACTIVO' OR estado IS NULL ORDER BY nombre_completo")
    rows = c.fetchall()
    cols = [d[0] for d in c.description]
    conn.close()
    return [dict(zip(cols, r)) for r in rows]
