"""Briefing-Assembly: aus dem globalen FeedItem-Pool ein personalisiertes,
interessengewichtetes Tages-Briefing bauen.

Deterministischer Kern (Scoring + Diversität + Sektionen), optional durch eine
LLM-Redaktion (Sprech-Intro) veredelt. Alles pro `sub`: Feedback-Modifier und
Präferenzen sind user-privat.

Portierte Mechaniken aus dem alten briefing_lib.py:
- Recency-Decay + Interessen-Gewichte (statt fixer Homelab-Slots).
- Quellen-Cap (max_same_source) + Near-Dup-Filter gegen Themen-Wiederholung.
- Sektions-Struktur: „Top-Themen" + je Interesse eine Sektion.

Das Briefing und der News-Feed arbeiten auf demselben Artikelbestand und teilen
sich deshalb auch dessen Zustand (`UserItemState`, sub-gescoped):
- Was im Feed **gemerkt** wurde, ist das stärkste Interessensignal, das ein Nutzer
  freiwillig gibt: stärker als jedes Häkchen im Onboarding. Es hebt die Gewichte
  der zugehörigen Themen an (`_bookmark_boost`).
- Was im Feed **gelesen** wurde, wird gedämpft statt entfernt. Entfernen wäre falsch:
  wer eine Meldung gelesen hat, will sie am Morgen trotzdem im Überblick haben,
  nur nicht an erster Stelle.
"""
from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..briefing_models import BriefingFeedback, BriefingProfile, UserBriefing
from ..config import settings
from ..models import FeedItem, FeedSource, UserItemState
from . import interest_taxonomy as tax
from . import kalender_client
from . import llm_client
from . import plans
from . import weather as weather_svc

BERLIN = ZoneInfo("Europe/Berlin")

log = structlog.get_logger()

_LENGTH_FACTOR = {"kurz": 0.6, "mittel": 1.0, "lang": 1.5}

# Wie stark gemerkte Artikel die Themengewichte anheben dürfen. Ein Deckel ist
# nötig, sonst kippt das Briefing nach ein paar Wochen in das eine Thema, das man
# am häufigsten merkt, und die Nachrichtenlage verschwindet hinter der Gewohnheit.
_BOOKMARK_MAX_BOOST = 0.6
# Wie viele der jüngsten Bookmarks das Lernen betrachtet.
_BOOKMARK_LOOKBACK = 200
# Dämpfung für Artikel, die im News-Feed schon gelesen wurden.
_READ_PENALTY = 0.55


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _recency_weight(published: datetime | None, now: datetime) -> float:
    """1.0 für frisch, linear abfallend über das Fenster bis 0.3."""
    if not published:
        return 0.5
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    age_h = max(0.0, (now - published).total_seconds() / 3600.0)
    span = max(1.0, float(settings.briefing_window_hours))
    return max(0.3, 1.0 - 0.7 * min(1.0, age_h / span))


# Wörter ohne Themengehalt. Sie kommen in jeder zweiten Schlagzeile vor und
# würden die Ähnlichkeitsmessung in Richtung "alles hängt mit allem zusammen"
# verschieben.
_FUELLWOERTER = frozenset({
    "nach", "ueber", "über", "beim", "eine", "einen", "einer", "eines", "noch",
    "doch", "aber", "auch", "sich", "sein", "ihre", "mehr", "wird", "wurde",
    "will", "kann", "koennen", "können", "soll", "sollen", "ohne", "gegen",
    "schon", "immer", "wieder", "dann", "denn", "dass", "wenn", "weil", "sind",
    "haben", "hatte", "worden", "werden", "diese", "dieser", "dieses", "alle",
    "jetzt", "heute", "laut", "statt", "erst", "einst", "bereits", "neue",
    "neuen", "neues", "mehrere", "weiter", "weitere",
})

# Länge des Wortanfangs, auf den ein Wort für den Vergleich eingekürzt wird.
_KERN_LAENGE = 6


def _kerne(text: str) -> set[str]:
    """Themen-Kerne eines Titels: Wortanfänge fester Länge, ohne Füllwörter.

    Der Wortanfang statt des ganzen Wortes, weil Deutsch Komposita bildet:
    `Notfallmedizin` und `Notfallversorgung` sind dieselbe Nachricht, teilen
    aber kein einziges ganzes Wort. Sechs Zeichen fassen sie zusammen, ohne
    dass dafür ein Wörterbuch oder eine Wortstamm-Bibliothek nötig wäre.
    """
    worte = "".join(c if c.isalnum() else " " for c in text.lower()).split()
    return {w[:_KERN_LAENGE] for w in worte if len(w) > 3 and w not in _FUELLWOERTER}


# Ab welchem Anteil zwei Titel als dieselbe Nachricht gelten.
#
# An den echten Briefings von acht Tagen kalibriert, nicht geschätzt. Die
# vier tatsächlichen Doppelungen in diesem Zeitraum liegen bei 0,33 bis 0,60
# (Character.ai-Insolvenz zweimal, Yandex-Angriff zweimal, Trump/Selenskyj
# zweimal, Notfallreform zweimal); das erste FALSCH zusammengelegte Paar
# folgt erst bei 0,25 ("KI-Partnerschaft mit Nvidia" gegen "Bundesstaaten
# verklagen OpenAI"). 0,30 liegt im Abstand dazwischen.
_DOPPELUNG_AB = 0.30


def _zu_aehnlich(a: set[str], b: set[str], schwelle: float = _DOPPELUNG_AB) -> bool:
    """Trägt der kürzere der beiden Titel dieselbe Nachricht wie der längere?

    Gemessen am KÜRZEREN Titel, nicht an der Vereinigung beider. Das vorige
    Jaccard-Maß (Schnitt durch Vereinigung, Schwelle 0,6) bestrafte
    Längenunterschiede so stark, dass es über acht Tage **keine einzige** der
    vier echten Doppelungen fand: eine knappe Agenturmeldung und eine
    ausführliche Fassung desselben Ereignisses erreichen dort nie 0,6, weil
    die Vereinigung mit jedem Zusatzwort des längeren Titels mitwächst.
    """
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) >= schwelle


# Wie viele Meldungen eines Tages denselben Themen-Kern tragen dürfen.
#
# Die Doppelungsprüfung oben fasst nur zwei Fassungen DERSELBEN Nachricht
# zusammen. Am 15.11. standen drei verschiedene Anthropic-Meldungen im Briefing
# (Börsenwette, IPO, Modellvergleich), am 13.11. drei zu Nvidia: jede für sich
# eine eigene Nachricht, zusammen ein Drittel der Sendezeit für eine Firma.
# Zwei lassen ein großes Thema stehen, die dritte macht Platz für etwas anderes.
_THEMA_MAX = 2


def _thema_voll(kerne: set[str], zaehler: dict[str, int]) -> bool:
    """Trägt der Titel einen Kern, der heute schon `_THEMA_MAX`-mal gewählt wurde?"""
    return any(zaehler.get(k, 0) >= _THEMA_MAX for k in kerne)


# Herkunfts-Markierung am Titelanfang (`heise+ | …`). Sie sagt etwas über die
# Quelle, nichts über den Inhalt, und vorgelesen ist sie Geräusch. Gemessen
# trugen 737 der 39881 Feed-Titel diese Marke.
_QUELLMARKE = re.compile(r"^\s*(?:heise\+|heise online)\s*\|\s*", re.I)


def _titel_saeubern(roh: str) -> str:
    """Titel so, wie er angezeigt UND vorgelesen werden kann.

    Die HTML-Entschlüsselung ist hier kein Schönheitsschritt: die Feeds
    liefern `&amp;` und `&quot;` wörtlich (gemessen 45 Titel im Bestand), und
    der Sprech-Text geht unverändert ins TTS. Ein vorgelesenes
    „Word Ampersand amp Semikolon Co." ist für den Hörer kaputt, während es
    auf dem Bildschirm nur unschön aussieht.
    """
    text = html.unescape(roh or "")
    text = _QUELLMARKE.sub("", text)
    return re.sub(r"\s{2,}", " ", text).strip()


_HTML_TAG = re.compile(r"<[^>]*>")
# Feed-Abspann der Fachpresse: „Der Artikel X erschien zuerst auf the-decoder.de."
_ABSPANN = re.compile(r"\s*Der Artikel\b.*$", re.S)
# Autorenzeile am Ende der tagesschau-Kurztexte: „Von Susanne Henn." oder
# „Von A. B und C. D.". Am 14.11. wurde sie mitvorgelesen.
_AUTORENZEILE = re.compile(
    r"\s*\bVon\s+[A-ZÄÖÜ][\w.\-]*(?:\s+(?:und\s+)?[A-ZÄÖÜ][\w.\-]*){1,5}\.?\s*$"
)


def _zusammenfassung_saeubern(roh: str) -> str:
    """Kurztext ohne HTML, Feed-Abspann und Autorenzeile.

    `_titel_saeubern` löst nur Entities auf, Tags lässt es stehen. DLF und
    the-decoder liefern den Kurztext mit `<img alt="…">` davor; das stand bis
    14.11. wörtlich im Briefing, ging so ans Modell und lieferte der
    Themensuche Wörter aus Bild-Alt-Texten und Adressen („Teresa" traf „esa",
    die Türkei-Demo lief deshalb unter Wissenschaft).
    """
    text = html.unescape(_HTML_TAG.sub(" ", roh or ""))
    text = _ABSPANN.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = _AUTORENZEILE.sub("", text).strip()
    return _titel_saeubern(text)


def _hinter_bezahlschranke(item: FeedItem) -> bool:
    """heise+ ist das einzige im Bestand gemessene Bezahlangebot (14.11.: 879
    Titel mit `heise+`, 880 Links mit `beitrag_plus`, deckungsgleich bis auf
    einen). Vorgelesen ist so eine Meldung eine Überschrift ohne Inhalt, und
    wer sie nachlesen will, steht vor der Schranke."""
    return (item.title or "").lstrip().lower().startswith("heise+") or (
        "beitrag_plus" in (item.link or "")
    )


# Programmhinweis („tagesschau 20:00 Uhr") und Tages-Sammelzeile
# („Mittwoch: KI-Insolvenz …, KI-Vereinfachung …").
_SENDUNGSHINWEIS = re.compile(r"^\S+\s+\d{1,2}:\d{2}\s+Uhr$")
_SAMMELZEILE = re.compile(
    r"^(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag)\s*:", re.I
)


def _ohne_eigene_nachricht(titel: str) -> bool:
    """Trägt dieser Eintrag überhaupt eine Nachricht?

    `tagesschau 20:00 Uhr` stand an fünf von acht gemessenen Tagen im
    Briefing und wurde jeden dieser Morgen mitvorgelesen. Es ist ein
    Programmhinweis auf eine Sendung, kein Artikel: weder gelesen noch gehört
    hat er einen Wert, und im Audio klingt er wie ein abgebrochener Satz
    mitten in den Nachrichten. Die Tages-Sammelzeilen der Fachpresse fallen
    aus demselben Grund weg, zusätzlich doppeln sie Meldungen, die ohnehin
    einzeln im Bestand liegen.
    """
    t = (titel or "").strip()
    return bool(_SENDUNGSHINWEIS.match(t) or _SAMMELZEILE.match(t))


def _interest_weights(profile: BriefingProfile) -> dict[str, float]:
    out: dict[str, float] = {}
    for entry in profile.interests or []:
        tag = entry.get("tag")
        if tag in tax.INTERESTS:
            try:
                out[tag] = max(0.0, float(entry.get("weight", 1.0)))
            except (TypeError, ValueError):
                out[tag] = 1.0
    if not out:  # Fallback: Defaults
        out = {e["tag"]: e["weight"] for e in tax.DEFAULT_INTERESTS}
    return out


def _feedback_map(db: Session, sub: str) -> dict[str, int]:
    rows = db.query(BriefingFeedback).filter(BriefingFeedback.sub == sub).all()
    return {r.item_link: r.signal for r in rows}


def _bookmark_boost(db: Session, sub: str) -> dict[str, float]:
    """Themengewicht-Zuschläge, gelernt aus den Bookmarks desselben Nutzers im News-Feed.

    Rückgabe: tag -> Zuschlag zwischen 0 und `_BOOKMARK_MAX_BOOST`, proportional zum
    Anteil dieses Themas an allen gemerkten Artikeln. Wer jeden zweiten gemerkten
    Artikel über IT-Sicherheit merkt, bekommt dort den halben Maximalzuschlag.

    Bewusst additiv auf die eingestellten Gewichte statt ersetzend: die bewusste
    Auswahl des Nutzers bleibt führend, das Verhalten justiert nach.
    """
    rows = (
        db.query(FeedItem)
        .join(UserItemState, UserItemState.item_id == FeedItem.id)
        .filter(UserItemState.sub == sub, UserItemState.bookmarked.is_(True))
        .order_by(UserItemState.updated_at.desc())
        .limit(_BOOKMARK_LOOKBACK)
        .all()
    )
    if not rows:
        return {}
    counts: dict[str, int] = {}
    for item in rows:
        for tag in tax.match_tags(f"{item.title} {item.summary or ''}"):
            counts[tag] = counts.get(tag, 0) + 1
    if not counts:
        return {}
    total = len(rows)
    return {tag: _BOOKMARK_MAX_BOOST * (n / total) for tag, n in counts.items()}


def _score_item(
    item: FeedItem,
    weights: dict[str, float],
    free_topics: list[str],
    feedback: dict[str, int],
    now: datetime,
    already_read: bool = False,
) -> tuple[float, list[str]]:
    text = f"{item.title} {_zusammenfassung_saeubern(item.summary or '')}"
    matched = tax.match_tags(text)
    ft_hits = tax.free_topic_hits(text, free_topics)

    interest_score = sum(weights.get(t, 0.0) for t in matched)
    # "top"-Gewicht zählt für ALLE Artikel (allgemeine Relevanz), nicht nur getaggte.
    interest_score += weights.get("top", 0.0) * 0.5
    interest_score += 2.0 * len(ft_hits)  # Freitext-Treffer = starkes Signal

    if interest_score <= 0:
        return 0.0, []

    score = interest_score * _recency_weight(item.published_at, now)

    fb = feedback.get(item.link, 0)
    if fb > 0:
        score *= 1.4
    elif fb < 0:
        score *= 0.2  # nicht ganz raus, aber stark gedämpft

    # Im News-Feed schon gelesen → nach hinten, nicht raus (s. Modul-Doku).
    if already_read:
        score *= _READ_PENALTY

    tags = sorted(matched, key=lambda t: weights.get(t, 0.0), reverse=True)
    return score, tags


# Wie viele Vortage ein Thema sperren. Gemessen 08.-14.11.: die Nvidia-Affaere
# stand sechs Tage hintereinander im Briefing, jede Folgemeldung mit 0,40 bis
# 0,50 Ueberlappung zum Vortag. Mit zwei Tagen kommt ein Dauerthema hoechstens
# jeden dritten Tag, eine echte neue Lage verdraengt es nicht auf Dauer.
_VORTAGE = 2


def _vortags_meldungen(db: Session, sub: str, for_date: date) -> tuple[set[str], list[set[str]]]:
    """Links und Titel-Kerne der Briefings derselben Person aus den Vortagen.

    Dieselbe Schwelle wie innerhalb eines Tages (`_DOPPELUNG_AB`): an den
    Briefings vom 08. bis 14.11. lagen alle echten Wiederholungen bei 0,30
    oder darueber, alle verschiedenen Themen darunter (hoechstes 0,29).
    """
    rows = (
        db.query(UserBriefing.content)
        .filter(
            UserBriefing.sub == sub,
            UserBriefing.briefing_date >= for_date - timedelta(days=_VORTAGE),
            UserBriefing.briefing_date < for_date,
        )
        .all()
    )
    links: set[str] = set()
    kerne: list[set[str]] = []
    for (content,) in rows:
        for d in _alle_meldungen(content or {}):
            if d.get("link"):
                links.add(d["link"])
            k = _kerne(d.get("title") or "")
            if k:
                kerne.append(k)
    return links, kerne


def _alle_meldungen(content: dict) -> list[dict]:
    out = list(content.get("top_items") or [])
    for sec in content.get("sections") or []:
        out.extend(sec.get("items") or [])
    return out


def _rubrik(titel: str, tags: list[str], weights: dict[str, float]) -> str | None:
    """Die eine Rubrik einer Meldung: was der TITEL sagt, vor dem Kurztext.

    Vorher landete eine Meldung in der ersten Rubrik, deren Wort irgendwo in
    Titel oder Kurztext stand. „Nvidia-Chef tritt ab, KI-Aktien fahren
    Achterbahn" lief unter Politik, weil im Kurztext „Midterm-Wahlen" stand.
    Bei gleichem Gewicht entscheidet die Reihenfolge im Profil (sorted ist
    stabil, die Gewichte stehen in Profilreihenfolge).
    """
    im_titel = tax.match_tags(_titel_saeubern(titel))
    kandidaten = [t for t in tags if t in im_titel and t in weights] or [
        t for t in tags if t in weights
    ]
    if not kandidaten:
        return None
    reihenfolge = list(weights)
    return sorted(
        kandidaten, key=lambda t: (-weights[t], reihenfolge.index(t))
    )[0]


def assemble(db: Session, profile: BriefingProfile, for_date: date | None = None) -> dict:
    """Baut das content-JSON für genau diesen User. Reiner Lese-Zugriff auf den Pool."""
    now = _utcnow()
    for_date = for_date or now.date()
    weights = _interest_weights(profile)
    # Kostenbremse: Freitext-Themen nur mit voller Rechenzeit; Länge auf das Erlaubte begrenzen.
    plan_feats = plans.features(profile.plan)
    free_topics = (profile.free_topics or []) if plan_feats["custom_topics"] else []
    eff_length = plans.clamp_length(profile.plan, profile.length)
    feedback = _feedback_map(db, profile.sub)
    optout = set(profile.feed_optout or [])

    # Gelerntes aus dem News-Feed: gemerkte Themen anheben (s. Modul-Doku).
    for tag, boost in _bookmark_boost(db, profile.sub).items():
        if tag in weights:
            weights[tag] += boost

    cutoff = now - timedelta(hours=settings.briefing_window_hours)
    # LEFT JOIN auf den eigenen Feed-Zustand: dasselbe „gelesen/gemerkt", das der
    # News-Feed führt, ein Artikel hat in beiden Ansichten denselben Zustand.
    rows = (
        db.query(FeedItem, FeedSource, UserItemState)
        .join(FeedSource, FeedSource.id == FeedItem.source_id)
        .outerjoin(
            UserItemState,
            and_(UserItemState.item_id == FeedItem.id, UserItemState.sub == profile.sub),
        )
        .filter(FeedItem.fetched_at >= cutoff)
        .all()
    )

    scored: list[tuple[float, list[str], FeedItem, FeedSource, UserItemState | None]] = []
    for item, src, state in rows:
        if src.slug in optout:
            continue
        s, tags = _score_item(
            item, weights, free_topics, feedback, now,
            already_read=bool(state and state.read),
        )
        if s > 0:
            scored.append((s, tags, item, src, state))
    scored.sort(key=lambda x: x[0], reverse=True)
    vortag_links, vortag_kerne = _vortags_meldungen(db, profile.sub, for_date)

    max_items = max(4, round(settings.briefing_max_items * _LENGTH_FACTOR.get(eff_length, 1.0)))
    per_source: dict[str, int] = {}
    picked_tokens: list[set[str]] = []
    thema_zaehler: dict[str, int] = {}
    selected: list[tuple[float, list[str], FeedItem, FeedSource, UserItemState | None]] = []
    for entry in scored:
        _s, _tags, item, src, _state = entry
        if per_source.get(src.slug, 0) >= settings.briefing_max_same_source:
            continue
        if _hinter_bezahlschranke(item) or item.link in vortag_links:
            continue
        titel = _titel_saeubern(item.title)
        if _ohne_eigene_nachricht(titel):
            continue
        toks = _kerne(titel)
        if any(_zu_aehnlich(toks, pt) for pt in picked_tokens):
            continue
        if any(_zu_aehnlich(toks, vk) for vk in vortag_kerne):
            continue
        if _thema_voll(toks, thema_zaehler):
            continue
        selected.append(entry)
        per_source[src.slug] = per_source.get(src.slug, 0) + 1
        picked_tokens.append(toks)
        for k in toks:
            thema_zaehler[k] = thema_zaehler.get(k, 0) + 1
        if len(selected) >= max_items:
            break

    # Sektionen: „Top-Themen" (die 3 höchsten) + je dominantem Interesse eine Sektion.
    def _item_dict(
        item: FeedItem, src: FeedSource, tags: list[str], state: UserItemState | None
    ) -> dict:
        return {
            # Die id ist der Griff, mit dem das Frontend denselben Artikel im
            # News-Feed anfassen kann (POST /api/news/items/{id}/state). Ohne sie
            # wären Briefing und Feed zwei Listen über denselben Bestand ohne
            # gemeinsame Handhabe.
            "id": item.id,
            # Gesäubert an EINER Stelle, damit Anzeige und Sprech-Text denselben
            # Titel führen. Säuberte nur der Sprech-Pfad, stünde im Briefing auf
            # dem Bildschirm etwas anderes als im Audio.
            "title": _titel_saeubern(item.title),
            "link": item.link,
            "source": src.name,
            "source_slug": src.slug,
            "summary": _zusammenfassung_saeubern(item.summary or "")[:600],
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "tags": tags,
            "read": bool(state and state.read),
            "bookmarked": bool(state and state.bookmarked),
        }

    top_n = 3 if eff_length != "kurz" else 2
    top_items = [_item_dict(i, s, t, st) for (_sc, t, i, s, st) in selected[:top_n]]
    used_links = {d["link"] for d in top_items}

    sections: list[dict] = []
    ordered_tags = sorted(weights, key=lambda t: weights[t], reverse=True)
    rubrik = {i.link: _rubrik(i.title, t, weights) for (_sc, t, i, _s, _st) in selected}
    for tag in ordered_tags:
        if tag == "top":
            continue
        bucket = [
            _item_dict(i, s, t, st)
            for (_sc, t, i, s, st) in selected
            if rubrik.get(i.link) == tag and i.link not in used_links
        ]
        if bucket:
            sections.append({"tag": tag, "label": tax.label_for(tag), "items": bucket})
            used_links.update(d["link"] for d in bucket)

    # Rest-Artikel (getaggt, aber Interesse nicht in Sektion oben) → „Weiteres".
    rest = [
        _item_dict(i, s, t, st)
        for (_sc, t, i, s, st) in selected
        if i.link not in used_links
    ]
    if rest:
        sections.append({"tag": "weiteres", "label": "Weiteres", "items": rest})

    # „Dein Tag": Tagestyp + Termine + Ziele + geplante Lern-Sessions (Soft-Fail None).
    day = kalender_client.fetch_day_context(profile.sub, for_date)
    # Wetter für den Ort des Nutzers (Soft-Fail None, kein Wetter, kein Drama).
    weather = weather_svc.today(profile, for_date)
    spoken_text = _build_spoken_text(
        top_items, sections, for_date, day=day, now=now, weather=weather
    )

    return {
        "date": for_date.isoformat(),
        "generated_at": now.isoformat(),
        "day": day,
        "weather": weather,
        "top_story": top_items[0] if top_items else None,
        "top_items": top_items,
        "sections": sections,
        "item_count": len(selected),
        "spoken_text": spoken_text,
    }


def _greeting(now: datetime | None) -> str:
    """Tageszeit-abhängige Begrüßung (nach Berlin-Ortszeit)."""
    hour = now.astimezone(BERLIN).hour if now else 8
    if 5 <= hour < 11:
        return "Guten Morgen."
    if 11 <= hour < 17:
        return "Guten Tag."
    if 17 <= hour < 22:
        return "Guten Abend."
    return "Hallo."


def _closing(now: datetime | None) -> str:
    hour = now.astimezone(BERLIN).hour if now else 8
    return "Einen schönen Abend." if 17 <= hour < 23 else "Einen guten Tag."


_DAYTYPE_FRAME = {
    "arbeit": "Heute ist ein Arbeitstag.",
    "schule": "Heute ist ein Schultag.",
    "urlaub": "Heute hast du Urlaub.",
    "feiertag": "Heute ist ein Feiertag.",
    "frei": "Heute ist ein freier Tag.",
    "wochenende": "Heute ist Wochenende.",
}

_DAYTYPE_TOMORROW = {
    "arbeit": "Morgen ist ein Arbeitstag.",
    "schule": "Morgen ist ein Schultag.",
    "urlaub": "Morgen hast du Urlaub.",
    "feiertag": "Morgen ist ein Feiertag.",
    "frei": "Morgen ist ein freier Tag.",
    "wochenende": "Morgen ist Wochenende.",
}


def _event_time(iso: str | None, all_day: bool) -> str:
    """HH:MM aus ISO-Start; Events liegen naiv Berlin-Wanduhr (bzw. tz-aware→Berlin)."""
    if all_day:
        return "ganztägig"
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is not None:
            dt = dt.astimezone(BERLIN)
        return dt.strftime("%H:%M Uhr")
    except ValueError:
        return iso[11:16] if len(iso) >= 16 else ""


def _session_groups(sessions: list[dict]) -> list[dict]:
    """Gleichnamige Lern-/Habit-Blöcke zusammenfassen, früheste Startzeit voran.

    Der Habit-Scheduler legt denselben Block gern mehrfach am Tag an (2× „Lernen
    für CompTIA"). Ungruppiert liest sich das wie ein Stotterer, nur den Namen zu
    nennen verschweigt die Uhrzeit: beides zusammen ist die brauchbare Auskunft.
    """
    groups: dict[str, dict] = {}
    for s in sessions:
        title = s.get("title")
        if not title:
            continue
        g = groups.setdefault(title, {"title": title, "count": 0, "start": None})
        g["count"] += 1
        start = s.get("start")
        if start and (g["start"] is None or start < g["start"]):
            g["start"] = start
    return sorted(groups.values(), key=lambda g: g["start"] or "")


def _ohne_klammer(titel: str | None) -> str:
    """Klammerzusatz aus einem Termintitel: „Probepruefung: Lagerlogistik
    (Lernstufe, IHK-Modus)" oder „Weg nach Hause (Zuhause)". Vorgelesen ist
    das ein Nachsatz ohne Auskunft; auf dem Bildschirm bleibt der volle Titel."""
    return re.sub(r"\s*\([^)]*\)", "", titel or "").strip()


def _day_passage(day: dict | None) -> list[str]:
    """Sprech-Zeilen für „Dein Tag": Tagestyp + Termine + Lern-Routine + Ziele + Ausblick."""
    if not day:
        return []
    lines: list[str] = []
    frame = _DAYTYPE_FRAME.get(day.get("day_type") or "")
    if frame:
        lines.append(frame)
    events = day.get("events") or []
    if events:
        parts = []
        for e in events[:3]:
            t = _event_time(e.get("start"), e.get("all_day", False))
            title = _ohne_klammer(e.get("title")) or "Termin"
            parts.append(f"{t}: {title}" if t and t != "ganztägig" else title)
        lines.append("Deine Termine: " + "; ".join(parts) + ".")
    groups = _session_groups(day.get("sessions") or [])
    if groups:
        parts = []
        for g in groups[:4]:
            t = _event_time(g["start"], False)
            wie_oft = f" ({g['count']} Blöcke)" if g["count"] > 1 else ""
            parts.append(f"{t} {g['title']}{wie_oft}" if t else f"{g['title']}{wie_oft}")
        lines.append("Für heute geplant: " + ", ".join(parts) + ".")
    goals = day.get("goals") or []
    if goals:
        gt = [g.get("title") for g in goals[:3] if g.get("title")]
        if gt:
            lines.append("Deine Tagesziele: " + ", ".join(gt) + ".")
    lines.extend(_tomorrow_passage(day.get("tomorrow")))
    return lines


def _tomorrow_passage(tomorrow: dict | None) -> list[str]:
    """Ein bis zwei Sätze Ausblick, der Grund, ein Briefing abends zu hören."""
    if not tomorrow:
        return []
    lines: list[str] = []
    frame = _DAYTYPE_TOMORROW.get(tomorrow.get("day_type") or "")
    if frame:
        lines.append(frame)
    events = tomorrow.get("events") or []
    if events:
        first = events[0]
        t = _event_time(first.get("start"), first.get("all_day", False))
        title = _ohne_klammer(first.get("title")) or "ein Termin"
        rest = len(events) - 1
        weitere = f" und {rest} weitere{'r' if rest == 1 else ''} Termin{'e' if rest > 1 else ''}" if rest > 0 else ""
        if t and t != "ganztägig":
            lines.append(f"Morgen um {t.replace(' Uhr', '')} Uhr: {title}{weitere}.")
        else:
            lines.append(f"Morgen ganztägig: {title}{weitere}.")
    return lines


# Satzzeichen, die einen Titel schon abschliessen.
_SATZENDE = (".", "?", "!", ":", ";")


# Sendungs- und Kolumnennamen vor dem eigentlichen Titel. Auf dem Bildschirm
# sagen sie, woher ein Beitrag kommt; vorgelesen klingt „Europamagazin: Ein
# Aufschwung …" (15.11.) wie der Anfang einer Nachricht über ein Magazin.
_SENDUNGSMARKE = re.compile(
    r"^\s*(?:Europamagazin|Weltspiegel|Bericht aus Berlin|Tagesthemen|"
    r"Bit-Rauschen|Liveblog|Podcast)\s*:\s*",
    re.I,
)
# Dachzeile der Agenturtitel: „Raffineriekrise - SPD forderte …". Der Bindestrich
# mit Leerzeichen ist kein Gedankenstrich im Sinne von `_GEDANKENSTRICH`, das TTS
# liest ihn je nach Stimme als Pause oder gar nicht. Ein Doppelpunkt trägt die
# Pause an der richtigen Stelle. Nur bis vier Worte vorne („Nach Einigung für
# 2027 - …"), sonst trifft es einen Strich mitten im Satz.
_DACHWORT = r"(?!-(?:\s|$))[^\s:]+"
_DACHZEILE = re.compile(rf"^((?:{_DACHWORT}\s){{0,3}}{_DACHWORT})\s+-\s+")


def _als_satz(titel: str) -> str:
    """Eine Schlagzeile als vorlesbarer Satz.

    Zwei Dinge, die beim Vorlesen auffallen und auf dem Bildschirm nicht:

    Ein Titel, der auf ein Satzzeichen endet, bekommt keinen Punkt mehr
    dazu. Sonst entsteht `... selbst replizieren?.`, am 15.10. genau so im
    Briefing und im Audio. Das TTS liest die Doppelung als zwei Pausen und
    verschluckt die Frageintonation.

    Das kaufmaennische Und wird ausgeschrieben. Es steht in Titeln wie
    `Photoshop, Word & Co.`; vorgelesen wird daraus je nach Stimme nichts
    oder ein Buchstabenname, nie „und".
    """
    text = (titel or "").strip()
    if not text:
        return ""
    text = _SENDUNGSMARKE.sub("", text)
    text = _DACHZEILE.sub(r"\1: ", text, count=1)
    text = re.sub(r"\s*&\s*", " und ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text if text.endswith(_SATZENDE) else f"{text}."


def _build_spoken_text(
    top_items: list[dict],
    sections: list[dict],
    for_date: date,
    day: dict | None = None,
    now: datetime | None = None,
    weather: dict | None = None,
) -> str:
    """Deterministischer Sprech-Baseline-Text (schnell, kein LLM).

    Wird in assemble() gesetzt, damit /today nie auf das (CPU-langsame) LLM wartet.
    Beginnt tageszeit-abhängig, dann Wetter, dann „Dein Tag" (Termine/Lern-Routine),
    dann die News. Die redaktionelle LLM-Fassung entsteht später im Audio-Pfad via
    spoken_narration().
    """
    datum = for_date.strftime("%d.%m.%Y")
    lines = [f"{_greeting(now)} Hier ist dein Briefing für den {datum}."]
    wetter_satz = weather_svc.spoken(weather)
    if wetter_satz:
        lines.append(wetter_satz)
    lines.extend(_day_passage(day))
    if top_items:
        lines.append("Die wichtigsten Themen:")
        for d in top_items:
            lines.append(_als_satz(d["title"]))
    for sec in sections:
        if sec["tag"] == "weiteres":
            continue
        lines.append(f"Aus dem Bereich {sec['label']}:")
        for d in sec["items"][:3]:
            lines.append(_als_satz(d["title"]))
    lines.append("Das war dein Briefing. " + _closing(now))
    # Auch der deterministische Pfad läuft durch die Strich-Bereinigung.
    # Sie stand bis hierher NUR im LLM-Pfad (`_clean_narration`), also genau in
    # dem Zweig, der an einem Tag mit langsamem Modell nie ausgeliefert wird:
    # 874 Feed-Titel im Bestand tragen einen en/em dash, und sobald einer davon
    # ausgewählt wird, steht er im Vorlese-Text. Dass das in acht gemessenen
    # Tagen nicht passierte, war Zufall der Auswahl, keine Absicherung.
    return _ohne_gedankenstrich(" ".join(lines))


def _quellen_kerne(content: dict) -> set[str]:
    """Alles, was dem Modell als Tatsache vorgelegt wurde, als Wort-Kerne."""
    kerne: set[str] = set()
    for d in content.get("top_items", []):
        kerne |= _kerne(d.get("title") or "")
        kerne |= _kerne(d.get("summary") or "")
    for sec in content.get("sections", []):
        for d in sec.get("items", []):
            kerne |= _kerne(d.get("title") or "")
            kerne |= _kerne(d.get("summary") or "")
    for zeile in _day_passage(content.get("day")):
        kerne |= _kerne(zeile)
    kerne |= _kerne(weather_svc.spoken(content.get("weather")))
    return kerne


# Wörter, mit denen eine Erzählung Sätze verbindet, ohne eine Tatsache zu
# behaupten. Sie dürfen in der Sprachfassung stehen, ohne in der Quelle
# vorzukommen, sonst schlüge die Treueprüfung schon beim Umformulieren an.
_ERZAEHLWORTE = frozenset({
    "guten", "morgen", "briefi", "hier", "deinem", "deine", "dein", "themen",
    "bereic", "bereich", "dazu", "danach", "ausser", "zudem", "parall",
    "gleich", "schlie", "waehre", "dabei", "darueb", "einem", "seine",
    "ihrem", "wurden", "gibt", "steht", "stehen", "kommt", "geht", "macht",
    "sagte", "sagt", "berich", "meldun", "nachri", "tages", "freier", "frei",
    "geplan", "grad", "wetter", "oktobe", "januar", "februa", "maerz", "april",
    "juni", "juli", "august", "septem", "novemb", "dezemb", "jahr", "zukun",
    "fragen", "lage", "ihnen", "jedoch", "wichti", "klare", "grosse",
    "grosser", "grossem", "derzei", "herrsc", "stellt", "stellen", "eigene",
    "eigenes", "kuenst", "intell", "wissen", "gesund", "politi", "wirtsc",
})

# Ab welchem Anteil erfundener Inhaltswörter die Sprachfassung verworfen wird.
#
# Am 15.10.-Briefing gegen beide verfügbaren lokalen Modelle gemessen, nicht
# geschätzt: der deterministische Text liegt bei 5,5 % (und das sind allein die
# Sektions-Überschriften), die Fassung des 4B auf node2 bei 52,8 %, die des 4B
# auf `.16` bei 42,4 %. Darin standen Sätze wie „der Bundestag hat sich auf
# eine Reform geeinigt" (die Schlagzeile sagt: er stimmt erst darüber ab) und
# frei erfundene Begründungen („um die Versorgungslücken zu schließen"). 25 %
# hat zu beiden Seiten großen Abstand.
_ERFUNDEN_MAX = 0.25


def erfundener_anteil(text: str, content: dict) -> float:
    """Anteil der Inhaltswörter einer Sprachfassung, die in keiner Quelle stehen."""
    worte = _kerne(text) - _ERZAEHLWORTE
    if not worte:
        return 0.0
    return len(worte - _quellen_kerne(content)) / len(worte)


# „X will belegt haben", „soll gesagt haben": die Quelle gibt eine Behauptung
# wieder. Erfasst wird das Partizip davor.
_BEHAUPTUNG = re.compile(
    r"\b(?:will|wollen|soll|sollen)\b(?:\s+\S+){0,8}?\s+(\w{4,})\s+haben\b"
)
# Woran man in der Sprachfassung erkennt, dass die Behauptung als solche
# stehen blieb. Kleingeschrieben und ohne IGNORECASE: „Will DePue" ist ein
# Name, „will" das Modalverb.
_VORBEHALT = re.compile(
    r"\b(?:will|wollen|soll|sollen|(?i:angeblich|laut|behauptet|behaupten|"
    r"nach eigenen Angaben|eigenen Angaben zufolge|nach Angaben))\b"
)


def behauptung_verloren(text: str, content: dict) -> list[str]:
    """Partizipien, die in der Quelle als Behauptung stehen und in der
    Sprachfassung als Tatsache.

    Gemessen am 14.11.: die Quelle schrieb „Will DePue will erstmals
    technisch belegt haben", vorgelesen wurde „hat erstmals technisch
    belegt". Die Wortpruefung (`erfundener_anteil`) sieht das nicht, weil
    jedes Wort der Sprachfassung in der Quelle steht; verloren ging nur das
    eine Modalverb, und mit ihm die ganze Aussage.
    """
    partizipien: set[str] = set()
    for d in _alle_meldungen(content):
        for feld in (d.get("title") or "", d.get("summary") or ""):
            partizipien.update(m.lower() for m in _BEHAUPTUNG.findall(feld))
    if not partizipien:
        return []
    verloren: list[str] = []
    for satz in re.split(r"(?<=[.!?])\s+", text):
        worte = {w.lower() for w in re.findall(r"\w+", satz)}
        for p in partizipien & worte:
            if not _VORBEHALT.search(satz):
                verloren.append(p)
    return sorted(set(verloren))


def spoken_narration(content: dict) -> tuple[str, str]:
    """Liefert den Text, der vertont wird, UND woher er kommt.

    Rückgabe `(text, herkunft)` mit herkunft aus `llm`, `llm_ausweich`, `deterministisch`,
    `deterministisch_llm_stumm`, `deterministisch_llm_unbrauchbar`,
    `deterministisch_llm_behauptung` oder `deterministisch_llm_erfand`.

    Die Herkunft ist Teil des Ergebnisses und nicht nur ein Logeintrag.
    Vorher gab diese Funktion allein den Text zurück, und der Rückfall auf die
    deterministische Fassung war von außen nicht zu erkennen: gespeichert wurde
    nur `spoken_text` (immer die Baseline), vertont wurde etwas anderes, und
    welche der beiden Fassungen der Hörer am Morgen bekam, stand nirgends. Am
    16.10. fiel der Dienst in den Timeout des Modells und lieferte die
    nüchterne Liste, ohne dass das irgendwo sichtbar wurde.

    Latenz-/Kosten-relevant, also NICHT im /today-Request nutzen.
    """
    baseline = content.get("spoken_text", "")
    headlines: list[str] = []
    for d in content.get("top_items", []):
        headlines.append(_quellzeile(d))
    for sec in content.get("sections", []):
        if sec.get("tag") == "weiteres":
            continue
        for d in sec.get("items", [])[:3]:
            headlines.append(_quellzeile(d))
    if not headlines:
        return baseline, "deterministisch"

    try:
        datum = date.fromisoformat(content["date"]).strftime("%d.%m.%Y")
    except (KeyError, ValueError):
        datum = ""
    day_lines = _day_passage(content.get("day"))
    day_block = ("\n\nPersönlicher Tagesplan (Termine/Zeiten und Routine WÖRTLICH und "
                 "unverändert übernehmen, nicht erfinden):\n" + "\n".join(day_lines)) if day_lines else ""
    wetter_satz = weather_svc.spoken(content.get("weather"))
    weather_block = ("\n\nWetter (Zahlen WÖRTLICH übernehmen, nichts dazuerfinden):\n"
                     + wetter_satz) if wetter_satz else ""
    if not llm_client.gateway_lebt():
        return baseline, "deterministisch_llm_stumm"
    system = (
        "Du bist ein Nachrichten-Sprecher für ein persönliches Briefing zum Anhören. "
        "Formuliere einen flüssigen gesprochenen Text auf Deutsch. "
        "WICHTIGE REGELN: Antworte AUSSCHLIESSLICH mit dem Sprech-Text selbst. KEINE "
        "Einleitung wie 'Hier ist...', KEINE Nummerierung, KEINE Aufzählungszeichen, KEINE "
        "Klammer-Quellen, KEINE Sprecher-Vorstellung ('mein Name ist …') und NIEMALS "
        "Platzhalter in eckigen Klammern. Sprich den Hörer mit DU an, nicht mit Sie. "
        "Beginne mit einer kurzen Begrüßung samt Datum (nenne KEINEN "
        "Wochentag, nur das Datum). Nenne danach, falls gegeben, kurz das Wetter "
        "(Temperaturen exakt übernehmen). Falls ein persönlicher Tagesplan gegeben ist, nenne "
        "danach kurz die Termine und die geplante Routine (Uhrzeiten exakt übernehmen) und, "
        "falls ein Ausblick auf morgen dabei steht, auch diesen: er ist Teil des Tagesplans "
        "und darf nicht wegfallen. Dann die wichtigsten Nachrichten in ganzen Sätzen, "
        "thematisch gruppiert. Ca. 200 Wörter. Benutze keine langen Gedankenstriche, "
        "sondern Komma, Doppelpunkt oder Punkt. "
        # Der harte Teil. Er steht hier UND wird nachgemessen, weil eine
        # Bitte im Prompt keine Zusicherung ist: beide lokalen Modelle
        # erfanden am Messtag Gründe, Ergebnisse und Zeitformen dazu.
        "ENTSCHEIDEND: Du darfst NUR das wiedergeben, was in den Meldungen steht. "
        "Erfinde keine Gründe, keine Folgen, keine Zahlen und keine Ergebnisse. "
        "Wandle KEINE geplante Sache in eine beschlossene um: steht 'stimmt ab', "
        "dann ist nichts entschieden. Eine Behauptung bleibt eine Behauptung: "
        "steht 'will belegt haben' oder 'soll', dann schreibe 'will' oder 'soll' "
        "bzw. 'laut', nie 'hat belegt'. Weißt du zu einer Meldung nichts weiter, "
        "nenne sie knapp in einem Satz."
    )
    # Mit der Zusammenfassung, nicht nur mit dem Titel. Gemessen sinkt der
    # Anteil erfundener Inhalte dadurch von 63,9 auf 52,8 Prozent: ein
    # Modell, das aus sieben Wörtern Überschrift einen Absatz machen soll,
    # MUSS den Rest ergänzen. Es behebt das Erfinden nicht, deshalb bleibt
    # die Nachmessung darunter.
    user = (f"Datum: {datum}{weather_block}{day_block}\n\nMeldungen:\n"
            + "\n".join(headlines[:14]))
    llm = llm_client.chat(system=system, user=user, max_tokens=600)
    if llm:
        return _narration_pruefen(llm, content, baseline, "llm")
    # Zweites Modell auf einem anderen Wirt. Es durchläuft dieselben Prüfungen
    # und trägt eine eigene Herkunft, damit sichtbar bleibt, an wie vielen Tagen
    # das Hauptmodell ausfiel.
    log.warning("briefing.narration.ausweich", modell=settings.llm_model_ausweich)
    llm = llm_client.chat(system=system, user=user, max_tokens=600,
                          model=settings.llm_model_ausweich,
                          timeout=settings.llm_ausweich_timeout)
    if llm:
        return _narration_pruefen(llm, content, baseline, "llm_ausweich")
    return baseline, "deterministisch_llm_stumm"


def _narration_pruefen(llm: str, content: dict, baseline: str, herkunft: str) -> tuple[str, str]:
    """Die Prüfungen jeder Modellfassung; bei Befund die Baseline."""
    cleaned = _ensure_greeting(_clean_narration(llm), content)
    # Fail-safe: lieber der schlichte, korrekte Baseline-Text als eine Sprachfassung
    # mit Platzhaltern. Das kleine lokale Modell produziert gelegentlich Vorspann wie
    # „mein Name ist [Dein Name]": vorgelesen ist das schlimmer als nüchtern.
    if _narration_is_broken(cleaned):
        return baseline, "deterministisch_llm_unbrauchbar"
    verloren = behauptung_verloren(cleaned, content)
    if verloren:
        log.warning("briefing.narration.behauptung_als_tatsache", worte=verloren)
        return baseline, "deterministisch_llm_behauptung"
    anteil = erfundener_anteil(cleaned, content)
    if anteil > _ERFUNDEN_MAX:
        log.warning("briefing.narration.erfunden", anteil=round(anteil, 3),
                    grenze=_ERFUNDEN_MAX)
        return baseline, "deterministisch_llm_erfand"
    return cleaned, herkunft


def _quellzeile(d: dict) -> str:
    """Eine Meldung fürs Modell: Titel, Quelle und die Zusammenfassung."""
    kopf = f"- {d.get('title') or ''} ({d.get('source', '')})"
    zusammenfassung = (d.get("summary") or "").strip()
    if not zusammenfassung:
        return kopf
    return f"{kopf}\n  {zusammenfassung[:300]}"


# Muster, die eine Sprachfassung unbrauchbar machen (Vorlesetext!).
_BROKEN_NARRATION = (
    re.compile(r"\[[^\]]{1,40}\]"),            # [Dein Name], [Ort], …
    re.compile(r"mein name ist", re.I),
    re.compile(r"\b(ich (bin|heiße)|sprecher(in)?:)", re.I),
)


def _narration_is_broken(text: str) -> bool:
    if not text or len(text) < 80:
        return True
    return any(p.search(text) for p in _BROKEN_NARRATION)


# Das kleine Modell echot gelegentlich die Prompt-Beschriftungen mit ("Datum: 16.08.2026 …").
# Vorgelesen klingt das wie ein Formular, deshalb am Textanfang entfernen.
_LABEL_ECHO = re.compile(
    r"^\s*(datum|wetter|schlagzeilen|persönlicher tagesplan|tagesplan)\s*:\s*", re.I
)
_GREETINGS = ("guten morgen", "guten tag", "guten abend", "hallo", "moin")
_FREMDE_BEGRUESSUNG = re.compile(
    r"^(?:guten\s+(?:morgen|tag|abend)|hallo|moin)\b[\s,.!]*", re.I
)


def _ensure_greeting(text: str, content: dict) -> str:
    """Label-Echo abschneiden und sicherstellen, dass der Text mit einer Begrüßung
    beginnt, sonst startet das Audio mitten im Wetterbericht."""
    if not text:
        return text
    previous = None
    while previous != text:  # mehrere Labels hintereinander abtragen
        previous = text
        text = _LABEL_ECHO.sub("", text, count=1)
        # Ein nach dem Label übriggebliebenes nacktes Datum ebenfalls weg.
        text = re.sub(r"^\s*\d{1,2}\.\d{1,2}\.\d{4}\s*[.,]?\s*", "", text, count=1)
    text = text.strip()
    # Die Begruessung des Modells wird ersetzt, nicht nur ergaenzt: am 13.11.
    # sagte es um 06:13 „Hallo", am 14.11. um 07:13 „Guten Tag". Die Uhrzeit
    # kennt der Dienst, das Modell nicht.
    text = _FREMDE_BEGRUESSUNG.sub("", text, count=1).strip()
    if text[:1].islower():
        text = text[:1].upper() + text[1:]
    try:
        now = datetime.fromisoformat(content.get("generated_at", ""))
    except (TypeError, ValueError):
        now = None
    return f"{_greeting(now)} {text}".strip()


# Lange Gedankenstriche (en/em dash) sollen weder im angezeigten noch im
# vorgelesenen Briefing vorkommen. Die Bitte im System-Prompt allein genuegt
# dafuer nicht: ein Modell haelt sich daran oder eben nicht, und niemand merkt
# es, weil der Text jeden Tag neu entsteht. Deshalb hier die Durchsetzung.
# Vorgelesen ist der Strich ohnehin nichts, das TTS macht daraus bestenfalls
# eine Pause an einer Stelle, an der ein Komma die richtige Pause waere.
_GEDANKENSTRICH = re.compile("\\s*[\u2013\u2014]\\s*")


def _ohne_gedankenstrich(line: str) -> str:
    """Ersetzt lange Striche durch Komma und raeumt die dabei moegliche
    Doppel-Interpunktion auf (", ." oder ", ,")."""
    line = _GEDANKENSTRICH.sub(", ", line)
    line = re.sub(r",\s*([,.;:!?])", r"\1", line)
    return re.sub(r"\s{2,}", " ", line).strip()


def _clean_narration(text: str) -> str:
    """Entfernt typische Kleinmodell-Artefakte (Meta-Vorspann, Listen-Marker), damit
    das TTS sauberen Fließtext vorliest."""
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Listen-Marker am Zeilenanfang entfernen (1. / 2) / - / * / •)
        line = re.sub(r"^\s*(\d+[.)]|[-*•])\s+", "", line)
        line = _ohne_gedankenstrich(line)
        lines.append(line)
    # Führende Meta-Einleitung (endet auf ":") verwerfen.
    if lines and lines[0].rstrip().endswith(":"):
        low = lines[0].lower()
        if any(w in low for w in ("hier sind", "hier ist", "schlagzeile", "zusammenfass",
                                  "sätze", "folgende", "briefing:")):
            lines = lines[1:]
    return " ".join(lines).strip()
