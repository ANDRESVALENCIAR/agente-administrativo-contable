"""
Envío REAL de notificaciones (correo y WhatsApp) para alertas que no pueden simularse.

A diferencia de gmail_client / whatsapp_client (que en modo demo simulan y devuelven True),
aquí cada función devuelve:
    True  → salió de verdad
    False → se intentó y falló
    None  → el canal no está configurado (no se intentó)
Así el agente solo marca una alerta como "enviada" cuando realmente llegó a algún canal.
"""
from __future__ import annotations

import json
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid

from config import cfg, gmail_configurado, microsoft_configurado

logger = logging.getLogger(__name__)


# ───────────────────────── Correo ─────────────────────────

def smtp_configurado() -> bool:
    return bool(cfg.SMTP_HOST and cfg.SMTP_USER and cfg.SMTP_PASSWORD)


def canal_correo() -> str | None:
    if smtp_configurado():
        return f"SMTP {cfg.SMTP_HOST}"
    if gmail_configurado():
        return "Gmail API"
    if microsoft_configurado():
        return "Microsoft 365"
    return None


def _enviar_smtp(destino: str, asunto: str, html: str, texto: str | None) -> bool:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = formataddr((f"Shaki · {cfg.NOMBRE_EMPRESA}", cfg.SMTP_FROM or cfg.SMTP_USER))
    msg["To"] = destino
    msg["Message-ID"] = make_msgid(domain=(cfg.SMTP_FROM or cfg.SMTP_USER).split("@")[-1])
    if texto:
        msg.attach(MIMEText(texto, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    contexto = ssl.create_default_context()
    if int(cfg.SMTP_PORT) == 465:
        with smtplib.SMTP_SSL(cfg.SMTP_HOST, 465, context=contexto, timeout=30) as s:
            s.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
            s.sendmail(msg["From"], [destino], msg.as_string())
    else:
        with smtplib.SMTP(cfg.SMTP_HOST, int(cfg.SMTP_PORT), timeout=30) as s:
            s.ehlo()
            if s.has_extn("starttls"):
                s.starttls(context=contexto)
                s.ehlo()
            s.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
            s.sendmail(msg["From"], [destino], msg.as_string())
    return True


def enviar_email(destino: str, asunto: str, html: str, texto: str | None = None) -> bool | None:
    try:
        if smtp_configurado():
            return _enviar_smtp(destino, asunto, html, texto)
        if gmail_configurado():
            from conexiones.gmail_client import enviar_correo

            return bool(enviar_correo(destino, asunto, html))
        if microsoft_configurado():
            from conexiones.outlook_client import enviar_correo

            return bool(enviar_correo(destino, asunto, html))
    except Exception as exc:
        logger.error("Correo a %s falló: %s", destino, exc)
        return False
    logger.warning("Correo no enviado a %s: ningún canal de correo configurado (SMTP_*, Gmail o M365)", destino)
    return None


# ───────────────────────── WhatsApp (Twilio) ─────────────────────────

def twilio_configurado() -> bool:
    return bool(cfg.TWILIO_ACCOUNT_SID and cfg.TWILIO_AUTH_TOKEN and cfg.TWILIO_WHATSAPP_FROM)


def canal_whatsapp() -> str | None:
    if not twilio_configurado():
        return None
    return "Twilio · plantilla aprobada" if cfg.TWILIO_WHATSAPP_CONTENT_SID else "Twilio · texto libre (sandbox)"


def enviar_whatsapp(destino: str, texto: str, variables: dict[str, str] | None = None) -> bool | None:
    """
    destino: 'whatsapp:+57...'. Si hay TWILIO_WHATSAPP_CONTENT_SID usa la plantilla aprobada con
    `variables` ({"1": detalle, "2": fecha, "3": valor, "4": enlace}); si no, envía `texto`.
    """
    if not twilio_configurado():
        logger.warning("WhatsApp no enviado a %s: Twilio no configurado", destino)
        return None
    try:
        from twilio.rest import Client

        client = Client(cfg.TWILIO_ACCOUNT_SID, cfg.TWILIO_AUTH_TOKEN)
        origen = cfg.TWILIO_WHATSAPP_FROM
        if not origen.startswith("whatsapp:"):
            origen = f"whatsapp:{origen}"
        if cfg.TWILIO_WHATSAPP_CONTENT_SID and variables:
            client.messages.create(
                from_=origen, to=destino,
                content_sid=cfg.TWILIO_WHATSAPP_CONTENT_SID,
                content_variables=json.dumps(variables, ensure_ascii=False),
            )
        else:
            client.messages.create(from_=origen, to=destino, body=texto)
        return True
    except Exception as exc:
        logger.error("WhatsApp a %s falló: %s", destino, exc)
        return False
