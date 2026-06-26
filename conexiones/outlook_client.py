"""
Cliente Microsoft Graph API para correo corporativo Outlook.
"""
import logging
from typing import Any

import msal
import requests

from config import cfg, microsoft_configurado

logger = logging.getLogger(__name__)


def get_token() -> str:
    """Obtiene token de acceso de Microsoft."""
    if not microsoft_configurado():
        raise RuntimeError("Microsoft 365 no configurado en .env")
    app = msal.ConfidentialClientApplication(
        cfg.MS_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{cfg.MS_TENANT_ID}",
        client_credential=cfg.MS_CLIENT_SECRET,
    )
    resultado = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" in resultado:
        return resultado["access_token"]
    raise Exception(f"Error obteniendo token Microsoft: {resultado.get('error_description')}")


def get_headers() -> dict[str, str]:
    """Retorna headers HTTP con token Bearer."""
    return {"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}


def _base_url() -> str:
    return f"https://graph.microsoft.com/v1.0/users/{cfg.MS_USER_EMAIL}"


def leer_correos_nuevos(max_resultados: int = 50) -> list[dict[str, Any]]:
    """Lee correos no leídos de Outlook."""
    if not microsoft_configurado():
        logger.info("Outlook no configurado — retornando lista vacía.")
        return []
    try:
        url = (
            f"{_base_url()}/messages?$filter=isRead eq false"
            f"&$top={max_resultados}&$select=id,from,subject,body,receivedDateTime"
        )
        resp = requests.get(url, headers=get_headers(), timeout=30)
        resp.raise_for_status()
        mensajes = resp.json().get("value", [])
        correos = []
        for msg in mensajes:
            correos.append(
                {
                    "id": msg["id"],
                    "remitente": msg["from"]["emailAddress"]["address"],
                    "asunto": msg.get("subject", ""),
                    "fecha": msg.get("receivedDateTime", ""),
                    "cuerpo": msg["body"]["content"][:3000],
                    "origen": "OUTLOOK",
                }
            )
        return correos
    except Exception as e:
        logger.error("Error leyendo Outlook: %s", e)
        return []


def reenviar_correo(message_id: str, destino: str, nota: str = "") -> bool:
    """Reenvía correo de Outlook."""
    try:
        url = f"{_base_url()}/messages/{message_id}/forward"
        body = {"toRecipients": [{"emailAddress": {"address": destino}}], "comment": nota}
        resp = requests.post(url, headers=get_headers(), json=body, timeout=30)
        resp.raise_for_status()
        marcar_como_leido(message_id)
        return True
    except Exception as e:
        logger.error("Error reenviando desde Outlook: %s", e)
        return False


def marcar_como_leido(message_id: str) -> bool:
    """Marca correo Outlook como leído."""
    try:
        url = f"{_base_url()}/messages/{message_id}"
        resp = requests.patch(url, headers=get_headers(), json={"isRead": True}, timeout=30)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error("Error marcando leído en Outlook: %s", e)
        return False


def enviar_correo(destino: str, asunto: str, cuerpo_html: str) -> bool:
    """Envía correo desde Outlook."""
    if not microsoft_configurado():
        logger.info("[Demo] Correo Outlook simulado a %s: %s", destino, asunto)
        return True
    try:
        url = f"{_base_url()}/sendMail"
        body = {
            "message": {
                "subject": asunto,
                "body": {"contentType": "HTML", "content": cuerpo_html},
                "toRecipients": [{"emailAddress": {"address": destino}}],
            }
        }
        resp = requests.post(url, headers=get_headers(), json=body, timeout=30)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error("Error enviando desde Outlook: %s", e)
        return False
