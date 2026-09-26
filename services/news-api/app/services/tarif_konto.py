"""Den Tarif am Konto setzen, nicht nur im Briefing-Profil.

★ Warum es diesen Umweg gibt: Der Stripe-Webhook landet hier, weil in diesem
Dienst das Briefing-Produkt und der Stripe-Schluessel liegen. Die Wahrheit ueber
den Tarif gehoert aber ans Konto (``user.plan`` in der auth-DB), denn nur von
dort erreicht sie ueber den ``plan``-Claim alle sieben Backends. Bis zum
02.09.2026 schrieb der Webhook ausschliesslich in ``briefing_profiles.plan``,
also in eine Tabelle, die kein anderer Dienst sieht.

Statt diesem Dienst einen zweiten Datenbankzugang zu geben, ruft er den
auth-service an (``POST /api/intern/tarif``). Ausgewiesen wird er mit einem
kurzlebigen HS256-Token auf eine eigene Zielgruppe. Das Geheimnis dafuer ist
dasselbe, das der auth-service schon heute zum Stempeln der Backend-Tokens
benutzt und das dieser Dienst zum Pruefen braucht, es kommt also kein neues
hinzu.

``briefing_profiles.plan`` bleibt als **Spiegel** bestehen und wird
weitergeschrieben. Der Briefing-Scheduler laeuft ohne Anfrage und sieht deshalb
nie einen Token; er braucht einen lesbaren Wert in der eigenen Datenbank.
"""
from __future__ import annotations

import json
import secrets
import time
import urllib.error
import urllib.request

import structlog
from jose import jwt

from ..config import settings

log = structlog.get_logger()

ZIELGRUPPE = "auth-service-intern"
_TOKEN_LAUFZEIT_S = 60


def _token(ziel_sub: str) -> str:
    jetzt = int(time.time())
    return jwt.encode(
        {
            "iss": "saganta",
            "aud": ZIELGRUPPE,
            "sub": ziel_sub,
            "iat": jetzt,
            "exp": jetzt + _TOKEN_LAUFZEIT_S,
            "jti": secrets.token_hex(12),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def setze_tarif(sub: str, plan: str, status: str | None = None) -> bool:
    """Setzt den Tarif am Konto. Gibt zurueck, ob es geklappt hat.

    ★ Wirft bewusst nicht: der Aufrufer ist der Stripe-Webhook, und ein
    Ausnahmefehler dort wuerde Stripe eine Wiederholung schicken, die denselben
    Fehler noch einmal produziert. Stattdessen wird laut protokolliert und der
    Spiegel im Briefing-Profil trotzdem gesetzt, damit der Kunde sein Produkt
    bekommt. Der Abgleich ``scripts/tarif-abgleich.sh`` findet die Luecke.
    """
    if not settings.auth_service_url:
        log.error("tarif.konto.keine_url", sub=sub, plan=plan)
        return False
    ziel = settings.auth_service_url.rstrip("/") + "/api/intern/tarif"
    rumpf = json.dumps({"sub": sub, "plan": plan, "status": status}).encode()
    anfrage = urllib.request.Request(
        ziel,
        data=rumpf,
        method="POST",
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {_token(sub)}",
        },
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=8) as antwort:
            if 200 <= antwort.status < 300:
                log.info("tarif.konto.gesetzt", sub=sub, plan=plan, status=status)
                return True
            log.error("tarif.konto.abgelehnt", sub=sub, plan=plan, code=antwort.status)
            return False
    except urllib.error.HTTPError as e:
        # ★ Den Rumpf mitlesen: der auth-service unterscheidet 401 (Token) von
        # 404 (Konto gibt es nicht), und das sind sehr verschiedene Fehler.
        try:
            text = e.read().decode()[:200]
        except Exception:
            text = ""
        log.error("tarif.konto.fehler", sub=sub, plan=plan, code=e.code, antwort=text)
        return False
    except Exception as e:
        # httpx/urllib-Netzwerkfehler haben oft keinen Text, deshalb den Typ mit.
        log.error("tarif.konto.unerreichbar", sub=sub, plan=plan, fehler=type(e).__name__)
        return False
