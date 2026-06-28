"""Motor IA: LangChain + Anthropic con fallback directo."""
import logging

from config import cfg, en_modo_demo

logger = logging.getLogger(__name__)

_llm = None

try:
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage

    _HAS_LC = True
except ImportError:
    try:
        from langchain_anthropic import ChatAnthropic
        from langchain.schema import HumanMessage, SystemMessage

        _HAS_LC = True
    except ImportError:
        _HAS_LC = False


def ia_disponible() -> dict[str, bool]:
    """Estado del stack IA."""
    return {
        "anthropic": not en_modo_demo(),
        "langchain": _HAS_LC and not en_modo_demo(),
    }


def _get_llm():
    global _llm
    if _llm is None and _HAS_LC and cfg.ANTHROPIC_API_KEY:
        from core.registro_libs import registrar_uso_libreria

        registrar_uso_libreria("chat", "langchain_anthropic")
        _llm = ChatAnthropic(
            model=cfg.MODELO_COMPLEJO,
            anthropic_api_key=cfg.ANTHROPIC_API_KEY,
            max_tokens=1500,
        )
    return _llm


def chat_completar(system: str, mensaje: str, historial: list[dict] | None = None) -> str:
    """
    Completa chat usando LangChain si está instalado; si no, Anthropic directo.

    Args:
        system: System prompt.
        mensaje: Mensaje actual del usuario.
        historial: [{role, content}, ...]

    Returns:
        Texto de respuesta.
    """
    historial = historial or []

    if _HAS_LC and not en_modo_demo():
        llm = _get_llm()
        if llm is not None:
            msgs = [SystemMessage(content=system)]
            for h in historial[-6:]:
                if h.get("role") == "user":
                    msgs.append(HumanMessage(content=h["content"]))
                elif h.get("role") == "assistant":
                    from langchain_core.messages import AIMessage

                    msgs.append(AIMessage(content=h["content"]))
            msgs.append(HumanMessage(content=mensaje))
            try:
                resp = llm.invoke(msgs)
                return resp.content if hasattr(resp, "content") else str(resp)
            except Exception as e:
                logger.warning("LangChain falló, usando Anthropic directo: %s", e)

    from conexiones.claude_client import llamar_claude

    return llamar_claude(f"{system}\n\nUsuario: {mensaje}", modulo="chat")
