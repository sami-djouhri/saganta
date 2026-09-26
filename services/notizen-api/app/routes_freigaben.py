"""Freigaben verwalten, der angemeldete Teil.

Der oeffentliche Gegenpart steht in ``routes_oeffentlich.py`` und teilt sich mit
diesem Modul nur das Datenmodell. Diese Trennung ist mit Absicht scharf: die
Routen hier setzen alle ein gueltiges Token voraus, die dort keine einzige.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import Me, verify_jwt
from .config import settings
from .db import get_db
from .helfer import freigabe_aus, notiz_holen
from .models import Freigabe
from .schemas import FreigabeAn, FreigabeAus
from .util import jetzt, neues_merkmal, passwort_hash

router = APIRouter()


def _chiffrierte_pruefen(daten: FreigabeAn) -> None:
    """Vollstaendigkeit einer verschluesselten Freigabe pruefen.

    Der Server kann den Inhalt nicht beurteilen: umso wichtiger, dass die
    Beigaben stimmen, die zum Aufschliessen noetig sind. Eine Freigabe ohne
    ``iv`` waere ein Link, den niemand mehr oeffnen kann; das faellt sonst erst
    beim Empfaenger auf, und dann ist der Text schon verschickt.
    """
    if not daten.chiffrat:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Chiffrat fehlt")
    if len(daten.chiffrat) > settings.freigabe_max_chiffrat_bytes:
        raise HTTPException(
            413,
            "Verschluesselter Inhalt ist zu gross fuer eine Freigabe.",
        )
    if not daten.iv:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "iv fehlt")
    if daten.schluessel_quelle not in {"fragment", "passwort"}:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "schluessel_quelle muss 'fragment' oder 'passwort' sein"
        )
    if daten.schluessel_quelle == "passwort" and not (daten.kdf_salz and daten.kdf_iterationen):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Bei Passwort-Ableitung muessen kdf_salz und kdf_iterationen mitkommen.",
        )
    if daten.passwort:
        # Ein serverseitig geprueftes Passwort waere hier nicht nur ueberfluessig,
        # sondern schaedlich: es wuerde genau das Geheimnis auf den Server holen,
        # aus dem der Empfaenger den Schluessel ableitet.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Bei verschluesselten Freigaben darf das Passwort den Server nicht erreichen: "
            "es gehoert in die Schluesselableitung im Browser.",
        )


@router.get("", response_model=list[FreigabeAus])
def liste(
    nur_aktive: bool = False,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> list[FreigabeAus]:
    """Alle Freigaben des Kontos, der Ort, an dem man sieht, was draussen ist."""
    freigaben = db.scalars(
        select(Freigabe)
        .where(Freigabe.owner_sub == me.sub)
        .order_by(Freigabe.erstellt_am.desc())
    ).all()
    aus = [freigabe_aus(f) for f in freigaben]
    return [f for f in aus if f.zustand == "aktiv"] if nur_aktive else aus


@router.post(
    "/notizen/{notiz_id}", response_model=FreigabeAus, status_code=status.HTTP_201_CREATED
)
def anlegen(
    notiz_id: int,
    daten: FreigabeAn,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> FreigabeAus:
    notiz = notiz_holen(db, me.sub, notiz_id)

    ablauf = None
    if daten.ablauf_tage is not None:
        tage = min(daten.ablauf_tage, settings.freigabe_max_tage)
        ablauf = jetzt() + timedelta(days=tage)

    freigabe = Freigabe(
        merkmal=neues_merkmal(),
        owner_sub=me.sub,
        notiz_id=notiz.id,
        modus=daten.modus,
        ablauf_am=ablauf,
        max_abrufe=daten.max_abrufe,
        mit_anhaengen=daten.mit_anhaengen,
        # Nur fuer die eigene Uebersicht, der Titel verlaesst den Server auf
        # diesem Weg nicht. Bei verschluesselten Freigaben ist er dennoch die
        # einzige Spur des Inhalts in der Datenbank, deshalb steht er dort
        # bewusst nur, weil er dem Eigentuemer gehoert und nicht mit
        # ausgeliefert wird.
        notiz_titel_kopie=notiz.titel[:300],
    )

    if daten.modus == "chiffriert":
        _chiffrierte_pruefen(daten)
        freigabe.chiffrat = daten.chiffrat
        freigabe.iv = daten.iv
        freigabe.kdf_salz = daten.kdf_salz
        freigabe.kdf_iterationen = daten.kdf_iterationen
        freigabe.algo = daten.algo or "AES-GCM-256"
        freigabe.schluessel_quelle = daten.schluessel_quelle
        # Anhaenge einer verschluesselten Freigabe liegen unverschluesselt in
        # der Ablage, sie mitzugeben wuerde die Zusicherung aushebeln, dass
        # der Server nichts vom Inhalt weiss. Runde zwei kann sie ebenfalls im
        # Browser verschluesseln; bis dahin ist Weglassen die ehrliche Variante.
        freigabe.mit_anhaengen = False
    elif daten.passwort:
        freigabe.passwort_hash, freigabe.passwort_salz = passwort_hash(daten.passwort)

    db.add(freigabe)
    db.commit()
    db.refresh(freigabe)
    return freigabe_aus(freigabe)


@router.delete("/{freigabe_id}", status_code=status.HTTP_204_NO_CONTENT)
def widerrufen(
    freigabe_id: int,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> None:
    """Freigabe zurueckziehen.

    Das Chiffrat wird dabei geloescht, nicht nur ein Vermerk gesetzt: „widerrufen"
    soll heissen, dass der Inhalt weg ist, auch fuer den, der spaeter die
    Datenbank in der Hand haelt. Der Eintrag selbst bleibt, damit ein alter Link
    „widerrufen" melden kann statt „gibt es nicht", der Unterschied ist fuer den
    Empfaenger die ganze Auskunft.
    """
    freigabe = db.scalar(
        select(Freigabe).where(Freigabe.id == freigabe_id, Freigabe.owner_sub == me.sub)
    )
    if freigabe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Freigabe nicht gefunden")
    freigabe.widerrufen_am = jetzt()
    freigabe.chiffrat = None
    db.commit()
