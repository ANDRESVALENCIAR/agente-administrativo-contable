"""Verificación centralizada de alertas al cargar el dashboard."""
from datetime import date, datetime, timedelta

from database import crear_alerta, get_conn


def _alerta_existe(modulo: str, titulo: str) -> bool:
    """Evita duplicar alertas activas."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM alertas WHERE modulo=? AND titulo=? AND resuelto=0 LIMIT 1",
        (modulo, titulo),
    )
    ok = c.fetchone() is not None
    conn.close()
    return ok


def verificar_alertas_globales() -> int:
    """
    Ejecuta todas las reglas de alerta del prompt maestro.

    Returns:
        Cantidad de alertas nuevas creadas.
    """
    nuevas = 0
    hoy = date.today()
    conn = get_conn()
    c = conn.cursor()

    # Impuestos < 15 días
    c.execute(
        """SELECT impuesto, periodo, fecha_vencimiento FROM impuestos_maestro
           WHERE estado NOT IN ('PRESENTADO','PAGADO')
           AND fecha_vencimiento <= ?""",
        ((hoy + timedelta(days=15)).isoformat(),),
    )
    for imp, per, fv in c.fetchall():
        titulo = f"Impuesto {imp} {per} vence pronto"
        if not _alerta_existe("impuestos", titulo):
            crear_alerta("URGENTE", "impuestos", titulo, f"Vencimiento: {fv}")
            nuevas += 1

    # Contratos < 30 días
    c.execute(
        """SELECT empleado, fecha_fin FROM contratos_rrhh
           WHERE fecha_fin <= ? AND estado='VIGENTE'""",
        ((hoy + timedelta(days=30)).isoformat(),),
    )
    for emp, ff in c.fetchall():
        titulo = f"Contrato vence: {emp}"
        if not _alerta_existe("personal", titulo):
            crear_alerta("AVISO", "personal", titulo, f"Fin contrato: {ff}")
            nuevas += 1

    # Exámenes médicos < 30 días
    c.execute(
        """SELECT empleado, fecha_vencimiento FROM examenes_medicos
           WHERE fecha_vencimiento <= ?""",
        ((hoy + timedelta(days=30)).isoformat(),),
    )
    for emp, fv in c.fetchall():
        titulo = f"Examen médico: {emp}"
        if not _alerta_existe("personal", titulo):
            crear_alerta("AVISO", "personal", titulo, f"Vence: {fv}")
            nuevas += 1

    # CXP hoy o mañana
    c.execute(
        """SELECT proveedor, monto, fecha_pago FROM cxp_programados
           WHERE estado='PROGRAMADO' AND fecha_pago <= ?""",
        ((hoy + timedelta(days=1)).isoformat(),),
    )
    for prov, monto, fp in c.fetchall():
        titulo = f"Pago programado: {prov}"
        if not _alerta_existe("pagos", titulo):
            crear_alerta("URGENTE", "pagos", titulo, f"${monto:,.0f} — {fp}")
            nuevas += 1

    # Cartera mora > 60 días
    c.execute("SELECT cliente, dias_mora, saldo FROM cartera_cxc WHERE dias_mora > 60")
    for cli, dias, saldo in c.fetchall():
        titulo = f"Mora crítica: {cli}"
        if not _alerta_existe("creditos", titulo):
            crear_alerta("CRITICO", "creditos", titulo, f"{dias} días — ${saldo:,.0f}")
            nuevas += 1

    # Dotación pendiente (tabla legacy)
    c.execute("SELECT empleado, periodo FROM dotacion_rrhh WHERE entregado=0")
    for emp, per in c.fetchall():
        titulo = f"Dotación pendiente: {emp}"
        if not _alerta_existe("personal", titulo):
            crear_alerta("AVISO", "personal", titulo, f"Período {per}")
            nuevas += 1

    # Dotación próxima a vencer (≤ 15 días) — tabla novedades RRHH
    limite_dot = (hoy + timedelta(days=15)).isoformat()
    c.execute(
        """SELECT empleado, item, proxima_entrega FROM dotacion
           WHERE proxima_entrega IS NOT NULL AND proxima_entrega <= ?""",
        (limite_dot,),
    )
    for emp, item, prox in c.fetchall():
        titulo = f"Dotación próxima: {emp}"
        if not _alerta_existe("personal", titulo):
            crear_alerta(
                "AVISO",
                "personal",
                titulo,
                f"{item or 'Ítem'} — próxima entrega {prox} (≤15 días)",
            )
            nuevas += 1

    # Vacaciones pendientes de aprobar
    c.execute(
        """SELECT empleado, tipo, fecha_inicio FROM novedades_rrhh
           WHERE estado='PENDIENTE' AND tipo='Vacaciones'"""
    )
    for emp, tipo, fi in c.fetchall():
        titulo = f"Vacaciones pendientes: {emp}"
        if not _alerta_existe("personal", titulo):
            crear_alerta("AVISO", "personal", titulo, f"{tipo} desde {fi} — pendiente de aprobación")
            nuevas += 1

    conn.close()

    try:
        from modulos.carpetas_rrhh import generar_alertas_carpetas

        nuevas += generar_alertas_carpetas()
    except Exception:
        pass

    return nuevas
