"""
Cliente WhatsApp — Twilio API (producción) o log en modo demo.
"""
import logging
from typing import Iterable

from config import cfg, en_modo_demo

logger = logging.getLogger(__name__)


def _parse_destinatarios(raw: str | None) -> list[str]:
    if not raw:
        return []
    nums = []
    for part in raw.replace(";", ",").split(","):
        n = part.strip()
        if not n:
            continue
        if not n.startswith("whatsapp:"):
            if n.startswith("+"):
                n = f"whatsapp:{n}"
            else:
                n = f"whatsapp:+57{n.lstrip('57')}"
        nums.append(n)
    return nums


def enviar_whatsapp(mensaje: str, destinos: Iterable[str] | None = None) -> int:
    """
    Envía mensaje WhatsApp a lista de números.

    Returns:
        Cantidad de envíos exitosos (o simulados en demo).
    """
    lista = list(destinos) if destinos else _parse_destinatarios(cfg.WHATSAPP_DESTINATARIOS)
    if not lista:
        logger.warning("WhatsApp: sin destinatarios configurados (WHATSAPP_DESTINATARIOS)")
        return 0

    if en_modo_demo() or not cfg.TWILIO_ACCOUNT_SID:
        for d in lista:
            logger.info("[Demo WhatsApp] → %s: %s", d, mensaje[:120])
        return len(lista)

    try:
        from twilio.rest import Client

        client = Client(cfg.TWILIO_ACCOUNT_SID, cfg.TWILIO_AUTH_TOKEN)
        enviados = 0
        origen = cfg.TWILIO_WHATSAPP_FROM or "whatsapp:+14155238886"
        for dest in lista:
            client.messages.create(body=mensaje, from_=origen, to=dest)
            enviados += 1
        return enviados
    except ImportError:
        logger.error("Instale twilio: pip install twilio")
        return 0
    except Exception as e:
        logger.error("Error WhatsApp: %s", e)
        return 0
