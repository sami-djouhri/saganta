"""Versand AUSSCHLIESSLICH über den Origin-SMTP des jeweiligen Kontos („Senden als").

Damit verschickt die saganta-/netcup-Infrastruktur NIE im Namen Fremder → keine fremde Last
auf der eigenen IP-Reputation. Wir authentifizieren uns mit den Zugangsdaten des
Nutzers gegen dessen Anbieter und senden von dort.
"""
import asyncio
from email.message import EmailMessage

import aiosmtplib
import structlog

from .config import settings
from .models import MailAccount
from .zugang import anmeldung_fuer

log = structlog.get_logger()


async def send_via_origin(
    account: MailAccount,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    in_reply_to: str | None = None,
) -> None:
    # Passwort oder frisches OAuth2-Token, je nach Konto (siehe app/zugang.py).
    # Im Thread, weil das Auffrischen eine Anbieter-Anfrage kosten kann.
    anmeldung = await asyncio.to_thread(anmeldung_fuer, account.id)

    msg = EmailMessage()
    msg["From"] = account.email
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.set_content(body or "")

    # Port 465 = implizites TLS; 587 = STARTTLS. aiosmtplib leitet aus use_tls/start_tls ab.
    use_tls = account.smtp_port == 465
    start_tls = account.smtp_port == 587

    if not anmeldung.oauth:
        await aiosmtplib.send(
            msg,
            hostname=account.smtp_host,
            port=account.smtp_port,
            username=anmeldung.benutzer,
            password=anmeldung.geheimnis,
            use_tls=use_tls,
            start_tls=start_tls,
            timeout=settings.imap_fetch_timeout,
        )
        log.info("mail.send.ok", account=account.id, to=len(to))
        return

    # ★ OAuth2 braucht einen eigenen Weg: `aiosmtplib.send()` kennt nur
    # Benutzername und Passwort. Wer das Zugriffstoken einfach als `password`
    # übergibt, bekommt eine Ablehnung, die wie ein falsches Passwort aussieht,
    # obwohl das Token gültig ist: der Server erwartet ein anderes
    # SASL-Verfahren, nicht andere Zeichen.
    #
    # ★★ Benutzt wird `auth_xoauth2` der Bibliothek und **kein** selbst gebautes
    # `AUTH XOAUTH2`. Der Unterschied ist der Fehlerfall: bei einem abgelehnten
    # Token antwortet der Server mit einer Zwischenmeldung (334) samt Grund als
    # base64-JSON und erwartet darauf eine Leerzeile, bevor er die endgültige
    # Fehlermeldung schickt. Wer das nicht tut, sieht nur ein hängendes 334 und
    # verliert genau die Auskunft, warum der Zugang abgelehnt wurde.
    smtp = aiosmtplib.SMTP(
        hostname=account.smtp_host,
        port=account.smtp_port,
        use_tls=use_tls,
        start_tls=start_tls,
        timeout=settings.imap_fetch_timeout,
    )
    async with smtp:
        await smtp.auth_xoauth2(anmeldung.benutzer, anmeldung.geheimnis)
        await smtp.send_message(msg)
    log.info("mail.send.ok", account=account.id, to=len(to), oauth=True)
