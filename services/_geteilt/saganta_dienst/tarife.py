"""Tarife der Saganta-Suite, an einer Stelle statt in einem einzelnen Dienst.

★ Warum das hier liegt: bis zum 02.09.2026 kannte genau ein Backend den Tarif,
naemlich ``news-api``, und es hielt ihn in ``briefing_profiles.plan``. Der Tarif
ist aber kein Merkmal eines Briefing-Profils, sondern eines Kontos. Solange er
in einer App-Tabelle liegt, kann kein anderer Dienst ihn pruefen, und ein
zweiter Nutzer bekaeme beim Oeffnen der Registrierung ueberall dasselbe wie ein
zahlender.

Die Wahrheit liegt jetzt am Konto (``user.plan`` in der auth-DB) und reist im
Backend-JWT als ``plan``-Claim mit. Dieses Modul sagt, was ein Tarif bedeutet.

★★ Fail-closed: ein Token ohne ``plan``-Claim gilt als ``free``, nicht als
zahlend. Ein alter BFF, der den Claim noch nicht stempelt, verschenkt damit
Merkmale, statt sie zu verschenken (das waere andersherum der teure Fehler).

★ Dieses Modul zieht bewusst KEINE neuen Schranken ein. Es bildet ab, was am
02.09.2026 tatsaechlich galt, und macht es fuer alle Dienste abfragbar. Welche
weiteren Merkmale kostenpflichtig werden, ist eine Produktentscheidung und
gehoert nicht in einen Umbau der Auth-Kette.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

FREI = "free"
PRO = "pro"

#: Bekannte Tarife in aufsteigender Ordnung.
TARIFE = (FREI, PRO)

# Reihenfolge der Briefing-Laengen, fuer das Zurechtstutzen.
_LAENGEN = ("kurz", "mittel", "lang")

#: Merkmale je Tarif. Der Namensraum vor dem Punkt nennt den Dienst, damit
#: erkennbar bleibt, wer ein Merkmal durchsetzt. Ein Merkmal ohne Durchsetzung
#: gehoert nicht in diese Tabelle: es waere ein Versprechen, das niemand haelt.
MERKMALE: dict[str, dict[str, Any]] = {
    FREI: {
        "etikett": "Free",
        # ── briefing (durchgesetzt in news-api) ──────────────────────────────
        "briefing.max_laenge": "mittel",   # „lang" ist Pro
        "briefing.audio": False,           # die Synthese selbst, siehe unten
        "briefing.premium_stimme": False,  # LLM-redigierte Sprech-Fassung
        "briefing.webhook": False,         # Zustellung ans Smart Home
        "briefing.eigene_themen": False,   # Freitext-Stichwoerter
    },
    PRO: {
        "etikett": "Pro",
        "briefing.max_laenge": "lang",
        "briefing.audio": True,
        "briefing.premium_stimme": True,
        "briefing.webhook": True,
        "briefing.eigene_themen": True,
    },
}

# ★ Warum ``briefing.audio`` ein eigenes Merkmal ist und nicht an
# ``premium_stimme`` haengt: Bis zum 30.08.2026 trennte nur die redigierte
# Textfassung die Tarife. Die Sprachsynthese lief auch fuer Free, und genau sie
# ist der teure Teil (XTTS arbeitet single-threaded und braucht 20 bis 40
# Sekunden je Briefing, ein LLM-Aufruf einen Bruchteil davon). Das Kosten-Gating
# deckte damit die guenstigere Ressource ab und liess die teurere offen.

#: Was Pro zusaetzlich bringt, fuer die Oberflaeche.
PRO_VORTEILE = [
    "Natuerliche Premium-Stimme (redaktionell aufbereitet)",
    "Laengere Briefings (Laenge: lang)",
    "Eigene Themen-Stichwoerter",
    "Zustellung an dein Smart Home (Webhook)",
    "Prioritaets-Generierung",
]


def normalisiere(plan: str | None) -> str:
    """Unbekanntes oder Fehlendes wird ``free``.

    Das ist die fail-closed-Stelle: ein Tippfehler in der Datenbank, ein alter
    Token ohne Claim und ein geloeschtes Abo landen alle im Gratis-Tarif.
    """
    if plan in TARIFE:
        return plan  # type: ignore[return-value]
    return FREI


def merkmale(plan: str | None) -> dict[str, Any]:
    """Alle Merkmale eines Tarifs."""
    return MERKMALE[normalisiere(plan)]


def hat(plan: str | None, merkmal: str) -> bool:
    """Ob ein Tarif ein Ja/Nein-Merkmal einschliesst.

    Ein unbekanntes Merkmal ist ``False``, nicht ``True``: ein Tippfehler im
    Namen soll eine Schranke schliessen, nicht oeffnen.
    """
    return bool(merkmale(plan).get(merkmal, False))


def ist_pro(plan: str | None) -> bool:
    return normalisiere(plan) == PRO


def verlange(plan: str | None, merkmal: str, hinweis: str = "") -> None:
    """Bricht mit 402 ab, wenn der Tarif das Merkmal nicht einschliesst.

    ★ 402 (Payment Required) und nicht 403: die Oberflaeche muss die beiden
    Faelle auseinanderhalten koennen. 403 heisst „du darfst hier nicht her",
    402 heisst „dein Tarif reicht dafuer nicht" und ist das Einzige von beiden,
    worauf ein Hinweis auf Pro die richtige Antwort ist.
    """
    if hat(plan, merkmal):
        return
    text = hinweis or f"Dieses Merkmal gehoert zu Pro ({merkmal})."
    raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, text)


def stutze_laenge(plan: str | None, laenge: str) -> str:
    """Begrenzt die gewuenschte Briefing-Laenge auf das im Tarif Erlaubte."""
    erlaubt = merkmale(plan)["briefing.max_laenge"]
    if laenge not in _LAENGEN:
        laenge = "mittel"
    if _LAENGEN.index(laenge) > _LAENGEN.index(erlaubt):
        return erlaubt
    return laenge
