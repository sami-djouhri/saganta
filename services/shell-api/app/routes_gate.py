"""SSO-Gate für nginx `auth_request`: es sagt jetzt WER, nicht nur DASS.

Native Dienste (briefkasten/nachrichten/nativer Kalender) haben nur schwache
LAN-Auth (statisches Token-Auto-Login bzw. gar keine). Um sie über `*.saganta.de`
und `*.home.arpa` anzubieten, gatet nginx jeden Request erst hier: dieser
Endpoint prüft die better-auth-Session-Cookie und liefert 204 (eingeloggt) bzw.
401 (nicht). Ein unauthentifizierter Request kommt also nie am nativen Dienst an.

**Was daran bis 2026-09-27 fehlte, und warum es mehr als eine Lücke war.**
Die Antwort trug nur den Status. Hinter dem Gate schrieb nginx den ersten Aufruf
auf `…/api/auth/token-login?token=<feed_token>` um, und dieser Token ist der des
**Owners**: jeder angemeldete Saganta-Nutzer landete damit in dessen Kalender und
Postfach. Nicht durch einen Fehler in der Mandantentrennung, sondern an ihr
vorbei, denn die Dienste hinter dem Gate wurden nie gefragt, wer da ist. Ein
zweites Konto hätte das ohne jede Fehlermeldung und ohne Protokollspur getan.

Jetzt liefert das Gate den Mandanten mit, **signiert** mit dem Geheimnis des
Zieldienstes (`X-Saganta-Sub` + `X-Saganta-Sub-Sig`). nginx hebt beide per
`auth_request_set` aus der Antwort und setzt sie am Upstream. Der native Dienst
tauscht sie über seinen Gate-Login gegen eine Sitzung für genau diesen Mandanten.

⚠️ **Der Client darf diese Header nicht selbst setzen können.** Das ist die
Aufgabe von nginx (`proxy_set_header … ""` für die eingehende Richtung), nicht die
dieses Endpoints: er sieht den Upstream-Request gar nicht. Die zweite Sperre liegt
im Zieldienst, der die Signatur prüft.

Bewusst stdlib-`urllib` (kein httpx-Runtime-Dep). Sync-Endpoint genügt für den
leichtgewichtigen internen get-session-Call.
"""

from __future__ import annotations

import json
import urllib.request

from fastapi import APIRouter, Request, Response
from saganta_dienst.tenant_sig import SIG_HEADER, SUB_HEADER, kopfzeilen

from .config import settings

router = APIRouter()

# Den Namen des Zieldienstes nennt nginx im Subrequest. Der Header ist kein
# Geheimnis und trägt keine Berechtigung: er wählt nur aus, mit welchem Geheimnis
# signiert wird. Ein falscher Wert führt zu keiner Signatur, nicht zu einer
# falschen.
ZIEL_HEADER = "x-saganta-ziel"


@router.get("/auth/check")
def auth_check(request: Request) -> Response:
    cookie = request.headers.get("cookie", "")
    # Schnell-Filter: ohne Session-Cookie gar nicht erst nachfragen.
    if "saganta.session_token" not in cookie:
        return Response(status_code=401)
    try:
        req = urllib.request.Request(
            f"{settings.auth_service_url}/api/auth/get-session",
            headers={"Cookie": cookie},
        )
        with urllib.request.urlopen(req, timeout=4) as r:  # noqa: S310 (interne URL)
            body = r.read().decode("utf-8", "replace").strip()
    except Exception:
        # Fail-closed: Auth-Service nicht erreichbar → kein Zugang.
        return Response(status_code=401)

    # better-auth get-session: `null` = keine Session; sonst Objekt mit `user`.
    try:
        data = json.loads(body)
    except ValueError:
        return Response(status_code=401)
    if not (isinstance(data, dict) and data.get("user")):
        return Response(status_code=401)

    nutzer = data["user"]
    sub = str(nutzer.get("id") or "").strip()

    # Das Owner-Gate gilt auch hier. `allowed_subs` leer = offen (wie im ganzen
    # Dienst), sonst darf nur eine gelistete Kennung durch. Ohne diese Zeile wäre
    # das Gate der eine Weg, der die Allowlist der Suite nicht kennt.
    if settings.allowed_subs and sub not in settings.allowed_subs:
        return Response(status_code=403)

    ziel = (request.headers.get(ZIEL_HEADER) or "").strip().lower()

    # Hinter das Gate darf ein zweites Konto nur bei Zielen, die ihre
    # Mandantentrennung belegt haben. Sonst landet es im Auto-Login des Owners,
    # und das ist kein Fehlerfall: es sieht wie eine funktionierende Anmeldung aus.
    #
    # Fail-closed in beide Richtungen. Ein unbekanntes Ziel (vergessener
    # `X-Saganta-Ziel`-Header am Vhost) gilt als ungetrennt, und ohne
    # konfigurierten Owner kommt dort niemand durch, auch der Owner nicht.
    if ziel not in settings.ziele_mit_mandanten:
        if not settings.owner_sub or sub != settings.owner_sub:
            return Response(status_code=403)

    kopf = {}
    if sub:
        kopf = kopfzeilen(sub, settings.tenant_geheimnis(ziel))

    # 204 ohne Inhalt, die beiden Header holt nginx per auth_request_set heraus.
    # Fehlt ein Geheimnis für dieses Ziel, bleibt es bei der reinen Ja/Nein-Antwort:
    # dann verhält sich das Gate exakt wie vorher, statt halb zu wirken.
    return Response(status_code=204, headers=kopf)


__all__ = ["router", "SIG_HEADER", "SUB_HEADER", "ZIEL_HEADER"]
