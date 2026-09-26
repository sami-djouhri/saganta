"""Briefing-Routen (Multiuser). Authed-Routen sind `sub`-gated über CurrentUser;
die öffentlichen Podcast-/Audio-Routen sind ausschließlich per unguessable
feed_token geschützt (kein Login-Credential in fremden Apps).
"""
from datetime import date

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .auth import CurrentUser, Me
from .db import SessionLocal
from .briefing_models import BriefingFeedback, DeliveryConfig, UserBriefing
from .models import UserItemState
from .briefing_schemas import (
    BriefingOut,
    BriefingSummary,
    DeliveryOut,
    DeliveryPatch,
    FeedbackIn,
    GenerateIn,
    InterestOption,
    PlanOut,
    ProfileOut,
    ProfilePatch,
)
from . import briefing_sched
from .config import settings
from .db import get_db
from .services import (
    briefing_service,
    briefing_tts,
    delivery,
    plans,
    podcast_feed,
    stripe_service,
    tarif_konto,
)
from .services import interest_taxonomy as tax

log = structlog.get_logger()
router = APIRouter()


def _profile_out(prof) -> ProfileOut:
    return ProfileOut(
        enabled=prof.enabled,
        plan=prof.plan or "free",
        interests=prof.interests or [],
        free_topics=prof.free_topics or [],
        feed_optout=prof.feed_optout or [],
        length=prof.length,
        audio_enabled=prof.audio_enabled,
        voice=prof.voice,
        delivery_time=prof.delivery_time,
        weather_lat=prof.weather_lat,
        weather_lon=prof.weather_lon,
        weather_place=prof.weather_place,
    )


# ── Onboarding-Metadaten ────────────────────────────────────────────────────
@router.get("/interests", response_model=list[InterestOption])
def list_interests(me: Me = CurrentUser) -> list[InterestOption]:
    return [InterestOption(tag=t, label=tax.label_for(t)) for t in tax.SELECTABLE_TAGS]


# ── Tarif / Freemium ────────────────────────────────────────────────────────
@router.get("/plan", response_model=PlanOut)
def get_plan(me: Me = CurrentUser, db: Session = Depends(get_db)) -> PlanOut:
    prof = briefing_service.profil_mit_tarif(db, me)
    plan = prof.plan or "free"
    return PlanOut(
        plan=plan,
        features=plans.features(plan),
        pro_benefits=plans.PRO_BENEFITS,
        is_pro=(plan == plans.PRO),
        stripe_enabled=stripe_service.enabled(),
        plan_status=prof.plan_status,
    )


# ── Stripe Self-Service-Payment ─────────────────────────────────────────────
@router.post("/checkout")
def create_checkout(me: Me = CurrentUser, db: Session = Depends(get_db)) -> dict:
    """Startet den Stripe-Checkout für Pro. 503 wenn Stripe (noch) nicht konfiguriert
    ist → Frontend fällt auf den mailto-Kontakt zurück."""
    if not stripe_service.enabled():
        raise HTTPException(503, "Zahlung ist noch nicht aktiviert")
    try:
        url = stripe_service.create_checkout_session(me.sub, me.email, db)
    except Exception as exc:
        log.error("stripe.checkout.error", sub=me.sub, error=str(exc)[:200])
        raise HTTPException(502, "Checkout konnte nicht gestartet werden")
    return {"url": url}


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
) -> dict:
    """Stripe-Webhook (KEIN Login, nur Signatur-Verify). Setzt plan bei Kauf,
    entzieht ihn bei Kündigung. Idempotent gegen Retries."""
    if not stripe_service.enabled() or not settings.stripe_webhook_secret:
        raise HTTPException(503, "Stripe nicht konfiguriert")
    if not stripe_signature:
        raise HTTPException(400, "Signatur fehlt")
    payload = await request.body()
    try:
        return stripe_service.handle_webhook_event(payload, stripe_signature, db)
    except HTTPException:
        raise
    except Exception as exc:
        # Ungültige Signatur / Parse-Fehler → 400, Stripe wiederholt später.
        log.error("stripe.webhook.error", error=str(exc)[:200])
        raise HTTPException(400, "Webhook-Verifizierung fehlgeschlagen")


def _require_admin(me: Me) -> None:
    """Owner-Gate für Admin-Routen (settings.admin_subs). Leer = niemand."""
    if not settings.admin_subs or me.sub not in settings.admin_subs:
        raise HTTPException(403, "Nur Owner darf diese Aktion ausführen")


@router.post("/admin/set-plan")
def admin_set_plan(
    target_sub: str = Query(..., description="better-auth sub des Ziel-Users"),
    plan: str = Query(..., pattern="^(free|pro)$"),
    me: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    """Vergibt/entzieht Pro. Owner-gegatet (settings.admin_subs), bis Stripe live ist.
    Später ersetzt ein Stripe-Webhook diesen manuellen Pfad.

    ★ Schreibt ans Konto (auth-DB) und in den Spiegel. Ginge es nur in den
    Spiegel, waere die Vergabe hier wirksam und in den sechs anderen Backends
    unsichtbar: der Nutzer haette Pro im Briefing und `free` im Token.
    """
    _require_admin(me)
    am_konto = tarif_konto.setze_tarif(target_sub, plan, "manuell")
    prof = briefing_service.get_or_create_profile(db, target_sub)
    prof.plan = plan
    db.commit()
    if not am_konto:
        # Nicht verschweigen: der Aufrufer glaubt sonst, es habe suite-weit
        # gewirkt. Der Spiegel steht, das Konto nicht.
        log.error("admin.set_plan.konto_nicht_erreicht", sub=target_sub, plan=plan)
    return {"ok": True, "sub": target_sub, "plan": plan, "am_konto": am_konto}


def _with_live_item_state(db: Session, sub: str, content: dict) -> dict:
    """Überlagert `read`/`bookmarked` im Briefing-Inhalt mit dem aktuellen Feed-Zustand.

    Das gespeicherte `content` ist ein Schnappschuss vom Erzeugungszeitpunkt: richtig
    für Auswahl, Reihenfolge und Texte, falsch für den Zustand: wer einen Artikel merkt,
    sähe sonst bis morgen weiter „Merken" und hielte seinen Klick für wirkungslos.
    Die Auswahl wird bewusst NICHT neu berechnet; nur die zwei Zustandsfelder.
    """
    ids = {
        e["id"]
        for group in [content.get("top_items", [])] + [
            s.get("items", []) for s in content.get("sections", [])
        ]
        for e in group
        if isinstance(e.get("id"), int)
    }
    if not ids:
        return content
    states = {
        st.item_id: st
        for st in db.query(UserItemState)
        .filter(UserItemState.sub == sub, UserItemState.item_id.in_(ids))
        .all()
    }

    def _apply(entry: dict) -> None:
        st = states.get(entry.get("id"))
        entry["read"] = bool(st and st.read)
        entry["bookmarked"] = bool(st and st.bookmarked)

    for entry in content.get("top_items", []):
        _apply(entry)
    if isinstance(content.get("top_story"), dict):
        _apply(content["top_story"])
    for sec in content.get("sections", []):
        for entry in sec.get("items", []):
            _apply(entry)
    return content


def _generate_bg(sub: str, for_date, with_audio: bool) -> None:
    """BackgroundTask: eigene DB-Session, erzeugt Text (+optional Audio) für einen Sub."""
    db = SessionLocal()
    try:
        briefing_service.generate_for_sub(db, sub, for_date, force=True, with_audio=with_audio)
    except Exception as exc:
        log.error("briefing.admin.generate.error", sub=sub, error=str(exc)[:200])
    finally:
        db.close()


@router.post("/admin/generate")
def admin_generate(
    background: BackgroundTasks,
    target_sub: str = Query(..., description="better-auth sub des Ziel-Users"),
    with_audio: bool = Query(True, description="Auch das MP3 erzeugen (CPU-schwer)"),
    me: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    """On-Demand-Erzeugung eines Briefings für einen Sub (Owner-gegatet), ohne auf den
    nächtlichen Scheduler zu warten. Text sofort, Audio (~100 s) als BackgroundTask →
    löst den Owner-Playback-Timeout (Samis MP3 vorab erzeugen)."""
    _require_admin(me)
    audio = with_audio and briefing_tts.available()
    # Text synchron erzeugen (schnell), damit der Aufrufer sofort Erfolg sieht.
    ub = briefing_service.generate_for_sub(db, target_sub, None, force=True, with_audio=False)
    if ub is None:
        raise HTTPException(400, "Generierung fehlgeschlagen (Profil deaktiviert?)")
    if audio:
        background.add_task(_generate_bg, target_sub, ub.briefing_date, True)
    return {
        "ok": True,
        "sub": target_sub,
        "date": ub.briefing_date.isoformat(),
        "audio_queued": bool(audio),
        "tts_available": briefing_tts.available(),
    }


@router.get("/admin/sched-status")
def admin_sched_status(me: Me = CurrentUser) -> dict:
    """Beobachtbarkeit: letzter/nächster Scheduler-Lauf (Owner-gegatet)."""
    _require_admin(me)
    return briefing_sched.status()


# ── Profil ──────────────────────────────────────────────────────────────────
@router.get("/profile", response_model=ProfileOut)
def get_profile(me: Me = CurrentUser, db: Session = Depends(get_db)) -> ProfileOut:
    return _profile_out(briefing_service.profil_mit_tarif(db, me))


@router.patch("/profile", response_model=ProfileOut)
def patch_profile(
    payload: ProfilePatch, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> ProfileOut:
    prof = briefing_service.profil_mit_tarif(db, me)
    data = payload.model_dump(exclude_unset=True)
    if "interests" in data and data["interests"] is not None:
        prof.interests = [
            {"tag": i["tag"], "weight": float(i["weight"])}
            for i in data["interests"]
            if i["tag"] in tax.INTERESTS
        ]
    for field in ("enabled", "free_topics", "feed_optout", "length", "audio_enabled", "voice",
                  "delivery_time", "weather_lat", "weather_lon", "weather_place"):
        if field in data and data[field] is not None:
            setattr(prof, field, data[field])
    db.commit()
    db.refresh(prof)
    return _profile_out(prof)


# ── Briefing lesen / erzeugen ───────────────────────────────────────────────
@router.get("/history", response_model=list[BriefingSummary])
def get_history(me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[BriefingSummary]:
    """Die aufbewahrten Briefings dieses Users, neuestes zuerst.

    Damit lässt sich zurückblättern statt nur „heute" zu sehen, die Briefings
    liegen ohnehin `briefing_retention_days` lang in der Datenbank, es fehlte
    bloss der Weg dorthin.
    """
    rows = (
        db.query(UserBriefing)
        .filter(UserBriefing.sub == me.sub)
        .order_by(UserBriefing.briefing_date.desc())
        .limit(settings.briefing_retention_days)
        .all()
    )
    out = []
    for ub in rows:
        content = ub.content or {}
        top = content.get("top_story") or {}
        out.append(
            BriefingSummary(
                date=ub.briefing_date,
                item_count=content.get("item_count", 0),
                has_audio=bool(ub.audio_path),
                top_title=top.get("title"),
            )
        )
    return out


@router.get("/today/item-ids")
def get_today_item_ids(me: Me = CurrentUser, db: Session = Depends(get_db)) -> dict:
    """Die Artikel-IDs im heutigen Briefing: **schlägt nur nach, erzeugt nie**.

    Gegenstück zur Verknüpfung in der anderen Richtung: der News-Feed markiert
    damit, was es ins Briefing geschafft hat. Bewusst als eigener Endpunkt statt
    über `/today`, denn `/today` erzeugt das Briefing bei Bedarf (samt Kalender-
    und Wetterabruf), ein Seiteneffekt, den das blosse Öffnen der Feed-Liste
    nicht auslösen darf.
    """
    ub = (
        db.query(UserBriefing)
        .filter(UserBriefing.sub == me.sub, UserBriefing.briefing_date == date.today())
        .one_or_none()
    )
    if not ub:
        return {"date": None, "item_ids": []}
    content = ub.content or {}
    ids: list[int] = []
    for entry in content.get("top_items", []):
        if isinstance(entry.get("id"), int):
            ids.append(entry["id"])
    for sec in content.get("sections", []):
        for entry in sec.get("items", []):
            if isinstance(entry.get("id"), int):
                ids.append(entry["id"])
    return {"date": ub.briefing_date.isoformat(), "item_ids": sorted(set(ids))}


@router.get("/today", response_model=BriefingOut)
def get_today(
    me: Me = CurrentUser,
    for_date: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
) -> BriefingOut:
    # Vergangene Tage werden nur nachgeschlagen, nie erzeugt: der Artikelpool
    # reicht nur `briefing_window_hours` zurück, ein nachträglich gebautes
    # „Briefing von gestern" wäre aus heutigen Meldungen zusammengesetzt und
    # trüge trotzdem das alte Datum. Lieber 404 als eine plausible Fälschung.
    today = date.today()
    if for_date and for_date != today:
        ub = (
            db.query(UserBriefing)
            .filter(UserBriefing.sub == me.sub, UserBriefing.briefing_date == for_date)
            .one_or_none()
        )
        if ub is None:
            raise HTTPException(404, "Für diesen Tag gibt es kein Briefing")
    else:
        # Lazy: nur Text generieren (Audio ist CPU-schwer → Scheduler/explizit).
        ub = briefing_service.generate_for_sub(db, me.sub, for_date, force=False, with_audio=False)
    if ub is None:
        raise HTTPException(404, "Briefing deaktiviert oder nicht verfügbar")
    return BriefingOut(
        date=ub.briefing_date,
        content=_with_live_item_state(db, me.sub, ub.content or {}),
        has_audio=bool(ub.audio_path),
        audio_mime=ub.audio_mime,
    )


def _render_audio_bg(sub: str, for_date) -> None:
    """BackgroundTask: eigene DB-Session (Request-Session ist längst geschlossen)."""
    db = SessionLocal()
    try:
        briefing_service.render_audio(db, sub, for_date)
    finally:
        db.close()


@router.post("/generate", response_model=BriefingOut)
def generate(
    payload: GenerateIn,
    background: BackgroundTasks,
    me: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> BriefingOut:
    # Text sofort erzeugen (schnell); Audio-TTS (~100 s) läuft asynchron im Hintergrund,
    # damit der Request nicht in Proxy-Timeouts läuft. Frontend lädt danach neu.
    ub = briefing_service.generate_for_sub(db, me.sub, payload.date, force=True, with_audio=False)
    if ub is None:
        raise HTTPException(400, "Generierung fehlgeschlagen")
    if payload.with_audio and briefing_tts.available():
        background.add_task(_render_audio_bg, me.sub, ub.briefing_date)
    return BriefingOut(
        date=ub.briefing_date,
        content=ub.content or {},
        has_audio=bool(ub.audio_path),
        audio_mime=ub.audio_mime,
    )


@router.get("/audio/today")
def get_own_audio(
    me: Me = CurrentUser,
    for_date: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
) -> FileResponse:
    q = db.query(UserBriefing).filter(UserBriefing.sub == me.sub)
    if for_date:
        q = q.filter(UserBriefing.briefing_date == for_date)
    ub = q.order_by(UserBriefing.briefing_date.desc()).first()
    if not ub or not ub.audio_path:
        raise HTTPException(404, "Kein Audio vorhanden")
    return FileResponse(ub.audio_path, media_type=ub.audio_mime or "audio/mpeg")


# ── Feedback ────────────────────────────────────────────────────────────────
@router.post("/feedback")
def post_feedback(
    payload: FeedbackIn, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> dict:
    row = (
        db.query(BriefingFeedback)
        .filter(BriefingFeedback.sub == me.sub, BriefingFeedback.item_link == payload.link)
        .one_or_none()
    )
    if row is None:
        row = BriefingFeedback(sub=me.sub, item_link=payload.link)
        db.add(row)
    row.signal = payload.signal
    db.commit()
    return {"ok": True}


# ── Delivery-Konfiguration ──────────────────────────────────────────────────
def _feed_url(dc: DeliveryConfig) -> str | None:
    if not settings.public_base_url:
        return None
    return f"{settings.public_base_url.rstrip('/')}/briefing/feed/{dc.feed_token}.xml"


def _json_url(dc: DeliveryConfig) -> str | None:
    """Abruf-Adresse fuer eine Heim-Automation (Home Assistant, Skript).

    ★ Gegenstueck zum Webhook daneben, und der Unterschied ist die Richtung: der
    Webhook verlangt, dass die eigene Hausautomation von aussen erreichbar ist.
    Beim Abruf geht die Verbindung von innen nach aussen, es muss also nichts
    geoeffnet werden. Fuer ein Heimnetz ist das der richtige Weg herum.
    """
    if not settings.public_base_url:
        return None
    return f"{settings.public_base_url.rstrip('/')}/briefing/json/{dc.feed_token}"


@router.get("/delivery", response_model=DeliveryOut)
def get_delivery(me: Me = CurrentUser, db: Session = Depends(get_db)) -> DeliveryOut:
    dc = briefing_service.get_or_create_delivery(db, me.sub)
    return DeliveryOut(
        feed_url=_feed_url(dc),
        json_url=_json_url(dc),
        webhook_url=dc.webhook_url,
        webhook_configured=bool(dc.webhook_url),
    )


@router.patch("/delivery", response_model=DeliveryOut)
def patch_delivery(
    payload: DeliveryPatch, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> DeliveryOut:
    dc = briefing_service.get_or_create_delivery(db, me.sub)
    prof = briefing_service.profil_mit_tarif(db, me)
    data = payload.model_dump(exclude_unset=True)
    if "webhook_url" in data:
        wanted = (data["webhook_url"] or "").strip() or None
        # Webhook-Zustellung ist ein Pro-Feature.
        if wanted and not plans.features(prof.plan)["webhook"]:
            raise HTTPException(402, "Webhook-Zustellung ist ein Pro-Feature")
        dc.webhook_url = wanted
    if "webhook_secret" in data:
        dc.webhook_secret = (data["webhook_secret"] or "").strip() or None
    db.commit()
    db.refresh(dc)
    return DeliveryOut(
        feed_url=_feed_url(dc),
        json_url=_json_url(dc),
        webhook_url=dc.webhook_url,
        webhook_configured=bool(dc.webhook_url),
    )


@router.post("/delivery/rotate", response_model=DeliveryOut)
def rotate_delivery(me: Me = CurrentUser, db: Session = Depends(get_db)) -> DeliveryOut:
    dc = briefing_service.rotate_feed_token(db, me.sub)
    return DeliveryOut(
        feed_url=_feed_url(dc),
        json_url=_json_url(dc),
        webhook_url=dc.webhook_url,
        webhook_configured=bool(dc.webhook_url),
    )


@router.post("/delivery/webhook-test")
def test_webhook(me: Me = CurrentUser, db: Session = Depends(get_db)) -> dict:
    dc = briefing_service.get_or_create_delivery(db, me.sub)
    if not dc.webhook_url:
        raise HTTPException(400, "Kein Webhook konfiguriert")
    ok = delivery.post_webhook(
        dc.webhook_url, dc.webhook_secret,
        {"event": "briefing.test", "message": "Saganta-Briefing Testzustellung"},
    )
    return {"ok": ok}


# ── Öffentlich (nur per feed_token, KEIN Login) ─────────────────────────────
def _resolve_token(db: Session, feed_token: str) -> DeliveryConfig:
    dc = db.query(DeliveryConfig).filter(DeliveryConfig.feed_token == feed_token).one_or_none()
    if not dc:
        raise HTTPException(404, "Feed nicht gefunden")
    return dc


@router.get("/public/feed/{feed_token}")
def public_feed(feed_token: str, db: Session = Depends(get_db)) -> Response:
    dc = _resolve_token(db, feed_token)
    briefings = (
        db.query(UserBriefing)
        .filter(UserBriefing.sub == dc.sub)
        .order_by(UserBriefing.briefing_date.desc())
        .limit(settings.briefing_retention_days)
        .all()
    )
    xml = podcast_feed.build_feed(settings.public_base_url or "", feed_token, briefings)
    return Response(
        content=xml,
        media_type="application/rss+xml",
        headers={"X-Robots-Tag": "noindex, nofollow"},
    )


def _resolve_briefing(db: Session, dc: DeliveryConfig, for_date: str) -> UserBriefing:
    """Briefing zu einem Datum oder (bei 'latest') das neueste vorhandene.

    'latest' gibt es, damit ein Client (Skript, Podcast-App, der Lautsprecher auf
    host) nicht vorher wissen muss, welches Datum erzeugt wurde.
    """
    query = db.query(UserBriefing).filter(UserBriefing.sub == dc.sub)
    if for_date == "latest":
        ub = query.order_by(UserBriefing.briefing_date.desc()).first()
    else:
        try:
            parsed = date.fromisoformat(for_date)
        except ValueError:
            raise HTTPException(400, "Datum bitte als YYYY-MM-DD oder 'latest'")
        ub = query.filter(UserBriefing.briefing_date == parsed).one_or_none()
    if not ub:
        raise HTTPException(404, "Kein Briefing für dieses Datum")
    return ub


@router.get("/public/briefing/{feed_token}")
@router.get("/public/briefing/{feed_token}/{for_date}")
def public_briefing(
    feed_token: str,
    for_date: str = "latest",
    db: Session = Depends(get_db),
) -> dict:
    """Das eigene Briefing als JSON, ohne Login, nur mit dem Feed-Token.

    Gegenstück zu /public/audio: bislang gab es den token-basierten Zugang nur als
    RSS-XML und als MP3, aber nicht als Daten. Damit lässt sich das Briefing aus
    einem Skript, einer eigenen Oberfläche oder einer Heim-Automation abholen,
    ohne den kurzlebigen BFF-Token nachzubauen.

    Der Feed-Token ist unerraten und über POST /delivery/rotate wechselbar; er ist
    ein Lesezugang auf die eigenen Briefings, kein Konto-Zugang.
    """
    dc = _resolve_token(db, feed_token)
    ub = _resolve_briefing(db, dc, for_date)
    return {
        "date": ub.briefing_date.isoformat(),
        "content": ub.content or {},
        "has_audio": bool(ub.audio_path),
        "audio_mime": ub.audio_mime,
        "audio_url": (
            f"{settings.public_base_url.rstrip('/')}/briefing/audio/{feed_token}/{ub.briefing_date.isoformat()}"
            if settings.public_base_url else None
        ),
    }


@router.get("/public/audio/{feed_token}/{for_date}")
def public_audio(feed_token: str, for_date: str, db: Session = Depends(get_db)) -> FileResponse:
    dc = _resolve_token(db, feed_token)
    ub = _resolve_briefing(db, dc, for_date)
    if not ub.audio_path:
        raise HTTPException(404, "Kein Audio vorhanden")
    return FileResponse(
        ub.audio_path,
        media_type=ub.audio_mime or "audio/mpeg",
        headers={"X-Robots-Tag": "noindex, nofollow"},
    )
