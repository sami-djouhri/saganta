from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class ProviderPreset(BaseModel):
    key: str
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    note: str | None = None


class AccountIn(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, description="App-Passwort (wird verschlüsselt abgelegt)")
    provider: str = "custom"
    display_name: str | None = None
    # Optional: bei bekanntem provider aus Presets gefüllt, sonst Pflicht.
    imap_host: str | None = None
    imap_port: int | None = None
    imap_username: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None


class AccountOut(BaseModel):
    id: int
    email: str
    provider: str
    display_name: str | None
    # `passwort` oder `oauth2`. Die Oberflaeche zeigt damit, woran ein Konto
    # haengt: bei OAuth2 gibt es kein Passwort zu aendern, sondern einen Zugriff
    # zu erneuern, und das sind zwei verschiedene Saetze.
    auth_typ: str = "passwort"

    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    enabled: bool
    last_sync_at: datetime | None
    last_error: str | None
    created_at: datetime


class MessageOut(BaseModel):
    id: int
    account_id: int
    account_email: str
    folder: str
    uid: str
    subject: str
    from_addr: str
    from_name: str | None
    to_addr: str | None
    snippet: str | None
    date: datetime | None
    is_read: bool
    is_starred: bool


class MessagePage(BaseModel):
    items: list[MessageOut]
    offset: int
    limit: int
    total: int
    next_offset: int | None


class MessageBody(BaseModel):
    id: int
    subject: str
    from_addr: str
    to_addr: str | None
    date: datetime | None
    text: str | None
    html: str | None

    # Felder fuer eine Antwort. Live aus der Nachricht geholt, nicht gespeichert
    # (Begruendung in sync.fetch_body_blocking).
    #: RFC-5322-Message-ID, fuer `In-Reply-To`/`References` beim Antworten.
    message_id: str | None = None
    #: Antwortadresse des Absenders, falls gesetzt. Hat Vorrang vor `from_addr`.
    reply_to: list[str] = Field(default_factory=list)
    #: Empfaenger und Mitempfaenger des Originals, fuer "Allen antworten".
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)


class StatePatch(BaseModel):
    is_read: bool | None = None
    is_starred: bool | None = None


class AccountEnabledIn(BaseModel):
    enabled: bool


class SendIn(BaseModel):
    account_id: int
    to: list[EmailStr] = Field(..., min_length=1)
    subject: str = ""
    body: str = ""
    cc: list[EmailStr] = Field(default_factory=list)
    in_reply_to: str | None = None
