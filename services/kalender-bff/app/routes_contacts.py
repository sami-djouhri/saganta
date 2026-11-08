"""Kontakte-Proxy zum nativen Kalender (kalender:8085).

Kontakte fehlten im BFF vollständig, die native App verwaltet sie, das Saganta-
Frontend kam nicht heran. Beim Umstieg der App aufs Saganta-Konto wäre damit
Funktion verloren gegangen, deshalb hier nachgezogen.

⚠️ **Ein Kontakt ist nicht nur ein Adressbucheintrag:** Trägt er ein Geburtsdatum,
erzeugt der native Kalender daraus Termine im System-Kalender „Geburtstage", und
zwar durch **vollständige Neuerzeugung aller** Geburtstagstermine bei jeder
Kontaktänderung (`birthday_utils`). Das ist beim nativen Dienst so gewollt und
idempotent; hier ist nur wichtig zu wissen, dass ein PUT auf einen Kontakt mehr
anfasst als die eine Zeile.

Der native Kalender bleibt Datenquelle und validiert erneut; die Schemata hier
spiegeln seine Constraints (defense in depth).
"""
from fastapi import APIRouter, HTTPException
from typing import Literal

from pydantic import BaseModel, Field

from .auth import CurrentUser, Me
from .upstream import upstream

router = APIRouter()

_DATE = r"^\d{4}-\d{2}-\d{2}$"


class ContactIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    birthday: str | None = Field(default=None, pattern=_DATE)
    email: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)


class ContactPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    birthday: str | None = Field(default=None, pattern=_DATE)
    email: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)


class AbgleichEintrag(BaseModel):
    id: str = Field(..., min_length=1, max_length=36)
    name: str = Field(..., min_length=1, max_length=200)
    birthday: str = Field(..., pattern=_DATE)
    art: Literal["geburtstag", "jahrestag"] = "geburtstag"


class Abgleich(BaseModel):
    eintraege: list[AbgleichEintrag] = Field(default_factory=list, max_length=2000)


@router.put("/api/contacts/abgleich")
async def abgleich(data: Abgleich, me: Me = CurrentUser) -> dict:
    """Spiegel aus Saganta Kontakte (``kontakte-api``), seit 2026-11-07.

    Der Dienst ist die Quelle; der Kalender haelt nur eine Zeile je Geburtstag
    oder Jahrestag, erzeugt daraus die Termine und erinnert daran. Ersetzt den
    ganzen Bestand des Aufrufers in einem Schritt.
    """
    r = await upstream("PUT", "/api/contacts/abgleich", json=data.model_dump())
    return r.json() if r.content else {}


@router.get("/api/contacts")
async def list_contacts(me: Me = CurrentUser) -> list:
    r = await upstream("GET", "/api/contacts")
    data = r.json() if r.content else []
    return data if isinstance(data, list) else []


# Seit 2026-11-07 schreibt hier niemand mehr. Kontakte liegen in Saganta
# Kontakte (`kontakte-api`), das den Bestand per `/api/contacts/abgleich`
# ersetzt. Ein Schreiben ueber diese Routen (Kalender-App bis 0.10.1, alte
# Linux-Fassung) waere beim naechsten Abgleich still verschwunden; 410 sagt
# stattdessen, wo der Kontakt jetzt hingehoert.
_UMGEZOGEN = "Kontakte liegen seit 2026-11-07 in Saganta Kontakte (kontakte.home.arpa)."


@router.post("/api/contacts", status_code=201)
async def create_contact(data: ContactIn, me: Me = CurrentUser) -> dict:
    raise HTTPException(410, _UMGEZOGEN)


@router.put("/api/contacts/{contact_id}")
async def update_contact(contact_id: str, data: ContactPatch, me: Me = CurrentUser) -> dict:
    raise HTTPException(410, _UMGEZOGEN)


@router.delete("/api/contacts/{contact_id}", status_code=204)
async def delete_contact(contact_id: str, me: Me = CurrentUser) -> None:
    raise HTTPException(410, _UMGEZOGEN)
