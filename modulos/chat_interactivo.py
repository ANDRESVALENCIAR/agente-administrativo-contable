"""
Acciones ejecutables desde el chat por módulo.
Detecta intención por palabras clave y ejecuta funciones reales del agente.
"""
import logging
import re
from typing import Any

from config import cfg
from dashboard.utils.contexto_chat import construir_contexto_modulos
from dashboard.utils.db_helper import execute, query_df
from database import aprobar_pago, marcar_alerta_resuelta, obtener_pagos_pendientes, rechazar_pago

logger = logging.getLogger(__name__)

ACCIONES_AYUDA = """
Puedo consultar y ejecutar acciones en estos módulos:
• Alertas — verificar alertas, resolver alerta por ID
• Pagos — aprobar pago #ID, rechazar pago #ID, listar pendientes
• Correos — procesar correos, sincronizar reglas desde .env
• Impuestos — listar vencimientos, sincronizar calendario DIAN/SHD, recordatorios 48h/24h
• CXP/CXC — resumen cartera mora, bloquear cliente por nombre
• Créditos, Comisiones, Personal, Presupuesto, Jurídico — consultar estado (pregúntame)
Ejemplos: "aprobar pago 1", "verificar alertas", "procesar correos", "cartera vencida"
"""


def _extraer_id(mensaje: str) -> int | None:
    m = re.search(r"#?\s*(\d+)", mensaje)
    return int(m.group(1)) if m else None


def _extraer_nombre_cliente(mensaje: str) -> str | None:
    m = re.search(r"cliente\s+(.+?)(?:\.|$)", mensaje, re.I)
    if m:
        return m.group(1).strip()
    return None


def detectar_intencion(mensaje: str) -> str | None:
    """Retorna clave de acción o None si es solo consulta."""
    t = mensaje.lower().strip()
    if any(x in t for x in ("ayuda", "qué puedes", "que puedes", "comandos", "acciones")):
        return "ayuda"
    if "verificar alertas" in t or "revisar alertas" in t:
        return "verificar_alertas"
    if re.search(r"resolver alerta", t):
        return "resolver_alerta"
    if re.search(r"aprobar pago", t):
        return "aprobar_pago"
    if re.search(r"rechazar pago", t):
        return "rechazar_pago"
    if "pagos pendientes" in t or "listar pagos" in t:
        return "listar_pagos"
    if "procesar correos" in t or "clasificar correos" in t:
        return "procesar_correos"
    if "sincronizar reglas" in t or "reglas correo" in t:
        return "sincronizar_reglas"
    if "sincronizar calendario" in t or "open data impuestos" in t:
        return "sincronizar_calendario"
    if "recordatorios impuestos" in t or "recordatorio tributario" in t:
        return "recordatorios_impuestos"
    if "impuestos" in t and any(x in t for x in ("venc", "próxim", "proxim", "estado", "calendario")):
        return "impuestos_vencimientos"
    if "cartera" in t or "mora" in t or "cxc" in t:
        return "cartera_mora"
    if "bloquear cliente" in t or "bloquear" in t and "cliente" in t:
        return "bloquear_cliente"
    return None


def ejecutar_accion(intencion: str, mensaje: str) -> dict[str, Any]:
    """
    Ejecuta acción del módulo correspondiente.

    Returns:
        dict con keys: ejecutada (bool), modulo, resultado (str)
    """
    try:
        if intencion == "ayuda":
            return {"ejecutada": True, "modulo": "chat", "resultado": ACCIONES_AYUDA.strip()}

        if intencion == "verificar_alertas":
            from dashboard.utils.alertas_globales import verificar_alertas_globales

            n = verificar_alertas_globales()
            return {
                "ejecutada": True,
                "modulo": "alertas",
                "resultado": f"Verificación completada. {n} alerta(s) nuevas registradas.",
            }

        if intencion == "resolver_alerta":
            aid = _extraer_id(mensaje)
            if not aid:
                return {"ejecutada": False, "modulo": "alertas", "resultado": "Indica el ID: resolver alerta 3"}
            marcar_alerta_resuelta(aid)
            return {"ejecutada": True, "modulo": "alertas", "resultado": f"Alerta #{aid} marcada como resuelta."}

        if intencion == "aprobar_pago":
            pid = _extraer_id(mensaje)
            if not pid:
                pagos = obtener_pagos_pendientes()[:3]
                ids = ", ".join(f"#{p[0]}" for p in pagos) or "ninguno"
                return {
                    "ejecutada": False,
                    "modulo": "pagos",
                    "resultado": f"Indica el ID. Pendientes: {ids}",
                }
            aprobar_pago(pid, "chat-shaki")
            return {"ejecutada": True, "modulo": "pagos", "resultado": f"Pago #{pid} aprobado por chat."}

        if intencion == "rechazar_pago":
            pid = _extraer_id(mensaje)
            if not pid:
                return {"ejecutada": False, "modulo": "pagos", "resultado": "Indica el ID: rechazar pago 2"}
            rechazar_pago(pid, "chat-shaki")
            return {"ejecutada": True, "modulo": "pagos", "resultado": f"Pago #{pid} rechazado."}

        if intencion == "listar_pagos":
            pagos = obtener_pagos_pendientes()
            if not pagos:
                return {"ejecutada": True, "modulo": "pagos", "resultado": "No hay pagos pendientes."}
            lineas = [f"#{p[0]} {p[2]} — ${p[4]:,.0f} — {p[7]}" for p in pagos[:10]]
            return {"ejecutada": True, "modulo": "pagos", "resultado": "Pagos pendientes:\n" + "\n".join(lineas)}

        if intencion == "procesar_correos":
            from modulos.correos import procesar_correos

            procesar_correos()
            return {"ejecutada": True, "modulo": "correos", "resultado": "Procesamiento de correos ejecutado."}

        if intencion == "sincronizar_reglas":
            from modulos.correos import sincronizar_reglas_desde_config

            n = sincronizar_reglas_desde_config()
            return {
                "ejecutada": True,
                "modulo": "correos",
                "resultado": f"{n} reglas sincronizadas desde configuración (.env).",
            }

        if intencion == "sincronizar_calendario":
            from modulos.impuestos_calendario import sincronizar_calendario_opendata

            n = sincronizar_calendario_opendata()
            return {
                "ejecutada": True,
                "modulo": "impuestos",
                "resultado": f"Calendario open data sincronizado: {n} vencimientos (DIAN + SHD Bogotá).",
            }

        if intencion == "recordatorios_impuestos":
            from modulos.impuestos_calendario import enviar_recordatorios_vencimientos

            stats = enviar_recordatorios_vencimientos()
            return {
                "ejecutada": True,
                "modulo": "impuestos",
                "resultado": f"Recordatorios: {stats['email_48h']} emails (48h), {stats['whatsapp_24h']} WhatsApp (24h).",
            }

        if intencion == "impuestos_vencimientos":
            df = query_df(
                """SELECT impuesto, periodo, fecha_vencimiento, estado
                   FROM impuestos_maestro ORDER BY fecha_vencimiento LIMIT 10"""
            )
            if df.empty:
                return {"ejecutada": True, "modulo": "impuestos", "resultado": "Sin impuestos en tabla maestro."}
            lineas = [
                f"{r.impuesto} {r.periodo} — vence {r.fecha_vencimiento} ({r.estado})"
                for r in df.itertuples()
            ]
            return {"ejecutada": True, "modulo": "impuestos", "resultado": "Impuestos:\n" + "\n".join(lineas)}

        if intencion == "cartera_mora":
            df = query_df(
                "SELECT cliente, saldo, dias_mora FROM cartera_cxc WHERE dias_mora >= 30 ORDER BY dias_mora DESC"
            )
            if df.empty:
                return {"ejecutada": True, "modulo": "cxp_cxc", "resultado": "Sin clientes en mora ≥ 30 días."}
            total = df["saldo"].sum()
            lineas = [f"{r.cliente}: ${r.saldo:,.0f} — {r.dias_mora} días" for r in df.itertuples()]
            return {
                "ejecutada": True,
                "modulo": "cxp_cxc",
                "resultado": f"Cartera en mora (${total:,.0f} total):\n" + "\n".join(lineas),
            }

        if intencion == "bloquear_cliente":
            nombre = _extraer_nombre_cliente(mensaje)
            if not nombre:
                return {
                    "ejecutada": False,
                    "modulo": "creditos",
                    "resultado": 'Indica el nombre: bloquear cliente Cliente Alfa',
                }
            df = query_df("SELECT id, cliente FROM cartera_cxc WHERE cliente LIKE ?", (f"%{nombre}%",))
            if df.empty:
                return {"ejecutada": False, "modulo": "creditos", "resultado": f"No encontré cliente '{nombre}'."}
            cid = int(df.iloc[0]["id"])
            execute("UPDATE cartera_cxc SET bloqueado=1, notas=? WHERE id=?", (f"Bloqueo vía chat — {cfg.NOMBRE_EMPRESA}", cid))
            return {
                "ejecutada": True,
                "modulo": "creditos",
                "resultado": f"Cliente '{df.iloc[0]['cliente']}' bloqueado en cartera.",
            }

    except Exception as e:
        logger.error("Error ejecutar_accion %s: %s", intencion, e, exc_info=True)
        return {"ejecutada": False, "modulo": "sistema", "resultado": f"Error al ejecutar: {e}"}

    return {"ejecutada": False, "modulo": "sistema", "resultado": "Acción no reconocida."}


def procesar_mensaje_interactivo(mensaje: str) -> tuple[str | None, str]:
    """
    Detecta y ejecuta acción si aplica.

    Returns:
        (intencion o None, texto_resultado_accion o contexto módulos)
    """
    intencion = detectar_intencion(mensaje)
    if intencion:
        res = ejecutar_accion(intencion, mensaje)
        return intencion, res["resultado"]
    return None, construir_contexto_modulos()
