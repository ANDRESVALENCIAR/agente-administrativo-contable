"""
Módulo de pagos: CXP administrativos, registro de pagos y revisión de nómina.
"""
import logging
import sqlite3
from datetime import date, datetime

import pandas as pd

from config import cfg
from conexiones.claude_client import llamar_claude
from conexiones.gmail_client import enviar_correo
from conexiones.onedrive_client import leer_excel, actualizar_celda
from database import registrar_accion

logger = logging.getLogger(__name__)


def _clasificar_prioridad(dias: int) -> str:
    """Clasifica prioridad según días al vencimiento."""
    if dias < 0:
        return "VENCIDO"
    if dias == 0:
        return "HOY"
    if dias <= 3:
        return "URGENTE"
    if dias <= 7:
        return "PROXIMO"
    return "NORMAL"


def revisar_cxp_diario() -> None:
    """
    Lee CXP administrativos, inserta pagos pendientes y envía resumen a tesorería.
    """
    logger.info("Revisando CXP administrativos...")
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
    """
    Marca un pago como ejecutado en SQLite, registra historial y actualiza Excel.

    Args:
        pago_id: ID del pago en pagos_pendientes.
        fecha: Fecha de pago (ISO).
        referencia: Referencia bancaria.

    Returns:
        True si se actualizó correctamente.
    """
    logger.info("Registrando pago %s ref %s", pago_id, referencia)
    try:
        conn = sqlite3.connect(cfg.DATABASE_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT proveedor, concepto, monto, estado FROM pagos_pendientes WHERE id=?",
            (pago_id,),
        )
        row = c.fetchone()
        if not row:
            logger.warning("Pago %s no encontrado", pago_id)
            conn.close()
            return False
        proveedor, concepto, monto, estado = row
        if estado not in ("APROBADO", "PENDIENTE"):
            logger.warning("Pago %s en estado %s — no se puede ejecutar", pago_id, estado)
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


def revision_nomina() -> None:
    """Verifica cálculos de nómina según normativa colombiana con Claude."""
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
    except Exception as e:
        logger.error("Error revision_nomina: %s", e)
        registrar_accion("pagos", "revision_nomina", str(e), "ERROR", detalle_error=str(e))
