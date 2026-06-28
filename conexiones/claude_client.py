"""
Cliente Claude API con prompt caching, Batch API y registro de tokens.
"""
import hashlib
import anthropic
import json
import time
import logging
from typing import Any

from config import cfg, en_modo_demo
from database import registrar_accion

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""Eres el asistente administrativo-contable de {cfg.NOMBRE_EMPRESA} (NIT: {cfg.NIT_EMPRESA}).
Tu rol es ejecutar funciones administrativas con precisión, usando la normatividad colombiana vigente.
Siempre responde en español colombiano formal.
Para cálculos financieros, usa las reglas fiscales colombianas (DIAN).
Cuando generes documentos, sigue los formatos legales colombianos.
Nunca inventes datos — si no tienes la información, indícalo claramente.
Cuando el usuario pregunte sobre el estado del sistema, responde con datos concretos y precisos.
Si necesitas ejecutar una acción que requiere confirmación, descríbela claramente y espera aprobación."""

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic | None:
    """Retorna cliente Anthropic o None en modo demo."""
    global _client
    if en_modo_demo():
        return None
    if _client is None:
        _client = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
    return _client


def _respuesta_demo(prompt: str, modulo: str) -> str:
    """Genera respuesta simulada cuando no hay API key."""
    logger.info("Modo demo: respuesta simulada para módulo %s", modulo)
    if "categoría" in prompt.lower() or "clasifica" in prompt.lower():
        return "comunicacion"
    if "json" in prompt.lower():
        return '{"decision": "CONDICIONAL", "justificacion": "Modo demo — configure ANTHROPIC_API_KEY"}'
    return (
        f"[Modo demo] Respuesta simulada del asistente administrativo de {cfg.NOMBRE_EMPRESA}. "
        "Configure ANTHROPIC_API_KEY en .env para respuestas reales de Claude."
    )


def _cache_get(clave: str) -> str | None:
    """Retorna respuesta cacheada si tiene menos de 1 hora."""
    from database import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT respuesta FROM cache_api WHERE clave=? AND timestamp >= datetime('now','-1 hour')",
        (clave,),
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def _cache_set(clave: str, respuesta: str) -> None:
    """Guarda respuesta en caché API."""
    from database import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO cache_api (clave, respuesta) VALUES (?,?) ON CONFLICT(clave) DO UPDATE SET respuesta=excluded.respuesta, timestamp=CURRENT_TIMESTAMP",
        (clave, respuesta),
    )
    conn.commit()
    conn.close()


def llamar_claude(
    prompt: str,
    modelo: str | None = None,
    max_tokens: int = 2000,
    modulo: str = "general",
    usar_cache: bool = True,
) -> str:
    """
    Llama a Claude con manejo de errores y registro de tokens.

    Args:
        prompt: Texto de la consulta al modelo.
        modelo: ID del modelo Anthropic (default: Sonnet).
        max_tokens: Máximo de tokens de salida.
        modulo: Módulo origen para logging.
        usar_cache: Si True, activa prompt caching en system prompt.

    Returns:
        Texto de respuesta del modelo o mensaje de error.
    """
    if modelo is None:
        modelo = cfg.MODELO_COMPLEJO

    clave_cache = hashlib.md5(f"{modelo}:{prompt}".encode()).hexdigest()
    if usar_cache:
        cached = _cache_get(clave_cache)
        if cached:
            logger.info("Cache hit para módulo %s", modulo)
            return cached

    client = _get_client()
    if client is None:
        resp = _respuesta_demo(prompt, modulo)
        registrar_accion(modulo, "llamar_claude", "Modo demo", "EXITOSO")
        return resp

    system_content: list[dict[str, Any]] = [{"type": "text", "text": SYSTEM_PROMPT}]
    if usar_cache:
        system_content[0]["cache_control"] = {"type": "ephemeral"}

    for intento in range(3):
        try:
            respuesta = client.messages.create(
                model=modelo,
                max_tokens=max_tokens,
                system=system_content,
                messages=[{"role": "user", "content": prompt}],
            )
            tokens_in = respuesta.usage.input_tokens
            tokens_out = respuesta.usage.output_tokens
            registrar_accion(
                modulo,
                "llamar_claude",
                f"Modelo: {modelo} | Tokens: {tokens_in}in/{tokens_out}out",
                "EXITOSO",
                tokens_input=tokens_in,
                tokens_output=tokens_out,
            )
            texto = respuesta.content[0].text
            if usar_cache:
                _cache_set(clave_cache, texto)
            return texto

        except anthropic.RateLimitError:
            espera = (intento + 1) * 10
            logger.warning("Rate limit. Esperando %ss...", espera)
            time.sleep(espera)
        except anthropic.APIError as e:
            logger.error("Error API Claude (intento %s): %s", intento + 1, e)
            if intento == 2:
                registrar_accion(
                    modulo,
                    "llamar_claude",
                    f"Error después de 3 intentos: {str(e)}",
                    "ERROR",
                    detalle_error=str(e),
                )
                return f"Error al consultar el asistente: {str(e)}"
            time.sleep(5)

    return "Error desconocido al consultar Claude."


def llamar_claude_simple(prompt: str, modulo: str = "clasificacion") -> str:
    """Usa Haiku para tareas simples — más económico que Sonnet."""
    return llamar_claude(prompt, modelo=cfg.MODELO_SIMPLE, max_tokens=500, modulo=modulo)


def llamar_claude_json(prompt: str, modulo: str = "general") -> dict[str, Any]:
    """Llama a Claude y parsea la respuesta como JSON."""
    prompt_json = prompt + "\n\nResponde ÚNICAMENTE con JSON válido, sin texto adicional, sin markdown."
    respuesta = llamar_claude(prompt_json, modulo=modulo)
    try:
        respuesta_limpia = respuesta.strip().strip("```json").strip("```").strip()
        return json.loads(respuesta_limpia)
    except json.JSONDecodeError as e:
        logger.error("Error parseando JSON de Claude: %s\nRespuesta: %s", e, respuesta)
        return {"error": str(e), "respuesta_raw": respuesta}
