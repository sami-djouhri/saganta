"""IMAP-Aggregation: pollt aktive MailAccounts, cacht Header/Metadaten (kein Body).

Bewusst wie news/ingest.py: In-Process asyncio-Loop, eine kaputte Quelle killt den Loop nicht.
imap-tools ist synchron → wir kapseln die IMAP-Calls in asyncio.to_thread, damit der
Event-Loop nicht blockiert. Voller Body wird NICHT gecacht (live via fetch_body), nur
Header/Snippet-freie Metadaten landen at-rest (DSGVO-schonend).
"""
import asyncio
from datetime import datetime, timezone

import structlog
from imap_tools import AND, MailBox
from imap_tools.errors import MailboxLoginError
from sqlalchemy.orm import Session

from .config import settings
from .crypto import decrypt
from .zugang import Anmeldung, ZugangFehler, anmeldung_fuer
from .db import SessionLocal
from .models import MailAccount, MailMessage

log = structlog.get_logger()


def _anmelden(host: str, port: int, anmeldung: Anmeldung, ordner: str = "INBOX") -> MailBox:
    """Eine angemeldete MailBox, egal ob Passwort oder OAuth2.

    ★ Die eine Stelle, an der sich die beiden Wege unterscheiden. Ohne sie
    stuende die Fallunterscheidung an jedem der drei Anmeldeorte in dieser Datei,
    und beim naechsten waere sie vergessen worden.
    """
    box = MailBox(host, port=port, timeout=settings.imap_fetch_timeout)
    if anmeldung.oauth:
        return box.xoauth2(anmeldung.benutzer, anmeldung.geheimnis, initial_folder=ordner)
    return box.login(anmeldung.benutzer, anmeldung.geheimnis, initial_folder=ordner)


def test_connection(host: str, port: int, username: str, password: str) -> None:
    """Verbindungstest beim Anlegen eines Kontos mit Passwort. Wirft bei Fehlschlag."""
    with MailBox(host, port=port, timeout=settings.imap_fetch_timeout).login(username, password):
        pass


def test_oauth_verbindung(host: str, port: int, benutzer: str, zugriffstoken: str) -> None:
    """Verbindungstest beim Verbinden eines OAuth2-Kontos.

    ★ Gegenstueck zu `test_connection`, und der Grund ist derselbe: der Fehler
    soll beim Verbinden auffallen, wo jemand davorsitzt, nicht Stunden spaeter im
    Hintergrund-Abgleich. Bei OAuth2 faellt hier zusaetzlich der haeufigste
    Einrichtungsfehler auf, naemlich ein zu schmaler Scope: der Zugang wird
    erteilt, IMAP lehnt ihn aber ab.
    """
    with MailBox(host, port=port, timeout=settings.imap_fetch_timeout).xoauth2(
        benutzer, zugriffstoken
    ):
        pass


def _sync_account_blocking(account_id: int, host: str, port: int,
                           anmeldung: Anmeldung) -> tuple[int, str | None]:
    """Synchroner IMAP-Teil (läuft im Thread). Gibt (#neu, error) zurück.

    Eigene DB-Session, da in fremdem Thread. Nur INBOX in Stage 1.
    """
    db = SessionLocal()
    new_items = 0
    error: str | None = None
    folder = "INBOX"
    try:
        seen: set[str] = {
            u for (u,) in db.query(MailMessage.uid)
            .filter(MailMessage.account_id == account_id, MailMessage.folder == folder)
            .all()
        }
        with _anmelden(host, port, anmeldung, folder) as mailbox:
            for msg in mailbox.fetch(
                reverse=True,
                limit=settings.sync_max_messages,
                headers_only=True,
                mark_seen=False,
                bulk=True,
            ):
                uid = str(msg.uid or "")
                if not uid or uid in seen:
                    continue
                seen.add(uid)
                msg_date = msg.date
                if msg_date and msg_date.tzinfo is None:
                    msg_date = msg_date.replace(tzinfo=timezone.utc)
                db.add(
                    MailMessage(
                        account_id=account_id,
                        folder=folder,
                        uid=uid,
                        subject=(msg.subject or "")[:998],
                        from_addr=(msg.from_ or "")[:320],
                        from_name=(msg.from_values.name if msg.from_values else None),
                        to_addr=", ".join(msg.to)[:2000] if msg.to else None,
                        snippet=None,  # Body nicht cachen: live via fetch_body
                        date=msg_date,
                        is_read="\\Seen" in (msg.flags or ()),
                    )
                )
                new_items += 1
        db.commit()
    except MailboxLoginError as exc:
        db.rollback()
        error = f"Login fehlgeschlagen: {str(exc)[:200]}"
    except Exception as exc:  # eine kaputte Verbindung darf den Loop nicht killen
        db.rollback()
        error = str(exc)[:300]
    finally:
        db.close()
    return new_items, error


async def sync_account(account_id: int) -> int:
    """Async-Wrapper: lädt Konto in eigener Session, entschlüsselt Secret, synct im Thread, schreibt Status zurück.

    Nimmt bewusst die account_id (nicht das ORM-Objekt): Aufrufer wie der Erst-Sync
    (`create_task` nach Request-Ende) und `sync_all` reichten zuvor request-/loop-scoped
    MailAccount-Instanzen an diese Coroutine, die erst NACH Session-Close lief
    → DetachedInstanceError beim ersten Attributzugriff. Eigene Session = robust.
    """
    db = SessionLocal()
    try:
        account = db.get(MailAccount, account_id)
        if account is None:
            log.warning("mail.sync.account_gone", account=account_id)
            return 0
        imap_host = account.imap_host
        imap_port = account.imap_port
    finally:
        db.close()

    # Passwort oder frisches OAuth2-Token, je nach Konto. Die Auffrischung kann
    # eine Anbieter-Anfrage kosten, deshalb im Thread: der Ereignisschleife
    # dieses Dienstes gehoert kein blockierender Netzaufruf.
    try:
        anmeldung = await asyncio.to_thread(anmeldung_fuer, account_id)
    except ZugangFehler as exc:
        _record_status(account_id, str(exc)[:300])
        log.warning("mail.sync.zugang", account=account_id, error=str(exc)[:200])
        return 0
    except Exception as exc:
        _record_status(account_id, str(exc)[:300])
        log.warning("mail.sync.decrypt_error", account=account_id, error=str(exc)[:200])
        return 0

    new_items, error = await asyncio.to_thread(
        _sync_account_blocking,
        account_id, imap_host, imap_port, anmeldung,
    )
    _record_status(account_id, error)
    if error:
        log.warning("mail.sync.error", account=account_id, error=error[:200])
    else:
        log.info("mail.sync.ok", account=account_id, new=new_items)
    return new_items


def _record_status(account_id: int, error: str | None) -> None:
    db = SessionLocal()
    try:
        acct = db.get(MailAccount, account_id)
        if acct:
            acct.last_sync_at = datetime.now(timezone.utc)
            acct.last_error = error
            db.commit()
    finally:
        db.close()


async def sync_all() -> int:
    db = SessionLocal()
    try:
        account_ids = [
            a.id for a in db.query(MailAccount).filter(MailAccount.enabled.is_(True)).all()
        ]
    finally:
        db.close()
    total = 0
    for account_id in account_ids:
        total += await sync_account(account_id)
    return total


async def poll_loop() -> None:
    log.info("mail.poll_loop.start", interval=settings.sync_interval_seconds)
    while True:
        try:
            await sync_all()
        except Exception as exc:  # Loop-Backstop
            log.error("mail.poll_loop.error", error=str(exc)[:200])
        await asyncio.sleep(settings.sync_interval_seconds)


def fetch_body_blocking(host: str, port: int, anmeldung: Anmeldung,
                        folder: str, uid: str) -> dict[str, object]:
    """Holt EINE Nachricht live (Thread). Cacht nichts.

    Liefert neben Text/HTML die Felder, die eine **Antwort** braucht: die
    Message-ID fuer `In-Reply-To`/`References`, das `Reply-To` des Absenders und
    die Mitempfaenger fuer "Allen antworten".

    ★ Sie werden hier geholt und nicht gespeichert, und das ist der Punkt: die
    Entscheidung, Nachrichteninhalte nicht at-rest zu halten (siehe Modul-Kopf),
    bleibt unberuehrt, und es gibt trotzdem einen Weg zu antworten. Eine eigene
    Spalte haette zusaetzlich nur fuer kuenftig abgeholte Nachrichten gegolten.

    ⚠️ `Reply-To` gewinnt bewusst gegen `From`. Newsletter und Ticketsysteme
    setzen genau dafuer diesen Kopf; wer stattdessen an `From` antwortet,
    schreibt an eine Adresse, die niemand liest (`noreply@`).
    """
    with _anmelden(host, port, anmeldung, folder) as mailbox:
        for msg in mailbox.fetch(AND(uid=uid), mark_seen=False, bulk=True):
            kopf = msg.headers.get("message-id", ())
            return {
                "text": msg.text or None,
                "html": msg.html or None,
                "message_id": (kopf[0].strip() if kopf else None),
                "reply_to": list(msg.reply_to or ()),
                "to": list(msg.to or ()),
                "cc": list(msg.cc or ()),
            }
    return {"text": None, "html": None, "message_id": None, "reply_to": [], "to": [], "cc": []}
