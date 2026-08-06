"""Alertas del módulo PAGOS para dashboard e inicio."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from database import get_conn


def resumen_pagos_widget() -> dict[str, Any]:
    """Mini-resumen para widget de inicio."""
    hoy = date.today()
    lim7 = (hoy + timedelta(days=7)).isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM pagos WHERE estado='VENCIDO'")
    vencidos = c.fetchone()[0]
    c.execute(
        "SELECT COUNT(*) FROM pagos WHERE fecha_limite=? AND estado NOT IN ('PAGADO','RECHAZADO')",
        (hoy.isoformat(),),
    )
    hoy_n = c.fetchone()[0]
    c.execute(
        """SELECT COUNT(*) FROM pagos
           WHERE fecha_limite BETWEEN ? AND ?
             AND estado NOT IN ('PAGADO','RECHAZADO')""",
        (hoy.isoformat(), lim7),
    )
    prox7 = c.fetchone()[0]
    c.execute(
        """SELECT COALESCE(SUM(COALESCE(valor_a_pagar,0) - COALESCE(valor_pagado,0)),0)
           FROM pagos WHERE estado NOT IN ('PAGADO','RECHAZADO')"""
    )
    pendiente = float(c.fetchone()[0] or 0)
    c.execute("SELECT COUNT(*) FROM pagos WHERE estado='APROBADO'")
    aprobados = c.fetchone()[0]
    conn.close()
    return {
        "vencidos": vencidos,
        "hoy": hoy_n,
        "proximos_7d": prox7,
        "total_pendiente": pendiente,
        "aprobados": aprobados,
    }


def generar_alertas_pagos() -> list[dict[str, Any]]:
    """Lista de alertas para el panel principal / alertas globales."""
    alertas: list[dict[str, Any]] = []
    hoy = date.today()
    conn = get_conn()

    try:
        vencidos = pd.read_sql(
            "SELECT id FROM pagos WHERE estado='VENCIDO'",
            conn,
        )
        if len(vencidos) > 0:
            alertas.append(
                {
                    "icono": "🔴",
                    "tipo": "PAGOS",
                    "mensaje": f"{len(vencidos)} pago(s) VENCIDO(S) sin pagar",
                    "prioridad": "CRITICA",
                    "modulo": "PAGOS",
                }
            )

        pagos_hoy = pd.read_sql(
            """SELECT id FROM pagos
               WHERE fecha_limite=? AND estado NOT IN ('PAGADO','RECHAZADO')""",
            conn,
            params=(hoy.isoformat(),),
        )
        if len(pagos_hoy) > 0:
            alertas.append(
                {
                    "icono": "🟠",
                    "tipo": "PAGOS",
                    "mensaje": f"{len(pagos_hoy)} pago(s) vencen HOY",
                    "prioridad": "ALTA",
                    "modulo": "PAGOS",
                }
            )

        lim15 = (hoy + timedelta(days=15)).isoformat()
        impuestos = pd.read_sql(
            """SELECT id, detalle, fecha_limite FROM pagos
               WHERE UPPER(COALESCE(periodicidad,'')) LIKE '%IMPUESTO%'
                 AND fecha_limite BETWEEN ? AND ?
                 AND estado NOT IN ('PAGADO','RECHAZADO')""",
            conn,
            params=(hoy.isoformat(), lim15),
        )
        if len(impuestos) > 0:
            alertas.append(
                {
                    "icono": "🟣",
                    "tipo": "IMPUESTOS",
                    "mensaje": f"{len(impuestos)} impuesto(s) vencen en ≤15 días",
                    "prioridad": "CRITICA",
                    "modulo": "IMPUESTOS",
                }
            )

        aprobados = pd.read_sql(
            "SELECT id FROM pagos WHERE estado='APROBADO'",
            conn,
        )
        if len(aprobados) > 0:
            alertas.append(
                {
                    "icono": "🔵",
                    "tipo": "PAGOS",
                    "mensaje": f"{len(aprobados)} pago(s) APROBADO(S) por ejecutar",
                    "prioridad": "MEDIA",
                    "modulo": "PAGOS",
                }
            )
    except Exception:
        pass
    finally:
        conn.close()

    return alertas
