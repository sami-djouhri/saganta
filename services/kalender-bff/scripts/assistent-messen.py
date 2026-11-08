"""KI-Chat Stufe 1: misst, ob ein Modell im Haus den Aktionsvertrag traegt.

Vertrag: ../ASSISTENT_VERTRAG.md. Gemessen wird je Modell und Testsatz:
Antwortzeit, ob die Antwort dem Schema folgt, ob die richtigen Aktionsarten
darin stehen und ob Kennung, Umfang und Tag stimmen. Geschrieben wird nichts,
weder in den Kalender noch sonst wohin.

Laeuft IM Container des kalender-bff, weil dort Gateway-Adresse und Schluessel
als Umgebung liegen. Der Schluessel wird nie ausgegeben::

    bash scripts/ki-chat-einrichten.sh --nur-messen
    docker exec -i saganta-kalender-bff python - homelab-smart < scripts/assistent-messen.py

Zweite Fassung, nach der ersten Messung vom 2026-11-02 (homelab-smart 4/8,
Median 24 s; homelab-fast 1/8, Median 81 s). Drei Befunde haben sie geformt:

1. **Das Format war das kleinere Problem.** Zwei der vier Fehlwertungen waren
   richtig verstanden und nur anders geschachtelt (`{"termin_anlegen": {...}}`
   statt `{"art": ...}`), das kleine Modell schrieb `aktion` statt `art`. Jetzt
   geht ein JSON-Schema als `response_format` mit, llama.cpp erzwingt es per
   Grammatik. Mit `--ohne-schema` laesst sich der alte Weg vergleichen.
2. **Datumsrechnung kann es nicht.** „Freitag“ wurde zum Mittwoch. Das Modell
   gibt den Tag jetzt **wörtlich** zurück (`tag_text`: „morgen“, „Freitag“),
   gerechnet wird mit denselben Regeln wie im Freitext-Parser des Kalenders
   (`kalender/backend/capture.py`, `_parse_date_str`). Regelbasiert, wo es geht.
3. **Freie Zeiten erfindet es** („Dienstag 00:00 bis 02:00“). Die rechnet im
   Chat der Planer; bewertet wird hier deshalb nur, dass eine Frage keine
   Aenderung ausloest.

Dritte Fassung nach der zweiten Messung (4/8, Median 22 s): mit Schema
liess das Modell jedes optionale Feld weg (kein Tag, keine Uhrzeit, bei
„ich bin morgen krank“ gar keine Aktion). Jetzt liefert es nur noch, was ein
Sprachmodell kann: die Art, die gemeinte Kennung, Titel, Umfang, Tagestyp und
den **wörtlichen Ausschnitt** des Satzes, der zu diesem Wunsch gehoert. Alle
Felder sind Pflicht (null erlaubt). Tag, Uhrzeit und Dauer rechnen die Regeln
des Freitext-Parsers aus dem Ausschnitt; im Chat ruft der Dienst dafuer
`/api/capture` des Kalenders.

`reasoning_effort: low` geht immer mit. gpt-oss liefert ohne ihn eine leere
Antwort ohne Fehler (Root-Policy, AI Services); das Gateway verwirft den
Parameter fuer Modelle, die ihn nicht kennen (`drop_params: true`).
Ohne `homelab-large`, obwohl routes_chat.ERLAUBTE_MODELLE es fuehrt: der
Alias zeigt auf gamehost, also aus dem Haus. Der Key des kalender-bff erlaubt
ihn deshalb auch nicht.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date, timedelta

import httpx

ERLAUBT = ["homelab-smart", "homelab-fast"]
HEUTE = date(2026, 11, 2)  # Montag, fester Bezug des erfundenen Kontexts

KONTEXT = """Heute ist Montag, 2026-11-02, jetzt 10:00.
Termine:
- e-1: heute 19:00 bis 22:30: Kino mit Tim
- e-2: Mittwoch 2026-11-04 09:30 bis 10:15: Zahnarzt
- e-3: Dienstag 2026-11-03 18:00 bis 19:00: Training (Serie, jeden Dienstag)
Sitzungen:
- s-1: heute 16:30 bis 18:00: Gitarre (angenommen)
Offene Aufgaben:
- t-1: Steuererklaerung (faellig 2026-11-10)
"""

ARTEN = [
    "frage", "termin_anlegen", "termin_aendern", "termin_loeschen",
    "aufgabe_anlegen", "aufgabe_erledigt", "sitzung_verschieben",
    "tagestyp_setzen", "urlaub_bereich", "tag_planen",
]

SYSTEM = """Du bist der Kalender-Assistent. Du aenderst nichts selbst, du machst Vorschlaege, die der Nutzer bestaetigt.
Antworte als JSON nach dem vorgegebenen Schema: "antwort" ist ein kurzer deutscher Satz, "aktionen" eine Liste, je Wunsch genau eine Aktion.

Jede Aktion hat diese Felder (null, wenn nicht zutreffend):
- art: was getan werden soll.
- ausschnitt: der Teil der Nachricht, der zu DIESEM Wunsch gehoert, Wort fuer Wort kopiert, mit allen Zeit- und Tagesangaben (z. B. "morgen 15 Uhr Friseur"). Tag, Uhrzeit und Dauer rechnet das Programm daraus, du rechnest nichts.
- titel: Name des neuen Termins oder der Aufgabe.
- ziel_id: Kennung aus der Liste, wenn ein vorhandener Eintrag gemeint ist. e-... sind Termine, s-... sind Sitzungen (Gewohnheiten), t-... Aufgaben.
- umfang (nur bei Serien): "dieser" = nur dieses eine Mal, "ab_hier" = dieses und alle folgenden, "alle" = die ganze Serie.
- typ (nur tagestyp_setzen und urlaub_bereich): urlaub, krank, frei, arbeit, schule.

Regeln: Kennungen nur aus der Liste. Eine Sitzung (s-...) verschiebt man mit sitzung_verschieben, nie mit termin_aendern. Eine reine Frage bekommt art "frage". Freie Zeit erfindest du nie.

Beispiele:
"Training faellt nur diese Woche aus" -> termin_loeschen, ziel_id der Serie, umfang "dieser", ausschnitt "Training faellt nur diese Woche aus".
"morgen 2h Keller" -> termin_anlegen, titel "Keller", ausschnitt "morgen 2h Keller".
"ich bin Freitag krank" -> tagestyp_setzen, typ "krank", ausschnitt "Freitag krank".
"schieb Lernen auf Mittwoch" (Lernen ist s-7) -> sitzung_verschieben, ziel_id "s-7", ausschnitt "Lernen auf Mittwoch"."""

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
                # der Grammatik jedes weg, das es nicht musste (zweite Messung).
                "required": _FELDER,
                "additionalProperties": False,
            },
        },
    },
    "required": ["antwort", "aktionen"],
    "additionalProperties": False,
}

# Satz -> erwartete Aktionen. Jede erwartete Aktion ist ein dict von Feldern,
# die stimmen muessen; `tag`/`neu_tag` werden aus tag_text/neu_tag_text gerechnet.
FAELLE = [
    ("plane morgen 2 Stunden Steuer ein",
     [{"art": "termin_anlegen", "tag": "2026-11-03", "dauer_min": 120}]),
    ("sag das Kino heute ab",
     [{"art": "termin_loeschen", "termin_id": "e-1"}]),
    ("schieb den Zahnarzt auf Donnerstag 14 Uhr",
     [{"art": "termin_aendern", "termin_id": "e-2", "neu_tag": "2026-11-05", "neu_von": "14:00"}]),
    ("ich bin morgen krank",
     [{"art": "tagestyp_setzen", "tag": "2026-11-03", "typ": "krank"}]),
    ("Training faellt nur diese Woche aus",
     [{"art": "termin_loeschen", "termin_id": "e-3", "umfang": "dieser"}]),
    ("morgen 15 Uhr Friseur und Freitag Einkauf als Aufgabe",
     [{"art": "termin_anlegen", "tag": "2026-11-03", "von": "15:00"},
      {"art": "aufgabe_anlegen", "tag": "2026-11-06"}]),
    ("wann habe ich diese Woche noch zwei Stunden frei?",
     [{"art": "frage"}]),
    ("verschieb Gitarre auf morgen",
     [{"art": "sitzung_verschieben", "sitzung_id": "s-1", "neu_tag": "2026-11-03"}]),
]

# --- Tag aus Worten, dieselben Regeln wie kalender/backend/capture.py ---------
_WOCHENTAGE = {"montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3,
               "freitag": 4, "samstag": 5, "sonnabend": 5, "sonntag": 6}


def tag_aus_text(text: str | None, basis: date = HEUTE) -> str | None:
    if not text:
        return None
    low = text.lower()
    for wort, versatz in (("übermorgen", 2), ("uebermorgen", 2), ("morgen", 1), ("heute", 0)):
        if re.search(rf"\b{wort}\b", low):
            return (basis + timedelta(days=versatz)).isoformat()
    m = re.search(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(\d{2,4})?", text)
    if m:
        jahr = int(m.group(3)) if m.group(3) else basis.year
        jahr += 2000 if jahr < 100 else 0
        try:
            d = date(jahr, int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
        if not m.group(3) and d < basis:
            d = d.replace(year=d.year + 1)
        return d.isoformat()
    m = re.match(r"^\d{4}-\d{2}-\d{2}$", text.strip())
    if m:
        return text.strip()
    for name, wt in _WOCHENTAGE.items():
        if re.search(rf"\b{name}\b", low):
            return (basis + timedelta(days=(wt - basis.weekday()) % 7)).isoformat()
    return None


H_DAUER_BIS = 8  # wie capture.py: ein nacktes "2h" bis 8 ist eine Dauer


def uhrzeit_aus_text(text: str | None) -> str | None:
    """Erste Uhrzeit, Regeln wie capture._parse_time_str (gekuerzt)."""
    if not text:
        return None
    m = re.search(r"\bhalb\s+(\d{1,2})\b", text, re.I)
    if m:
        return f"{(int(m.group(1)) - 1) % 24:02d}:30"
    m = re.search(r"\b(\d{1,2})[:.](\d{2})\s*(uhr|h)?\b", text, re.I)
    if m and int(m.group(1)) <= 23 and int(m.group(2)) <= 59:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
    for m in re.finditer(r"\b(um\s+)?(\d{1,2})\s*(uhr|h)\b", text, re.I):
        h = int(m.group(2))
        if h > 23 or (m.group(3).lower() == "h" and not m.group(1) and h <= H_DAUER_BIS):
            continue
        return f"{h:02d}:00"
    m = re.search(r"\bum\s+(\d{1,2})(?![:.\d])", text, re.I)
    if m and int(m.group(1)) <= 23:
        return f"{int(m.group(1)):02d}:00"
    return None


def dauer_aus_text(text: str | None) -> int | None:
    """Dauer in Minuten, Regeln wie capture._parse_duration_minutes (gekuerzt)."""
    if not text:
        return None
    m = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(min\w*|std\.?|stunden?|h)(?!\w)", text, re.I)
    if m:
        wert = float(m.group(1).replace(",", "."))
        minuten = round(wert if m.group(2).lower().startswith("min") else wert * 60)
        return minuten or None
    for muster, minuten in ((r"halbe\s+stunde", 30), (r"anderthalb\s+stunden", 90), (r"eine\s+stunde", 60)):
        if re.search(muster, text, re.I):
            return minuten
    return None


def erstes_json(text: str) -> dict | None:
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


def normalisieren(aktion: dict) -> dict:
    """Auch die alte Schachtelung lesen, damit `--ohne-schema` vergleichbar bleibt."""
    if "art" not in aktion and "aktion" in aktion:
        aktion = {**aktion, "art": aktion["aktion"]}
    if "art" not in aktion and len(aktion) == 1:
        (art, felder), = aktion.items()
        if isinstance(felder, dict):
            aktion = {"art": art, **felder}
    a = dict(aktion)
    # Kennung nach Vorsilbe auf das Feld der Erwartung legen.
    ziel = a.get("ziel_id") or ""
    for vorsilbe, feld in (("e-", "termin_id"), ("s-", "sitzung_id"), ("t-", "aufgabe_id")):
        if ziel.startswith(vorsilbe):
            a.setdefault(feld, ziel)
    # Tag, Uhrzeit, Dauer aus dem woertlichen Ausschnitt, nach Regeln.
    text = a.get("ausschnitt")
    a["tag"] = tag_aus_text(text) or tag_aus_text(a.get("tag_text") or a.get("tag"))
    a["von"] = uhrzeit_aus_text(text) or a.get("von")
    a["dauer_min"] = dauer_aus_text(text) or a.get("dauer_min")
    if a.get("art") in ("termin_aendern", "sitzung_verschieben"):
        a["neu_tag"], a["neu_von"] = a["tag"], a["von"]
    return a


def passt(ist: dict, soll: dict) -> list[str]:
    return [f"{k}={ist.get(k)!r} statt {v!r}" for k, v in soll.items() if ist.get(k) != v]


def bewerten(aktionen: list[dict], erwartet: list[dict]) -> list[str]:
    """Leere Liste = richtig. Reihenfolge egal, je Erwartung eine passende Aktion."""
    if [e["art"] for e in erwartet] == ["frage"]:
        aenderungen = [a for a in aktionen if a.get("art") != "frage"]
        return [f"Frage loeste Aenderung aus: {[a.get('art') for a in aenderungen]}"] if aenderungen else []
    if len(aktionen) != len(erwartet):
        return [f"{len(aktionen)} Aktionen statt {len(erwartet)}: {[a.get('art') for a in aktionen]}"]
    fehler: list[str] = []
    rest = list(aktionen)
    for soll in erwartet:
        kandidaten = [a for a in rest if a.get("art") == soll["art"]]
        if not kandidaten:
            fehler.append(f"fehlt {soll['art']}")
            continue
        bester = min(kandidaten, key=lambda a: len(passt(a, soll)))
        fehler += passt(bester, soll)
        rest.remove(bester)
    return fehler


def messen(modell: str, url: str, kopf: dict, mit_schema: bool) -> None:
    print(f"\n== {modell} ({'mit Schema' if mit_schema else 'ohne Schema'}) ==")
    treffer = 0
    zeiten: list[float] = []
    for satz, erwartet in FAELLE:
        rumpf = {
            "model": modell,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"{KONTEXT}\nNachricht: {satz}"},
            ],
            "max_tokens": 800,
            "temperature": 0.1,
            "reasoning_effort": "low",
        }
        if mit_schema:
            rumpf["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "kalender_aktionen", "schema": SCHEMA},
            }
        start = time.monotonic()
        try:
            r = httpx.post(url, headers=kopf, timeout=180, json=rumpf)
            dauer = time.monotonic() - start
        except httpx.HTTPError as e:
            print(f"  FEHLER  {satz[:40]:40}  {type(e).__name__}")
            continue
        if r.status_code != 200:
            print(f"  HTTP {r.status_code} {satz[:40]:40}  {r.text[:160]!r}")
            continue
        zeiten.append(dauer)
        antwort = r.json()
        inhalt = ((antwort.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        obj = erstes_json(inhalt)
        if obj is None:
            print(f"  {dauer:5.1f}s  KEIN JSON  {satz[:40]:40}  {inhalt[:80]!r}")
            continue
        aktionen = [normalisieren(a) for a in obj.get("aktionen") or [] if isinstance(a, dict)]
        fehler = bewerten(aktionen, erwartet)
        treffer += not fehler
        print(f"  {dauer:5.1f}s  {'ok    ' if not fehler else 'FALSCH'}  {satz[:40]:40}  {[a.get('art') for a in aktionen]}")
        if fehler:
            print(f"           {'; '.join(fehler)[:240]}")
    if zeiten:
        zeiten.sort()
        print(f"  -> {treffer}/{len(FAELLE)} richtig, Median {zeiten[len(zeiten) // 2]:.1f}s, langsamste {zeiten[-1]:.1f}s")


def main() -> int:
    basis = os.environ.get("LLM_GATEWAY_URL", "").rstrip("/")
    if not basis:
        print("LLM_GATEWAY_URL fehlt: im Container des kalender-bff aufrufen.")
        return 2
    kopf = {}
    if os.environ.get("LLM_GATEWAY_KEY"):
        kopf["Authorization"] = "Bearer " + os.environ["LLM_GATEWAY_KEY"]
    argumente = [m for m in sys.argv[1:] if m != "-"]
    mit_schema = "--ohne-schema" not in argumente
    modelle = [m for m in argumente if not m.startswith("--")] or ["homelab-smart"]
    fremd = [m for m in modelle if m not in ERLAUBT]
    if fremd:
        print(f"Nicht erlaubt (kein Modell im Haus belegt): {fremd}")
        return 2
    for m in modelle:
        messen(m, basis + "/v1/chat/completions", kopf, mit_schema)
    return 0


if __name__ == "__main__":
    sys.exit(main())
