"""Stripe-Anbindung für das Self-Service-Pro-Abo.

Soft-Fail-Prinzip (wie tts/llm): ohne `stripe_secret_key` ist Stripe AUS:
`enabled()` ist False, `create_checkout_session` wirft, der Owner vergibt Pro
weiter manuell via /admin/set-plan. Der Webhook ist die einzige Quelle, die
`plan` automatisch setzt; er verifiziert IMMER die Signatur (kein blindes Vertrauen
auf den Body). Idempotent gegen Stripe-Retries via Event-ID-Cache.
"""
from __future__ import annotations

import structlog
from sqlalchemy.orm import Session

from ..briefing_models import BriefingProfile
from ..config import settings
from . import briefing_service, plans, tarif_konto

log = structlog.get_logger()

# Stripe liefert Webhook-Events mehrfach (at-least-once). Schlanker In-Process-Cache
# der zuletzt verarbeiteten Event-IDs, damit ein Retry nicht doppelt schreibt.
_seen_events: set[str] = set()
_SEEN_MAX = 512


def enabled() -> bool:
    return bool(settings.stripe_secret_key and settings.stripe_price_id_pro)


def _client():
    """Lazy-Import, damit die Dependency lokal/ohne Stripe nicht zwingend da sein muss."""
    import stripe

    stripe.api_key = settings.stripe_secret_key
    return stripe


def create_checkout_session(sub: str, email: str | None, db: Session) -> str:
    """Erzeugt eine hosted Stripe-Checkout-Session (mode=subscription) und gibt die
    Redirect-URL zurück. `client_reference_id=sub` verknüpft den Kauf mit dem User."""
    if not enabled():
        raise RuntimeError("Stripe ist nicht konfiguriert")
    stripe = _client()
    prof = briefing_service.get_or_create_profile(db, sub)
    params: dict = {
        "mode": "subscription",
        "line_items": [{"price": settings.stripe_price_id_pro, "quantity": 1}],
        "client_reference_id": sub,
        "success_url": settings.stripe_success_url or "https://news.saganta.de/briefing/upgrade/success",
        "cancel_url": settings.stripe_cancel_url or "https://news.saganta.de/briefing/upgrade/cancel",
        # sub zusätzlich in metadata → im Webhook robust auslesbar, falls client_reference_id fehlt.
        "metadata": {"sub": sub},
        "subscription_data": {"metadata": {"sub": sub}},
        "allow_promotion_codes": True,
    }
    if prof.stripe_customer_id:
        params["customer"] = prof.stripe_customer_id
    elif email:
        params["customer_email"] = email
    session = stripe.checkout.Session.create(**params)
    log.info("stripe.checkout.created", sub=sub, session=session.get("id"))
    return session["url"]


def _profile_by_sub_or_customer(db: Session, sub: str | None, customer_id: str | None) -> BriefingProfile | None:
    if sub:
        return briefing_service.get_or_create_profile(db, sub)
    if customer_id:
        return (
            db.query(BriefingProfile)
            .filter(BriefingProfile.stripe_customer_id == customer_id)
            .one_or_none()
        )
    return None


def _setze_tarif(db: Session, prof: BriefingProfile, plan: str, status: str) -> None:
    """Schreibt den Tarif ans Konto UND in den Spiegel dieses Dienstes.

    ★ Eine Funktion statt drei Fundstellen: der Webhook kennt drei Ereignisse,
    die alle denselben Doppelschritt brauchen. Waere er ausgeschrieben, wuerde
    eine vierte Ereignisart ihn frueher oder spaeter nur zur Haelfte machen, und
    das Ergebnis (Konto und Spiegel gehen auseinander) faellt niemandem auf,
    weil beide Werte fuer sich plausibel aussehen.

    Reihenfolge mit Absicht: erst das Konto, denn das ist die Wahrheit fuer alle
    anderen Dienste. Scheitert es, wird der Spiegel trotzdem gesetzt, damit der
    Kunde das bezahlte Produkt hier bekommt; die Abweichung findet
    ``scripts/tarif-abgleich.sh``.
    """
    tarif_konto.setze_tarif(prof.sub, plan, status)
    prof.plan = plan
    prof.plan_status = status


def handle_webhook_event(payload: bytes, sig_header: str, db: Session) -> dict:
    """Verifiziert die Stripe-Signatur und wendet den Event an. Setzt plan bei
    erfolgreichem Kauf, entzieht ihn bei Kündigung. Wirft bei ungültiger Signatur."""
    if not settings.stripe_webhook_secret:
        raise RuntimeError("Kein stripe_webhook_secret gesetzt")
    stripe = _client()
    event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)

    event_id = event.get("id")
    if event_id and event_id in _seen_events:
        return {"ok": True, "duplicate": True, "type": event.get("type")}

    etype = event.get("type")
    obj = event["data"]["object"]
    handled = True

    if etype == "checkout.session.completed":
        sub = (obj.get("client_reference_id")
               or (obj.get("metadata") or {}).get("sub"))
        prof = _profile_by_sub_or_customer(db, sub, obj.get("customer"))
        if prof:
            _setze_tarif(db, prof, plans.PRO, "active")
            if obj.get("customer"):
                prof.stripe_customer_id = obj["customer"]
            if obj.get("subscription"):
                prof.stripe_subscription_id = obj["subscription"]
            db.commit()
            log.info("stripe.pro.activated", sub=prof.sub)
        else:
            log.error("stripe.webhook.no_profile", type=etype, sub=sub, customer=obj.get("customer"))

    elif etype in ("customer.subscription.deleted", "customer.subscription.canceled"):
        sub = (obj.get("metadata") or {}).get("sub")
        prof = _profile_by_sub_or_customer(db, sub, obj.get("customer"))
        if prof:
            _setze_tarif(db, prof, plans.FREE, "canceled")
            db.commit()
            log.info("stripe.pro.canceled", sub=prof.sub)

    elif etype == "customer.subscription.updated":
        # Status-Spiegel: bei past_due/unpaid/canceled runter auf free, sonst active.
        status = obj.get("status")
        sub = (obj.get("metadata") or {}).get("sub")
        prof = _profile_by_sub_or_customer(db, sub, obj.get("customer"))
        if prof:
            if status in ("active", "trialing"):
                _setze_tarif(db, prof, plans.PRO, "active")
            elif status in ("canceled", "unpaid", "incomplete_expired"):
                _setze_tarif(db, prof, plans.FREE, "canceled")
            db.commit()
            log.info("stripe.subscription.updated", sub=prof.sub, status=status)
    else:
        handled = False

    if event_id:
        _seen_events.add(event_id)
        if len(_seen_events) > _SEEN_MAX:
            _seen_events.clear()
    return {"ok": True, "type": etype, "handled": handled}
