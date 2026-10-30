"""Das Loeschen eines Mandanten: die Mechanik, geteilt von allen Backends.

WARUM ES DAS GIBT
=================

Gemessen am 2026-10-03 hatte von zehn Saganta-Diensten **einer** einen Weg, die
Daten eines Mandanten zu entfernen. Ein in der Anmelde-Datenbank geloeschtes
Konto hinterliess seinen vollstaendigen Bestand in den uebrigen. Das ist
dreierlei: stille Last (ein Pruef-Sub bekam acht Naechte hintereinander ein
Briefing erzeugt, weil ``briefing_sched`` jedes aktive Profil nimmt und nie
fragt, ob dazu noch ein Konto gehoert), ein Loeschrecht, das sich nicht erfuellen
laesst (DSGVO Art. 17, und das trifft schon Familie und Freunde), und ein
Bestand, der mit jedem Probierkonto waechst.

WAS HIER LIEGT UND WAS NICHT
============================

Hier liegt die **Mechanik**: Vorschau, Bericht, Reihenfolge, Restpruefung.
Hier liegt **nicht**, welche Tabelle in welcher Reihenfolge fallen muss. Das
weiss nur der Dienst selbst, denn es haengt an seinen Fremdschluesselketten, und
ein Werkzeug von aussen, das in zehn Datenbanken Zeilen entfernt, waere die
schlechtere Haelfte dieser Loesung. Jeder Dienst legt deshalb einen ``Plan``
neben seine Modelle.

DER EIGENTLICHE WERT STECKT IN ``abdeckung_pruefen``
=======================================================

Eine Liste von Loeschschritten ist eine Liste, die man pflegen muss, und die
Lehre dieses Hauses ist, dass genau solche Listen in beide Richtungen veralten:
wer morgen eine Tabelle mit ``owner_sub`` hinzufuegt, faellt still aus dem
Loeschweg. Das faellt nicht auf, denn ein Loeschlauf meldet weiterhin Erfolg.

``abdeckung_pruefen`` leitet das Soll deshalb aus den SQLAlchemy-Metadaten ab,
also aus dem **Ist** der Modelle, und nicht aus einer zweiten Liste. Sie laeuft
an zwei Stellen:

* im Test je Dienst, wo sie ohne jede Daten greift (eine neue Tabelle macht den
  Test rot, bevor sie Daten tragen kann),
* beim Loeschen selbst, wo ihr Befund im Bericht landet.

Eine Tabelle gilt als abgedeckt, wenn sie in einem Schritt steht, wenn sie
ausdruecklich als gemeinsamer Bestand erklaert ist, oder wenn sie per
``ondelete="CASCADE"`` an einer abgedeckten Tabelle haengt. Das Letzte wird
transitiv aufgeloest, denn Ketten sind laenger als ein Glied.

⚠️ Die Pruefung sieht nur, was in den Metadaten steht. Tabellen, die ein Dienst
per rohem SQL anlegt (die FTS5-Indizes der Notizen), muss er deshalb selbst als
``per_trigger`` oder ``gemeinsam`` erklaeren. Ein Volltextindex ist dabei kein
Nebenschauplatz: er traegt den Klartext mit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from pydantic import BaseModel, Field

# Spaltennamen, die einen Mandanten bezeichnen. Die Namen weichen zwischen den
# Diensten ab (``owner_sub``, ``sub``, ``owner``), deshalb steht hier eine Liste
# und kein einziger Name: ein Pruefer, der Eigenschaften am Namen erkennt,
# findet genau das nicht, was anders benannt ist.
MANDANTEN_SPALTEN = frozenset({"owner_sub", "sub", "owner", "created_by_sub", "user_sub"})

#: Was der Aufrufer schicken muss, damit geloescht wird. Bewusst derselbe Wortlaut
#: wie im nativen Kalender (``/api/account/delete``), damit ein Mandant nicht je
#: Dienst eine andere Zauberformel lernt.
BESTAETIGUNG = "KONTO LOESCHEN"


@dataclass(frozen=True)
class Schritt:
    """Eine Tabelle und die Bedingung, die darin den Mandanten trifft.

    ``wo`` ist eine SQL-Bedingung mit genau einem Parameter ``:sub``. Sie ist
    kein freier Text aus einer Anfrage, sondern steht im Quelltext des Dienstes;
    der Mandant selbst kommt immer als gebundener Parameter.
    """

    tabelle: str
    wo: str
    warum: str = ""


def eigene(tabelle: str, spalte: str = "owner_sub", warum: str = "") -> Schritt:
    """Der Normalfall: die Tabelle traegt den Mandanten in einer eigenen Spalte."""
    return Schritt(tabelle=tabelle, wo=f"{spalte} = :sub", warum=warum)


def ueber(tabelle: str, fremdschluessel: str, eltern: str, eltern_spalte: str,
          mandanten_spalte: str = "owner_sub", warum: str = "") -> Schritt:
    """Der Kindfall ohne CASCADE: die Tabelle haengt nur ueber ihre Eltern am Mandanten.

    Gebraucht, wo ein Fremdschluessel ``NO ACTION`` traegt. Bei aktivem
    ``PRAGMA foreign_keys=ON`` scheitert dort sonst schon das Loeschen der
    Elternzeile, und zwar mit einem Datenbankfehler statt mit einer Aussage.
    """
    return Schritt(
        tabelle=tabelle,
        wo=(f"{fremdschluessel} IN "
            f"(SELECT {eltern_spalte} FROM {eltern} WHERE {mandanten_spalte} = :sub)"),
        warum=warum,
    )


@dataclass(frozen=True)
class Plan:
    """Der Loeschweg eines Dienstes.

    Die Reihenfolge der ``schritte`` ist die Ausfuehrungsreihenfolge: Kinder vor
    Eltern. Sie ist bewusst nicht aus den Fremdschluesseln hergeleitet, denn
    ``SET NULL`` und ``NO ACTION`` verlangen unterschiedliche Behandlung, und
    eine geratene Reihenfolge waere an genau der Stelle falsch, an der sie
    zaehlt.
    """

    dienst: str
    schritte: tuple[Schritt, ...]
    #: Tabellen, die bewusst allen gehoeren und niemandem: Feiertage,
    #: Seed-Rezepte, der Uebungskatalog, abgerufene Feed-Artikel. Je Eintrag
    #: gehoert die Begruendung in den Dienst, nicht hierher.
    gemeinsam: frozenset[str] = frozenset()
    #: Tabellen ausserhalb der Metadaten, die ein Datenbank-Trigger mitfuehrt
    #: (FTS5-Indizes). Sie stehen hier, damit die Abdeckungspruefung sie als
    #: bedacht verbuchen kann, statt sie gar nicht zu sehen.
    per_trigger: frozenset[str] = frozenset()
    #: Was ausserhalb der Datenbank liegt: Anhaenge, gerenderte Sprachausgaben.
    #: Bekommt Session und Mandanten und gibt Pfade zurueck, loescht selbst nichts.
    #:
    #: Die Aufteilung in Sammeln und Vollziehen ist der Kern dieser Stelle,
    #: und beide Haelften haben einen eigenen Grund:
    #:
    #: * **Gesammelt wird VOR den Schritten.** Danach sind genau die Zeilen weg,
    #:   die die Pfade nennen. Ein Haken, der hinterher laeuft, findet nichts und
    #:   meldet trotzdem Erfolg, und die Dateien bleiben fuer immer liegen.
    #: * **Vollzogen wird NACH dem Commit.** Rollt die Transaktion zurueck, sind
    #:   die Dateien noch da. Der umgekehrte Riss waere der schlimmere: eine
    #:   Datenbankzeile, die auf eine geloeschte Datei zeigt, ist ein Defekt,
    #:   den niemand mehr reparieren kann.
    dateien: Callable[[Any, str], list[Any]] | None = None


@dataclass
class Bericht:
    """Was ein Lauf gefunden und was er getan hat."""

    dienst: str
    sub: str
    trockenlauf: bool
    #: Tabelle -> Zeilen. Bei einem Trockenlauf die Zahl, die fallen WUERDE.
    zeilen: dict[str, int] = field(default_factory=dict)
    #: Klartextzeilen der Nebenwirkungen (Dateien).
    nebenwirkungen: list[str] = field(default_factory=list)
    #: Befunde der Abdeckungspruefung. Nicht leer heisst: der Loeschweg ist
    #: unvollstaendig, und zwar unabhaengig davon, ob dieser Lauf Daten fand.
    luecken: list[str] = field(default_factory=list)
    #: Was nach dem Loeschen noch da war. Nicht leer heisst: etwas hat nicht
    #: gegriffen. Bei einem Trockenlauf immer leer, dort wurde nichts geloescht.
    reste: dict[str, int] = field(default_factory=dict)
    #: Pfade, die nicht entfernt werden konnten. Zaehlt wie ein Rest: die Zeile
    #: ist weg, der Inhalt liegt noch auf der Platte.
    dateifehler: list[str] = field(default_factory=list)

    @property
    def summe(self) -> int:
        return sum(self.zeilen.values())

    @property
    def sauber(self) -> bool:
        """Ist der Loeschweg vollstaendig und hat er vollstaendig gegriffen?"""
        return not self.luecken and not self.reste and not self.dateifehler

    def als_dict(self) -> dict[str, Any]:
        return {
            "dienst": self.dienst,
            "sub": self.sub,
            "trockenlauf": self.trockenlauf,
            "zeilen": self.zeilen,
            "summe": self.summe,
            "nebenwirkungen": self.nebenwirkungen,
            "luecken": self.luecken,
            "reste": self.reste,
            "dateifehler": self.dateifehler,
            "sauber": self.sauber,
        }


def _tabellen_im_plan(plan: Plan) -> set[str]:
    return {s.tabelle for s in plan.schritte}


def abdeckung_pruefen(plan: Plan, metadata: Any) -> list[str]:
    """Welche Tabelle faellt aus dem Loeschweg? Klartext-Befunde, leer ist gut.

    Das Soll kommt aus ``metadata`` und damit aus den Modellen des Dienstes.
    Eine neu hinzugefuegte Tabelle mit Mandantenspalte erscheint hier sofort,
    auch wenn sie noch keine Zeile traegt. Genau das ist der Zweck: der Befund
    soll vor den Daten da sein.
    """
    # Leere Metadaten sind kein leeres Ergebnis, sondern eine blinde Pruefung.
    # ``Base.metadata`` fuellt sich erst, wenn das ``models``-Modul importiert
    # wurde; geschieht das nicht, findet die Abdeckungspruefung nichts, die
    # Restsuche findet nichts, und der Lauf meldet "sauber". Genau diese Stille
    # ist der Fehlerfall, gegen den dieses Modul gebaut ist, deshalb bricht es
    # hier laut statt freundlich.
    if not metadata.tables:
        raise RuntimeError(
            "Die Metadaten sind leer. Vermutlich wurde das models-Modul nicht "
            "importiert. Ohne Tabellen laufen Abdeckungs- und Restpruefung blind."
        )

    befunde: list[str] = []
    abgedeckt = _tabellen_im_plan(plan) | set(plan.gemeinsam) | set(plan.per_trigger)

    # Eltern-Kind-Kanten einsammeln: Kind -> [(Eltern, ondelete), ...]
    kanten: dict[str, list[tuple[str, str | None]]] = {}
    for name, tabelle in metadata.tables.items():
        for spalte in tabelle.columns:
            for fk in spalte.foreign_keys:
                kanten.setdefault(name, []).append((fk.column.table.name, fk.ondelete))

    # Transitiver Abschluss ueber CASCADE: haengt ein Kind per CASCADE an einer
    # abgedeckten Tabelle, ist es mit abgedeckt, und seine Kinder dann auch.
    # Fixpunkt, weil Ketten laenger als ein Glied sind.
    gewachsen = True
    while gewachsen:
        gewachsen = False
        for name in metadata.tables:
            if name in abgedeckt:
                continue
            for eltern, ondelete in kanten.get(name, []):
                if eltern in abgedeckt and (ondelete or "").upper() == "CASCADE":
                    abgedeckt.add(name)
                    gewachsen = True
                    break

    for name, tabelle in sorted(metadata.tables.items()):
        if name in abgedeckt:
            continue
        eigene_spalten = [c.name for c in tabelle.columns if c.name in MANDANTEN_SPALTEN]
        if eigene_spalten:
            befunde.append(
                f"{name} traegt {'/'.join(eigene_spalten)}, steht aber in keinem Schritt: "
                f"Bestand dieses Mandanten bliebe stehen."
            )
            continue
        eltern_liste = kanten.get(name, [])
        if not eltern_liste:
            # Weder Mandantenspalte noch Elternteil. Das ist der Normalfall fuer
            # echten Stammdatenbestand, aber es muss ausgesprochen sein: sonst
            # ist "gehoert allen" eine Annahme und keine Entscheidung.
            befunde.append(
                f"{name} hat keine Mandantenspalte und keinen Fremdschluessel. "
                f"Wenn das gemeinsamer Bestand ist, gehoert es in `gemeinsam`."
            )
            continue
        beschreibung = ", ".join(
            f"{eltern} ({ondelete or 'ohne ondelete'})" for eltern, ondelete in eltern_liste
        )
        befunde.append(
            f"{name} haengt an {beschreibung} und wird dadurch nicht mitgeloescht. "
            f"Entweder CASCADE setzen oder einen Schritt mit `ueber(...)` ergaenzen."
        )
    return befunde


def ungedeckte_live_tabellen(plan: Plan, db: Any, metadata: Any) -> list[str]:
    """Welche Tabelle gibt es in der Datenbank, die der Plan nicht kennt?

    WARUM DAS ZUSAETZLICH ZU ``abdeckung_pruefen`` NOETIG IST

    ``abdeckung_pruefen`` liest die SQLAlchemy-Metadaten, also die **Modelle**.
    Alles, was ein Dienst per rohem SQL anlegt, steht dort nicht und ist fuer
    sie unsichtbar. Das ist keine theoretische Grenze: gemessen am 2026-10-06
    behielt der ``briefkasten`` nach einem als "sauber" gemeldeten Loeschlauf
    das **Embedding des geloeschten Briefs** in ``letter_vec`` (eine
    ``vec0``-Virtualtabelle, die keinen Fremdschluessel haben kann). Ein
    384-dimensionaler Vektor kodiert den Inhalt und erlaubt
    Aehnlichkeitssuche; er ist Nutzerinhalt, nicht Verwaltung.

    Diese Pruefung fragt deshalb die **Datenbank** und nicht die Modelle. Sie
    braucht eine Verbindung und laeuft darum nicht im reinen Abdeckungstest,
    sondern bei jedem Lauf und im Abgleich-Werkzeug.

    Schattentabellen von Virtualtabellen (``letter_fts_data``,
    ``letter_vec_rowids`` und ihre Geschwister) werden ihrem Elternteil
    zugerechnet, sobald der erklaert ist: sie werden von FTS5 bzw. vec0 selbst
    verwaltet, und sie einzeln aufzuzaehlen waere eine Liste, die mit der
    naechsten SQLite-Fassung veraltet.

    ⚠️ ``ondelete`` wird auch hier aufgeloest, aus der Datenbank statt aus den
    Modellen. Die erste Fassung tat das nicht und meldete sofort einen
    Fehlalarm (``paperless_import_map``, das sein ``ON DELETE CASCADE`` hat und
    sauber mitfaellt). Eine Pruefung, die bei jeder per-SQL angelegten Tabelle
    mit CASCADE anschlaegt, wird nach dem dritten Mal ignoriert, und dann ist
    sie schlechter als keine.
    """
    from sqlalchemy import text

    erklaert = (_tabellen_im_plan(plan) | set(plan.gemeinsam) | set(plan.per_trigger)
                | set(metadata.tables))

    zeilen = db.execute(text(
        "SELECT name, COALESCE(sql, '') FROM sqlite_master WHERE type='table'"
    )).all()
    alle = {name: ddl for name, ddl in zeilen
            if not name.startswith("sqlite_") and not name.startswith("alembic")}

    # Kanten aus der Datenbank: Kind -> [(Eltern, on_delete), ...]
    kanten: dict[str, list[tuple[str, str]]] = {}
    for name in alle:
        try:
            fks = db.execute(text(f"PRAGMA foreign_key_list({name})")).all()
        except Exception:
            continue  # Virtualtabellen antworten hier nicht
        for reihe in fks:
            # (id, seq, table, from, to, on_update, on_delete, match)
            kanten.setdefault(name, []).append((reihe[2], (reihe[6] or "").upper()))

    abgedeckt = set(erklaert)
    gewachsen = True
    while gewachsen:
        gewachsen = False
        for name in alle:
            if name in abgedeckt:
                continue
            for eltern, on_delete in kanten.get(name, []):
                if eltern in abgedeckt and on_delete == "CASCADE":
                    abgedeckt.add(name)
                    gewachsen = True
                    break

    # ⚠️ Schatten gehoeren nur zu einer **Virtualtabelle**, nie zu einer
    # gewoehnlichen. Die erste Fassung prüfte nur den Namensanfang gegen alles
    # Abgedeckte, und damit verbuchte sie ``notizen_fts`` als Schatten von
    # ``notizen``: der Volltextindex, also genau die Tabelle, die den Klartext
    # traegt, waere still durchgefallen. Gefunden hat das die Positivkontrolle
    # im Test, nicht das Nachdenken.
    virtuelle_eltern = {name for name, ddl in alle.items()
                        if "VIRTUAL TABLE" in ddl.upper() and name in abgedeckt}

    befunde: list[str] = []
    for name, ddl in sorted(alle.items()):
        if name in abgedeckt:
            continue
        if any(name.startswith(f"{eltern}_") for eltern in virtuelle_eltern):
            continue
        art = "Virtualtabelle" if "VIRTUAL TABLE" in ddl.upper() else "Tabelle"
        befunde.append(
            f"{name}: {art} in der Datenbank, aber in keinem Modell, in keinem "
            f"Schritt und an keiner CASCADE-Kante. Sie wird per rohem SQL angelegt "
            f"und bleibt beim Loeschen stehen, bis sie einen Schritt bekommt oder "
            f"als gemeinsam erklaert ist."
        )
    return befunde


def _zaehlen(verbindung: Any, tabelle: str, wo: str, sub: str) -> int:
    from sqlalchemy import text

    treffer = verbindung.execute(
        text(f"SELECT count(*) FROM {tabelle} WHERE {wo}"), {"sub": sub}
    ).scalar()
    return int(treffer or 0)


def _reste_suchen(verbindung: Any, plan: Plan, metadata: Any, sub: str) -> dict[str, int]:
    """Nach dem Loeschen: traegt irgendeine Tabelle den Mandanten noch?

    Fragt die Datenbank, nicht den Plan. Ein Schritt, der seine Tabelle verfehlt
    (falsche Spalte, Bedingung die nie greift), meldet sonst 0 geloeschte Zeilen
    und sieht wie "war nichts da" aus.
    """
    reste: dict[str, int] = {}
    for name, tabelle in sorted(metadata.tables.items()):
        if name in plan.gemeinsam:
            continue
        for spalte in tabelle.columns:
            if spalte.name not in MANDANTEN_SPALTEN:
                continue
            uebrig = _zaehlen(verbindung, name, f"{spalte.name} = :sub", sub)
            if uebrig:
                reste[f"{name}.{spalte.name}"] = uebrig
    return reste


def ausfuehren(db: Any, plan: Plan, metadata: Any, sub: str,
               trockenlauf: bool = False) -> Bericht:
    """Den Plan abarbeiten und berichten.

    ``db`` ist eine SQLAlchemy-``Session``. Alles laeuft in deren Transaktion:
    bricht ein Schritt, ist nichts geloescht. Ein halb geloeschtes Konto waere
    schlimmer als ein nicht geloeschtes, weil es danach keinen Zustand gibt, von
    dem aus man es nochmal versuchen kann.
    """
    from sqlalchemy import text

    bericht = Bericht(dienst=plan.dienst, sub=sub, trockenlauf=trockenlauf)
    # Zwei Pruefungen, zwei Quellen: die Modelle und die Datenbank. Die erste
    # findet eine vergessene Modell-Tabelle ohne jede Daten, die zweite alles,
    # was per rohem SQL entstanden ist und in keinem Modell steht.
    bericht.luecken = abdeckung_pruefen(plan, metadata)
    bericht.luecken += ungedeckte_live_tabellen(plan, db, metadata)

    # Erst sammeln, dann loeschen: nach den Schritten nennt keine Zeile mehr
    # einen Pfad.
    pfade: list[Any] = plan.dateien(db, sub) if plan.dateien is not None else []

    for schritt in plan.schritte:
        if trockenlauf:
            bericht.zeilen[schritt.tabelle] = _zaehlen(db, schritt.tabelle, schritt.wo, sub)
            continue
        ergebnis = db.execute(
            text(f"DELETE FROM {schritt.tabelle} WHERE {schritt.wo}"), {"sub": sub}
        )
        bericht.zeilen[schritt.tabelle] = int(ergebnis.rowcount or 0)

    if trockenlauf:
        bericht.nebenwirkungen, bericht.dateifehler = dateien_entfernen(
            pfade, trockenlauf=True)
        return bericht

    # Vor dem Commit pruefen: die Restsuche laeuft in derselben Transaktion und
    # sieht damit den Zustand, der entstehen wuerde. Finden wir etwas, ist das
    # ein Fehler und kein Hinweis, also wird zurueckgerollt und keine einzige
    # Datei angefasst.
    bericht.reste = _reste_suchen(db, plan, metadata, sub)
    if bericht.reste:
        db.rollback()
        bericht.nebenwirkungen = [
            f"{len(pfade)} Datei(en)/Ordner unberuehrt gelassen, weil der Lauf zurueckgerollt wurde"
        ] if pfade else []
        return bericht

    db.commit()
    bericht.nebenwirkungen, bericht.dateifehler = dateien_entfernen(
        pfade, trockenlauf=False)
    return bericht


def bestaetigt(wert: str | None) -> bool:
    """Hat der Aufrufer die Bestaetigungsformel geschickt?

    Gross-/Kleinschreibung und Randleerzeichen sind nachsichtig behandelt, der
    Wortlaut nicht. Ein ``DELETE`` ohne Rumpf soll nicht versehentlich treffen.
    """
    return (wert or "").strip().upper() == BESTAETIGUNG


class Loeschauftrag(BaseModel):
    """Der Rumpf von ``POST /api/konto/loeschen``.

    ⚠️ Steht auf Modulebene und nicht in ``baue_router``, und das ist kein
    Stilthema: dieses Modul hat ``from __future__ import annotations``, also sind
    alle Annotationen Zeichenketten. FastAPI loest sie im **Modul**-Namensraum
    auf. Eine in der Fabrik definierte Klasse findet es dort nicht, deutet den
    Parameter als Query-Parameter und antwortet mit 422 statt den Rumpf zu
    lesen. Gemessen, nicht vermutet.
    """

    confirm: str = Field(default="", description=f'Muss woertlich "{BESTAETIGUNG}" lauten.')


def als_programm(plan: Plan, metadata: Any, sitzung_fabrik: Any,
                 argumente: list[str] | None = None) -> int:
    """Der Betreiberweg: ``python -m app.konto --sub X [--loeschen]``.

    Gedacht fuer **verwaiste** Bestaende, deren Konto schon weg ist: fuer die
    laesst sich kein Token mehr ausstellen, der Routenweg steht also nicht offen.
    Ohne ``--loeschen`` zeigt es nur an, was fallen wuerde.

    Liegt hier und nicht sechsmal im Dienst, aus demselben Grund wie
    ``baue_router``: ein Einstieg, der in sechs Fassungen existiert, hat sechs
    Gelegenheiten, leicht anders zu sein.

    Rueckgabe ist der Prozess-Rueckgabewert: 0 nur, wenn der Lauf sauber war.
    Ein Skript, das diesen Weg verkettet, kann sich darauf verlassen.
    """
    import argparse
    import json

    zerleger = argparse.ArgumentParser(
        prog=f"python -m app.konto  ({plan.dienst})",
        description="Den Bestand eines Mandanten anzeigen oder entfernen.",
    )
    zerleger.add_argument("--sub", required=True, help="Mandant (sub aus der Anmeldung)")
    zerleger.add_argument(
        "--loeschen", action="store_true",
        help="wirklich loeschen. Ohne diesen Schalter nur anzeigen, was faellt.",
    )
    args = zerleger.parse_args(argumente)

    db = sitzung_fabrik()
    try:
        bericht = ausfuehren(db, plan, metadata, args.sub, trockenlauf=not args.loeschen)
    finally:
        db.close()
    print(json.dumps(bericht.als_dict(), indent=2, ensure_ascii=False))
    return 0 if bericht.sauber else 1


def baue_router(plan: Plan, metadata: Any, hole_db: Any, pruefer: Any) -> Any:
    """Die beiden Konto-Routen, fertig verdrahtet, fuer jeden Dienst dieselben.

    Warum hier und nicht siebenmal im Dienst: genau dieser Schnitt lag bis zum
    02.09.2026 bei der JWT-Pruefung achtmal im Baum, in acht leicht abweichenden
    Fassungen, und der Unterschied war nirgends beabsichtigt. Eine Loeschgrenze
    hat dieselbe Eigenschaft wie eine Auth-Grenze: eine Korrektur daran muss an
    einer Stelle wirken, sonst wirkt sie an sechs.

    Der Mandant kommt immer aus dem Token. Es gibt keinen Parameter, mit dem ein
    Aufrufer einen fremden ``sub`` nennen koennte; der Betreiberweg fuer
    verwaiste Bestaende laeuft bewusst ausserhalb des Netzes.
    """
    from fastapi import APIRouter, Depends, HTTPException, status

    router = APIRouter()

    @router.get("/bestand")
    def bestand(me: Any = Depends(pruefer), db: Any = Depends(hole_db)) -> dict[str, Any]:
        """Was dieser Dienst ueber mich haelt, und was ein Loeschen entfernen wuerde.

        Loescht nichts. Gedacht als Blick vor der Entscheidung und zugleich als
        Auskunftsweg: wer wissen will, was gespeichert ist, fragt hier.
        """
        bericht = ausfuehren(db, plan, metadata, me.sub, trockenlauf=True)
        return bericht.als_dict()

    @router.post("/loeschen")
    def konto_loeschen(
        auftrag: Loeschauftrag,
        me: Any = Depends(pruefer),
        db: Any = Depends(hole_db),
    ) -> dict[str, Any]:
        """Allen Bestand dieses Mandanten in diesem Dienst entfernen.

        Alles oder nichts: findet die Restpruefung danach noch Zeilen, wird
        zurueckgerollt und mit 500 geantwortet. Ein halb geloeschtes Konto waere
        schlimmer als ein nicht geloeschtes, weil es danach keinen Zustand gibt,
        von dem aus man es nochmal versuchen kann.
        """
        if not bestaetigt(auftrag.confirm):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Bestätigung erforderlich: sende confirm="{BESTAETIGUNG}".',
            )
        bericht = ausfuehren(db, plan, metadata, me.sub)
        if not bericht.sauber:
            # 500 und nicht 200 mit einem Feld im Rumpf: ein Aufrufer, der nur
            # den Statuscode liest, darf hier nicht "erledigt" verstehen.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "fehler": "Löschen unvollständig, zurückgerollt.",
                    "bericht": bericht.als_dict(),
                },
            )
        return bericht.als_dict()

    return router


def dateien_entfernen(pfade: Iterable[Any],
                      trockenlauf: bool) -> tuple[list[str], list[str]]:
    """Pfade aus der Ablage entfernen. Gibt (Berichtszeilen, Fehler) zurueck.

    Vertraegt Dateien und Verzeichnisse: ``notizen`` legt je Anhang eine Datei
    ab, ``news`` je Mandant einen Ordner mit den gerenderten Sprachausgaben.

    Ein fehlender Pfad ist kein Fehler. Die Datenbank ist die Wahrheit darueber,
    was es geben soll; eine Datei, die schon weg ist, erfuellt genau den Zweck.
    Ein Fehlschlag beim Loeschen dagegen wird berichtet und nicht verschluckt:
    sonst meldet der Lauf ein geloeschtes Konto, und die Inhalte liegen weiter
    auf der Platte.
    """
    import shutil

    zeilen: list[str] = []
    entfernt = 0
    fehlend = 0
    fehler: list[str] = []
    for pfad in pfade:
        if not pfad.exists():
            fehlend += 1
            continue
        if not trockenlauf:
            try:
                if pfad.is_dir():
                    shutil.rmtree(pfad)
                else:
                    pfad.unlink()
            except OSError as problem:
                fehler.append(f"{pfad}: {problem}")
                continue
        entfernt += 1
    if entfernt:
        zeilen.append(
            f"{entfernt} Datei(en)/Ordner in der Ablage "
            f"{'waeren zu loeschen' if trockenlauf else 'geloescht'}"
        )
    if fehlend:
        zeilen.append(f"{fehlend} Pfad(e) lagen nicht mehr in der Ablage")
    return zeilen, fehler
