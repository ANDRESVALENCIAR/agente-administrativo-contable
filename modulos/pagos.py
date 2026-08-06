"""
Módulo de pagos: CONTROL DE PAGOS (Excel), aprobación, ejecución y nómina.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Any

import pandas as pd
from openpyxl import Workbook

from config import cfg, en_modo_demo
from conexiones.claude_client import llamar_claude
from conexiones.gmail_client import enviar_correo
from conexiones.onedrive_client import actualizar_celda, leer_excel
from database import crear_alerta, get_conn, registrar_accion
from utils.sync_pagos import (
    calcular_estado,
    exportar_sqlite_a_excel,
    importar_excel_a_sqlite,
    inicializar_tablas_pagos,
    sincronizar_bidireccional,
)

logger = logging.getLogger(__name__)


def _clasificar_prioridad(dias: int) -> str:
    """Clasifica prioridad según días al vencimiento (legacy CXP)."""
    if dias < 0:
        return "VENCIDO"
    if dias == 0:
        return "HOY"
    if dias <= 3:
        return "URGENTE"
    if dias <= 7:
        return "PROXIMO"
    return "NORMAL"


def _log_cambio(pago_id: int, campo: str, anterior: Any, nuevo: Any, quien: str = "SISTEMA") -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO pagos_log (pago_id, campo_modificado, valor_anterior, valor_nuevo, modificado_por)
           VALUES (?,?,?,?,?)""",
        (pago_id, campo, str(anterior) if anterior is not None else None, str(nuevo) if nuevo is not None else None, quien),
    )
    conn.commit()
    conn.close()


def aprobar_pago_control(pago_id: int, usuario: str = "ADMIN", comentario: str = "") -> bool:
    """Marca pago como APROBADO y registra en pagos_aprobaciones."""
    inicializar_tablas_pagos()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT estado FROM pagos WHERE id=?", (pago_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    anterior = row[0]
    c.execute(
        "UPDATE pagos SET estado='APROBADO', actualizado_en=CURRENT_TIMESTAMP WHERE id=?",
        (pago_id,),
    )
    c.execute(
        """INSERT INTO pagos_aprobaciones (pago_id, accion, usuario, comentario)
           VALUES (?,'APROBAR',?,?)""",
        (pago_id, usuario, comentario or None),
    )
    conn.commit()
    conn.close()
    _log_cambio(pago_id, "estado", anterior, "APROBADO", usuario)
    return True


def rechazar_pago_control(pago_id: int, usuario: str = "ADMIN", comentario: str = "") -> bool:
    """Marca pago como RECHAZADO."""
    inicializar_tablas_pagos()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT estado FROM pagos WHERE id=?", (pago_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    anterior = row[0]
    c.execute(
        "UPDATE pagos SET estado='RECHAZADO', actualizado_en=CURRENT_TIMESTAMP WHERE id=?",
        (pago_id,),
    )
    c.execute(
        """INSERT INTO pagos_aprobaciones (pago_id, accion, usuario, comentario)
           VALUES (?,'RECHAZAR',?,?)""",
        (pago_id, usuario, comentario or None),
    )
    conn.commit()
    conn.close()
    _log_cambio(pago_id, "estado", anterior, "RECHAZADO", usuario)
    return True


def marcar_pago_ejecutado(
    pago_id: int,
    fecha_pago: str,
    valor_pagado: float | None = None,
    cuenta: str | None = None,
    referencia: str | None = None,
    sincronizar_excel: bool = True,
) -> bool:
    """Marca como PAGADO, actualiza montos/cuenta y opcionalmente Excel."""
    inicializar_tablas_pagos()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT estado, valor_a_pagar, proveedor, detalle FROM pagos WHERE id=?",
        (pago_id,),
    )
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    estado, valor_a_pagar, proveedor, detalle = row
    monto = valor_pagado if valor_pagado is not None else valor_a_pagar
    c.execute(
        """UPDATE pagos SET
            estado='PAGADO', fecha_pago=?, valor_pagado=?,
            cuenta_origen_destino=COALESCE(?, cuenta_origen_destino),
            pago_total=COALESCE(?, pago_total),
            actualizado_en=CURRENT_TIMESTAMP
           WHERE id=?""",
        (fecha_pago, monto, cuenta, referencia, pago_id),
    )
    c.execute(
        """INSERT INTO historial_pagos (proveedor, concepto, valor, fecha_pago, comprobante, estado)
           VALUES (?,?,?,?,?,'PAGADO')""",
        (proveedor, detalle, monto, fecha_pago, referencia or cuenta or ""),
    )
    conn.commit()
    conn.close()
    _log_cambio(pago_id, "estado", estado, "PAGADO", "ADMIN")
    if sincronizar_excel:
        try:
            exportar_sqlite_a_excel()
        except Exception as e:
            logger.warning("No se pudo exportar pago %s al Excel: %s", pago_id, e)
    registrar_accion("pagos", "marcar_pago_ejecutado", f"Pago {pago_id} PAGADO", "EXITOSO")
    return True


def crear_pago_manual(datos: dict[str, Any], aprobar: bool = False) -> int:
    """Inserta pago con origen=MANUAL. Retorna id."""
    inicializar_tablas_pagos()
    fl = datos["fecha_limite"]
    if isinstance(fl, datetime):
        fl = fl.date()
    if isinstance(fl, date):
        fl_s = fl.isoformat()
    else:
        fl_s = str(fl)
    estado = "APROBADO" if aprobar else calcular_estado(
        date.fromisoformat(fl_s) if isinstance(fl_s, str) else fl,
        None,
    )
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO pagos (
            prioridad, dia_semana, fecha_limite, detalle, proveedor, periodo, anio,
            centro_costos, valor_a_pagar, cuenta_origen_destino, observaciones,
            periodicidad, estado, origen, actualizado_en
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
        (
            int(datos.get("prioridad") or 4),
            datos.get("dia_semana"),
            fl_s,
            datos["detalle"],
            datos.get("proveedor"),
            datos.get("periodo"),
            datos.get("anio"),
            datos.get("centro_costos"),
            datos.get("valor_a_pagar"),
            datos.get("cuenta_origen_destino"),
            datos.get("observaciones"),
            datos.get("periodicidad"),
            estado,
            "MANUAL",
        ),
    )
    pago_id = int(c.lastrowid)
    if aprobar:
        c.execute(
            """INSERT INTO pagos_aprobaciones (pago_id, accion, usuario, comentario)
               VALUES (?,'APROBAR','ADMIN','Alta manual')""",
            (pago_id,),
        )
    conn.commit()
    conn.close()
    return pago_id


def actualizar_valor_a_pagar(pago_id: int, valor: float) -> None:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT valor_a_pagar FROM pagos WHERE id=?", (pago_id,))
    row = c.fetchone()
    anterior = row[0] if row else None
    c.execute(
        "UPDATE pagos SET valor_a_pagar=?, actualizado_en=CURRENT_TIMESTAMP WHERE id=?",
        (valor, pago_id),
    )
    conn.commit()
    conn.close()
    _log_cambio(pago_id, "valor_a_pagar", anterior, valor, "ADMIN")


def listar_proveedores() -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT DISTINCT proveedor FROM pagos
           WHERE proveedor IS NOT NULL AND TRIM(proveedor) != ''
           ORDER BY proveedor"""
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def query_pagos(
    estados: list[str] | None = None,
    centros: list[str] | None = None,
    periodicidades: list[str] | None = None,
    proveedor: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    proximos_dias: int | None = None,
) -> pd.DataFrame:
    """Consulta filtrada de la tabla pagos."""
    inicializar_tablas_pagos()
    sql = "SELECT * FROM pagos WHERE 1=1"
    params: list[Any] = []
    if estados:
        sql += f" AND estado IN ({','.join('?' * len(estados))})"
        params.extend(estados)
    if centros:
        sql += f" AND centro_costos IN ({','.join('?' * len(centros))})"
        params.extend(centros)
    if periodicidades:
        sql += f" AND periodicidad IN ({','.join('?' * len(periodicidades))})"
        params.extend(periodicidades)
    if proveedor:
        sql += " AND proveedor LIKE ?"
        params.append(f"%{proveedor}%")
    if fecha_desde:
        sql += " AND fecha_limite >= ?"
        params.append(fecha_desde)
    if fecha_hasta:
        sql += " AND fecha_limite <= ?"
        params.append(fecha_hasta)
    if proximos_dias is not None:
        hoy = date.today()
        sql += " AND fecha_limite BETWEEN ? AND ?"
        params.append(hoy.isoformat())
        params.append((hoy + timedelta(days=proximos_dias)).isoformat())
    sql += " ORDER BY fecha_limite ASC, prioridad ASC, id ASC"
    conn = get_conn()
    df = pd.read_sql(sql, conn, params=params)
    conn.close()
    return df


def exportar_pagos_filtrados_excel(df: pd.DataFrame) -> bytes:
    """Genera .xlsx con los filtros aplicados."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Pagos"
    cols = [
        "fecha_limite",
        "detalle",
        "proveedor",
        "centro_costos",
        "valor_a_pagar",
        "valor_pagado",
        "fecha_pago",
        "estado",
        "periodicidad",
        "observaciones",
        "cuenta_origen_destino",
    ]
    headers = [
        "Fecha límite",
        "Detalle",
        "Proveedor",
        "Centro",
        "Valor a pagar",
        "Valor pagado",
        "Fecha pago",
        "Estado",
        "Periodicidad",
        "Observaciones",
        "Cuenta",
    ]
    ws.append(headers)
    for _, r in df.iterrows():
        ws.append([r.get(c) for c in cols])
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


# ── Callbacks calendario ──────────────────────────────────────────────


def revisar_pagos_pendientes() -> dict[str, Any]:
    """Actualiza estados y crea alertas de vencidos/hoy."""
    from utils.sync_pagos import actualizar_estados_pagos
    from utils.alertas_pagos import generar_alertas_pagos

    n = actualizar_estados_pagos()
    for a in generar_alertas_pagos():
        nivel = {"CRITICA": "CRITICO", "ALTA": "URGENTE", "MEDIA": "AVISO"}.get(a["prioridad"], "AVISO")
        crear_alerta(nivel, "pagos", a["mensaje"], a.get("tipo", "PAGOS"))
    registrar_accion("pagos", "revisar_pagos_pendientes", f"estados_act={n}", "EXITOSO")
    return {"estados_actualizados": n}


def alerta_pagos_manana() -> dict[str, int]:
    manana = (date.today() + timedelta(days=1)).isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """SELECT COUNT(*), COALESCE(SUM(valor_a_pagar),0) FROM pagos
           WHERE fecha_limite=? AND estado NOT IN ('PAGADO','RECHAZADO')""",
        (manana,),
    )
    n, total = c.fetchone()
    conn.close()
    if n:
        crear_alerta(
            "URGENTE",
            "pagos",
            f"{n} pago(s) vencen mañana",
            f"Total ≈ ${total:,.0f}",
        )
    return {"pagos_manana": int(n or 0)}


def alerta_nomina_semanal() -> None:
    crear_alerta(
        "CRITICO",
        "pagos",
        "Pago nómina semanal EIF",
        "Recordatorio viernes — verificar PAGO NOMINA SEMANAL en CONTROL DE PAGOS",
    )


def alerta_vencimiento_impuesto(pago_id: int | None = None) -> None:
    if not pago_id:
        return
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT detalle, proveedor, fecha_limite, valor_a_pagar FROM pagos WHERE id=?",
        (pago_id,),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return
    detalle, proveedor, fl, valor = row
    crear_alerta(
        "CRITICO",
        "impuestos",
        f"IMPUESTO: {detalle}",
        f"{proveedor or ''} · Vence {fl} · ${valor or 0:,.0f}",
    )


# ── Legacy CXP OneDrive (compatibilidad) ──────────────────────────────


def revisar_cxp_diario() -> None:
    """
    Preferencia: sincroniza CONTROL_DE_PAGOS.xlsx.
    Fallback: CXP_ADMINISTRATIVOS en OneDrive (flujo anterior).
    """
    logger.info("Revisando pagos / CXP...")
    try:
        res = sincronizar_bidireccional()
        revisar_pagos_pendientes()
        registrar_accion(
            "pagos",
            "revisar_cxp_diario",
            f"sync Excel: {res}",
            "EXITOSO",
        )
        return
    except FileNotFoundError:
        logger.info("CONTROL DE PAGOS no encontrado — fallback OneDrive CXP")
    except Exception as e:
        logger.warning("Sync CONTROL DE PAGOS falló (%s) — fallback CXP", e)

    try:
        df = leer_excel(cfg.EXCEL_CXP_CXC_ID or "demo", "CXP_ADMINISTRATIVOS")
        if df.empty:
            registrar_accion("pagos", "revisar_cxp_diario", "Sin datos CXP", "ERROR")
            return

        pendientes = df[df["ESTADO"].astype(str).str.upper() == "PENDIENTE"]
        conn = sqlite3.connect(cfg.DATABASE_PATH)
        c = conn.cursor()
        filas_html = []

        for _, fila in pendientes.iterrows():
            try:
                fv = pd.to_datetime(fila["FECHA_VENCIMIENTO"]).date()
            except Exception:
                fv = date.today()
            dias = (fv - date.today()).days
            prioridad = _clasificar_prioridad(dias)
            monto = float(fila["MONTO"])
            proveedor = str(fila["PROVEEDOR"])
            concepto = str(fila.get("CONCEPTO", ""))

            c.execute(
                """INSERT INTO pagos_pendientes
                (proveedor, concepto, monto, fecha_vencimiento, dias_vencimiento,
                 prioridad, cuenta_bancaria, tipo_pago, estado)
                SELECT ?,?,?,?,?,?,?,?,'PENDIENTE'
                WHERE NOT EXISTS (
                    SELECT 1 FROM pagos_pendientes
                    WHERE proveedor=? AND concepto=? AND estado='PENDIENTE'
                )""",
                (
                    proveedor,
                    concepto,
                    monto,
                    fv.isoformat(),
                    dias,
                    prioridad,
                    str(fila.get("CUENTA_BANCARIA", "")),
                    str(fila.get("TIPO_PAGO", "")),
                    proveedor,
                    concepto,
                ),
            )
            filas_html.append(
                f"<tr><td>{prioridad}</td><td>{proveedor}</td><td>{concepto}</td>"
                f"<td>${monto:,.0f}</td><td>{fv.strftime('%d/%m/%Y')}</td></tr>"
            )

        conn.commit()
        conn.close()

        if filas_html:
            html = f"""
            <h2>CXP Administrativos — {datetime.now().strftime('%d/%m/%Y')}</h2>
            <table border='1' cellpadding='6'>
            <tr><th>Prioridad</th><th>Proveedor</th><th>Concepto</th><th>Monto</th><th>Vence</th></tr>
            {''.join(filas_html)}
            </table>
            """
            enviar_correo(
                cfg.EMAIL_TESORERIA or "tesoreria@empresa.com",
                f"Resumen CXP {datetime.now().strftime('%d/%m/%Y')}",
                html,
            )

        registrar_accion(
            "pagos",
            "revisar_cxp_diario",
            f"{len(filas_html)} pagos identificados",
            "EXITOSO",
        )
    except Exception as e:
        logger.error("Error revisar_cxp_diario: %s", e, exc_info=True)
        registrar_accion("pagos", "revisar_cxp_diario", str(e), "ERROR", detalle_error=str(e))


def registrar_pago_ejecutado(pago_id: int, fecha: str, referencia: str) -> bool:
    """Compat: marca pago en pagos_pendientes (flujo legacy)."""
    logger.info("Registrando pago legacy %s ref %s", pago_id, referencia)
    try:
        conn = sqlite3.connect(cfg.DATABASE_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT proveedor, concepto, monto, estado FROM pagos_pendientes WHERE id=?",
            (pago_id,),
        )
        row = c.fetchone()
        if not row:
            conn.close()
            return False
        proveedor, concepto, monto, estado = row
        if estado not in ("APROBADO", "PENDIENTE"):
            conn.close()
            return False

        c.execute(
            """UPDATE pagos_pendientes SET estado='PAGADO', fecha_decision=?
               WHERE id=?""",
            (datetime.now(), pago_id),
        )
        c.execute(
            """INSERT INTO historial_pagos (proveedor, concepto, valor, fecha_pago, comprobante, estado)
               VALUES (?,?,?,?,?, 'PAGADO')""",
            (proveedor, concepto, monto, fecha, referencia),
        )
        conn.commit()
        conn.close()

        if cfg.EXCEL_CXP_CXC_ID:
            actualizar_celda(cfg.EXCEL_CXP_CXC_ID, "CXP_ADMINISTRATIVOS", "G1", "PAGADO")

        registrar_accion(
            "pagos",
            "registrar_pago_ejecutado",
            f"Pago {pago_id} {proveedor} — ref {referencia}",
            "EXITOSO",
        )
        return True
    except Exception as e:
        logger.error("Error registrando pago: %s", e)
        return False


def revision_nomina() -> str:
    """Verifica cálculos de nómina con Claude si hay API key; si no, mensaje claro."""
    if en_modo_demo() or not (cfg.ANTHROPIC_API_KEY or "").strip():
        msg = "Active la API key para usar esta función"
        registrar_accion("pagos", "revision_nomina", msg, "ERROR")
        return msg

    logger.info("Revisión de nómina...")
    try:
        df = leer_excel(cfg.EXCEL_PERSONAL_ID or "demo", "NOMINA")
        if df.empty:
            df_resumen = "Sin datos de nómina — modo demo activo."
        else:
            df_resumen = df.head(20).to_string()

        prompt = f"""Revisa estos datos de nómina colombiana y verifica:
- Salud empleado: 4%
- Pensión empleado: 4%
- ARL según nivel de riesgo
Reporta inconsistencias encontradas.

Datos:
{df_resumen}"""
        informe = llamar_claude(prompt, modulo="pagos", max_tokens=2000)
        html = f"<h2>Revisión nómina — {datetime.now().strftime('%d/%m/%Y')}</h2><pre>{informe}</pre>"
        for destino in [cfg.EMAIL_RRHH, cfg.EMAIL_CONTABILIDAD]:
            if destino:
                enviar_correo(destino, "Revisión nómina automática", html)
        registrar_accion("pagos", "revision_nomina", "Informe enviado", "EXITOSO")
        return informe
    except Exception as e:
        logger.error("Error revision_nomina: %s", e)
        registrar_accion("pagos", "revision_nomina", str(e), "ERROR", detalle_error=str(e))
        return str(e)
