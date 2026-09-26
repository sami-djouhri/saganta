"""Kanonische Interessen-Tags + Keyword-Maps.

Bewusst schlank und deterministisch (kein Embedding im news-api): ein Artikel wird
per Keyword-Treffer in Titel+Summary einem oder mehreren Tags zugeordnet. Das ist
die Generalisierung von Samis früher hartkodierten Homelab-Topic-Gewichten
(Owner-Entscheidung 2026-07-10: „generalisiert als Interessen-Tags").

Wenn später der Story-Engine-Pool (BGE-M3-Cluster) angebunden wird, kann die
Zuordnung durch echte Embedding-Ähnlichkeit ersetzt werden, die Tag-Liste bleibt
die stabile öffentliche Auswahl fürs Onboarding.
"""
from __future__ import annotations

# tag -> (Anzeigename, Keywords lowercase). Keywords matchen als Substring auf
# den normalisierten (lowercase) Text von Titel + Summary.
INTERESTS: dict[str, tuple[str, list[str]]] = {
    "top": ("Top-Themen", []),  # Sonderfall: höchste Roh-Scores unabhängig vom Tag
    "politik": (
        "Politik",
        ["bundestag", "regierung", "wahl", "kanzler", "minister", "eu-", "brüssel",
         "parlament", "koalition", "gesetzentwurf", "opposition"],
    ),
    "wirtschaft": (
        "Wirtschaft",
        ["wirtschaft", "inflation", "aktie", "börse", "dax", "zins", "ezb", "konjunktur",
         "arbeitsmarkt", "konzern", "insolvenz", "umsatz", "quartalszahlen"],
    ),
    "tech": (
        "Technik",
        ["software", "hardware", "chip", "prozessor", "smartphone", "gadget", "app ",
         "open source", "linux", "windows", "cloud", "rechenzentrum", "programmier"],
    ),
    "ki": (
        "Künstliche Intelligenz",
        ["ki-", "künstliche intelligenz", "artificial intelligence", " ai ", "chatgpt",
         "openai", "anthropic", "llm", "sprachmodell", "machine learning", "neuronale"],
    ),
    "security": (
        "IT-Sicherheit",
        ["sicherheitslücke", "schwachstelle", "cve-", "exploit", "ransomware", "hacker",
         "datenleck", "malware", "phishing", "zero-day", "patchday", "cyberangriff",
         "verschlüsselung", "botnet"],
    ),
    "homeserver": (
        "Homeserver & Self-Hosting",
        ["self-host", "selfhost", "homelab", "home assistant", "docker", "proxmox",
         "raspberry pi", "nas ", "synology", "heimserver", "kubernetes", "container"],
    ),
    "wissenschaft": (
        "Wissenschaft",
        ["studie", "forscher", "forschung", "wissenschaftler", "physik", "biologie",
         "chemie", "medizin", "klimaforschung", "weltraum", "nasa", "esa"],
    ),
    "gesundheit": (
        "Gesundheit",
        ["gesundheit", "krankheit", "impf", "medikament", "klinik", "ernährung",
         "psyche", "virus", "rki", "who ", "diagnose"],
    ),
    "umwelt": (
        "Umwelt & Klima",
        ["klima", "klimawandel", "erneuerbare", "solar", "windkraft", "co2", "emission",
         "naturschutz", "energiewende", "wärmepumpe", "nachhaltig"],
    ),
    "sport": (
        "Sport",
        # Kurz-Token wie "em "/"wm "/"tor " matchen deutsche Wortenden
        # (Problem/Motor/Autor) → nur eindeutige Sport-Begriffe.
        ["bundesliga", "champions league", "olympia", "olympische", "fußball", "handball",
         "tennis", "formel 1", "dfb-", "weltmeister", "europameister", "nationalmannschaft",
         "torschütze", "auswärtssieg", "spieltag"],
    ),
    "kultur": (
        "Kultur & Medien",
        ["film", "kino", "serie", "netflix", "musik", "album", "roman", "ausstellung",
         "theater", "festival", "streaming"],
    ),
    "welt": (
        "Weltgeschehen",
        ["ukraine", "russland", "china", "usa", "nahost", "israel", "gaza", "krieg",
         "un-", "vereinte nationen", "sanktion", "flüchtling"],
    ),
    "auto": (
        "Auto & Mobilität",
        # "auto" nackt matcht Autor/Automat/autonom → nur eindeutige Mobilitäts-Begriffe.
        ["elektroauto", "e-auto", "auto ", "autos", "verbrenner", "tesla", "deutsche bahn",
         "verkehr", "ladesäule", "führerschein", "tempolimit", "pkw", "autobahn"],
    ),
}

# Öffentlich anwählbare Tags (ohne den "top"-Sonderfall).
SELECTABLE_TAGS = [t for t in INTERESTS if t != "top"]

# Sinnvolle Default-Auswahl für neue User (ein Klick reicht → Non-Techie-freundlich).
DEFAULT_INTERESTS = [
    {"tag": "top", "weight": 1.5},
    {"tag": "politik", "weight": 1.0},
    {"tag": "wirtschaft", "weight": 1.0},
    {"tag": "wissenschaft", "weight": 1.0},
    {"tag": "welt", "weight": 1.0},
]


def label_for(tag: str) -> str:
    entry = INTERESTS.get(tag)
    return entry[0] if entry else tag.capitalize()


def match_tags(text: str) -> set[str]:
    """Gibt die Interessen-Tags zurück, deren Keywords im Text vorkommen."""
    low = f" {text.lower()} "
    hits: set[str] = set()
    for tag, (_label, keywords) in INTERESTS.items():
        if not keywords:
            continue
        for kw in keywords:
            if kw in low:
                hits.add(tag)
                break
    return hits


def free_topic_hits(text: str, topics: list[str]) -> list[str]:
    """Freitext-Themen des Users, die im Text vorkommen (Substring, case-insensitive)."""
    low = text.lower()
    return [t for t in topics if t and t.lower() in low]
