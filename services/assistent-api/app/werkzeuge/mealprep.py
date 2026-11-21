"""Das Werkzeug fuer MealPrep.

Gleiche Arbeitsteilung wie im Kalender (Vertrag ``kalender-bff/ASSISTENT_VERTRAG.md``):
das Modell versteht, Regeln rechnen. Es liefert je Wunsch eine Aktion mit dem
woertlichen Ausschnitt, einem Rezept- oder Zutatennamen als Text und einer
Kurzkennung (``m-3``) fuer eine Mahlzeit aus dem Kontext. Rezepte stehen NICHT
im Kontext: es sind ueber 200, und das Modell liest auf CPU rund 15 Token/s.
Den Namen loest dieser Dienst gegen den Katalog auf und bietet bis zu drei
Treffer an.

Hier wird nichts geschrieben. Jede Option einer Karte traegt fertige
Operationen fuer ``POST /api/app/abgleich`` (ohne Kennung ``op``, die vergibt
die App). Die App reiht sie nach dem Tipp in ihre Warteschlange ein, genau wie
eine Eingabe von Hand; MealPrep fuehrt jede genau einmal aus.

Zahlen kommen nie vom Modell: der Tagesstand aus ``/api/dashboard``, das
Machbare aus ``/api/swap-candidates`` (der Planer rechnet mit dem Lager),
Naehrwerte eines Nachtrags aus dem Rezept oder aus Zahlen in der Nachricht.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Awaitable, Callable
from datetime import date as _date
from datetime import timedelta
from difflib import SequenceMatcher
from typing import Any

APP = "mealprep"
ZIELGRUPPE = "mealprep-api"

ARTEN = [
    "frage", "tagesstand", "kochbar", "nachtragen", "tauschen", "gegessen",
    "anpinnen", "neu_planen", "ausblenden", "vorliebe",
]

SYSTEM = """Du bist der MealPrep-Assistent. Du aenderst nichts selbst, du machst Vorschlaege, die der Nutzer bestaetigt.
Antworte als JSON nach dem vorgegebenen Schema: "antwort" ist ein kurzer deutscher Satz, "aktionen" eine Liste, je Wunsch genau eine Aktion.

Jede Aktion hat diese Felder (null, wenn nicht zutreffend):
- art: was getan werden soll.
- ausschnitt: der Teil der Nachricht, der zu DIESEM Wunsch gehoert, Wort fuer Wort kopiert, mit Tages- und Mengenangaben. Tage und Zahlen rechnet das Programm daraus, du rechnest nichts.
- titel: Name eines Gerichts, Rezepts oder einer Zutat, so wie der Nutzer ihn nennt.
- ziel_id: Kennung einer Mahlzeit aus der Liste (m-...), wenn eine geplante Mahlzeit gemeint ist.
- urteil (nur vorliebe): "oefter" oder "seltener".

Arten:
- tagesstand: Fragen nach Kalorien, Eiweiss, Makros oder was heute noch fehlt. Zahlen nennst du nie, die rechnet das Programm.
- kochbar: Fragen, was man mit dem Vorrat kochen oder essen kann.
- nachtragen: der Nutzer hat etwas gegessen, das nicht im Plan steht.
- gegessen: eine geplante Mahlzeit (m-...) wurde gegessen.
- tauschen: eine geplante Mahlzeit (m-...) soll ein anderes Gericht werden; titel ist das Wunschgericht oder null.
- anpinnen: eine geplante Mahlzeit soll fest bleiben (oder nicht mehr fest sein).
- neu_planen: ein Tag oder die Woche soll neu geplant werden.
- ausblenden: ein Rezept soll nicht mehr vorgeschlagen werden.
- vorliebe: ein Gericht oefter oder seltener.
- frage: alles andere.

Regeln: Kennungen nur aus der Liste. "Mittag", "Abendessen", "Fruehstueck" meinen die Mahlzeit dieses Namens am genannten Tag, ohne Tag heute. Bezieht sich der Nutzer auf eine fruehere Nachricht, schreibe den ganzen Wunsch neu in den ausschnitt.

Beispiele:
"wie viel Eiweiss fehlt mir noch?" -> tagesstand, ausschnitt "wie viel Eiweiss fehlt mir noch".
"was kann ich heute kochen?" -> kochbar, ausschnitt "was kann ich heute kochen".
"ich hatte mittags einen Doener" -> nachtragen, titel "Doener", ausschnitt "ich hatte mittags einen Doener".
"gestern Abend Pizza, etwa 900 kcal" -> nachtragen, titel "Pizza", ausschnitt "gestern Abend Pizza, etwa 900 kcal".
"Fruehstueck hab ich gegessen" (Fruehstueck heute ist m-1) -> gegessen, ziel_id "m-1".
"tausch das Abendessen gegen Linsensuppe" (Abendessen heute ist m-3) -> tauschen, ziel_id "m-3", titel "Linsensuppe".
"morgen Mittag lieber was anderes" (Mittag morgen ist m-5) -> tauschen, ziel_id "m-5", titel null.
"plane morgen neu" -> neu_planen, ausschnitt "morgen".
"plane die Woche neu" -> neu_planen, ausschnitt "die Woche".
"Rosenkohl-Auflauf will ich nie wieder sehen" -> ausblenden, titel "Rosenkohl-Auflauf".
"Linsencurry gern oefter" -> vorliebe, titel "Linsencurry", urteil "oefter"."""

_N = {"type": ["string", "null"]}
_FELDER = ["art", "ausschnitt", "titel", "ziel_id", "urteil"]
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
                    "urteil": {"type": ["string", "null"], "enum": ["oefter", "seltener", None]},
                },
                # Alles Pflicht: mit optionalen Feldern laesst das Modell unter
                # der Grammatik jedes weg, das es nicht muss (Messung 02.11.).
                "required": _FELDER,
                "additionalProperties": False,
            },
        },
    },
    "required": ["antwort", "aktionen"],
    "additionalProperties": False,
}

#: Holt JSON von MealPrep im Namen des Aufrufers: ``holen("/api/...")``.
Holen = Callable[..., Awaitable[Any]]

_WOCHENTAG = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
_KURZTAG = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
_STATUS = {"eaten": "gegessen", "skipped": "ausgelassen"}


class Verworfen(Exception):
    pass


# ── Text ─────────────────────────────────────────────────────────────────

def norm(text: str) -> str:
    """Kleinschreibung, Umlaute als ae/oe/ue/ss, nur Buchstaben und Ziffern."""
    t = (text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def aehnlichkeit(frage: str, name: str) -> float:
    """0 bis 1. Ein vollstaendig enthaltener Name zaehlt fast wie ein Treffer."""
    f, n = norm(frage), norm(name)
    if not f or not n:
        return 0.0
    if f == n:
        return 1.0
    if f in n or n in f:
        return 0.9 - 0.1 * abs(len(n) - len(f)) / max(len(n), len(f))
    woerter_f, woerter_n = set(f.split()), set(n.split())
    deckung = len(woerter_f & woerter_n) / len(woerter_f)
    return max(SequenceMatcher(None, f, n).ratio(), 0.8 * deckung)


SCHWELLE = 0.6


def treffer(frage: str, eintraege: list[dict], namen: Callable[[dict], list[str]],
            anzahl: int = 3) -> list[dict]:
    bewertet = []
    for e in eintraege:
        wert = max((aehnlichkeit(frage, n) for n in namen(e) if n), default=0.0)
        if wert >= SCHWELLE:
            bewertet.append((wert, e))
    bewertet.sort(key=lambda p: -p[0])
    return [e for _, e in bewertet[:anzahl]]


def rezept_namen(r: dict) -> list[str]:
    return [str(r.get("name") or "")] + [str(a) for a in r.get("aliases") or []]


# ── Tage ─────────────────────────────────────────────────────────────────

def tag_lesen(ausschnitt: str, heute: _date, *, vorwaerts: bool = True) -> _date | None:
    """Ein Tag nach festen Regeln; ``vorwaerts=False`` fuer Gegessenes (Wochentag = letzter)."""
    t = norm(ausschnitt)
    for wort, abstand in (("vorgestern", -2), ("uebermorgen", 2), ("gestern", -1),
                          ("morgen", 1), ("heute", 0)):
        if re.search(rf"\b{wort}\b", t):
            return heute + timedelta(days=abstand)
    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.?", ausschnitt or "")
    if m:
        try:
            tag = _date(heute.year, int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
        if vorwaerts and tag < heute - timedelta(days=180):
            tag = tag.replace(year=heute.year + 1)
        return tag
    for i, name in enumerate(_WOCHENTAG):
        if re.search(rf"\b{norm(name)}\b", t):
            diff = (i - heute.weekday()) % 7
            return heute + timedelta(days=diff) if vorwaerts else heute - timedelta(days=(heute.weekday() - i) % 7)
    return None


def kurz_tag(tag: _date, heute: _date) -> str:
    return {0: "heute", 1: "morgen", -1: "gestern"}.get((tag - heute).days, f"{_KURZTAG[tag.weekday()]} {tag:%d.%m.}")


# ── Kontext ──────────────────────────────────────────────────────────────

def kontext_bauen(stand: dict, heute: _date, jetzt: str) -> tuple[str, dict[str, dict]]:
    """Klartext fuer das Modell und die Zuordnung Kurzkennung -> Mahlzeit.

    Knapp und die Uhrzeit am Ende, aus demselben Grund wie im Kalender: was
    vorn gleich bleibt, holt der Modellwirt aus dem Cache.
    """
    zuordnung: dict[str, dict] = {}
    zeilen = ["Mahlzeiten:"]
    tage = stand.get("days") or [{"date": stand.get("date"), "slots": stand.get("slots") or []}]
    n = 0
    for tag in tage:
        try:
            datum = _date.fromisoformat(str(tag.get("date"))[:10])
        except ValueError:
            continue
        if datum < heute or not tag.get("slots"):
            continue
        zeilen.append(f"{kurz_tag(datum, heute)}:")
        for s in tag["slots"]:
            n += 1
            kurz = f"m-{n}"
            zuordnung[kurz] = {**s, "datum": datum.isoformat()}
            gericht = (s.get("recipe") or {}).get("name") or "nichts geplant"
            merkmale = [_STATUS.get(str(s.get("status")), "")]
            if s.get("pinned"):
                merkmale.append("fest")
            merkmal = ", ".join(m for m in merkmale if m)
            zeilen.append(f"- {kurz} {s.get('slot_label') or s.get('slot_type')}: {gericht}"
                          + (f" ({merkmal})" if merkmal else ""))
    nachtraege = [str(i.get("label") or "") for i in stand.get("adhoc_intakes") or [] if i.get("label")]
    if nachtraege:
        zeilen.append("Heute nachgetragen: " + ", ".join(nachtraege[:10]))
    zeilen.append(f"Heute ist {_WOCHENTAG[heute.weekday()]}, {heute:%d.%m.%Y}, jetzt {jetzt}.")
    return "\n".join(zeilen), zuordnung


# ── Fakten: Regeln statt Modell ──────────────────────────────────────────

def _g(werte: dict | None, feld: str) -> int:
    try:
        return round(float((werte or {}).get(feld) or 0))
    except (TypeError, ValueError):
        return 0


def tagesstand_text(stand: dict) -> str:
    ziel, ist = stand.get("targets") or {}, stand.get("intake_totals") or {}
    zeilen = [
        f"Heute bisher {_g(ist, 'kcal')} von {_g(ziel, 'kcal')} kcal, "
        f"{_g(ist, 'protein_g')} von {_g(ziel, 'protein_g')} g Eiweiß, "
        f"{_g(ist, 'carbs_g')} von {_g(ziel, 'carbs_g')} g Kohlenhydrate, "
        f"{_g(ist, 'fat_g')} von {_g(ziel, 'fat_g')} g Fett."
    ]
    status = stand.get("day_status") or {}
    if status:
        zeilen.append(f"Offen: {_g(status, 'remaining_kcal')} kcal und "
                      f"{_g(status, 'remaining_protein_g')} g Eiweiß.")
        if status.get("message"):
            zeilen.append(str(status["message"]))
    offen = [s for s in stand.get("slots") or [] if s.get("status") != "eaten" and s.get("recipe")]
    if offen:
        zeilen.append("Noch geplant: " + ", ".join(
            f"{s.get('slot_label')} {s['recipe'].get('name')}" for s in offen))
    return "\n".join(zeilen)


_TAGESSTAND = re.compile(
    r"\b(wie ?viel|was fehlt|fehlt|fehlen|noch|stand|bilanz|schon)\b.*"
    r"\b(kcal|kalorien|eiwei\w*|protein|fett|kohlenhydrat\w*|makros?|ziel)\b",
    re.IGNORECASE,
)
_KOCHBAR = re.compile(
    r"\bwas (kann|koennte|könnte|soll) ich\b.*\b(kochen|essen|machen)\b"
    r"|\bmachbar\b|\bmit dem vorrat\b|\baus dem vorrat\b",
    re.IGNORECASE,
)


def frage_regel(nachricht: str) -> str | None:
    """Erkennt die zwei Fragearten an der Nachricht, unabhaengig vom Modell.

    Muster wie ``fragt_nach_freier_zeit`` im Kalender: dort ordnete das
    Modell eine solche Frage als ``frage`` ein und nannte selbst Zahlen.
    """
    if _KOCHBAR.search(nachricht):
        return "kochbar"
    if _TAGESSTAND.search(nachricht):
        return "tagesstand"
    return None


def naechste_offene(stand: dict) -> dict | None:
    """Die naechste noch nicht gegessene Mahlzeit, heute zuerst."""
    for tag in stand.get("days") or [{"slots": stand.get("slots") or []}]:
        for s in tag.get("slots") or []:
            if s.get("status") != "eaten":
                return {**s, "datum": tag.get("date") or stand.get("date")}
    return None


_ZAHL = r"(\d+(?:[.,]\d+)?)"
_NAEHRWERTE = {
    "kcal": re.compile(_ZAHL + r"\s*(?:kcal|kalorien)", re.IGNORECASE),
    "protein_g": re.compile(_ZAHL + r"\s*g\s*(?:eiwei\w*|protein)", re.IGNORECASE),
    "carbs_g": re.compile(_ZAHL + r"\s*g\s*(?:kohlenhydrat\w*|kh)\b", re.IGNORECASE),
    "fat_g": re.compile(_ZAHL + r"\s*g\s*fett", re.IGNORECASE),
}


def naehrwerte_lesen(text: str) -> dict[str, float]:
    werte = {}
    for feld, muster in _NAEHRWERTE.items():
        m = muster.search(text or "")
        if m:
            werte[feld] = float(m.group(1).replace(",", "."))
    return werte


# ── Aus Aktionen werden Karten ───────────────────────────────────────────

def _option(text: str, *ops: dict) -> dict:
    return {"text": text, "daten": {"ops": [{k: v for k, v in op.items() if v is not None} for op in ops]}}


def _mahlzeit_text(slot: dict, heute: _date) -> str:
    gericht = (slot.get("recipe") or {}).get("name")
    tag = kurz_tag(_date.fromisoformat(slot["datum"][:10]), heute)
    return f"{slot.get('slot_label')} {tag}" + (f" ({gericht})" if gericht else "")


class Werkzeug:
    """Haelt den Stand einer Anfrage und laedt Katalog und Kandidaten erst bei Bedarf."""

    def __init__(self, holen: Holen, heute: _date):
        self.holen = holen
        self.heute = heute
        self._katalog: dict | None = None

    async def stand(self) -> dict:
        return await self.holen(f"/api/dashboard/{self.heute.isoformat()}") or {}

    async def katalog(self) -> dict:
        if self._katalog is None:
            self._katalog = await self.holen("/api/app/katalog") or {}
        return self._katalog

    async def rezepte(self, frage: str, *, auch_versteckte: bool = False) -> list[dict]:
        alle = [r for r in (await self.katalog()).get("rezepte") or []
                if auch_versteckte or not r.get("hidden")]
        return treffer(frage, alle, rezept_namen)

    async def kandidaten(self, slot_id: int) -> list[dict]:
        antwort = await self.holen(f"/api/swap-candidates/{slot_id}") or {}
        return antwort.get("recipes") or []

    async def kochbar_text(self, stand: dict) -> tuple[str, dict | None]:
        slot = naechste_offene(stand)
        if slot is None:
            return "Heute ist alles gegessen; geplant ist sonst nichts.", None
        machbar = [r for r in await self.kandidaten(slot["id"]) if r.get("feasible")]
        name = _mahlzeit_text(slot, self.heute)
        if not machbar:
            return (f"Für {name} ist mit dem Vorrat laut Lager gerade nichts machbar. "
                    "Fehlende Zutaten zeigt die Einkaufsliste."), None
        liste = ", ".join(f"{r['name']} ({r.get('cook_time_min') or '?'} min)" for r in machbar[:5])
        karte = {
            "art": "tauschen", "text": f"Tauschen: {name}",
            "optionen": [_option(r["name"], {"art": "tauschen", "slot_id": slot["id"], "recipe_id": r["id"]})
                         for r in machbar[:3]],
            "hinweis": "Ein gewähltes Gericht bleibt fest.",
        }
        return f"Mit dem Vorrat machbar für {name}: {liste}.", karte

    async def karte(self, aktion: dict, zuordnung: dict[str, dict]) -> dict | None:
        art = aktion.get("art")
        ausschnitt = str(aktion.get("ausschnitt") or "").strip()
        titel = str(aktion.get("titel") or "").strip()
        slot = None
        if aktion.get("ziel_id"):
            slot = zuordnung.get(str(aktion["ziel_id"]))
            if slot is None:
                raise Verworfen(f"unbekannte Kennung {aktion['ziel_id']}")

        if art in (None, "frage", "tagesstand", "kochbar"):
            return None

        if art == "nachtragen":
            label = titel or ausschnitt
            if not label:
                raise Verworfen("was gegessen wurde, fehlt")
            tag = tag_lesen(ausschnitt, self.heute, vorwaerts=False) or self.heute
            if tag > self.heute:
                raise Verworfen("Nachtragen geht nur für heute oder früher")
            datum = None if tag == self.heute else tag.isoformat()
            werte = naehrwerte_lesen(ausschnitt)
            optionen = []
            if werte:
                optionen.append(_option(
                    f"{label}: " + ", ".join(f"{round(v)} {_EINHEIT[k]}" for k, v in werte.items()),
                    {"art": "nachtragen", "label": label, "datum": datum, **werte}))
            else:
                for r in await self.rezepte(label, auch_versteckte=True):
                    kcal = _g(r.get("nutrition_per_portion"), "kcal")
                    optionen.append(_option(
                        f"1 Portion {r['name']}" + (f" ({kcal} kcal)" if kcal else ""),
                        {"art": "nachtragen", "recipe_id": r["id"], "datum": datum}))
                optionen.append(_option(f"„{label}“ ohne Nährwerte",
                                        {"art": "nachtragen", "label": label, "datum": datum}))
            return {"art": art, "text": f"Nachtragen {kurz_tag(tag, self.heute)}: {label}",
                    "optionen": optionen,
                    "hinweis": None if werte else
                    "Ohne Nährwerte zählt der Eintrag nicht in die Tagessumme. Nenne kcal in der Nachricht, dann trage ich sie mit ein."}

        if art in ("gegessen", "tauschen", "anpinnen"):
            if slot is None:
                raise Verworfen(f"{art} ohne Mahlzeit aus der Liste")
            name = _mahlzeit_text(slot, self.heute)
            if art != "anpinnen" and slot.get("status") == "eaten":
                raise Verworfen(f"{name} ist schon gegessen")
            if art == "gegessen":
                if not slot.get("recipe"):
                    raise Verworfen(f"für {name} ist nichts geplant, also nachtragen")
                return {"art": art, "text": f"Gegessen: {name}",
                        "optionen": [_option("Als gegessen buchen", {"art": "gegessen", "slot_id": slot["id"]})],
                        "hinweis": "Bucht die Zutaten im Lager ab."}
            if art == "anpinnen":
                loesen = bool(re.search(r"nicht mehr fest|loes|lös|frei ?geben|wieder frei", ausschnitt, re.IGNORECASE))
                return {"art": art, "text": ("Nicht mehr fest: " if loesen else "Festhalten: ") + name,
                        "optionen": [_option("Lösen" if loesen else "Festhalten",
                                             {"art": "anpinnen", "slot_id": slot["id"], "an": not loesen})],
                        "hinweis": None}
            if titel:
                rezepte = await self.rezepte(titel)
                if not rezepte:
                    raise Verworfen(f"kein Rezept passt zu „{titel}“")
                hinweis = "Ob alles im Vorrat ist, prüft der Plan danach."
            else:
                rezepte = [r for r in await self.kandidaten(slot["id"]) if r.get("feasible")][:3]
                if not rezepte:
                    raise Verworfen(f"für {name} ist mit dem Vorrat nichts anderes machbar")
                hinweis = "Vorschläge des Planers, alle mit dem Vorrat machbar."
            return {"art": art, "text": f"Tauschen: {name}",
                    "optionen": [_option(r["name"], {"art": "tauschen", "slot_id": slot["id"], "recipe_id": r["id"]})
                                 for r in rezepte],
                    "hinweis": hinweis + " Ein gewähltes Gericht bleibt fest."}

        if art == "neu_planen":
            if re.search(r"\bwoche\b", norm(ausschnitt)):
                tage = [self.heute + timedelta(days=i) for i in range(7)]
                text = f"Neu planen: {kurz_tag(tage[0], self.heute)} bis {kurz_tag(tage[-1], self.heute)}"
            else:
                tag = tag_lesen(ausschnitt, self.heute) or self.heute
                if tag < self.heute:
                    raise Verworfen("vergangene Tage werden nicht neu geplant")
                tage = [tag]
                text = f"Neu planen: {kurz_tag(tag, self.heute)}"
            return {"art": art, "text": text,
                    "optionen": [_option("Neu planen", *({"art": "neu_planen", "datum": t.isoformat()} for t in tage))],
                    "hinweis": "Auch festgehaltene Mahlzeiten werden neu geplant, nur Gegessenes bleibt."}

        if art == "ausblenden":
            rezepte = await self.rezepte(titel or ausschnitt)
            if not rezepte:
                raise Verworfen(f"kein Rezept passt zu „{titel or ausschnitt}“")
            return {"art": art, "text": "Nicht mehr vorschlagen",
                    "optionen": [_option(r["name"], {"art": "ausblenden", "recipe_id": r["id"], "an": True})
                                 for r in rezepte],
                    "hinweis": "Rückgängig in der Rezeptliste."}

        if art == "vorliebe":
            urteil = aktion.get("urteil")
            if urteil not in ("oefter", "seltener"):
                urteil = "seltener" if re.search(r"selten|weniger|nicht so", ausschnitt, re.IGNORECASE) else "oefter"
            rezepte = await self.rezepte(titel or ausschnitt, auch_versteckte=True)
            if not rezepte:
                zutaten = treffer(titel or ausschnitt, (await self.katalog()).get("zutaten") or [],
                                  lambda z: [str(z.get("name") or "")], anzahl=1)
                if zutaten:
                    raise Verworfen(f"„{zutaten[0]['name']}“ ist eine Zutat; öfter oder seltener geht nur für "
                                    "Gerichte, Zutaten vergleicht das Duell")
                raise Verworfen(f"kein Rezept passt zu „{titel or ausschnitt}“")
            wort = "Öfter" if urteil == "oefter" else "Seltener"
            return {"art": art, "text": f"{wort} vorschlagen",
                    "optionen": [_option(r["name"], {"art": "vorliebe", "ziel": "rezept", "urteil": urteil,
                                                     "a_id": r["id"]}) for r in rezepte],
                    "hinweis": "Fließt in die Vorliebe ein wie eine Antwort nach dem Essen."}

        raise Verworfen(f"unbekannte Art {art}")


_EINHEIT = {"kcal": "kcal", "protein_g": "g Eiweiß", "carbs_g": "g KH", "fat_g": "g Fett"}


def gegenpruefen(aktion: dict, nachricht: str, frueher: list[str]) -> dict:
    """Haelt das Modell an den Wortlaut des Nutzers.

    Gemessen 15.11.: auf „Chili gern öfter" kam ``titel: "Linsencurry"``, aus
    dem Beispiel im Systemtext abgeschrieben, und die Karte haette das falsche
    Gericht angeboten. Ein Titel, von dem kein Wort in der Nachricht oder im
    bisherigen Verlauf des Nutzers steht, faellt weg; gesucht wird dann mit dem
    Ausschnitt. Ebenso ein Ausschnitt, der nicht woertlich in der Nachricht steht.
    """
    aktion = dict(aktion)
    text = norm(nachricht)
    ausschnitt = norm(str(aktion.get("ausschnitt") or ""))
    if ausschnitt and ausschnitt not in text:
        aktion["ausschnitt"] = nachricht
    bezug = set(norm(" ".join([nachricht, *frueher])).split())
    titel = norm(str(aktion.get("titel") or ""))
    if titel and not any(w in bezug for w in titel.split() if len(w) >= 3):
        aktion["titel"] = None
    return aktion


async def beantworten(holen: Holen, heute: _date, jetzt: str, nachricht: str, frage,
                      frueher: list[str] | None = None) -> dict:
    """Der ganze Lauf: Stand holen, Modell fragen (``frage(kontext)``), Karten bauen.

    ``frueher`` sind die bisherigen Nachrichten des Nutzers (fuer Rueckbezuege).
    """
    w = Werkzeug(holen, heute)
    stand = await w.stand()
    try:
        heute = _date.fromisoformat(str(stand.get("date"))[:10])
        w.heute = heute
    except ValueError:
        pass
    kontext, zuordnung = kontext_bauen(stand, heute, jetzt)
    obj = await frage(kontext)

    aktionen = [gegenpruefen(a, nachricht, frueher or [])
                for a in obj.get("aktionen") or [] if isinstance(a, dict)]
    regel = frage_regel(nachricht)
    if regel and not any(a.get("art") not in ("frage", "tagesstand", "kochbar", None) for a in aktionen):
        aktionen = [{"art": regel, "ausschnitt": nachricht}]

    karten: list[dict] = []
    verworfen: list[dict] = []
    fakten: list[str] = []
    for aktion in aktionen:
        art = aktion.get("art")
        try:
            if art == "tagesstand":
                if not any("Heute bisher" in f for f in fakten):
                    fakten.append(tagesstand_text(stand))
                continue
            if art == "kochbar":
                text, karte = await w.kochbar_text(stand)
                fakten.append(text)
            else:
                karte = await w.karte(aktion, zuordnung)
        except Verworfen as v:
            verworfen.append({"art": art, "grund": str(v)})
            continue
        except _AbrufFehler as e:
            verworfen.append({"art": art, "grund": f"MealPrep: {e}"[:200]})
            continue
        if karte:
            karte["id"] = f"k{len(karten) + 1}"
            karten.append(karte)

    antwort = str(obj.get("antwort") or "").strip() or (
        "Hier sind meine Vorschläge." if karten else "Dazu habe ich nichts gefunden."
    )
    if fakten:
        # Der Satz des Modells entfaellt, er koennte Zahlen nennen, die
        # MealPrep nicht kennt. Die Antwort ist die Rechnung selbst.
        antwort = "\n\n".join(fakten) + ("\n\nVorschläge unten." if karten else "")
    return {"antwort": antwort, "karten": karten, "verworfen": verworfen}


class _AbrufFehler(Exception):
    """MealPrep antwortet nicht oder mit einem Fehler."""


AbrufFehler = _AbrufFehler

