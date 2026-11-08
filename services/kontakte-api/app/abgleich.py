"""Spiegel der Geburtstage und Jahrestage in den Kalender.

Nach jeder Aenderung bekommt der Kalender den **ganzen** Stand des Mandanten
(``PUT /api/contacts/abgleich`` am kalender-bff), nicht die eine Aenderung:
ein verlorener Einzelschritt liesse sonst dauerhaft eine Luecke, der ganze
Stand heilt sie beim naechsten Mal.

Faellt der Kalender aus, bleibt die Aenderung hier gespeichert, und ein Merker
(``AbgleichOffen``) sorgt dafuer, dass der Abgleich nachgeholt wird.
"""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import kalender
from .auth import Me
from .models import AbgleichOffen, Kontakt
from .tage import spiegelzeilen

log = structlog.get_logger()


def abgleichen(db: Session, me: Me) -> bool:
    """Schickt den Stand an den Kalender. ``True`` = angekommen."""
    kontakte = db.scalars(
        select(Kontakt).where(Kontakt.owner_sub == me.sub, Kontakt.geloescht_am.is_(None))
    ).all()
    zeilen = spiegelzeilen(list(kontakte))
    try:
        kalender.aufruf(me, "PUT", "/api/contacts/abgleich", json={"eintraege": zeilen})
    except Exception as exc:  # Netz, 5xx und 4xx: alles heisst "nicht angekommen"
        fehler = str(exc)[:300]
        merker = db.get(AbgleichOffen, me.sub)
        if merker is None:
            db.add(AbgleichOffen(owner_sub=me.sub, email=me.email or "", fehler=fehler))
        else:
            merker.fehler = fehler
        db.commit()
        log.warning("kontakte.abgleich_fehlgeschlagen", fehler=fehler, zeilen=len(zeilen))
        return False
    merker = db.get(AbgleichOffen, me.sub)
    if merker is not None:
        db.delete(merker)
        db.commit()
    log.info("kontakte.abgleich", zeilen=len(zeilen))
    return True


def offen(db: Session, sub: str) -> bool:
    return db.get(AbgleichOffen, sub) is not None


def nachholen(db: Session) -> int:
    """Holt alle offenen Abgleiche nach (Hintergrundlauf). Zahl der gelungenen."""
    gelungen = 0
    for merker in db.scalars(select(AbgleichOffen)).all():
        me = Me(sub=merker.owner_sub, email=merker.email or "")
        if abgleichen(db, me):
            gelungen += 1
    return gelungen
