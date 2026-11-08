"""KI-Chat Stufe 2: Vorschlaege statt Aenderungen (Vertrag: ../ASSISTENT_VERTRAG.md).

Das Modell versteht, Regeln rechnen. Es liefert je Wunsch eine Aktion mit dem
woertlichen Ausschnitt und einer Kurzkennung aus dem Kontext; Tag, Uhrzeit und
Dauer rechnet der Freitext-Parser des Kalenders (`/api/capture`), freie Zeit
der Planer. Das war das Ergebnis der Messung vom 2026-11-02 (Fassung 3, 8/8):
das Modell rechnet Tage falsch und erfindet freie Zeiten.

**Hier wird nichts geschrieben.** Zurueck gehen Vorschlagskarten; die App
fuehrt eine Karte erst nach einem Tipp aus, ueber ihre gewohnten Wege
(Repository, Warteschlange, Serienfrage). Am Kalender haengt die Weckkette.

Kurzkennungen (`e-3`) statt echter: das Modell sieht keine UUIDs und kann
deshalb keine erfinden, die zufaellig auf einen fremden Eintrag passt. Eine
Kennung, die nicht in der Liste stand, verwirft die Aktion.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import date as _date
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .auth import CurrentUser, Me
from .config import settings
from .routes_chat import ERLAUBTE_MODELLE
from .upstream import upstream

router = APIRouter()

_WOCHENTAG = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
#: Tagestyp-Kalender: Steuerdaten, kein Termin, den man im Chat absagt.
_TAGESTYP = re.compile(r"^daytype-")

ARTEN = [
    "frage", "termin_anlegen", "termin_aendern", "termin_loeschen",
    "aufgabe_anlegen", "aufgabe_erledigt", "sitzung_verschieben",
    "tagestyp_setzen", "urlaub_bereich", "tag_planen", "ziel_anlegen",
    "freie_zeit",
]

SYSTEM = """Du bist der Kalender-Assistent. Du aenderst nichts selbst, du machst Vorschlaege, die der Nutzer bestaetigt.
Antworte als JSON nach dem vorgegebenen Schema: "antwort" ist ein kurzer deutscher Satz, "aktionen" eine Liste, je Wunsch genau eine Aktion.

Jede Aktion hat diese Felder (null, wenn nicht zutreffend):
- art: was getan werden soll.
- ausschnitt: der Teil der Nachricht, der zu DIESEM Wunsch gehoert, Wort fuer Wort kopiert, mit allen Zeit- und Tagesangaben (z. B. "morgen 15 Uhr Friseur"). Tag, Uhrzeit und Dauer rechnet das Programm daraus, du rechnest nichts.
- titel: Name des neuen Termins, der Aufgabe oder des Tagesziels.
- ziel_id: Kennung aus der Liste, wenn ein vorhandener Eintrag gemeint ist. e-... sind Termine, s-... sind Sitzungen (Gewohnheiten), t-... Aufgaben.
- umfang (nur bei Serien): "dieser" = nur dieses eine Mal, "ab_hier" = dieses und alle folgenden, "alle" = die ganze Serie.
- typ (nur tagestyp_setzen und urlaub_bereich): urlaub, krank, frei, arbeit, schule.

Regeln: Fragt der Nutzer, wann oder ob er Zeit hat, ist das art "freie_zeit" mit dem Zeitraum und einer genannten Dauer im ausschnitt; die Zeiten rechnet das Programm, in "antwort" nennst du keine Uhrzeit und keine Dauer. Kennungen nur aus der Liste. Eine Sitzung (s-...) verschiebt man mit sitzung_verschieben, nie mit termin_aendern. Eine reine Frage bekommt art "frage". Freie Zeit erfindest du nie. Bezieht sich der Nutzer auf eine fruehere Nachricht ("lieber 15 Uhr"), schreibe den ganzen Wunsch neu in den ausschnitt ("morgen 15 Uhr Steuer").

Beispiele:
"Training faellt nur diese Woche aus" -> termin_loeschen, ziel_id der Serie, umfang "dieser", ausschnitt "Training faellt nur diese Woche aus".
"Yoga faellt ab jetzt immer aus" -> termin_loeschen, ziel_id der Serie, umfang "ab_hier" (ab jetzt, kuenftig, nicht mehr = ab_hier).
"Steuer ist erledigt" (Steuererklaerung ist t-1) -> aufgabe_erledigt, ziel_id "t-1", ausschnitt "Steuer ist erledigt".
"morgen 2h Keller" -> termin_anlegen, titel "Keller", ausschnitt "morgen 2h Keller".
"ich bin Freitag krank" -> tagestyp_setzen, typ "krank", ausschnitt "Freitag krank".
"Urlaub vom 20.12. bis 3.1." -> urlaub_bereich, typ "urlaub", ausschnitt "vom 20.12. bis 3.1.".
"schieb Lernen auf Mittwoch" (Lernen ist s-7) -> sitzung_verschieben, ziel_id "s-7", ausschnitt "Lernen auf Mittwoch".
"heute will ich die Garage aufraeumen" -> ziel_anlegen, titel "Garage aufraeumen", ausschnitt "heute".
"wann habe ich diese Woche Zeit?" -> freie_zeit, ausschnitt "diese Woche".
"hab ich morgen 2 Stunden fuer Sport?" -> freie_zeit, ausschnitt "morgen 2 Stunden".
"Freitag Milch kaufen als Aufgabe" -> aufgabe_anlegen, titel "Milch kaufen", ausschnitt "Freitag Milch kaufen". Aufgabe, Erinnerung oder "nicht vergessen" ist immer aufgabe_anlegen; ziel_anlegen nur, wenn der Nutzer sagt, was er an einem Tag schaffen will."""

_N = {"type": ["string", "null"]}
_FELDER = ["art", "ausschnitt", "titel", "ziel_id", "umfang", "typ"]
SCHEMA = {
    "type": "object",
    "properties": {
        "antwort": {"type": "string"},
        "aktionen": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "art": {"type": "string", "enum": ARTEN},
                    "ausschnitt": {"type": "string"},
                    "titel": _N,
                    "ziel_id": _N,
                    "umfang": {"type": ["string", "null"], "enum": ["dieser", "ab_hier", "alle", None]},
                    "typ": {"type": ["string", "null"], "enum": ["urlaub", "krank", "frei", "arbeit", "schule", None]},
                },
                # Alles Pflicht: mit optionalen Feldern liess das Modell unter
                # der Grammatik jedes weg, das es nicht musste (Messung 2).
                "required": _FELDER,
                "additionalProperties": False,
            },
        },
    },
    "required": ["antwort", "aktionen"],
    "additionalProperties": False,
}


class Zeile(BaseModel):
    rolle: str = Field(..., pattern=r"^(nutzer|assistent)$")
    text: str = Field(..., max_length=2000)


class AssistentIn(BaseModel):
    nachricht: str = Field(..., min_length=1, max_length=1000)
    #: Bisheriger Verlauf, nur bis zum Schliessen des Blatts; hier wird nichts
    #: gespeichert. Gekappt, damit eine lange Unterhaltung das Modell nicht
    #: ueber sein Fenster schiebt.
    verlauf: list[Zeile] = Field(default_factory=list, max_length=20)
    app: str = Field(default="kalender", pattern=r"^kalender$")


# ── Kontext ──────────────────────────────────────────────────────────────

def _zeit(text: str | None) -> str:
    return str(text or "")[11:16]


def _tag_text(iso: str, heute: _date) -> str:
    try:
        tag = _date.fromisoformat(iso[:10])
    except ValueError:
        return iso[:10]
    abstand = (tag - heute).days
    name = {0: "heute", 1: "morgen", -1: "gestern"}.get(abstand, _WOCHENTAG[tag.weekday()])
    return f"{name} {tag.isoformat()}"


#: Wie weit der Kontext nach vorn schaut. 21 Tage waren 33 Terminzeilen und
#: rund 1000 Token, bei 15 Tok/s Einlesen allein eine Minute (gemessen 03.11.).
KONTEXT_TAGE = 14


def _tag_kopf(tag: _date, heute: _date) -> str:
    name = {0: "heute", 1: "morgen"}.get((tag - heute).days, _WOCHENTAG[tag.weekday()][:2])
    return f"{name} {tag:%d.%m.}"


def kontext_bauen(daten: dict, heute: _date, jetzt: str) -> tuple[str, dict[str, dict]]:
    """Klartext fuer das Modell und die Zuordnung Kurzkennung -> Eintrag.

    Knapp und nach Tagen gruppiert, und die Uhrzeit steht am ENDE. Der
    Modellwirt rechnet auf CPU und liest rund 15 Token/s ein; was vorn gleich
    bleibt, holt er aus dem Cache (seit --swa-full, 03.11.). Stand „jetzt HH:MM"
    vorn, war ab der ersten Zeile alles neu, bei jeder Frage. Eine Terminzeile
    kostete in der alten Form (ISO-Datum, Wochentag ausgeschrieben, „bis“) rund
    30 Token, jetzt etwa 12.
    """
    zuordnung: dict[str, dict] = {}
    zeilen: list[str] = []
    grenze = (heute + timedelta(days=KONTEXT_TAGE)).isoformat()

    def nach_tagen(eintraege: list[tuple[str, dict]], kopf: str, zeile) -> None:
        if not eintraege:
            return
        zeilen.append(kopf)
        letzter = None
        for kurz, e in eintraege:
            tag = str(e.get("start") or "")[:10]
            if tag != letzter:
                try:
                    zeilen.append(_tag_kopf(_date.fromisoformat(tag), heute) + ":")
                except ValueError:
                    zeilen.append(tag + ":")
                letzter = tag
            zeilen.append(zeile(kurz, e))

    termine = [
        e for e in daten.get("events") or []
        if not _TAGESTYP.match(str(e.get("calendar_id") or ""))
        and heute.isoformat() <= str(e.get("start") or "")[:10] < grenze
    ]
    termine.sort(key=lambda e: str(e.get("start")))
    termine = [(f"e-{i}", e) for i, e in enumerate(termine[:40], 1)]
    for kurz, e in termine:
        zuordnung[kurz] = {"art": "termin", **e}

    def terminzeile(kurz: str, e: dict) -> str:
        zeit = "ganztägig" if e.get("all_day") else f"{_zeit(e.get('start'))}-{_zeit(e.get('end'))}"
        return f"- {kurz} {zeit} {e.get('title')}{' (Serie)' if e.get('recurrence_rule') else ''}"

    nach_tagen(termine, "Termine:", terminzeile)

    sitzungen = [
        s for s in daten.get("sessions") or []
        if s.get("status") in ("pending", "accepted")
        and heute.isoformat() <= str(s.get("start") or "")[:10] < grenze
    ]
    sitzungen.sort(key=lambda s: str(s.get("start")))
    sitzungen = [(f"s-{i}", s) for i, s in enumerate(sitzungen[:30], 1)]
    for kurz, s in sitzungen:
        zuordnung[kurz] = {"art": "sitzung", **s}

    def sitzungszeile(kurz: str, s: dict) -> str:
        stand = "angenommen" if s.get("status") == "accepted" else "vorgeschlagen"
        return f"- {kurz} {_zeit(s.get('start'))}-{_zeit(s.get('end'))} {s.get('habit_name') or 'Sitzung'} ({stand})"

    nach_tagen(sitzungen, "Sitzungen:", sitzungszeile)

    aufgaben = [t for t in daten.get("todos") or [] if not t.get("completed")]
    if aufgaben:
        zeilen.append("Offene Aufgaben:")
    for i, t in enumerate(aufgaben[:30], 1):
        kurz = f"t-{i}"
        zuordnung[kurz] = {"art": "aufgabe", **t}
        frist = ""
        if t.get("due_date"):
            try:
                frist = f" (fällig {_date.fromisoformat(str(t['due_date'])[:10]):%d.%m.})"
            except ValueError:
                frist = f" (fällig {t['due_date']})"
        zeilen.append(f"- {kurz} {t.get('title')}{frist}")

    zeilen.append(f"Heute ist {_WOCHENTAG[heute.weekday()]}, {heute:%d.%m.%Y}, jetzt {jetzt}.")
    return "\n".join(zeilen), zuordnung


# ── Modell ───────────────────────────────────────────────────────────────

def _modell() -> str | None:
    name = (settings.llm_model or "").strip()
    return name if name in ERLAUBTE_MODELLE else None


def _erstes_json(text: str) -> dict | None:
    t = text.strip()
    try:
        wert = json.loads(t)
    except ValueError:
        a, b = t.find("{"), t.rfind("}")
        if a < 0 or b <= a:
            return None
        try:
            wert = json.loads(t[a:b + 1])
        except ValueError:
            return None
    return wert if isinstance(wert, dict) else None


async def _modell_fragen(modell: str, kontext: str, data: AssistentIn) -> dict:
    nachrichten = [{"role": "system", "content": SYSTEM}]
    for zeile in data.verlauf[-10:]:
        nachrichten.append({
            "role": "user" if zeile.rolle == "nutzer" else "assistant",
            "content": zeile.text,
        })
    nachrichten.append({"role": "user", "content": f"{kontext}\n\nNachricht: {data.nachricht}"})
    kopf = {}
    if settings.llm_gateway_key:
        kopf["Authorization"] = f"Bearer {settings.llm_gateway_key}"
    try:
        async with httpx.AsyncClient(timeout=settings.assistent_timeout_seconds) as client:
            r = await client.post(
                settings.llm_gateway_url.rstrip("/") + "/v1/chat/completions",
                headers=kopf,
                json={
                    "model": modell,
                    "messages": nachrichten,
                    "max_tokens": 800,
                    "temperature": 0.1,
                    # gpt-oss gibt ohne ihn eine leere Antwort ohne Fehler;
                    # das Gateway verwirft ihn fuer Modelle, die ihn nicht kennen.
                    "reasoning_effort": "low",
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {"name": "kalender_aktionen", "schema": SCHEMA},
                    },
                },
            )
        r.raise_for_status()
        inhalt = ((r.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Modell nicht erreichbar: {e!r}"[:300]) from e
    obj = _erstes_json(inhalt) if isinstance(inhalt, str) else None
    if obj is None:
        raise HTTPException(502, "Das Modell hat keine lesbare Antwort gegeben.")
    return obj


# ── Regeln: aus Aktionen werden Karten ───────────────────────────────────

async def _erfassen(text: str) -> dict:
    """Tag, Uhrzeit, Dauer und freie Zeiten nach den Regeln des Kalenders."""
    r = await upstream("POST", "/api/capture", json={"text": text, "allow_llm": False})
    return r.json() if r.content else {}


def _iso(tag: str, uhrzeit: str) -> str:
    return f"{tag}T{uhrzeit}:00"


def _plus(tag: str, uhrzeit: str, minuten: int) -> str:
    beginn = datetime.fromisoformat(_iso(tag, uhrzeit))
    return (beginn + timedelta(minutes=minuten)).isoformat(timespec="seconds")


def _kurz_datum(iso: str, heute: _date) -> str:
    return _tag_text(iso, heute).split(" ")[0] if iso[:10] in (
        heute.isoformat(), (heute + timedelta(days=1)).isoformat()
    ) else _date.fromisoformat(iso[:10]).strftime("%d.%m.")


class Verworfen(Exception):
    pass


async def karte_bauen(
    aktion: dict, zuordnung: dict[str, dict], heute: _date, kalender_id: str | None,
) -> dict | None:
    art = aktion.get("art")
    ausschnitt = str(aktion.get("ausschnitt") or "").strip()
    titel = (aktion.get("titel") or "").strip()
    ziel = None
    if aktion.get("ziel_id"):
        ziel = zuordnung.get(str(aktion["ziel_id"]))
        if ziel is None:
            raise Verworfen(f"unbekannte Kennung {aktion['ziel_id']}")

    if art == "frage" or art is None:
        return None

    if art == "termin_anlegen":
        erfasst = await _erfassen(ausschnitt or titel)
        titel = titel or erfasst.get("title") or ausschnitt
        if erfasst.get("start_time"):
            tag = erfasst.get("date") or heute.isoformat()
            ende = (
                _iso(tag, erfasst["end_time"]) if erfasst.get("end_time")
                else _plus(tag, erfasst["start_time"], erfasst.get("dauer_min") or 60)
            )
            optionen = [{
                "text": f"{_kurz_datum(tag, heute)} {erfasst['start_time']} bis {ende[11:16]}",
                "daten": {"termin": {"calendar_id": kalender_id, "title": titel,
                                     "start": _iso(tag, erfasst["start_time"]), "end": ende,
                                     "all_day": False}},
            }]
        else:
            vorschlaege = erfasst.get("vorschlaege") or []
            if not erfasst.get("dauer_min"):
                # Ohne Dauer rechnet der Planer nichts; eine Stunde ist die
                # uebliche Annahme, und die Karte sagt sie.
                vorschlaege = (await _erfassen(f"{ausschnitt} 1h")).get("vorschlaege") or []
            if not vorschlaege:
                raise Verworfen(f"keine freie Zeit fuer „{titel}“ gefunden")
            optionen = [{
                "text": f"{_kurz_datum(v['date'], heute)} {v['start_time']} bis {v['end_time']}",
                "daten": {"termin": {"calendar_id": kalender_id, "title": titel,
                                     "start": _iso(v["date"], v["start_time"]),
                                     "end": _iso(v["date"], v["end_time"]), "all_day": False}},
            } for v in vorschlaege[:3]]
        return {"art": art, "text": f"Neuer Termin: {titel}", "optionen": optionen,
                "hinweis": None if erfasst.get("dauer_min") or erfasst.get("start_time")
                else "Dauer nicht genannt, eine Stunde angenommen."}

    if art in ("termin_loeschen", "termin_aendern"):
        if not ziel or ziel["art"] != "termin":
            raise Verworfen(f"{art} ohne Termin aus der Liste")
        serie = "::" in str(ziel.get("id"))
        umfang = (aktion.get("umfang") or "dieser") if serie else None
        beschreibung = f"{ziel.get('title')} ({_kurz_datum(str(ziel.get('start')), heute)} {_zeit(ziel.get('start'))})"
        if art == "termin_loeschen":
            return {"art": art, "text": f"Absagen: {beschreibung}",
                    "optionen": [{"text": "Absagen", "daten": {"termin_id": ziel["id"], "umfang": umfang}}],
                    "hinweis": _umfang_hinweis(umfang)}
        erfasst = await _erfassen(ausschnitt)
        alt_start = datetime.fromisoformat(str(ziel["start"])[:19])
        alt_ende = datetime.fromisoformat(str(ziel["end"])[:19])
        neuer_tag = erfasst.get("date") or alt_start.date().isoformat()
        neue_zeit = erfasst.get("start_time") or alt_start.strftime("%H:%M")
        if not erfasst.get("date") and not erfasst.get("start_time"):
            raise Verworfen(f"keine neue Zeit fuer „{ziel.get('title')}“ erkannt")
        start = datetime.fromisoformat(_iso(neuer_tag, neue_zeit))
        ende = (
            datetime.fromisoformat(_iso(neuer_tag, erfasst["end_time"])) if erfasst.get("end_time")
            else start + (alt_ende - alt_start)
        )
        return {"art": art, "text": f"Verschieben: {beschreibung}",
                "optionen": [{
                    "text": f"auf {_kurz_datum(neuer_tag, heute)} {start:%H:%M} bis {ende:%H:%M}",
                    "daten": {"termin_id": ziel["id"], "umfang": umfang, "termin": {
                        "calendar_id": ziel.get("calendar_id"), "title": ziel.get("title"),
                        "description": ziel.get("description"), "location": ziel.get("location"),
                        "start": start.isoformat(timespec="seconds"),
                        "end": ende.isoformat(timespec="seconds"), "all_day": bool(ziel.get("all_day")),
                        # „Ab hier" legt eine neue Serie an und braucht dafuer
                        # die Regel; „alle" laesst sie beim BFF ohnehin stehen.
                        "recurrence_rule": ziel.get("recurrence_rule"),
                    }},
                }],
                "hinweis": _umfang_hinweis(umfang)}

    if art == "aufgabe_anlegen":
        erfasst = await _erfassen(ausschnitt or titel)
        titel = titel or erfasst.get("title") or ausschnitt
        frist = erfasst.get("date")
        return {"art": art, "text": f"Neue Aufgabe: {titel}",
                "optionen": [{
                    "text": f"fällig {_kurz_datum(frist, heute)}" if frist else "ohne Frist",
                    "daten": {"aufgabe": {"title": titel, "due_date": frist,
                                          "due_time": erfasst.get("start_time")}},
                }], "hinweis": None}

    if art == "aufgabe_erledigt":
        if not ziel or ziel["art"] != "aufgabe":
            raise Verworfen("aufgabe_erledigt ohne Aufgabe aus der Liste")
        return {"art": art, "text": f"Erledigt: {ziel.get('title')}",
                "optionen": [{"text": "Abhaken", "daten": {"aufgabe_id": ziel["id"]}}], "hinweis": None}

    if art == "sitzung_verschieben":
        if not ziel or ziel["art"] != "sitzung":
            raise Verworfen("sitzung_verschieben ohne Sitzung aus der Liste")
        return {"art": art, "text": f"Verschieben: {ziel.get('habit_name') or 'Sitzung'} "
                                   f"({_kurz_datum(str(ziel.get('start')), heute)} {_zeit(ziel.get('start'))})",
                "optionen": [{"text": "Verschieben", "daten": {"sitzung_id": ziel["id"], "aktion": "dismissed"}}],
                # Ehrlich: einen Wunschtag kann der Kalender bei Sitzungen nicht
                # uebernehmen, er sucht selbst einen Platz in dieser Woche.
                "hinweis": "Der Kalender sucht selbst einen neuen Platz in dieser Woche."}

    if art in ("tagestyp_setzen", "urlaub_bereich"):
        typ = aktion.get("typ") or ("urlaub" if art == "urlaub_bereich" else None)
        if not typ:
            raise Verworfen("Tagestyp nicht erkannt")
        if art == "urlaub_bereich" and re.search(r"\bbis\b", ausschnitt):
            links, rechts = re.split(r"\bbis\b", ausschnitt, maxsplit=1)
            von = (await _erfassen(links)).get("date")
            bis = (await _erfassen(rechts)).get("date")
        else:
            von = bis = (await _erfassen(ausschnitt)).get("date") or heute.isoformat()
        if not von or not bis or bis < von:
            raise Verworfen("Zeitraum nicht erkannt")
        zeitraum = _kurz_datum(von, heute) if von == bis else f"{_kurz_datum(von, heute)} bis {_kurz_datum(bis, heute)}"
        return {"art": art, "text": f"{typ.capitalize()}: {zeitraum}",
                "optionen": [{"text": "Eintragen", "daten": {"von": von, "bis": bis, "typ": typ}}],
                "hinweis": "Steuert Wecker und Morgenlicht." if typ in ("arbeit", "schule", "urlaub", "krank", "frei") else None}

    if art == "ziel_anlegen":
        tag = (await _erfassen(ausschnitt)).get("date") if ausschnitt else None
        tag = tag or heute.isoformat()
        titel = titel or ausschnitt
        return {"art": art, "text": f"Tagesziel: {titel}",
                "optionen": [{"text": _kurz_datum(tag, heute),
                              "daten": {"ziel": {"title": titel, "date": tag, "priority": "B"}}}],
                "hinweis": None}

    if art == "tag_planen":
        raise Verworfen("„Tag planen“ geht im Chat noch nicht")
    raise Verworfen(f"unbekannte Art {art}")


# ── Freie Zeit: der Planer rechnet, nicht das Modell ─────────────────────

_KURZTAG = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def zeitraum_lesen(ausschnitt: str, heute: _date, erfasster_tag: str | None) -> list[_date]:
    """Die Tage, nach denen gefragt ist, nach festen Regeln.

    Woche und Wochenende kennt der Freitext-Parser nicht (er liefert einen Tag),
    deshalb stehen sie hier. Ohne erkennbaren Zeitraum: die naechsten sieben Tage.
    """
    text = ausschnitt.lower()
    wt = heute.weekday()
    if "wochenende" in text:
        if "naechste" in text or "nächste" in text or "kommende" in text:
            samstag = heute + timedelta(days=(5 - wt) % 7 + (7 if wt == 5 else 0))
            return [samstag, samstag + timedelta(days=1)]
        if wt == 6:
            return [heute]
        samstag = heute + timedelta(days=(5 - wt) % 7)
        return [samstag, samstag + timedelta(days=1)]
    if re.search(r"(naechste|nächste|kommende)n? woche", text):
        montag = heute + timedelta(days=7 - wt)
        return [montag + timedelta(days=i) for i in range(7)]
    if "woche" in text:
        return [heute + timedelta(days=i) for i in range(7 - wt)]
    if erfasster_tag:
        try:
            return [_date.fromisoformat(erfasster_tag)]
        except ValueError:
            pass
    return [heute + timedelta(days=i) for i in range(7)]


def _dauer_text(minuten: int) -> str:
    h, m = divmod(int(minuten), 60)
    return f"{h} h {m} min" if h and m else (f"{h} h" if h else f"{m} min")


def freie_zeit_text(tage: list[dict], heute: _date, dauer_min: int | None) -> str:
    """Klartext aus `/api/schedule/free-slots`, je Tag eine Zeile.

    Mit Dauer nur Bloecke, in die sie passt: „Zeit fuer 2 Stunden" mit einer
    Liste aus Viertelstunden zu beantworten waere formal richtig und nutzlos.
    """
    kopf = (f"Wo {_dauer_text(dauer_min)} am Stück passen" if dauer_min
            else "Freie Zeit") + " (8 bis 22 Uhr, Termine, Sitzungen und Arbeit abgezogen):"
    zeilen = [kopf]
    for tag in tage:
        try:
            datum = _date.fromisoformat(str(tag.get("date"))[:10])
        except ValueError:
            continue
        name = {0: "heute", 1: "morgen"}.get((datum - heute).days, _KURZTAG[datum.weekday()])
        bloecke = [b for b in tag.get("free_slots") or []
                   if not dauer_min or int(b.get("minutes") or 0) >= dauer_min]
        if not bloecke:
            zeilen.append(f"{name} {datum:%d.%m.}: " + ("nichts passend" if dauer_min else "nichts frei"))
            continue
        spannen = ", ".join(f"{str(b['start'])[11:16]}-{str(b['end'])[11:16]}" for b in bloecke)
        summe = sum(int(b.get("minutes") or 0) for b in bloecke)
        zeilen.append(f"{name} {datum:%d.%m.}: {spannen} ({_dauer_text(summe)})")
    return "\n".join(zeilen)


#: Fragen nach freier Zeit, an der Nachricht erkannt. Gemessen 04.11.: „was
#: ist am Wochenende frei?" ordnete das Modell als `frage` ein und nannte selbst
#: Zeiten („00:00 bis 10:00"). Die Regel greift deshalb unabhaengig davon, wie
#: das Modell die Nachricht einordnet.
_FREIE_ZEIT_FRAGE = re.compile(
    r"\b(wann|wie ?viel|habe?|hab ich|ist|was|wo)\b.*\b(frei|freie|zeit|luft)\b|\bfrei\b.*\?"
    r"|\bhabe? ich\b.*\b\d+([,.]\d+)?\s*(stunden?|std|minuten?|min|h)\b.*\?",
    re.IGNORECASE,
)
#: Wer etwas anlegen will, fragt nicht nach freier Zeit, auch wenn „Zeit" faellt.
_ANLEGEN = re.compile(r"\b(plane?|trag|leg|setz|schieb|verschieb|sag .* ab|erinner)\w*\b", re.IGNORECASE)


def fragt_nach_freier_zeit(nachricht: str) -> bool:
    return bool(_FREIE_ZEIT_FRAGE.search(nachricht)) and not _ANLEGEN.search(nachricht)


async def freie_zeit_beantworten(ausschnitt: str, heute: _date) -> str:
    erfasst = await _erfassen(ausschnitt) if ausschnitt else {}
    tage = zeitraum_lesen(ausschnitt, heute, erfasst.get("date"))
    antworten = await asyncio.gather(*[
        upstream("GET", "/api/schedule/free-slots", params={"date": t.isoformat()}) for t in tage
    ])
    return freie_zeit_text(
        [r.json() if r.content else {} for r in antworten], heute, erfasst.get("dauer_min"),
    )


def _umfang_hinweis(umfang: str | None) -> str | None:
    return {
        "dieser": "Nur dieser Termin der Serie.",
        "ab_hier": "Dieser und alle folgenden Termine der Serie.",
        "alle": "Die ganze Serie.",
    }.get(umfang or "")


@router.post("/api/assistent")
async def assistent(data: AssistentIn, me: Me = CurrentUser) -> dict:
    modell = _modell()
    if not settings.llm_gateway_url or not modell:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Kein Modell im Haus konfiguriert (LLM_GATEWAY_URL, LLM_MODEL aus {sorted(ERLAUBTE_MODELLE)}).",
        )
    heute = _date.today()
    r = await upstream(
        "GET", "/api/mobile/bootstrap",
        params={"start": heute.isoformat(), "end": (heute + timedelta(days=21)).isoformat()},
        timeout=30.0,
    )
    daten = r.json() if r.content else {}
    kontext, zuordnung = kontext_bauen(daten, heute, datetime.now().strftime("%H:%M"))
    kalender = next((k.get("id") for k in daten.get("calendars") or [] if k.get("name") == "Termine"), None)

    obj = await _modell_fragen(modell, kontext, data)
    karten: list[dict] = []
    verworfen: list[dict] = []
    fakten: list[str] = []
    aktionen = [a for a in obj.get("aktionen") or [] if isinstance(a, dict)]
    if fragt_nach_freier_zeit(data.nachricht) and not any(
        a.get("art") not in ("frage", None) for a in aktionen
    ):
        aktionen = [{"art": "freie_zeit", "ausschnitt": data.nachricht}]
    for aktion in aktionen:
        if not isinstance(aktion, dict):
            continue
        if aktion.get("art") == "freie_zeit":
            try:
                fakten.append(await freie_zeit_beantworten(str(aktion.get("ausschnitt") or "").strip(), heute))
            except HTTPException as e:
                verworfen.append({"art": "freie_zeit", "grund": f"Kalender: {e.detail}"[:200]})
            continue
        try:
            karte = await karte_bauen(aktion, zuordnung, heute, kalender)
        except Verworfen as v:
            verworfen.append({"art": aktion.get("art"), "grund": str(v)})
            continue
        except HTTPException as e:
            verworfen.append({"art": aktion.get("art"), "grund": f"Kalender: {e.detail}"[:200]})
            continue
        if karte:
            karte["id"] = f"k{len(karten) + 1}"
            karten.append(karte)
    antwort = str(obj.get("antwort") or "").strip() or (
        "Hier sind meine Vorschläge." if karten else "Dazu habe ich nichts gefunden."
    )
    if fakten:
        # Der Satz des Modells entfaellt: er koennte Zeiten nennen, die der
        # Planer nicht kennt (Messung 02.11.: „Dienstag 00:00 bis …"). Die
        # Antwort auf eine Frage nach freier Zeit ist die Rechnung selbst.
        antwort = "\n\n".join(fakten) + ("\n\nDazu Vorschläge unten." if karten else "")
    return {"antwort": antwort, "karten": karten, "verworfen": verworfen, "modell": modell}
