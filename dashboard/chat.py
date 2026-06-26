"""
Motor del chat conversacional con Claude.
Mantiene el contexto de la conversación y tiene acceso a los datos del sistema.
"""
import logging
from datetime import datetime
from typing import Any

import anthropic

from config import cfg, en_modo_demo
from conexiones.claude_client import llamar_claude
from database import (
    guardar_mensaje_chat,
    obtener_alertas_activas,
    obtener_estadisticas_hoy,
    obtener_historial_chat,
    obtener_pagos_pendientes,
)

logger = logging.getLogger(__name__)

SYSTEM_CHAT = f"""Eres el asistente administrativo de {cfg.NOMBRE_EMPRESA}.
Tienes acceso en tiempo real a todos los datos del sistema.
Cuando el usuario pregunta sobre datos, consultas las estadísticas y datos reales del sistema.
Cuando el usuario pide ejecutar una acción (aprobar pago, bloquear cliente, generar documento),
describes exactamente lo que harás y pides confirmación antes de ejecutar.
Responde siempre en español colombiano. Sé conciso pero completo.
Fecha y hora actual: {{fecha_hora}}

DATOS DEL SISTEMA EN TIEMPO REAL:
{{datos_sistema}}

HISTORIAL RECIENTE DE ACCIONES:
{{historial_acciones}}"""


def construir_contexto_sistema() -> str:
    """Construye el contexto con datos reales del sistema para el chat."""
    stats = obtener_estadisticas_hoy()
    alertas = obtener_alertas_activas()[:5]
    pagos = obtener_pagos_pendientes()[:5]

    alertas_texto = "\n".join([f"- [{a[3]}] {a[4]}: {a[5]}" for a in alertas]) or "Sin alertas activas."

    pagos_texto = "\n".join([f"- {p[2]}: ${p[4]:,.0f} ({p[7]})" for p in pagos]) or "Sin pagos pendientes."

    return f"""
ESTADÍSTICAS HOY:
- Correos procesados: {stats['correos_hoy']}
- Alertas activas: {stats['alertas_activas']}
- Pagos pendientes de aprobación: {stats['pagos_pendientes']}
- Documentos generados hoy: {stats['documentos_hoy']}
- Costo API hoy: ${stats['costo_hoy']}
- Costo API este mes: ${stats['costo_mes']}
- Tareas completadas hoy: {stats['tareas_completadas_hoy']}

ALERTAS ACTIVAS:
{alertas_texto}

PAGOS PENDIENTES:
{pagos_texto}
"""


def chat_responder(mensaje_usuario: str, historial: list[dict[str, str]] | None = None) -> tuple[str, list[dict[str, str]]]:
    """
    Procesa un mensaje del usuario y retorna la respuesta del agente.

    Args:
        mensaje_usuario: Texto del usuario.
        historial: Lista de mensajes previos {role, content}.

    Returns:
        Tupla (respuesta_texto, historial_actualizado).
    """
    if historial is None:
        historial = []

    guardar_mensaje_chat("user", mensaje_usuario)

    contexto = construir_contexto_sistema()
    historial_db = obtener_historial_chat(limite=10)
    historial_texto = "\n".join([f"{r[0].upper()}: {r[1][:200]}" for r in historial_db[-6:]])

    system = SYSTEM_CHAT.format(
        fecha_hora=datetime.now().strftime("%A %d de %B de %Y, %H:%M"),
        datos_sistema=contexto,
        historial_acciones=historial_texto,
    )

    mensajes: list[dict[str, str]] = []
    for msg in historial[-8:]:
        mensajes.append({"role": msg["role"], "content": msg["content"]})
    mensajes.append({"role": "user", "content": mensaje_usuario})

    if en_modo_demo():
        respuesta = llamar_claude(mensaje_usuario + "\n\n" + contexto, modulo="chat")
        tokens = 0
    else:
        try:
            client = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
            resp = client.messages.create(
                model=cfg.MODELO_COMPLEJO,
                max_tokens=1500,
                system=system,
                messages=mensajes,
            )
            respuesta = resp.content[0].text
            tokens = resp.usage.input_tokens + resp.usage.output_tokens
        except Exception as e:
            logger.error("Error en chat: %s", e)
            respuesta = f"Disculpa, tuve un problema al procesar tu mensaje: {str(e)}"
            tokens = 0

    guardar_mensaje_chat("assistant", respuesta, tokens)
    historial.append({"role": "user", "content": mensaje_usuario})
    historial.append({"role": "assistant", "content": respuesta})

    return respuesta, historial
