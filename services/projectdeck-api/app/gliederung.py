"""Ober- und Unterprojekte (Entscheide U1 bis U8, 2026-11-15).

Ein Unterprojekt ist ein vollwertiges Projekt. Es kann unter mehreren
Oberprojekten haengen und ist trotzdem nur einmal vorhanden; die Gliederung
ist damit ein gerichteter Graph ohne Kreis, kein Baum. Aufgaben, Notizen,
Termine und Buchungen nennen weiter genau einen Slug; ein Oberprojekt zeigt
alles, was an ihm selbst und an seinen Nachfahren haengt.
"""
from __future__ import annotations

from collections import deque

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Project, ProjectEltern


def kanten(db: Session, owner: str) -> list[tuple[int, int]]:
    """Alle (kind, eltern) des Mandanten, in einer Abfrage."""
    return [
        (k, e)
        for k, e in db.execute(
            select(ProjectEltern.kind_id, ProjectEltern.eltern_id)
            .join(Project, Project.id == ProjectEltern.kind_id)
            .where(Project.owner == owner)
        ).all()
    ]


def eltern_und_kinder(db: Session, owner: str) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    eltern: dict[int, list[int]] = {}
    kinder: dict[int, list[int]] = {}
    for k, e in kanten(db, owner):
        eltern.setdefault(k, []).append(e)
        kinder.setdefault(e, []).append(k)
    return eltern, kinder


def nachfahren(kinder: dict[int, list[int]], start: int) -> list[int]:
    """Alle Nachfahren in Breitensuche, ohne ``start``, jeder nur einmal.

    Ein Projekt mit zwei Eltern unter demselben Oberprojekt (Gartiko-Bot
    unter Discord-Bots und Gartiko, beide unter einem Dach) taucht so nur
    einmal auf; sonst zaehlte die Akte seine Aufgaben doppelt.
    """
    gesehen: set[int] = {start}
    reihe: list[int] = []
    offen = deque(kinder.get(start, []))
    while offen:
        pid = offen.popleft()
        if pid in gesehen:
            continue
        gesehen.add(pid)
        reihe.append(pid)
        offen.extend(kinder.get(pid, []))
    return reihe


def pfad_zur_wurzel(eltern: dict[int, list[int]], start: int) -> list[int]:
    """Ein Weg nach oben fuer die Brotkrumen: jeweils der erste Elternteil.

    Mehrere Eltern gibt es; die Brotkrumen zeigen einen Weg, die Akte nennt
    alle Eltern daneben. Bricht bei einem Kreis ab (darf es nicht geben).
    """
    weg: list[int] = []
    gesehen = {start}
    jetzt = start
    while eltern.get(jetzt):
        oben = sorted(eltern[jetzt])[0]
        if oben in gesehen:
            break
        weg.append(oben)
        gesehen.add(oben)
        jetzt = oben
    return list(reversed(weg))


def eltern_setzen(db: Session, projekt: Project, eltern_ids: list[int]) -> None:
    """Ersetzt die Eltern eines Projekts. 422 bei fremdem Projekt, sich selbst oder Kreis."""
    gewuenscht = list(dict.fromkeys(eltern_ids))
    if projekt.id in gewuenscht:
        raise HTTPException(422, "Ein Projekt kann nicht unter sich selbst haengen")
    if gewuenscht:
        eigene = set(db.scalars(
            select(Project.id).where(Project.owner == projekt.owner, Project.id.in_(gewuenscht))
        ))
        if eigene != set(gewuenscht):
            raise HTTPException(422, "Oberprojekt nicht gefunden")
        _, kinder = eltern_und_kinder(db, projekt.owner)
        unten = set(nachfahren(kinder, projekt.id))
        kreis = unten.intersection(gewuenscht)
        if kreis:
            raise HTTPException(422, "Das waere ein Kreis: das Oberprojekt haengt schon unter diesem Projekt")
    db.query(ProjectEltern).filter(ProjectEltern.kind_id == projekt.id).delete()
    for eid in gewuenscht:
        db.add(ProjectEltern(kind_id=projekt.id, eltern_id=eid))
