"""JWT-Pruefung am Dienst-Eingang, geteilt von allen Saganta-Backends.

Die Kette ist immer dieselbe: der BFF stempelt mit ``issueBackendToken`` ein
kurzlebiges HS256-Token auf die Zielgruppe des Backends, das Backend prueft
Signatur, Aussteller und Zielgruppe und laesst nur zugelassene ``sub`` durch.

★ Warum das hier liegt und nicht als Kopie in jedem Dienst: bis zum 02.09.2026
lag es acht Mal, in acht leicht abweichenden Fassungen. Der Unterschied war
nirgends beabsichtigt, aber er war wirksam: fuenf Dienste antworteten auf eine
Anfrage *ganz ohne* ``Authorization``-Kopf mit 422 statt 401, weil dort
``Header(...)`` statt ``Header(default=None)`` stand. Eine Aenderung an der
Auth-Grenze musste achtmal gemacht und achtmal einzeln ausgerollt werden. Genau
das ging am 30.08. beim Health-Filter schief, der in sieben von acht Diensten
monatelang nicht griff.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Protocol

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from . import tarife

AUSSTELLER = "saganta"

# Request-lokaler Mandant. Dienste, die an einen nativen Backend-Dienst
# weiterreichen (kalender-bff, projectdeck-api), lesen ihn und setzen ihn dort
# als ``X-Saganta-Sub``, statt headerlos auf dessen Owner-Vorgabe zu fallen.
# ``None`` heisst: kein angemeldeter Pfad.
#
# ★ Deshalb ist die Abhaengigkeit unten async. Eine sync-Dependency laesst
# FastAPI im Threadpool laufen, und ein dort gesetzter ContextVar-Wert ist im
# Route-Handler wieder weg. Das gilt einheitlich fuer alle Dienste, auch fuer
# die, die heute keinen nativen Client haben: sonst waere der Tag, an dem einer
# hinzukommt, der Tag, an dem die Isolation still ausfaellt.
aktueller_sub: ContextVar[str | None] = ContextVar("aktueller_sub", default=None)


class Me(BaseModel):
    """Der angemeldete Nutzer, so wie ihn die Routen sehen."""

    sub: str
    email: str = ""
    name: str | None = None
    groups: list[str] = Field(default_factory=list)
    #: Tarif des Kontos, aus dem ``plan``-Claim. Was er bedeutet, steht in
    #: ``saganta_dienst.tarife``. Fehlt der Claim (alter BFF), gilt ``free``:
    #: fail-closed, siehe ``tarife.normalisiere``.
    plan: str = "free"


class Einstellungen(Protocol):
    """Was die Pruefung aus der Dienst-Konfiguration braucht.

    Bewusst ein Protocol statt eines Imports: jeder Dienst hat sein eigenes
    ``config.settings`` mit eigenen Zusatzfeldern, geteilt sind nur diese zwei
    (plus das optionale ``allowed_subs``).
    """

    jwt_secret: str
    jwt_algorithm: str


def pruefe_bearer(
    authorization: str | None,
    *,
    geheimnis: str,
    algorithmus: str,
    zielgruppe: str,
    erlaubte_subs: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    """Prueft den ``Authorization``-Kopf und gibt die Token-Nutzlast zurueck.

    Wirft ``HTTPException`` mit 401 (Token unbrauchbar) oder 403 (Token gueltig,
    aber dieser ``sub`` ist hier nicht zugelassen). Der Unterschied ist keine
    Kosmetik. 401 heisst „melde dich an", 403 heisst „du bist es, aber du darfst
    hier nicht", und nur Letzteres ist die Owner-Bremse.
    """
    if not authorization:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing Authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        nutzlast = jwt.decode(
            token,
            geheimnis,
            algorithms=[algorithmus],
            audience=zielgruppe,
        )
    except JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}") from e
    if nutzlast.get("iss") != AUSSTELLER:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown issuer")
    sub = nutzlast.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token without sub")
    # Owner-Gate: leere Liste = offen. Wo Daten nicht mandantengetrennt sind,
    # ist das hier die einzige Bremse.
    if erlaubte_subs and sub not in erlaubte_subs:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")
    return nutzlast


def baue_pruefer(
    *,
    zielgruppe: str,
    einstellungen: Einstellungen,
    me_klasse: type[BaseModel] = Me,
):
    """Erzeugt die FastAPI-Abhaengigkeit fuer den angemeldeten Pfad eines Dienstes.

    ``einstellungen`` wird als Objekt gehalten und seine Felder erst beim Aufruf
    gelesen. Das ist Absicht: die Tests der Dienste stellen ``allowed_subs`` zur
    Laufzeit um, ein beim Bauen eingefrorener Wert wuerde sie stillschweigend
    wirkungslos machen.
    """

    async def verify_jwt(authorization: str | None = Header(default=None)):
        nutzlast = pruefe_bearer(
            authorization,
            geheimnis=einstellungen.jwt_secret,
            algorithmus=einstellungen.jwt_algorithm,
            zielgruppe=zielgruppe,
            erlaubte_subs=getattr(einstellungen, "allowed_subs", ()) or (),
        )
        sub = nutzlast["sub"]
        aktueller_sub.set(sub)
        felder = {
            "sub": sub,
            "email": nutzlast.get("email", ""),
            "name": nutzlast.get("name"),
            "groups": nutzlast.get("groups", []),
        }
        # Den Tarif nur setzen, wenn die Zielklasse ihn kennt: shell-api bringt
        # sein eigenes ``Me`` aus ``schemas`` mit, und pydantic wuerde ein
        # unbekanntes Feld je nach Modell-Konfiguration verwerfen oder werfen.
        if "plan" in getattr(me_klasse, "model_fields", {}):
            felder["plan"] = tarife.normalisiere(nutzlast.get("plan"))
        return me_klasse(**felder)

    return verify_jwt


def baue_abhaengigkeit(**kwargs):
    """``baue_pruefer`` fertig als ``Depends``, fuer ``me: Me = AktuellerNutzer``."""
    return Depends(baue_pruefer(**kwargs))
