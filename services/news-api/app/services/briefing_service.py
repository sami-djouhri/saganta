"""Orchestrierung: Profil/Delivery-Verwaltung, Briefing-Generierung (Assembly +
optional Audio), Retention und Webhook-Auslösung. Alles pro `sub`.
"""
from __future__ import annotations

import os
import secrets
from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy.orm import Session

from ..briefing_models import BriefingProfile, DeliveryConfig, UserBriefing
from ..config import settings
from saganta_dienst import tarife

from . import briefing_assembly, briefing_tts, delivery
from . import interest_taxonomy as tax
from . import plans

log = structlog.get_logger()


def get_or_create_profile(db: Session, sub: str) -> BriefingProfile:
    prof = db.get(BriefingProfile, sub)
    if prof is None:
        prof = BriefingProfile(sub=sub, interests=list(tax.DEFAULT_INTERESTS))
        db.add(prof)
        db.commit()
        db.refresh(prof)
    return prof


def profil_mit_tarif(db: Session, me) -> BriefingProfile:
    """Holt das Profil und gleicht seinen Tarif am Konto ab.

    ★ Warum ``briefing_profiles.plan`` trotz der Umstellung bleibt: der
    Briefing-Scheduler laeuft ohne Anfrage und sieht deshalb nie einen Token.
    Er braucht den Tarif als lesbaren Wert in dieser Datenbank. Die Spalte ist
    seit dem 02.09.2026 aber kein eigener Bestand mehr, sondern ein **Spiegel**
    des Kontos: die Wahrheit steht in ``user.plan`` der auth-DB und kommt mit
    jeder Anfrage im ``plan``-Claim mit.

    Der Abgleich passiert hier, weil dies die eine Stelle ist, an der ein
    angemeldeter Nutzer und sein Profil zusammentreffen. Kuendigt jemand, meldet
    Stripe es zwar direkt ans Konto, aber ein Weg, auf dem der Spiegel auch ohne
    Stripe nachzieht (Owner setzt von Hand, Datenbank restauriert), ist die
    billigere Absicherung gegen zwei Wahrheiten.
    """
    prof = get_or_create_profile(db, me.sub)
    konto_tarif = tarife.normalisiere(getattr(me, "plan", None))
    if (prof.plan or tarife.FREI) != konto_tarif:
        log.info(
            "briefing.tarif.spiegel_nachgezogen",
            sub=me.sub, vorher=prof.plan, nachher=konto_tarif,
        )
        prof.plan = konto_tarif
        db.commit()
        db.refresh(prof)
    return prof


def get_or_create_delivery(db: Session, sub: str) -> DeliveryConfig:
    dc = db.get(DeliveryConfig, sub)
    if dc is None:
        dc = DeliveryConfig(sub=sub, feed_token=secrets.token_urlsafe(24))
        db.add(dc)
        db.commit()
        db.refresh(dc)
    return dc


def rotate_feed_token(db: Session, sub: str) -> DeliveryConfig:
    dc = get_or_create_delivery(db, sub)
    dc.feed_token = secrets.token_urlsafe(24)
    db.commit()
    db.refresh(dc)
    return dc


def generate_for_sub(
    db: Session,
    sub: str,
    for_date: date | None = None,
    force: bool = False,
    with_audio: bool | None = None,
) -> UserBriefing | None:
    """Erzeugt (oder holt) das Briefing eines Users für einen Tag."""
    prof = get_or_create_profile(db, sub)
    if not prof.enabled and not force:
        return None
    for_date = for_date or datetime.now(timezone.utc).date()

    existing = (
        db.query(UserBriefing)
        .filter(UserBriefing.sub == sub, UserBriefing.briefing_date == for_date)
        .one_or_none()
    )
    if existing and not force:
        return existing

    content = briefing_assembly.assemble(db, prof, for_date)

    if existing:
        existing.content = content
        existing.audio_path = None
        existing.audio_mime = None
        ub = existing
    else:
        ub = UserBriefing(sub=sub, briefing_date=for_date, content=content)
        db.add(ub)
    db.commit()
    db.refresh(ub)

    do_audio = audio_erlaubt(prof) if with_audio is None else with_audio
    if do_audio and briefing_tts.available():
        render_audio(db, sub, for_date)  # synchron (Scheduler-Pfad läuft eh im Hintergrund)

    _fire_webhook(db, sub, ub)
    return ub


def audio_erlaubt(prof: BriefingProfile | None) -> bool:
    """Darf fuer dieses Profil ueberhaupt synthetisiert werden?

    Zwei Bedingungen, und beide muessen halten: der Nutzer will Audio, und sein
    Tarif schliesst es ein. Die Tarif-Bedingung ist seit dem 30.08.2026 dabei,
    weil die Synthese der teure Teil des Briefings ist (XTTS single-threaded,
    20 bis 40 s) und bei offener Registrierung sonst jeder Angemeldete taeglich
    Rechenzeit im Haus bindet.

    An einer Stelle, damit Scheduler und Lesepfad dieselbe Antwort bekommen.
    """
    if not prof or not prof.audio_enabled:
        return False
    return bool(plans.features(prof.plan)["audio"])


def render_audio(db: Session, sub: str, for_date: date | None = None) -> bool:
    """Rendert das Audio für ein bereits erzeugtes Briefing (CPU-schwer, ~1-2 min).

    Als eigene Funktion, damit Routen sie via BackgroundTask asynchron aufrufen können,
    ohne den HTTP-Request ~100 s zu blockieren.
    """
    if not briefing_tts.available():
        return False
    for_date = for_date or datetime.now(timezone.utc).date()
    ub = (
        db.query(UserBriefing)
        .filter(UserBriefing.sub == sub, UserBriefing.briefing_date == for_date)
        .one_or_none()
    )
    if not ub:
        return False
    prof = db.get(BriefingProfile, sub)
    if not plans.features(prof.plan if prof else None)["audio"]:
        # Auch hier und nicht nur beim Aufrufer: dies ist die einzige Stelle, an
        # der wirklich synthetisiert wird, und damit die einzige, die den Tarif
        # zuverlaessig durchsetzen kann.
        return False
    voice = prof.voice if prof else ""
    # Premium-Stimme (LLM-redigierte, natürliche Fassung) nur für Pro; Free bekommt
    # den deterministischen Sprech-Text. Das ist zugleich das Kosten-Gating (LLM-Calls
    # nur für zahlende Nutzer).
    if plans.features(prof.plan if prof else None)["premium_voice"]:
        narration = briefing_assembly.spoken_narration(ub.content or {})
    else:
        narration = (ub.content or {}).get("spoken_text", "")
    path, mime = briefing_tts.render(sub, for_date.isoformat(), narration, voice)
    if path:
        ub.audio_path = path
        ub.audio_mime = mime
        db.commit()
        return True
    return False


def _fire_webhook(db: Session, sub: str, ub: UserBriefing) -> None:
    dc = db.get(DeliveryConfig, sub)
    if not dc or not dc.webhook_url:
        return
    top = (ub.content or {}).get("top_story") or {}
    audio_url = None
    if dc.feed_token and settings.public_base_url:
        audio_url = f"{settings.public_base_url.rstrip('/')}/briefing/audio/{dc.feed_token}/{ub.briefing_date.isoformat()}"
    delivery.post_webhook(
        dc.webhook_url,
        dc.webhook_secret,
        {
            "event": "briefing.ready",
            "date": ub.briefing_date.isoformat(),
            "title": top.get("title"),
            "item_count": (ub.content or {}).get("item_count", 0),
            "audio_url": audio_url,
        },
    )


def generate_all(db: Session) -> int:
    """Scheduler-Einstieg: Briefings für alle aktivierten Profile erzeugen."""
    profiles = db.query(BriefingProfile).filter(BriefingProfile.enabled.is_(True)).all()
    count = 0
    for prof in profiles:
        try:
            generate_for_sub(db, prof.sub, force=True)
            count += 1
        except Exception as exc:  # ein User darf den Batch nicht killen
            db.rollback()
            log.error("briefing.generate.error", sub=prof.sub, error=str(exc)[:200])
    log.info("briefing.generate_all.done", profiles=count)
    return count


def cleanup(db: Session) -> int:
    """Löscht Briefings + Audios älter als Retention-Fenster."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=settings.briefing_retention_days)
    old = db.query(UserBriefing).filter(UserBriefing.briefing_date < cutoff).all()
    n = 0
    for ub in old:
        if ub.audio_path and os.path.exists(ub.audio_path):
            try:
                os.remove(ub.audio_path)
            except OSError:
                pass
        db.delete(ub)
        n += 1
    if n:
        db.commit()
    return n
