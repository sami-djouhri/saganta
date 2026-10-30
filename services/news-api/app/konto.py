"""Der Loeschweg dieses Dienstes.

Die Mechanik liegt geteilt in ``saganta_dienst.loeschen``; hier steht nur, was
dieser Dienst ueber sich selbst weiss. Zu den zwei Einstiegen (Route fuer den
Aufrufer, Programm fuer verwaiste Bestaende) siehe den Modulkopf dort.

DIESER DIENST IST DER ANLASS DER GANZEN UEBUNG
==================================================

Ein Pruef-Sub aus einem Beweislauf vom 26.09.2026 bekam **acht Naechte
hintereinander um 04:36 ein vollstaendiges Briefing erzeugt**, samt moeglicher
Sprachausgabe, obwohl zu ihm kein Konto mehr gehoerte: ``briefing_sched``
nimmt jedes ``BriefingProfile`` mit ``enabled`` und fragt nie, ob es dazu noch
einen Nutzer gibt. Ein verwaister Mandant ist hier also kein Datenrest, sondern
ein Verbraucher, der niemandem auffaellt. ``briefing_profiles`` steht deshalb
in den Schritten an erster Stelle: faellt es, hoert die Arbeit auf.

ZWEI ARTEN VON BESTAND, UND NUR EINE GEHOERT JEMANDEM
========================================================

``feed_sources`` und ``feed_items`` sind die abgerufenen Nachrichten selbst.
Sie gehoeren keinem Mandanten, sondern allen, und stehen darum ausdruecklich in
``gemeinsam``. Sie bei einer Kontoloeschung mitzunehmen, wuerde zehntausende
Artikel vernichten, die mit diesem Konto nichts zu tun haben. Was den Mandanten
betrifft, ist seine Sicht darauf: ``user_item_state`` (gelesen, gemerkt).
"""

from __future__ import annotations

from pathlib import Path

from saganta_dienst import loeschen
from sqlalchemy import text

from .config import settings


def _audio_dateien(db, sub: str) -> list[Path]:
    """Die gerenderten Sprachausgaben dieses Mandanten.

    Zwei Quellen, und beide braucht es:

    * die Pfade aus ``user_briefings.audio_path``, also das, was der Dienst
      selbst als seine Dateien fuehrt,
    * der Ordner ``<audio_dir>/<sub>``, in dem sie liegen. Er faengt Dateien,
      zu denen die Zeile schon fehlt, und die gibt es gemessen (Ordner aus
      abgebrochenen Laeufen).

    ⚠️ Der Ordnername kommt aus dem ``sub``, und daraus einen Loeschpfad zu
    bauen ist genau die Stelle, an der ein ``../`` teuer wird. Der ``sub``
    stammt zwar aus einem signierten Token, aber "stammt aus vertrauenswuerdiger
    Quelle" ist eine Annahme ueber den ganzen Aufrufpfad, und die Schranke
    kostet drei Zeilen. Geprueft wird nach dem Aufloesen, nicht am Text: eine
    Zeichenpruefung auf ``..`` uebersieht Kodierungen, ein aufgeloester Pfad
    nicht.
    """
    pfade: list[Path] = []

    for roh in db.execute(
        text("SELECT audio_path FROM user_briefings "
             "WHERE sub = :sub AND audio_path IS NOT NULL"),
        {"sub": sub},
    ).scalars().all():
        if roh:
            pfade.append(Path(roh))

    wurzel = Path(settings.audio_dir).resolve()
    mandantenordner = (wurzel / sub).resolve()
    if mandantenordner != wurzel and mandantenordner.is_relative_to(wurzel):
        pfade.append(mandantenordner)

    # Doppelte entfernen, Reihenfolge erhalten: der Ordner raeumt die Dateien
    # darin ohnehin mit, ein zweiter Versuch waere nur Rauschen im Bericht.
    gesehen: set[str] = set()
    eindeutig: list[Path] = []
    for pfad in pfade:
        schluessel = str(pfad)
        if schluessel not in gesehen:
            gesehen.add(schluessel)
            eindeutig.append(pfad)
    return eindeutig


PLAN = loeschen.Plan(
    dienst="news",
    schritte=(
        # Zuerst: hier haengt die naechtliche Arbeit dran.
        loeschen.eigene("briefing_profiles", spalte="sub",
                        warum="Briefing-Profil, Ausloeser der naechtlichen Erzeugung"),
        loeschen.eigene("briefing_delivery", spalte="sub", warum="Zustellvermerke"),
        loeschen.eigene("briefing_feedback", spalte="sub", warum="Rueckmeldungen zum Briefing"),
        loeschen.eigene("user_briefings", spalte="sub",
                        warum="erzeugte Briefings samt Verweis auf die Sprachausgabe"),
        loeschen.eigene("user_item_state", spalte="sub", warum="gelesen/gemerkt je Artikel"),
    ),
    gemeinsam=frozenset({"feed_sources", "feed_items"}),
    dateien=_audio_dateien,
)


if __name__ == "__main__":
    from . import briefing_models, models  # noqa: F401  (fuellen Base.metadata)
    from .db import Base, SessionLocal

    raise SystemExit(loeschen.als_programm(PLAN, Base.metadata, SessionLocal))
