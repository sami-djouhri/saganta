"""Erfundene Daten fuer mealprep. Kein Rezept, kein Koerperwert hier stammt aus dem echten Bestand.

Die Seiten sind Jinja-Vorlagen: dieser Handler rendert sie selbst mit erfundenem
Kontext (Namen aus app/api/routes_*.py), ohne Server und ohne Datenbank.
"""
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

import sys

try:
    import jinja2
except ImportError:  # das medien-venv hat kein jinja2, das System schon
    sys.path.append("/usr/lib/python3/dist-packages")
    import jinja2
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from probe import Antwort  # noqa: E402

DOCKER = Path(__file__).resolve().parents[4]
APP = DOCKER / "mealprep/app"
WURZELN = [("/static/", APP / "static")]

TAG_WORTE = {
    "fruehstueck": "Frühstück", "mittagessen": "Mittagessen", "abendessen": "Abendessen",
    "snack": "Snack", "high-protein": "Viel Protein", "meal-prep": "Zum Vorkochen",
    "schnell": "Schnell", "vegetarisch": "Vegetarisch", "vegan": "Vegan",
}
UMGEBUNG = jinja2.Environment(loader=jinja2.FileSystemLoader(str(APP / "templates")),
                              autoescape=True)
UMGEBUNG.filters["tag_wort"] = lambda t: TAG_WORTE.get(t, t.replace("-", " ").capitalize())

NAMEN = ["Linsen-Dal mit Reis", "Ofengemüse mit Feta und Kräuterquark", "Haferbrei mit Beeren",
         "Kichererbsen-Curry", "Vollkornnudeln mit Tomatensoße", "Rührei mit Spinat",
         "Bohnen-Chili sin Carne", "Quarkspeise mit Apfel", "Gemüsesuppe mit Graupen",
         "Reispfanne mit Erbsen und sehr langem Namen zum Testen des Umbruchs"]
TAGS = [["mittagessen", "schnell", "vegetarisch"], ["abendessen", "ofen"], ["fruehstueck", "schnell"],
        ["mittagessen", "meal-prep", "vegan"], ["abendessen"], ["fruehstueck", "high-protein"]]


def bild(i):
    return f"/recipes/{i}/bild?v=s1"


def svg(i):
    farben = ["#5a4630", "#3d4a36", "#4a3a4f", "#36444f", "#4f3a36"]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">'
            f'<rect width="400" height="300" fill="{farben[i % 5]}"/>'
            f'<circle cx="200" cy="150" r="80" fill="#00000033"/></svg>')


def naehrwert(i):
    return {"kcal": 420 + 37 * i, "protein_g": 18.4 + 2 * i, "carbs_g": 50.2 + i,
            "fat_g": 12.7 + i, "fiber_g": 6.3}


def rezept(i, **mehr):
    r = dict(id=i + 1, name=NAMEN[i % len(NAMEN)], bild_url=bild(i + 1), cook_time_min=10 + 5 * (i % 5),
             nutrition_per_portion=naehrwert(i), tags=TAGS[i % len(TAGS)], hidden=(i == 7),
             geraete=["Ofen"] if i % 4 == 1 else [], techniken=["Schmoren"], portions_default=2,
             bild_art="vault", bild_hinweis=None, aus_vault=(i % 2 == 0),
             instructions="Zwiebel würfeln und anschwitzen.\nLinsen und Gewürze zugeben.\n"
                          "Mit Wasser aufgießen und 20 Minuten köcheln.\nMit Reis servieren.",
             ingredients=[NS(ingredient_id=1, amount=200, unit="g", optional_bool=False)])
    r.update(mehr)
    return NS(**r)


def seite(vorlage, **kontext):
    kontext.setdefault("request", None)
    return UMGEBUNG.get_template(vorlage).render(**kontext)


# ------------------------------------------------------------------ Dashboard

def slot(i, label, status="planned", **mehr):
    s = {"id": 10 + i, "slot_label": label, "status": status, "feasibility_status": "feasible",
         "slot_status": "optimal" if i == 0 else None, "personen": 2 if i == 1 else 1, "pinned": i == 2,
         "recipe": {"id": i + 1, "name": NAMEN[i], "bild_url": bild(i + 1), "nutrition": naehrwert(i),
                    "instructions": "Alles in einen Topf geben und 20 Minuten köcheln lassen."},
         "goal_contribution": {"protein_label": "Protein gut", "carb_status": "ok", "fat_status": "am Limit"},
         "missing_ingredients": [], "rueckmeldung": None}
    s.update(mehr)
    return s


def dashboard(tag):
    d0 = date.fromisoformat(tag)
    montag = d0 - timedelta(days=d0.weekday())
    slots = [
        slot(0, "Frühstück", status="eaten", rueckmeldung="passt"),
        slot(1, "Mitnahme"),
        slot(2, "Abendessen", feasibility_status="partial",
             missing_ingredients=[{"name": "Kichererbsen", "available": 120, "needed": 400, "unit": "g"},
                                  {"name": "Kokosmilch", "available": 0, "needed": 200, "unit": "ml"}]),
        slot(3, "Snack", slot_status="replace_recommended"),
    ]
    tage = [{"date": (montag + timedelta(days=k)).isoformat(),
             "day_type": ["arbeit", "arbeit", "schule", "arbeit", "frei", "wochenende", "wochenende"][k],
             "slots": [{"slot_label": s["slot_label"], "status": s["status"],
                        "feasibility_status": "infeasible" if k == 3 and j == 2 else "feasible"}
                       for j, s in enumerate(slots)]} for k in range(7)]
    return {
        "date": tag, "days": tage, "slots": slots, "haushalt_personen": 2,
        "day_status": {"status": "attention", "status_label": "Achtung", "remaining_kcal": 1240,
                       "remaining_protein_g": 74, "message": "Protein liegt hinter dem Plan. Das Abendessen gleicht es aus.",
                       "next_meal": {"slot_id": 11, "slot_label": "Mitnahme", "recipe_name": NAMEN[1],
                                     "reason": "Nutzt die Paprika, die übermorgen abläuft.",
                                     "goal_contribution": {"protein_label": "Protein gut", "carb_status": "hoch"}}},
        "targets": {"kcal": 2400, "protein_g": 150, "carbs_g": 260, "fat_g": 80},
        "intake_totals": {"kcal": 620, "protein_g": 31, "carbs_g": 70, "fat_g": 20, "iron_mg": 4.2,
                          "vitamin_c_mg": 60},
        "planned_totals": {"kcal": 1300, "protein_g": 70, "carbs_g": 140, "fat_g": 45, "iron_mg": 6},
        "adhoc_intakes": [{"id": 5, "label": "Brezel vom Bäcker", "nutrition": {"kcal": 230, "protein_g": 7}}],
        "supplements": [
            {"id": 1, "name": "Vitamin D3", "dose": "1000 IE", "timing": "morgens", "taken_today": True,
             "category": "daily", "hint": None, "nutrition": None},
            {"id": 2, "name": "Omega-3", "dose": "2 Kapseln", "timing": "morgens", "taken_today": False,
             "category": "conditional", "hint": "nur ohne Fisch am Tag", "nutrition": None},
            {"id": 3, "name": "Magnesium", "dose": "300 mg", "timing": "abends", "taken_today": False,
             "category": "daily", "hint": None, "nutrition": None},
        ],
        "supplement_hints": ["Heute kein Fisch geplant: Omega-3 nehmen"],
        "nutrient_deficits": [{"nutrient_label": "Eisen", "deficit_pct": 0.32,
                               "food_solution": "Linsen oder Haferflocken", "supplement_solution": None}],
        "days_of_food_belastbar": True, "days_of_food": 4.2,
    }


def stats(periode):
    heute = date.today()
    tage = [{"date": (heute - timedelta(days=k)).isoformat(), "kcal": 1800 + (k * 137) % 700,
             "protein_g": 100 + (k * 13) % 50} for k in range(periode)][::-1]
    return {"days": tage, "avg_kcal": 2150, "avg_protein_g": 121}


def coach(tag):
    return {"date": tag, "day_type": "arbeit", "planned_coverage": 0.82,
            "day_status": {"status_label": "Gut im Plan", "message": "Mittag und Abend decken den Rest."},
            "remaining": {"kcal": 1240, "protein_g": 74, "carbs_g": 120, "fat_g": 40},
            "fitness": {"reachable": True, "planned_day": {"name": "Oberkörper"}, "workouts": []},
            "actions": ["Mitnahme heute Abend vorbereiten", "Kichererbsen einweichen"],
            "timing": [{"label": "Nach dem Training", "text": "Mahlzeit mit 30 g Protein"}],
            "expiring": [{"product_name": "Paprika rot", "amount": 2, "unit": "Stück", "expires_at": "2026-11-10"}]}


def swap_kandidaten():
    return {"recipes": [{"id": i + 1, "name": NAMEN[i], "bild_url": bild(i + 1), "feasible": i % 3 != 2,
                         "nutrition": naehrwert(i), "score": {"total": 0.9 - i * 0.08},
                         "cook_time_min": 15 + i, "missing_ingredients": [{"name": "x"}] if i % 3 == 2 else [],
                         "tags": TAGS[i % len(TAGS)]} for i in range(7)]}


# ------------------------------------------------------------------ Duell

def karte(i):
    n = naehrwert(i)
    return {"id": i + 1, "name": NAMEN[i % len(NAMEN)], "bild_url": bild(i + 1), "kcal": n["kcal"],
            "protein_g": round(n["protein_g"]), "kochzeit_min": 15 + i}


def zutat(i):
    namen = ["Brokkoli", "Blumenkohl", "Karotte", "Zucchini"]
    return {"id": 100 + i, "name": namen[i], "kategorie": "Gemüse", "gruppe": "Gemüse", "in_rezepten": 3 + i}


# ------------------------------------------------------------------ Seiten

def profil():
    p = NS(height_cm=180.0, weight_kg=78.5, sex="male", birth_date=date(1990, 1, 1), body_fat_pct=None,
           waist_cm=None, activity_level="moderate", target_weight_kg=75.0, kcal_target_override=None,
           fehlende_geraete=["Mixer"], haushalt_personen=2, probier_pro_woche=2, excluded_ingredient_ids=[3])
    zutaten = [NS(id=i, name_canonical=n, category="Gemüse")
               for i, n in enumerate(["Brokkoli", "Karotte", "Koriander", "Linsen", "Paprika"], 1)]
    return seite("profile.html", profile=p, bmr=1750.2, tdee=2712.8,
                 targets=NS(kcal=2400, protein_g=150, carbs_g=260, fat_g=80, fiber_g=30),
                 all_ingredients=zutaten, alle_geraete=[("Backofen", 12), ("Mixer", 3), ("Wok", 2)],
                 haushalt_mahlzeiten=[("breakfast", "Frühstück", "nie"), ("dinner", "Abendessen", "immer")],
                 probierliste=["Bohnen-Chili sin Carne"], flash="", active_nav="profile",
                 goal_phase_label="Definitionsphase", goal_phase_class="phase-cut",
                 goal_statement="Du isst 2400 kcal pro Tag, um Gewicht zu verlieren. Zielgewicht 75 kg.",
                 deficit_or_surplus="312 kcal Defizit pro Tag", ziel_richtung="defizit", ziel_quelle="phase",
                 ziel_widerspruch=None, ziel_phase_seit=date(2026, 10, 1),
                 protein_pct=25, carbs_pct=45, fat_pct=30)


def wochenplan():
    heute = date.today()
    montag = heute - timedelta(days=heute.weekday())
    tage = []
    for k in range(7):
        mahlzeiten = [] if k == 6 else [
            {"slot_type": "breakfast", "slot_label": "Frühstück", "recipe_name": NAMEN[2], "status": "eaten" if k < 2 else "planned", "pinned": False},
            {"slot_type": "packed_lunch", "slot_label": "Mitnahme", "recipe_name": NAMEN[(k + 3) % 10], "status": "planned", "pinned": k == 1},
            {"slot_type": "dinner", "slot_label": "Abendessen", "recipe_name": None if k == 4 else NAMEN[k], "status": "planned", "pinned": False},
        ]
        tage.append({"date": montag + timedelta(days=k), "meals": mahlzeiten,
                     "total_kcal": 0 if k == 6 else 1800 + 50 * k, "total_protein": 0 if k == 6 else 110.5})
    einkauf = [{"ingredient_name": n, "total_needed": m, "unit": "g", "in_stock": s, "to_buy": m - s if m > s else 0,
                "category": "Hülsenfrüchte" if i == 0 else None}
               for i, (n, m, s) in enumerate([("Rote Linsen", 400, 150), ("Paprika", 300, 300), ("Haferflocken", 500, 0)])]
    return seite("plan_week.html", start_date=montag, today=heute, days=tage,
                 weekday_labels=["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
                 weekday_full=["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
                 shopping_items=einkauf,
                 muss_weg={"erreichbar": True, "abgelaufen": 1, "vorschau_tage": 7, "posten": [
                     {"name": "Joghurt natur", "menge": 500, "unit": "g", "tage_uebrig": -2, "abgelaufen": True},
                     {"name": "Paprika rot", "menge": 2, "unit": "Stück", "tage_uebrig": 1, "abgelaufen": False},
                     {"name": "Spinat", "menge": None, "unit": "", "tage_uebrig": 4, "abgelaufen": False}]},
                 prev_week=montag - timedelta(weeks=1), next_week=montag + timedelta(weeks=1),
                 week_label=f"{montag:%d.%m.} - {montag + timedelta(days=6):%d.%m.%Y}", active_nav="wochenplan")


def api(methode, pfad, query, body):
    if pfad.startswith("/static/"):
        return None
    if pfad.startswith("/recipes/") and pfad.endswith("/bild"):
        return Antwort(200, svg(int(pfad.split("/")[2])).encode(), "image/svg+xml")
    if pfad.startswith("/api/dashboard/"):
        return dashboard(pfad.rsplit("/", 1)[1])
    if pfad == "/api/stats":
        return stats(int(query.get("period", 7)))
    if pfad.startswith("/api/day-coach/"):
        return coach(pfad.rsplit("/", 1)[1])
    if pfad.startswith("/api/replan/"):
        return Antwort(500, b'{"error": "Planer gerade nicht erreichbar"}', "application/json")
    if pfad.startswith("/api/intake/") and methode == "DELETE":
        return dashboard(date.today().isoformat())
    if pfad == "/plan/week" and methode == "POST":
        return Antwort(503, b'{"error": "Lager antwortet nicht"}', "application/json")
    if pfad.startswith("/api/swap-candidates/"):
        return swap_kandidaten()
    if pfad == "/rezepte/search":
        return {"recipes": [rezept(i).__dict__ | {"ingredients": []} for i in range(3)]}
    if pfad == "/api/vorliebe/paare":
        if query.get("ziel") == "zutat":
            return {"paare": [{"a": zutat(0), "b": zutat(1)}]}
        return {"paare": [{"a": karte(0), "b": karte(9)}]}
    if pfad == "/api/vorliebe/wahl" and methode == "GET":
        return {"runden": [{"waehlen": 3, "karten": [karte(i) for i in range(6)]}]}
    if pfad == "/api/vorliebe/stapel":
        return {"karten": [karte(3)]}
    if pfad == "/api/vorliebe/rangliste":
        return {"eintraege": [{"name": NAMEN[i], "wert": 80 - 9 * i} for i in range(5)], "ohne_urteil": 12}
    if pfad == "/api/vorliebe/urteil":
        return {"id": 1}
    if pfad == "/":
        return seite("index.html", active_nav="dashboard")
    if pfad == "/rezepte":
        rs = [rezept(i) for i in range(10)]
        return seite("recipes_list.html", fehlende_geraete=["Ofen"], show_hidden=False, hidden_count=2,
                     recipes=rs, q=query.get("q", ""), tags_active=None, max_time=None, max_kcal=None,
                     all_tags=sorted({t for r in rs for t in r.tags}), flash="", active_nav="recipes",
                     goal_match_map={1: {"goal_match_pct": 82}, 2: {"goal_match_pct": 55}, 3: {"goal_match_pct": 21}})
    if pfad == "/rezepte/leer":
        return seite("recipes_list.html", fehlende_geraete=[], show_hidden=False, hidden_count=0, recipes=[],
                     q="gibtesnicht", tags_active=None, max_time=None, max_kcal=None, all_tags=[],
                     flash="", active_nav="recipes", goal_match_map={})
    if pfad == "/rezepte/neu":
        zutaten = [NS(id=i, name_canonical=n) for i, n in enumerate(["Brokkoli", "Linsen", "Reis"], 1)]
        return seite("recipe_form.html", all_ingredients=zutaten, active_nav="recipes")
    if pfad == "/rezepte/2":
        r = rezept(1, aus_vault=False, bild_art="foto")
        zut = [{"name": "Rote Linsen", "amount": 200.0, "unit": "g", "optional": False},
               {"name": "Zwiebel", "amount": 1.0, "unit": "piece", "optional": False},
               {"name": "Koriander", "amount": 5.5, "unit": "g", "optional": True}]
        return seite("recipe_detail.html", fehlende_geraete=["Ofen"], recipe=r, ingredients=zut,
                     ingredient_categories={}, flash="Rezept gespeichert", active_nav="recipes")
    if pfad == "/zutaten":
        zutaten = [NS(name_canonical=n, category=c) for n, c in
                   [("Brokkoli", "Gemüse"), ("Linsen", "Hülsenfrüchte"), ("Reis", None)]]
        return seite("ingredients_list.html", ingredients=zutaten, lager_gefragt=True, flash="",
                     active_nav="recipes",
                     fehlende_produkte=[NS(lager_product_id=7, lager_product_name="Weizenmehl Type 405",
                                           kategorie="Backen", bestand=1000, lager_unit="g"),
                                        NS(lager_product_id=8, lager_product_name="Salz", kategorie=None,
                                           bestand=None, lager_unit=None)])
    if pfad == "/profil":
        return profil()
    if pfad == "/plan/wochenplan":
        return wochenplan()
    if pfad == "/duell":
        return seite("duell.html", active_nav="duell")
    return None


def klick(sel):
    # per Skript: Kopf und Fussleiste liegen fest ueber dem Inhalt
    return lambda s: s.eval_on_selector(sel, "e => e.click()")


def reiter(name):
    return klick(f".tab-btn[data-tab={name}]")


def duell(modus):
    return klick(f".duell-reiter [data-modus={modus}]")


SEITEN = [
    {"name": "dashboard", "pfad": "/", "warten": 700},
    {"name": "coach", "pfad": "/", "schritte": [reiter("coach")], "warten": 700},
    {"name": "statistik", "pfad": "/", "schritte": [reiter("stats")], "warten": 700},
    {"name": "tauschen", "pfad": "/", "schritte": [klick(".meal-card [data-action=swap]")],
     "wurzel": "#swap-modal"},
    {"name": "eintragen", "pfad": "/", "schritte": [klick("[data-action=open-adhoc]")],
     "wurzel": "#adhoc-modal"},
    {"name": "rezepte", "pfad": "/rezepte"},
    {"name": "rezepte-leer", "pfad": "/rezepte/leer"},
    {"name": "rezept", "pfad": "/rezepte/2"},
    {"name": "rezept-neu", "pfad": "/rezepte/neu"},
    {"name": "zutaten", "pfad": "/zutaten"},
    {"name": "profil", "pfad": "/profil"},
    {"name": "wochenplan", "pfad": "/plan/wochenplan"},
    {"name": "duell", "pfad": "/duell"},
    {"name": "duell-zutat", "pfad": "/duell", "schritte": [duell("zutat")]},
    {"name": "duell-wahl", "pfad": "/duell", "schritte": [duell("wahl")]},
    {"name": "duell-stapel", "pfad": "/duell", "schritte": [duell("stapel")]},
    {"name": "meldung-fehler", "pfad": "/", "schritte": [klick("[data-action=replan]")], "warten": 900, "fehler_erwartet": True},
    {"name": "meldung-info", "pfad": "/", "schritte": [klick("[data-action=delete-intake]")], "warten": 900},
    {"name": "woche-fehler", "pfad": "/plan/wochenplan", "schritte": [klick("#plan-week-btn")], "warten": 900, "fehler_erwartet": True},
]
