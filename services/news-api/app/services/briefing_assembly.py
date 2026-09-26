"""Briefing-Assembly: aus dem globalen FeedItem-Pool ein personalisiertes,
interessengewichtetes Tages-Briefing bauen.

Deterministischer Kern (Scoring + Diversität + Sektionen), optional durch eine
LLM-Redaktion (Sprech-Intro) veredelt. Alles pro `sub`: Feedback-Modifier und
Präferenzen sind user-privat.

Portierte Mechaniken aus dem alten briefing_lib.py (Owner „mindestens mein Niveau"):
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

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..briefing_models import BriefingFeedback, BriefingProfile
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


def _tokens(text: str) -> set[str]:
    return {w for w in "".join(c if c.isalnum() else " " for c in text.lower()).split() if len(w) > 3}


def _too_similar(a: set[str], b: set[str], thresh: float = 0.6) -> bool:
    if not a or not b:
        return False
    inter = len(a & b)
    union = len(a | b)
    return union > 0 and inter / union >= thresh


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
    text = f"{item.title} {item.summary or ''}"
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


def assemble(db: Session, profile: BriefingProfile, for_date: date | None = None) -> dict:
    """Baut das content-JSON für genau diesen User. Reiner Lese-Zugriff auf den Pool."""
    now = _utcnow()
    for_date = for_date or now.date()
    weights = _interest_weights(profile)
    # Tarif-Gating: Freitext-Themen nur Pro; Länge auf Tarif-Maximum begrenzen.
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

    max_items = max(4, round(settings.briefing_max_items * _LENGTH_FACTOR.get(eff_length, 1.0)))
    per_source: dict[str, int] = {}
    picked_tokens: list[set[str]] = []
    selected: list[tuple[float, list[str], FeedItem, FeedSource, UserItemState | None]] = []
    for entry in scored:
        _s, _tags, item, src, _state = entry
        if per_source.get(src.slug, 0) >= settings.briefing_max_same_source:
            continue
        toks = _tokens(item.title)
        if any(_too_similar(toks, pt) for pt in picked_tokens):
            continue
        selected.append(entry)
        per_source[src.slug] = per_source.get(src.slug, 0) + 1
        picked_tokens.append(toks)
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
            "title": item.title,
            "link": item.link,
            "source": src.name,
            "source_slug": src.slug,
            "summary": (item.summary or "")[:600],
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
    for tag in ordered_tags:
        if tag == "top":
            continue
        bucket = [
            _item_dict(i, s, t, st)
            for (_sc, t, i, s, st) in selected
            if tag in t and i.link not in used_links
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
            title = e.get("title") or "Termin"
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
        title = first.get("title") or "ein Termin"
        rest = len(events) - 1
        weitere = f" und {rest} weitere{'r' if rest == 1 else ''} Termin{'e' if rest > 1 else ''}" if rest > 0 else ""
        if t and t != "ganztägig":
            lines.append(f"Morgen um {t.replace(' Uhr', '')} Uhr: {title}{weitere}.")
        else:
            lines.append(f"Morgen ganztägig: {title}{weitere}.")
    return lines


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
            lines.append(f"{d['title']}.")
    for sec in sections:
        if sec["tag"] == "weiteres":
            continue
        lines.append(f"Aus dem Bereich {sec['label']}:")
        for d in sec["items"][:3]:
            lines.append(f"{d['title']}.")
    lines.append("Das war dein Briefing. " + _closing(now))
    return " ".join(lines)


def spoken_narration(content: dict) -> str:
    """Liefert den Text, der vertont wird. Versucht LLM-Redaktion (nur hier, im
    Audio-/Hintergrund-Pfad aufgerufen), fällt sonst auf den deterministischen
    spoken_text zurück. Latenz-/Kosten-relevant → NICHT im /today-Request nutzen.
    """
    baseline = content.get("spoken_text", "")
    headlines: list[str] = []
    for d in content.get("top_items", []):
        headlines.append(f"- {d['title']} ({d.get('source', '')})")
    for sec in content.get("sections", []):
        if sec.get("tag") == "weiteres":
            continue
        for d in sec.get("items", [])[:3]:
            headlines.append(f"- {d['title']} ({d.get('source', '')})")
    if not headlines:
        return baseline

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
    llm = llm_client.chat(
        system=(
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
            "sondern Komma, Doppelpunkt oder Punkt."
        ),
        user=f"Datum: {datum}{weather_block}{day_block}\n\nSchlagzeilen:\n"
             + "\n".join(headlines[:14]),
        max_tokens=600,
    )
    if not llm:
        return baseline
    cleaned = _ensure_greeting(_clean_narration(llm), content)
    # Fail-safe: lieber der schlichte, korrekte Baseline-Text als eine Sprachfassung
    # mit Platzhaltern. Das kleine lokale Modell produziert gelegentlich Vorspann wie
    # „mein Name ist [Dein Name]": vorgelesen ist das schlimmer als nüchtern.
    return baseline if _narration_is_broken(cleaned) else cleaned


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
    if text[:20].lower().startswith(_GREETINGS):
        return text
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
