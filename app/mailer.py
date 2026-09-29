import logging
import os
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from urllib.parse import quote

logger = logging.getLogger("gr.contact.mailer")

COLOMBIA = timezone(timedelta(hours=-5))


@dataclass(frozen=True)
class SmtpSettings:
    host: str
    port: int
    user: str
    password: str
    recipient: str
    sender_name: str


@dataclass(frozen=True)
class ContactNotification:
    id: int
    nombre: str
    email: str
    telefono: str | None
    mensaje: str
    created_at: datetime


def smtp_settings() -> SmtpSettings | None:
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").replace(" ", "")
    recipient = os.getenv("CONTACT_NOTIFY_TO", "").strip()
    if not user or not password or not recipient:
        return None
    return SmtpSettings(
        host=os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
        port=int(os.getenv("SMTP_PORT", "465")),
        user=user,
        password=password,
        recipient=recipient,
        sender_name=os.getenv("SMTP_FROM_NAME", "Habitar").strip() or "Habitar",
    )


def _row(label: str, value: str) -> str:
    return (
        '<tr><td style="padding:14px 0;border-bottom:1px solid #e4e7df;">'
        f'<div style="font-size:11px;letter-spacing:1.6px;text-transform:uppercase;color:#6a756d;">{label}</div>'
        f'<div style="margin-top:6px;font-size:16px;line-height:1.5;color:#17231d;">{value}</div>'
        "</td></tr>"
    )


def render_html(item: ContactNotification) -> str:
    nombre = escape(item.nombre)
    email = escape(item.email)
    telefono = escape(item.telefono) if item.telefono else '<span style="color:#6a756d;">No indicado</span>'
    mensaje = escape(item.mensaje).replace("\n", "<br>")
    fecha = item.created_at.astimezone(COLOMBIA).strftime("%d/%m/%Y · %I:%M %p")
    reply = f"mailto:{quote(item.email)}?subject={quote(f'Re: tu solicitud de contacto #{item.id}')}"
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nueva solicitud de contacto</title>
</head>
<body style="margin:0;padding:0;background:#f5f4ef;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;">{nombre} escribió desde el sitio de Habitar.</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f5f4ef;">
<tr><td align="center" style="padding:40px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">
<tr><td style="padding:0 0 20px;">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td style="width:40px;height:40px;background:#d9f264;border-radius:10px;text-align:center;vertical-align:middle;font-size:18px;font-weight:700;color:#17231d;letter-spacing:-1px;">h.</td>
<td style="padding-left:12px;">
<div style="font-size:16px;font-weight:700;color:#17231d;">Habitar</div>
<div style="font-size:12px;color:#6a756d;">Tu comunidad, en un lugar</div>
</td>
</tr></table>
</td></tr>
<tr><td style="background:#17231d;border-radius:22px 22px 0 0;padding:36px 36px 32px;">
<div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#d9f264;">Nueva solicitud · #{item.id}</div>
<div style="margin-top:14px;font-size:30px;line-height:1.15;font-weight:700;letter-spacing:-1px;color:#f5f4ef;">{nombre} quiere ponerse en contacto</div>
<div style="margin-top:12px;font-size:14px;color:#b7c0b4;">Recibida el {fecha} (hora de Colombia)</div>
</td></tr>
<tr><td style="background:#ffffff;border:1px solid #e4e7df;border-top:0;border-radius:0 0 22px 22px;padding:12px 36px 36px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
{_row("Nombre", nombre)}
{_row("Correo electrónico", f'<a href="mailto:{email}" style="color:#17231d;">{email}</a>')}
{_row("Teléfono", telefono)}
</table>
<div style="margin-top:24px;font-size:11px;letter-spacing:1.6px;text-transform:uppercase;color:#6a756d;">Mensaje</div>
<div style="margin-top:10px;padding:20px 22px;background:#f5f4ef;border-left:4px solid #d9f264;border-radius:12px;font-size:16px;line-height:1.6;color:#17231d;">{mensaje}</div>
<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:28px;"><tr>
<td style="background:#17231d;border-radius:999px;">
<a href="{escape(reply)}" style="display:inline-block;padding:14px 26px;font-size:15px;font-weight:600;color:#f5f4ef;text-decoration:none;">Responder a {nombre}</a>
</td>
</tr></table>
</td></tr>
<tr><td style="padding:24px 8px 0;text-align:center;font-size:12px;line-height:1.6;color:#6a756d;">
La solicitud también quedó registrada en la bandeja de Contacto del panel de administración.<br>
Habitar · Hecho para vivir en comunidad
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def render_text(item: ContactNotification) -> str:
    fecha = item.created_at.astimezone(COLOMBIA).strftime("%d/%m/%Y %I:%M %p")
    return (
        f"Nueva solicitud de contacto #{item.id}\n"
        f"Recibida el {fecha} (hora de Colombia)\n\n"
        f"Nombre: {item.nombre}\n"
        f"Correo: {item.email}\n"
        f"Teléfono: {item.telefono or 'No indicado'}\n\n"
        f"Mensaje:\n{item.mensaje}\n"
    )


def build_message(item: ContactNotification, settings: SmtpSettings) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"Nueva solicitud de contacto #{item.id} · {item.nombre}"
    message["From"] = formataddr((settings.sender_name, settings.user))
    message["To"] = settings.recipient
    message["Reply-To"] = formataddr((item.nombre, item.email))
    message.set_content(render_text(item))
    message.add_alternative(render_html(item), subtype="html")
    return message


def send_contact_notification(item: ContactNotification) -> None:
    settings = smtp_settings()
    if settings is None:
        logger.info("Notificación de contacto omitida: SMTP no configurado")
        return
    message = build_message(item, settings)
    try:
        if settings.port == 465:
            with smtplib.SMTP_SSL(
                settings.host, settings.port, context=ssl.create_default_context(), timeout=15
            ) as smtp:
                smtp.login(settings.user, settings.password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(settings.host, settings.port, timeout=15) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(settings.user, settings.password)
                smtp.send_message(message)
    except (smtplib.SMTPException, OSError):
        logger.exception("No se pudo enviar la notificación de la solicitud de contacto %s", item.id)
