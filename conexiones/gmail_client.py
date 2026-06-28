"""
Cliente Gmail API. Lee, reenvía, marca y elimina correos.
"""
import base64
import logging
import os
import pickle
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import cfg, gmail_configurado

logger = logging.getLogger(__name__)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_gmail_service() -> Any:
    """Autentica y retorna el servicio de Gmail."""
    if not gmail_configurado():
        raise RuntimeError("Gmail no configurado. Revise GMAIL_CREDENTIALS_PATH en .env")
    creds = None
    if cfg.GMAIL_TOKEN_PATH and os.path.exists(cfg.GMAIL_TOKEN_PATH):
        with open(cfg.GMAIL_TOKEN_PATH, "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cfg.GMAIL_CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(cfg.GMAIL_TOKEN_PATH, "wb") as token:
            pickle.dump(creds, token)
    return build("gmail", "v1", credentials=creds)


def _extraer_cuerpo(payload: dict[str, Any]) -> str:
    """Extrae el texto del cuerpo del correo (maneja multipart)."""
    cuerpo = ""
    if payload.get("body", {}).get("data"):
        cuerpo = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
    elif "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                cuerpo += base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
    return cuerpo


def leer_correos_nuevos(max_resultados: int = 50) -> list[dict[str, Any]]:
    """
    Lee correos no leídos de Gmail.

    Returns:
        Lista de dicts con id, remitente, asunto, cuerpo, fecha, origen.
    """
    if not gmail_configurado():
        logger.info("Gmail no configurado — retornando lista vacía.")
        return []
    try:
        service = get_gmail_service()
        resultado = service.users().messages().list(
            userId="me", q="is:unread", maxResults=max_resultados
        ).execute()
        mensajes = resultado.get("messages", [])
        correos = []
        for msg in mensajes:
            detalle = service.users().messages().get(
                userId="me", id=msg["id"], format="full"
            ).execute()
            headers = {h["name"]: h["value"] for h in detalle["payload"]["headers"]}
            cuerpo = _extraer_cuerpo(detalle["payload"])
            correos.append(
                {
                    "id": msg["id"],
                    "remitente": headers.get("From", ""),
                    "asunto": headers.get("Subject", ""),
                    "fecha": headers.get("Date", ""),
                    "cuerpo": cuerpo[:3000],
                    "origen": "GMAIL",
                }
            )
        return correos
    except Exception as e:
        logger.error("Error leyendo Gmail: %s", e)
        return []


def reenviar_correo(message_id: str, destino: str, nota: str = "") -> bool:
    """Reenvía un correo a la dirección indicada."""
    try:
        service = get_gmail_service()
        original = service.users().messages().get(userId="me", id=message_id, format="raw").execute()
        mime_msg = MIMEMultipart()
        mime_msg["To"] = destino
        if nota:
            mime_msg.attach(MIMEText(f"[AGENTE ADMIN SHAKI]: {nota}\n\n--- Correo original ---\n", "plain"))
        encoded = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": encoded}).execute()
        marcar_como_leido(message_id)
        return True
    except Exception as e:
        logger.error("Error reenviando correo %s: %s", message_id, e)
        return False


def marcar_como_leido(message_id: str) -> bool:
    """Marca un correo como leído."""
    try:
        service = get_gmail_service()
        service.users().messages().modify(
            userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
        ).execute()
        return True
    except Exception as e:
        logger.error("Error marcando como leído %s: %s", message_id, e)
        return False


def mover_a_papelera(message_id: str) -> bool:
    """Mueve un correo a la papelera."""
    try:
        service = get_gmail_service()
        service.users().messages().trash(userId="me", id=message_id).execute()
        return True
    except Exception as e:
        logger.error("Error moviendo a papelera %s: %s", message_id, e)
        return False


def enviar_correo(destino: str, asunto: str, cuerpo_html: str, adjuntos: list[str] | None = None) -> bool:
    """Envía un correo nuevo con soporte para adjuntos."""
    if not gmail_configurado():
        logger.info("[Demo] Correo simulado a %s: %s", destino, asunto)
        return True
    try:
        service = get_gmail_service()
        mensaje = MIMEMultipart("alternative")
        mensaje["To"] = destino
        mensaje["From"] = cfg.GMAIL_USER
        mensaje["Subject"] = asunto
        mensaje.attach(MIMEText(cuerpo_html, "html"))
        if adjuntos:
            for path in adjuntos:
                with open(path, "rb") as f:
                    parte = MIMEBase("application", "octet-stream")
                    parte.set_payload(f.read())
                encoders.encode_base64(parte)
                parte.add_header(
                    "Content-Disposition", f'attachment; filename="{os.path.basename(path)}"'
                )
                mensaje.attach(parte)
        raw = base64.urlsafe_b64encode(mensaje.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception as e:
        logger.error("Error enviando correo a %s: %s", destino, e)
        return False
