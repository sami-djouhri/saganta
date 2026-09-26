from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MailAccount(Base):
    """Ein externes Mailkonto eines Mitglieds (Gmail/GMX/...). sub-gescoped = privat.

    Anders als news (geteilte Quellen) gehört jedes Konto GENAU EINEM User → die
    Nachrichten sind über das Konto bereits user-privat, ein separates UserState
    entfällt (read/starred liegen direkt an MailMessage).
    """

    __tablename__ = "mail_accounts"
    __table_args__ = (UniqueConstraint("sub", "email", name="uq_account_sub_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sub: Mapped[str] = mapped_column(String(128), index=True)
    email: Mapped[str] = mapped_column(String(320))
    provider: Mapped[str] = mapped_column(String(40), default="custom")
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    imap_host: Mapped[str] = mapped_column(String(255))
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    imap_username: Mapped[str] = mapped_column(String(320))

    smtp_host: Mapped[str] = mapped_column(String(255))
    smtp_port: Mapped[int] = mapped_column(Integer, default=465)
    smtp_username: Mapped[str] = mapped_column(String(320))

    # Fernet-Ciphertext (NIE Klartext). IMAP- und SMTP-Passwort sind i. d. R. identisch
    # (ein App-Passwort) → ein Secret. Falls getrennt nötig, später zweites Feld.
    #
    # ★ Bei einem OAuth2-Konto steht hier der **Auffrischungstoken**, ebenfalls
    # verschlüsselt. Er hat dieselbe Rolle wie das Passwort (das eine Geheimnis,
    # das dauerhaft liegt) und darf deshalb im selben Feld liegen; welcher der
    # beiden es ist, sagt `auth_typ`.
    secret_cipher: Mapped[str] = mapped_column(Text)

    # ── OAuth2 (seit 2026-09-13) ────────────────────────────────────────────
    #
    # `passwort` ist die Vorbelegung, damit jedes bestehende Konto ohne
    # Datenwanderung weiterläuft: eine Spalte mit Vorgabewert ändert an ihnen
    # nichts, und ein Konto, das vorher ging, geht danach genauso.
    auth_typ: Mapped[str] = mapped_column(String(20), default="passwort", server_default="passwort")
    #: Anbieter-Schlüssel bei OAuth2 (`google`, `microsoft`), sonst leer.
    oauth_anbieter: Mapped[str | None] = mapped_column(String(40), nullable=True)
    #: Kurzlebiger Zugriffstoken, verschlüsselt. Wird bei Bedarf erneuert.
    oauth_zugriff_cipher: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Wann der Zugriffstoken abläuft. Vor jedem Abruf geprüft.
    oauth_laeuft_ab: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class MailMessage(Base):
    """Gecachte Nachrichten-Metadaten (Header + Snippet). Voller Body wird live geholt.

    Dedup über (account_id, folder, uid). Volltext bewusst NICHT at-rest (DSGVO/Leak);
    snippet ist nur die ersten Zeichen für die Listenansicht.
    """

    __tablename__ = "mail_messages"
    __table_args__ = (UniqueConstraint("account_id", "folder", "uid", name="uq_msg_acct_folder_uid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("mail_accounts.id"), index=True)
    folder: Mapped[str] = mapped_column(String(120), default="INBOX")
    uid: Mapped[str] = mapped_column(String(80))

    subject: Mapped[str] = mapped_column(String(998), default="")
    from_addr: Mapped[str] = mapped_column(String(320), default="")
    from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_addr: Mapped[str | None] = mapped_column(Text, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
