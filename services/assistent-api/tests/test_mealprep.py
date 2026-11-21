"""Das MealPrep-Werkzeug gegen einen erfundenen Stand, ohne Netz und ohne Modell."""
import asyncio
from datetime import date

import pytest
from jose import jwt
from saganta_dienst.auth import Me, pruefe_bearer

from app.auth import token_fuer
from app.config import settings
from app.werkzeuge import mealprep as mp

HEUTE = date(2026, 11, 14)  # ein Samstag

STAND = {
    "date": "2026-11-14",
    "targets": {"kcal": 2300, "protein_g": 140, "carbs_g": 250, "fat_g": 70},
    "intake_totals": {"kcal": 800.4, "protein_g": 40.6, "carbs_g": 90, "fat_g": 25},
    "day_status": {"remaining_kcal": 1500, "remaining_protein_g": 99.4, "message": "Eiweiß aufholen."},
    "slots": [
        {"id": 11, "slot_label": "Frühstück", "status": "eaten", "pinned": False, "recipe": {"id": 1, "name": "Haferbrei"}},
        {"id": 12, "slot_label": "Mittag", "status": "planned", "pinned": True, "recipe": {"id": 2, "name": "Linsensuppe"}},
    ],
    "days": [
        {"date": "2026-11-14", "slots": [
            {"id": 11, "slot_label": "Frühstück", "status": "eaten", "pinned": False, "recipe": {"id": 1, "name": "Haferbrei"}},
            {"id": 12, "slot_label": "Mittag", "status": "planned", "pinned": True, "recipe": {"id": 2, "name": "Linsensuppe"}},
        ]},
        {"date": "2026-11-15", "slots": [
            {"id": 21, "slot_label": "Abendessen", "status": "planned", "pinned": False, "recipe": None},
        ]},
    ],
    "adhoc_intakes": [{"label": "Apfel"}],
}

KATALOG = {
    "rezepte": [
        {"id": 2, "name": "Linsensuppe", "aliases": [], "nutrition_per_portion": {"kcal": 450}},
        {"id": 3, "name": "Rote Linsen Curry", "aliases": ["Dal"], "nutrition_per_portion": {"kcal": 520}},
        {"id": 4, "name": "Rosenkohl-Auflauf", "aliases": [], "nutrition_per_portion": {}},
        {"id": 5, "name": "Pizza Margherita", "aliases": [], "hidden": True, "nutrition_per_portion": {"kcal": 900}},
    ],
    "zutaten": [{"id": 70, "name": "Rosenkohl"}, {"id": 71, "name": "Brokkoli"}],
}

KANDIDATEN = {"recipes": [
    {"id": 3, "name": "Rote Linsen Curry", "cook_time_min": 25, "feasible": True},
    {"id": 4, "name": "Rosenkohl-Auflauf", "cook_time_min": 40, "feasible": False},
]}


class Fake:
    def __init__(self):
        self.pfade = []

    async def __call__(self, pfad, **_):
        self.pfade.append(pfad)
        if pfad.startswith("/api/dashboard/"):
            return STAND
        if pfad == "/api/app/katalog":
            return KATALOG
        if pfad.startswith("/api/swap-candidates/"):
            return KANDIDATEN
        raise AssertionError(pfad)


def lauf(nachricht, aktionen, antwort="Mache ich."):
    if nachricht == "x":
        # Eine Nachricht, in der Ausschnitt und Titel stehen, wie im echten Lauf.
        nachricht = " ".join(f"{x['ausschnitt']} {x['titel'] or ''}" for x in aktionen)
    fake = Fake()
    gesehen = {}

    async def frage(kontext):
        gesehen["kontext"] = kontext
        return {"antwort": antwort, "aktionen": aktionen}

    erg = asyncio.run(mp.beantworten(fake, HEUTE, "12:00", nachricht, frage))
    return erg, gesehen["kontext"], fake


def a(art, ausschnitt="", titel=None, ziel_id=None, urteil=None):
    return {"art": art, "ausschnitt": ausschnitt, "titel": titel, "ziel_id": ziel_id, "urteil": urteil}


# ── Text und Tage ─────────────────────────────────────────────────────────

def test_norm_umlaute():
    assert mp.norm("Rosenkohl-Auflauf mit Käse") == "rosenkohl auflauf mit kaese"


@pytest.mark.parametrize("frage,erwartet", [
    ("Linsensuppe", 2), ("linsen suppe", 2), ("Dal", 3), ("rosenkohl auflauf", 4),
])
def test_treffer_findet(frage, erwartet):
    assert mp.treffer(frage, KATALOG["rezepte"], mp.rezept_namen)[0]["id"] == erwartet


def test_treffer_erfindet_nichts():
    assert mp.treffer("Döner", KATALOG["rezepte"], mp.rezept_namen) == []


@pytest.mark.parametrize("text,vorwaerts,erwartet", [
    ("morgen", True, date(2026, 11, 15)),
    ("gestern Abend", False, date(2026, 11, 13)),
    ("am Dienstag", True, date(2026, 11, 17)),
    ("am Dienstag", False, date(2026, 11, 10)),
    ("am 20.11.", True, date(2026, 11, 20)),
    ("irgendwann", True, None),
])
def test_tag_lesen(text, vorwaerts, erwartet):
    assert mp.tag_lesen(text, HEUTE, vorwaerts=vorwaerts) == erwartet


def test_naehrwerte_lesen():
    assert mp.naehrwerte_lesen("Pizza, etwa 900 kcal und 35 g Eiweiß") == {"kcal": 900.0, "protein_g": 35.0}


# ── Kontext ───────────────────────────────────────────────────────────────

def test_kontext_kurzkennungen_und_ende_mit_uhrzeit():
    text, zuordnung = mp.kontext_bauen(STAND, HEUTE, "12:00")
    assert "- m-1 Frühstück: Haferbrei (gegessen)" in text
    assert "- m-2 Mittag: Linsensuppe (fest)" in text
    assert "- m-3 Abendessen: nichts geplant" in text
    assert "Heute nachgetragen: Apfel" in text
    assert text.splitlines()[-1].endswith("jetzt 12:00.")
    assert zuordnung["m-3"]["id"] == 21 and zuordnung["m-3"]["datum"] == "2026-11-15"


# ── Fakten statt Modell ───────────────────────────────────────────────────

def test_tagesstand_ersetzt_den_satz_des_modells():
    erg, _, _ = lauf("wie viel Eiweiß fehlt mir noch?", [a("frage")], antwort="Dir fehlen 12 g.")
    assert "12 g" not in erg["antwort"]
    assert "41 von 140 g Eiweiß" in erg["antwort"]
    assert "99 g Eiweiß" in erg["antwort"]
    assert "Noch geplant: Mittag Linsensuppe" in erg["antwort"]


def test_kochbar_nennt_nur_machbares_und_bietet_tausch():
    erg, _, fake = lauf("was kann ich heute kochen?", [a("frage")])
    assert "Rote Linsen Curry (25 min)" in erg["antwort"]
    assert "Rosenkohl" not in erg["antwort"]
    assert fake.pfade[-1] == "/api/swap-candidates/12"  # Frühstück ist gegessen
    karte = erg["karten"][0]
    assert karte["optionen"][0]["daten"]["ops"] == [{"art": "tauschen", "slot_id": 12, "recipe_id": 3}]


# ── Karten ────────────────────────────────────────────────────────────────

def test_nachtragen_mit_zahlen_aus_der_nachricht():
    erg, _, _ = lauf("gestern Pizza 900 kcal", [a("nachtragen", "gestern Pizza 900 kcal", "Pizza")])
    ops = erg["karten"][0]["optionen"][0]["daten"]["ops"]
    assert ops == [{"art": "nachtragen", "label": "Pizza", "datum": "2026-11-13", "kcal": 900.0}]


def test_nachtragen_ohne_zahlen_bietet_rezept_und_leer():
    erg, _, _ = lauf("ich hatte Linsensuppe", [a("nachtragen", "ich hatte Linsensuppe", "Linsensuppe")])
    optionen = erg["karten"][0]["optionen"]
    assert optionen[0]["daten"]["ops"] == [{"art": "nachtragen", "recipe_id": 2}]
    assert optionen[-1]["daten"]["ops"] == [{"art": "nachtragen", "label": "Linsensuppe"}]
    assert erg["karten"][0]["hinweis"]


def test_tauschen_mit_wunsch():
    erg, _, _ = lauf("x", [a("tauschen", "Mittag gegen Dal", "Dal", "m-2")])
    assert erg["karten"][0]["optionen"][0]["daten"]["ops"] == [{"art": "tauschen", "slot_id": 12, "recipe_id": 3}]


def test_tauschen_ohne_wunsch_nimmt_machbare_kandidaten():
    erg, _, _ = lauf("x", [a("tauschen", "Mittag was anderes", None, "m-2")])
    namen = [o["text"] for o in erg["karten"][0]["optionen"]]
    assert namen == ["Rote Linsen Curry"]


def test_gegessenes_wird_nicht_getauscht():
    erg, _, _ = lauf("x", [a("tauschen", "Frühstück", "Dal", "m-1")])
    assert erg["karten"] == [] and "schon gegessen" in erg["verworfen"][0]["grund"]


def test_unbekannte_kennung_wird_verworfen():
    erg, _, _ = lauf("x", [a("gegessen", "Mittag", None, "m-99")])
    assert erg["karten"] == [] and "m-99" in erg["verworfen"][0]["grund"]


def test_gegessen_und_anpinnen():
    erg, _, _ = lauf("x", [a("gegessen", "Mittag", None, "m-2"), a("anpinnen", "Mittag nicht mehr fest", None, "m-2")])
    assert erg["karten"][0]["optionen"][0]["daten"]["ops"] == [{"art": "gegessen", "slot_id": 12}]
    assert erg["karten"][1]["optionen"][0]["daten"]["ops"] == [{"art": "anpinnen", "slot_id": 12, "an": False}]
    assert [k["id"] for k in erg["karten"]] == ["k1", "k2"]


def test_neu_planen_woche_sind_sieben_operationen():
    erg, _, _ = lauf("x", [a("neu_planen", "die Woche")])
    ops = erg["karten"][0]["optionen"][0]["daten"]["ops"]
    assert len(ops) == 7 and ops[0] == {"art": "neu_planen", "datum": "2026-11-14"}


def test_neu_planen_vergangenheit_verworfen():
    erg, _, _ = lauf("x", [a("neu_planen", "gestern")])
    assert erg["karten"] == [] and erg["verworfen"]


def test_ausblenden_laesst_versteckte_weg():
    erg, _, _ = lauf("x", [a("ausblenden", "", "Pizza")])
    assert erg["karten"] == []  # Pizza ist schon ausgeblendet


def test_vorliebe_rezept_und_zutat():
    erg, _, _ = lauf("x", [a("vorliebe", "Dal gern öfter", "Dal", urteil="oefter"),
                           a("vorliebe", "Brokkoli seltener", "Brokkoli")])
    assert erg["karten"][0]["optionen"][0]["daten"]["ops"] == [
        {"art": "vorliebe", "ziel": "rezept", "urteil": "oefter", "a_id": 3}]
    assert "Zutat" in erg["verworfen"][0]["grund"]


def test_abgeschriebener_titel_faellt_weg():
    # gemessen 15.11.: "Chili gern oefter" kam mit titel "Linsencurry" zurueck
    erg, _, _ = lauf("Linsensuppe gern öfter", [a("vorliebe", "Linsensuppe gern öfter", "Rote Linsen Curry", urteil="oefter")])
    assert erg["karten"][0]["optionen"][0]["daten"]["ops"][0]["a_id"] == 2


def test_titel_aus_dem_verlauf_bleibt():
    aktion = mp.gegenpruefen(a("tauschen", "lieber das", "Dal", "m-2"), "lieber das", ["tausch Mittag gegen Dal"])
    assert aktion["titel"] == "Dal" and aktion["ausschnitt"] == "lieber das"


def test_erfundener_ausschnitt_wird_die_nachricht():
    aktion = mp.gegenpruefen(a("neu_planen", "die ganze Woche"), "plane morgen neu", [])
    assert aktion["ausschnitt"] == "plane morgen neu"


def test_schema_verlangt_jedes_feld():
    items = mp.SCHEMA["properties"]["aktionen"]["items"]
    assert set(items["required"]) == set(items["properties"])


# ── Token ─────────────────────────────────────────────────────────────────

def test_token_fuer_mealprep_traegt_nur_den_sub_des_aufrufers():
    token = token_fuer(Me(sub="nutzer-1", email="x@example.invalid"), "mealprep-api")
    nutzlast = pruefe_bearer(f"Bearer {token}", geheimnis=settings.jwt_secret,
                             algorithmus=settings.jwt_algorithm, zielgruppe="mealprep-api")
    assert nutzlast["sub"] == "nutzer-1" and nutzlast["exp"] - nutzlast["iat"] == 60
    with pytest.raises(Exception):
        jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], audience="assistent-api")
