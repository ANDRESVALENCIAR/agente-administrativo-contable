"""
Motor del chat conversacional con Claude.
Consulta todos los módulos y ejecuta acciones (pagos, alertas, correos, cartera, etc.).
"""
import logging
from datetime import datetime

from config import cfg, en_modo_demo
from conexiones.claude_client import llamar_claude
from core.ia_engine import chat_completar, ia_disponible
from database import (
    guardar_mensaje_chat,
    obtener_estadisticas_hoy,
    obtener_historial_chat,
)
from modulos.chat_interactivo import ACCIONES_AYUDA, detectar_intencion, ejecutar_accion, procesar_mensaje_interactivo
from core.formato_col import fecha_larga_es

logger = logging.getLogger(__name__)

SYSTEM_CHAT = f"""Eres AGENTE ADMIN SHAKI, asistente administrativo-contable de {cfg.NOMBRE_EMPRESA} (NIT {cfg.NIT_EMPRESA}).
Tienes acceso en tiempo real a todos los módulos: Alertas, Pagos, Correos, Impuestos, Contabilidad,
CXP/CXC, Créditos, Comisiones, Personal, Presupuesto y Jurídico.

Cuando el usuario pide una ACCIÓN (aprobar pago, procesar correos, verificar alertas, bloquear cliente),
el sistema ya la ejecutó antes de tu respuesta — confirma el resultado con claridad.
Para consultas, usa SOLO los datos del contexto; no inventes cifras.
Responde en español colombiano, conciso y profesional.
Fecha y hora: {{fecha_hora}}

{{acciones_disponibles}}

DATOS POR MÓDULO:
{{datos_sistema}}

ÚLTIMAS ACCIONES DEL AGENTE:
{{historial_acciones}}

{{resultado_accion}}"""

# Acciones que responden directo (sin llamar a Claude)
_ACCIONES_DIRECTAS = {
    "ayuda",
    "aprobar_pago",
    "rechazar_pago",
    "listar_pagos",
    "verificar_alertas",
    "resolver_alerta",
    "procesar_correos",
    "sincronizar_reglas",
    "impuestos_vencimientos",
    "sincronizar_calendario",
    "recordatorios_impuestos",
    "cartera_mora",
    "bloquear_cliente",
    "contratos_vencimientos",
    "tareas_hoy",
    "tareas_vencidas",
}


def _safe_guardar(rol: str, contenido: str, tokens: int = 0) -> None:
    try:
        guardar_mensaje_chat(rol, contenido, tokens)
    except Exception as e:
        logger.warning("No se pudo guardar mensaje chat: %s", e)


def chat_responder(mensaje_usuario: str, historial: list[dict[str, str]] | None = None) -> tuple[str, list[dict[str, str]]]:
    """Responde con los datos reales de Shaki (modulos.asistente); acciones: escanear alertas, leer correos."""
    historial = historial or []
    _safe_guardar("user", mensaje_usuario)
    t = mensaje_usuario.lower()
    try:
        if any(x in t for x in ("verificar alertas", "escanear alertas", "revisar alertas")):
            from modulos import motor_alertas
            r = motor_alertas.escanear()
            respuesta = (f"Listo: revisé todo. {r['nuevas']} alerta(s) nueva(s), {r['resueltas']} se cerraron solas, "
                         f"{r['vivas']} siguen abiertas. Pregúnteme «alertas críticas» para verlas.")
        elif any(x in t for x in ("procesar correos", "leer correos", "revisar correos", "leer buzones")):
            from modulos import buzones
            r = buzones.leer_todos()
            errores = [b["buzon"] for b in r["buzones"] if b.get("error")]
            respuesta = (f"Leí los buzones: {r['nuevos']} correo(s) nuevo(s)."
                         + (f" No pude leer: {', '.join(errores)}." if errores else "")
                         + " Pregúnteme «correos importantes» para verlos.")
        else:
            from modulos import asistente
            respuesta = asistente.responder(mensaje_usuario, historial)
    except Exception as e:
        logger.exception("chat_responder: %s", e)
        respuesta = f"Tuve un problema consultando los datos ({e}). Intente de nuevo."
    _safe_guardar("assistant", respuesta)
    historial = historial + [{"role": "user", "content": mensaje_usuario}, {"role": "assistant", "content": respuesta}]
    return respuesta, historial[-20:]


def chat_responder_anterior(mensaje_usuario: str, historial: list[dict[str, str]] | None = None) -> tuple[str, list[dict[str, str]]]:
    """
    Procesa un mensaje del usuario y retorna la respuesta del agente.

    Args:
        mensaje_usuario: Texto del usuario.
        historial: Lista de mensajes previos {{role, content}}.

    Returns:
        Tupla (respuesta_texto, historial_actualizado).
    """
    if historial is None:
        historial = []

    _safe_guardar("user", mensaje_usuario)

    try:
        intencion = detectar_intencion(mensaje_usuario)
    except Exception as e:
        logger.error("detectar_intencion: %s", e)
        intencion = None

    resultado_accion_txt = ""
    if intencion:
        try:
            acc = ejecutar_accion(intencion, mensaje_usuario)
        except Exception as e:
            logger.error("ejecutar_accion: %s", e, exc_info=True)
            acc = {
                "ejecutada": False,
                "modulo": "sistema",
                "resultado": f"No pude completar la consulta por un error interno: {e}",
            }
        resultado_accion_txt = f"ACCIÓN EJECUTADA ({acc['modulo']}):\n{acc['resultado']}"
        if intencion in _ACCIONES_DIRECTAS:
            if acc.get("ejecutada") or intencion == "ayuda":
                respuesta = acc["resultado"]
                _safe_guardar("assistant", respuesta)
                historial.append({"role": "user", "content": mensaje_usuario})
                historial.append({"role": "assistant", "content": respuesta})
                return respuesta, historial

    try:
        contexto = procesar_mensaje_interactivo(mensaje_usuario)[1]
    except Exception:
        contexto = "Contexto no disponible (BD ocupada)."

    try:
        stats = obtener_estadisticas_hoy()
    except Exception:
        stats = {}
    try:
        historial_db = obtener_historial_chat(limite=10)
        historial_texto = "\n".join([f"{r[0].upper()}: {r[1][:200]}" for r in historial_db[-6:]])
    except Exception:
        historial_texto = ""
    if stats.get("ultimas_acciones"):
        historial_texto += "\n" + "\n".join(
            f"- [{a[4]}] {a[0]}.{a[1]}: {a[2]}" for a in stats["ultimas_acciones"][:5]
        )

    system = SYSTEM_CHAT.format(
        fecha_hora=fecha_larga_es(datetime.now(), sep=", "),
        acciones_disponibles=ACCIONES_AYUDA.strip(),
        datos_sistema=contexto,
        historial_acciones=historial_texto or "Sin acciones recientes.",
        resultado_accion=resultado_accion_txt or "Ninguna acción ejecutada en este turno.",
    )

    mensajes: list[dict[str, str]] = []
    for msg in historial[-8:]:
        mensajes.append({"role": msg["role"], "content": msg["content"]})
    mensajes.append({"role": "user", "content": mensaje_usuario})

    if en_modo_demo():
        # Sin API: si hubo acción parcial, úsala; si no, respuesta demo clara
        if resultado_accion_txt:
            respuesta = resultado_accion_txt.replace("ACCIÓN EJECUTADA", "Resultado").split(":\n", 1)[-1]
        else:
            respuesta = llamar_claude(
                f"{mensaje_usuario}\n\nContexto del sistema:\n{contexto}\n\n{resultado_accion_txt}",
                modulo="chat",
            )
        tokens = 0
    else:
        try:
            stack = ia_disponible()
            if stack.get("langchain"):
                respuesta = chat_completar(system, mensaje_usuario, historial)
            else:
                import anthropic

                client = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
                resp = client.messages.create(
                    model=cfg.MODELO_COMPLEJO,
                    max_tokens=1500,
                    system=system,
                    messages=mensajes,
                )
                respuesta = resp.content[0].text
            tokens = 0
        except Exception as e:
            logger.error("Error en chat: %s", e)
            if resultado_accion_txt:
                respuesta = resultado_accion_txt.split(":\n", 1)[-1]
            else:
                respuesta = (
                    f"Disculpa, tuve un problema al procesar tu mensaje: {str(e)}. "
                    "Prueba de nuevo o usa el menú Personal / RRHH."
                )
            tokens = 0

    _safe_guardar("assistant", respuesta, tokens)
    historial.append({"role": "user", "content": mensaje_usuario})
    historial.append({"role": "assistant", "content": respuesta})

    return respuesta, historial
