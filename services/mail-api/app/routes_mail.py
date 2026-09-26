import asyncio

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .auth import CurrentUser, Me
from .config import PROVIDER_PRESETS, settings
from .crypto import encrypt
from .db import get_db
from .models import MailAccount, MailMessage
from .schemas import (
    AccountEnabledIn,
    AccountIn,
    AccountOut,
    MessageBody,
    MessageOut,
    MessagePage,
    ProviderPreset,
    SendIn,
    StatePatch,
)
from .smtp import send_via_origin
from .sync import fetch_body_blocking, sync_account, test_connection
from .zugang import ZugangFehler, anmeldung_fuer

log = structlog.get_logger()
router = APIRouter()


def _account_out(a: MailAccount) -> AccountOut:
    return AccountOut(
        id=a.id,
        email=a.email,
        provider=a.provider,
        display_name=a.display_name,
        auth_typ=a.auth_typ,
        imap_host=a.imap_host,
        imap_port=a.imap_port,
        smtp_host=a.smtp_host,
        smtp_port=a.smtp_port,
        enabled=a.enabled,
        last_sync_at=a.last_sync_at,
        last_error=a.last_error,
        created_at=a.created_at,
    )


def _message_out(m: MailMessage, account_email: str) -> MessageOut:
    return MessageOut(
        id=m.id,
        account_id=m.account_id,
        account_email=account_email,
        folder=m.folder,
        uid=m.uid,
        subject=m.subject,
        from_addr=m.from_addr,
        from_name=m.from_name,
        to_addr=m.to_addr,
        snippet=m.snippet,
        date=m.date,
        is_read=m.is_read,
        is_starred=m.is_starred,
    )


def _owned_account(db: Session, me: Me, account_id: int) -> MailAccount:
    acct = (
        db.query(MailAccount)
        .filter(MailAccount.id == account_id, MailAccount.sub == me.sub)
        .one_or_none()
    )
    if not acct:
        raise HTTPException(404, "account not found")
    return acct


def _resolve_endpoints(payload: AccountIn) -> dict[str, object]:
    """Füllt IMAP/SMTP-Felder aus Provider-Preset, wo nicht explizit angegeben."""
    preset = PROVIDER_PRESETS.get(payload.provider, {})
    imap_host = payload.imap_host or preset.get("imap_host")
    smtp_host = payload.smtp_host or preset.get("smtp_host")
    if not imap_host or not smtp_host:
        raise HTTPException(
            422,
            f"Provider '{payload.provider}' unbekannt: imap_host und smtp_host explizit angeben.",
        )
    return {
        "imap_host": imap_host,
        "imap_port": payload.imap_port or preset.get("imap_port", 993),
        "imap_username": payload.imap_username or str(payload.email),
        "smtp_host": smtp_host,
        "smtp_port": payload.smtp_port or preset.get("smtp_port", 465),
        "smtp_username": payload.smtp_username or str(payload.email),
    }


@router.get("/providers", response_model=list[ProviderPreset])
def list_providers(me: Me = CurrentUser) -> list[ProviderPreset]:
    return [
        ProviderPreset(
            key=k,
            imap_host=str(v["imap_host"]),
            imap_port=int(v["imap_port"]),
            smtp_host=str(v["smtp_host"]),
            smtp_port=int(v["smtp_port"]),
            note=v.get("note"),  # type: ignore[arg-type]
        )
        for k, v in PROVIDER_PRESETS.items()
    ]


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[AccountOut]:
    rows = (
        db.query(MailAccount)
        .filter(MailAccount.sub == me.sub)
        .order_by(MailAccount.created_at)
        .all()
    )
    return [_account_out(a) for a in rows]


@router.post("/accounts", response_model=AccountOut, status_code=201)
async def add_account(
    payload: AccountIn, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> AccountOut:
    ep = _resolve_endpoints(payload)

    # Verbindungstest VOR dem Speichern (im Thread, IMAP ist synchron).
    try:
        await asyncio.to_thread(
            test_connection,
            str(ep["imap_host"]), int(ep["imap_port"]), str(ep["imap_username"]), payload.password,
        )
    except Exception as exc:
        raise HTTPException(400, f"IMAP-Login fehlgeschlagen: {str(exc)[:200]}") from exc

    exists = (
        db.query(MailAccount)
        .filter(MailAccount.sub == me.sub, MailAccount.email == str(payload.email))
        .one_or_none()
    )
    if exists:
        raise HTTPException(409, "account already connected")

    acct = MailAccount(
        sub=me.sub,
        email=str(payload.email),
        provider=payload.provider,
        display_name=payload.display_name,
        secret_cipher=encrypt(payload.password),
        **ep,  # type: ignore[arg-type]
    )
    db.add(acct)
    db.commit()
    db.refresh(acct)
    # Erst-Sync sofort anstoßen (nicht blockierend fürs Ergebnis).
    # ID statt ORM-Objekt: die Task läuft nach Session-Close, sync_account lädt selbst.
    account_id = acct.id
    asyncio.create_task(sync_account(account_id))
    return _account_out(acct)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> None:
    acct = _owned_account(db, me, account_id)
    db.query(MailMessage).filter(MailMessage.account_id == acct.id).delete()
    db.delete(acct)
    db.commit()


@router.post("/accounts/{account_id}/sync", response_model=AccountOut)
async def sync_now(
    account_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> AccountOut:
    acct = _owned_account(db, me, account_id)
    await sync_account(acct.id)
    db.refresh(acct)
    return _account_out(acct)


@router.post("/accounts/{account_id}/enabled", response_model=AccountOut)
def set_account_enabled(
    account_id: int,
    payload: AccountEnabledIn,
    me: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> AccountOut:
    """Konto pausieren/fortsetzen ohne Löschen, der Poll-Loop überspringt disabled."""
    acct = _owned_account(db, me, account_id)
    acct.enabled = payload.enabled
    db.commit()
    db.refresh(acct)
    return _account_out(acct)


@router.get("/messages", response_model=MessagePage)
def list_messages(
    me: Me = CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1),
    account_id: int | None = Query(None),
    unread: bool = Query(False),
    starred: bool = Query(False),
    suche: str | None = Query(
        None,
        description=(
            "Sucht ueber Betreff, Absender und Empfaenger des GANZEN Bestands. "
            "Nachrichtentexte sind bewusst nicht gespeichert und deshalb auch "
            "nicht durchsuchbar."
        ),
    ),
    db: Session = Depends(get_db),
) -> MessagePage:
    page_size = min(limit or settings.default_page_size, settings.max_page_size)

    q = (
        db.query(MailMessage, MailAccount)
        .join(MailAccount, MailAccount.id == MailMessage.account_id)
        .filter(MailAccount.sub == me.sub)
    )
    if account_id is not None:
        q = q.filter(MailAccount.id == account_id)
    if unread:
        q = q.filter(MailMessage.is_read.is_(False))
    if starred:
        q = q.filter(MailMessage.is_starred.is_(True))
    if suche and suche.strip():
        # ⚠️ Grenze bewusst benannt: SQLite vergleicht bei LIKE nur ASCII ohne
        # Ruecksicht auf Gross-/Kleinschreibung. "Muenchen" findet "muenchen",
        # "MÜNCHEN" findet "münchen" nicht. Dieselbe Grenze hat die Suche im
        # briefkasten; sie hier anders zu loesen hiesse, zwei Verhalten unter
        # einem Suchfeld zu haben.
        muster = f"%{suche.strip()}%"
        q = q.filter(
            or_(
                MailMessage.subject.ilike(muster),
                MailMessage.from_addr.ilike(muster),
                MailMessage.from_name.ilike(muster),
                MailMessage.to_addr.ilike(muster),
            )
        )

    total = q.count()
    rows = (
        q.order_by(MailMessage.date.desc().nullslast(), MailMessage.fetched_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    items = [_message_out(m, a.email) for m, a in rows]
    next_offset = offset + page_size if offset + page_size < total else None
    return MessagePage(
        items=items, offset=offset, limit=page_size, total=total, next_offset=next_offset
    )


@router.get("/messages/{message_id}/body", response_model=MessageBody)
async def get_message_body(
    message_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> MessageBody:
    row = (
        db.query(MailMessage, MailAccount)
        .join(MailAccount, MailAccount.id == MailMessage.account_id)
        .filter(MailMessage.id == message_id, MailAccount.sub == me.sub)
        .one_or_none()
    )
    if not row:
        raise HTTPException(404, "message not found")
    m, acct = row

    # Passwort oder frisches OAuth2-Token, je nach Konto (siehe app/zugang.py).
    try:
        anmeldung = await asyncio.to_thread(anmeldung_fuer, acct.id)
    except ZugangFehler as exc:
        raise HTTPException(502, str(exc)) from exc
    try:
        geholt = await asyncio.to_thread(
            fetch_body_blocking,
            acct.imap_host, acct.imap_port, anmeldung, m.folder, m.uid,
        )
    except Exception as exc:
        raise HTTPException(502, f"Body konnte nicht geladen werden: {str(exc)[:200]}") from exc

    return MessageBody(
        id=m.id,
        subject=m.subject,
        from_addr=m.from_addr,
        to_addr=m.to_addr,
        date=m.date,
        text=geholt.get("text"),  # type: ignore[arg-type]
        html=geholt.get("html"),  # type: ignore[arg-type]
        message_id=geholt.get("message_id"),  # type: ignore[arg-type]
        reply_to=geholt.get("reply_to") or [],  # type: ignore[arg-type]
        to=geholt.get("to") or [],  # type: ignore[arg-type]
        cc=geholt.get("cc") or [],  # type: ignore[arg-type]
    )


@router.post("/messages/{message_id}/state", response_model=MessageOut)
def set_message_state(
    message_id: int,
    payload: StatePatch,
    me: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> MessageOut:
    row = (
        db.query(MailMessage, MailAccount)
        .join(MailAccount, MailAccount.id == MailMessage.account_id)
        .filter(MailMessage.id == message_id, MailAccount.sub == me.sub)
        .one_or_none()
    )
    if not row:
        raise HTTPException(404, "message not found")
    m, acct = row

    data = payload.model_dump(exclude_unset=True)
    if "is_read" in data:
        m.is_read = bool(data["is_read"])
    if "is_starred" in data:
        m.is_starred = bool(data["is_starred"])
    db.commit()
    db.refresh(m)
    return _message_out(m, acct.email)


@router.post("/send", status_code=202)
async def send_mail(
    payload: SendIn, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> dict[str, bool]:
    acct = _owned_account(db, me, payload.account_id)
    try:
        await send_via_origin(
            acct,
            to=[str(t) for t in payload.to],
            subject=payload.subject,
            body=payload.body,
            cc=[str(c) for c in payload.cc],
            in_reply_to=payload.in_reply_to,
        )
    except Exception as exc:
        raise HTTPException(502, f"Versand fehlgeschlagen: {str(exc)[:200]}") from exc
    return {"sent": True}
