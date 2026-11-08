"""Erfundene Daten fuer fitness. Keine Zahl hier stammt aus dem echten Training."""
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from probe import Antwort  # noqa: E402

BUILD = Path("/tmp/sichtprobe-build/fitness")
WURZELN = [("/", BUILD)]

UEBUNGEN = [
    (1, "Bankdrücken", "Brust", "Langhantel", ["brust_mitte"], True),
    (2, "Kniebeuge", "Beine", "Langhantel", ["rectus_femoris", "gluteus_maximus"], True),
    (3, "Klimmzug", "Rücken", "Klimmzugstange", ["latissimus"], True),
    (4, "Schulterdrücken mit Kurzhanteln", "Schultern", "Kurzhantel", ["delta_vorne"], True),
    (5, "Bizepscurl", "Arme", "Kurzhantel", ["bizeps_lang"], False),
    (6, "Rumänisches Kreuzheben", "Beine", "Langhantel", ["erector_spinae", "gluteus_maximus"], True),
    (7, "Seitheben", "Schultern", "Kurzhantel", ["delta_seite"], False),
    (8, "Hüftbeuger-Dehnung", "Dehnung", "Körpergewicht", ["rectus_femoris"], False),
]


def uebung(u, **extra):
    i, name, kat, ger, muskeln, grund = u
    d = {"id": i, "name": name, "category": kat, "equipment": ger, "primary_muscles": muskeln,
         "secondary_muscles": [], "is_compound": grund, "is_selected": True, "notes": None,
         "is_eigene": i == 8, "muskel_anteile": {m: 1.0 for m in muskeln}, "benoetigt": [],
         "muster": "drücken", "kg_anteil": 0, "griff": None, "reihe": None, "stufe": 2,
         "einseitig": False, "ist_zeit": i == 8, "wdh_min": 6, "wdh_max": 10, "pause_s": 120,
         "ausfuehrung": "Erfundene Anleitung: kontrolliert absenken, kurz halten, kräftig hochdrücken.",
         "fehler": "Erfundener Fehler: Ellbogen zu weit vom Körper.", "machbar": i != 3,
         "fehlt_namen": ["Klimmzugstange"] if i == 3 else []}
    d.update(extra)
    return d


GRUPPEN = [("brust", "Brust", "oberkoerper"), ("ruecken", "Rücken", "oberkoerper"),
           ("schultern", "Schultern", "oberkoerper"), ("arme", "Arme", "oberkoerper"),
           ("beine", "Beine", "unterkoerper"), ("rumpf", "Rumpf", "rumpf")]
BEWERTUNGEN = ["im_korridor", "unter_mev", "erhaltung", "ueber_mav", "unter_mv", "im_korridor"]


def gruppenwoche():
    return [{"gruppe": g, "name": n, "region": r, "direkt": d, "gewichtet": d, "volumen_kg": d * 400,
             "bewertung": b, "mv": 4, "mev": 8, "mav_min": 12, "mav_max": 18, "mrv": 22,
             "hinweis": "Erfundener Hinweis zur Woche."}
            for (g, n, r), b, d in zip(GRUPPEN, BEWERTUNGEN, [14, 7, 5, 19, 2, 12])]


def frische():
    return [{"gruppe": g, "name": n, "region": r, "stunden_seit": 20 + i * 15,
             "frische": [0.3, 0.9, 0.45, 1.0, 0.7, 0.2][i], "bereit_in_stunden": 30 - i * 4,
             "letzte_saetze": 6} for i, (g, n, r) in enumerate(GRUPPEN)]


PROFIL = {"geraete": ["langhantel", "kurzhantel", "bank"], "eingerichtet": True,
          "erfahrung": "fortgeschritten", "ziel": "muskelaufbau", "trainingstage_pro_woche": 3,
          "gewichtsschritt_kg": 2.5, "kurzhantel_max_kg": 30, "koerpergewicht_kg": 78.5,
          "koerpergroesse_cm": 180, "geburtsjahr": 1990, "geschlecht": "m",
          "einschraenkungen": [], "zielbereich_wdh": [6, 12]}


def jetzt_uebung(u, saetze, wdh, kg, quelle, **extra):
    d = {"exercise_id": u[0], "name": u[1], "kategorie": u[2], "equipment": u[3],
         "gruppenname": u[2], "saetze": saetze, "pause_s": 120, "wdh": wdh, "gewicht_kg": kg,
         "gewicht_quelle": quelle, "begruendung": "Erfunden: letzte Einheit sauber geschafft.",
         "gekuerzt_von": None, "ergaenzt": False}
    d.update(extra)
    return d


JETZT = {"minuten": 45, "minuten_quelle": "kalender", "quelle": "plan", "titel": "Oberkörper A",
         "begruendung": "Erfunden: Plantag zwei von drei, Brust ist wieder erholt.",
         "geplante_minuten": 44,
         "uebungen": [jetzt_uebung(UEBUNGEN[0], 4, 8, 72.5, "gemessen"),
                      jetzt_uebung(UEBUNGEN[3], 3, 10, 22, "geschaetzt"),
                      jetzt_uebung(UEBUNGEN[6], 3, 12, None, "fehlt", gekuerzt_von=4),
                      jetzt_uebung(UEBUNGEN[4], 2, 12, 14, "gemessen", ergaenzt=True)],
         "gruppen": ["brust", "schultern"], "plantag": "Oberkörper A", "plantag_id": 2,
         "hinweise": ["Beine sind noch belastet und bleiben heute draußen."],
         "warnungen": ["Klimmzug fehlt die Klimmzugstange."],
         "fehlende_ausruestung": ["Klimmzug"]}


def satz(i, u, nr, kg, wdh, fertig):
    return {"id": i, "exercise_id": u[0], "exercise_name": u[1], "set_number": nr,
            "weight_kg": kg, "reps": wdh, "duration_seconds": None, "distance_meters": None,
            "rpe": 8 if fertig else None, "is_warmup": False, "set_type": "normal",
            "group_id": None, "notes": None, "is_completed": fertig,
            "completed_at": "2026-11-08T10:05:00" if fertig else None}


WORKOUT = {"id": 7, "plan_day_id": 2, "plan_day_name": "Oberkörper A", "name": "Oberkörper A",
           "started_at": "2026-11-08T10:00:00", "finished_at": None, "notes": None, "rating": None,
           "fatigue_level": 2, "sleep_quality": 4, "motivation": 4, "pre_notes": None,
           "sets": [satz(1, UEBUNGEN[0], 1, 72.5, 8, True), satz(2, UEBUNGEN[0], 2, 72.5, 7, True),
                    satz(3, UEBUNGEN[0], 3, 72.5, 8, False), satz(4, UEBUNGEN[3], 1, 22, 10, False),
                    satz(5, UEBUNGEN[3], 2, 22, 10, False)],
           "plan_targets": [{"exercise_id": u[0], "exercise_name": u[1], "target_sets": 3,
                             "target_reps_min": 8, "target_reps_max": 10, "target_rpe": 8,
                             "rest_seconds": 120, "notes": None} for u in (UEBUNGEN[0], UEBUNGEN[3])]}

PLAN = {"id": 1, "name": "Ganzkörper dreimal", "description": "Erfundener Plan", "is_active": True,
        "created_at": "2026-10-01T00:00:00",
        "days": [{"id": 1 + t, "name": n, "day_of_week": dw, "sort_order": t,
                  "exercises": [{"id": 10 * t + k, "exercise_id": u[0], "exercise_name": u[1],
                                 "sort_order": k, "target_sets": 3, "target_reps_min": 8,
                                 "target_reps_max": 12, "target_rpe": 8, "rest_seconds": 90,
                                 "notes": None} for k, u in enumerate(us)]}
                 for t, (n, dw, us) in enumerate([("Unterkörper", 0, UEBUNGEN[1:2] + UEBUNGEN[5:6]),
                                                  ("Oberkörper A", 2, UEBUNGEN[0:1] + UEBUNGEN[3:5]),
                                                  ("Oberkörper B", None, UEBUNGEN[2:3] + UEBUNGEN[6:7])])]}

PR = [{"id": i, "exercise_id": u[0], "exercise_name": u[1], "pr_type": t, "value": v,
       "achieved_at": "2026-11-0%dT10:00:00" % (i + 1), "workout_set_id": None}
      for i, (u, t, v) in enumerate([(UEBUNGEN[0], "max_weight", 75.0), (UEBUNGEN[2], "max_reps", 9),
                                      (UEBUNGEN[1], "max_weight", 100.0)])]

KRAFT = {"exercise_id": 1, "exercise_name": "Bankdrücken", "current_1rm": 88.0, "body_weight": 78.5,
         "ratio": 1.12, "level": "Fortgeschritten",
         "levels": {"Anfänger": 40, "Einsteiger": 60, "Fortgeschritten": 85, "Erfahren": 110, "Elite": 140}}

PROGRESSION = {"exercise_id": 1, "exercise_name": "Bankdrücken", "gewicht_kg": 75, "wdh": 8,
               "letztes_gewicht_kg": 72.5, "letzte_wdh": 8, "art": "steigern",
               "begruendung": "Erfunden: alle Sätze im oberen Bereich geschafft.", "zielbereich": [6, 10],
               "e1rm": 88.0, "e1rm_unsicher": False, "plateau_seit": 0, "gewicht_quelle": "gemessen",
               "aufwaermsaetze": [{"gewicht_kg": 40, "wdh": 8, "anteil": 0.5},
                                  {"gewicht_kg": 60, "wdh": 3, "anteil": 0.8}]}


def registry():
    muskeln = [("brust_mitte", "Brust Mitte", "brust", "vorne"), ("latissimus", "Breiter Rückenmuskel", "ruecken", "hinten"),
               ("delta_vorne", "Vordere Schulter", "schultern", "vorne"), ("delta_seite", "Seitliche Schulter", "schultern", "vorne"),
               ("bizeps_lang", "Bizeps langer Kopf", "arme", "vorne"), ("rectus_femoris", "Gerader Schenkelmuskel", "beine", "vorne"),
               ("gluteus_maximus", "Großer Gesäßmuskel", "beine", "hinten"), ("erector_spinae", "Rückenstrecker", "rumpf", "hinten")]
    return {"regionen": [{"id": "oberkoerper", "name": "Oberkörper"}, {"id": "unterkoerper", "name": "Unterkörper"},
                         {"id": "rumpf", "name": "Rumpf"}],
            "gruppen": [{"id": g, "name": n, "region": r, "ppl": "push", "mv": 4, "mev": 8, "mav_min": 12,
                         "mav_max": 18, "mrv": 22, "erholung_stunden": 48} for g, n, r in GRUPPEN],
            "muskeln": [{"id": i, "name": n, "fachname": i, "gruppe": g, "ansicht": a,
                         "funktion": "Erfundene Funktionsbeschreibung."} for i, n, g, a in muskeln]}


def api(methode, pfad, query, body):
    if not pfad.startswith("/api/"):
        if pfad.startswith("/assets/") or "." in pfad.rsplit("/", 1)[-1]:
            return None
        return Antwort(200, (BUILD / "index.html").read_bytes(), "text/html; charset=utf-8")
    p = pfad[4:]
    if methode != "GET":
        if p == "/workouts":
            return WORKOUT
        return {"ok": True}
    if p == "/progress/summary":
        return {"workouts_7d": 2, "workouts_30d": 9, "total_volume_7d": 12400, "current_streak": 0,
                "last_workout": "2026-11-06", "next_plan_day": "Oberkörper A", "next_plan_day_id": 2,
                "tagestyp": "arbeit", "tagestyp_hinweis": None, "vorschlag_optional": False}
    if p == "/analyse/volumen":
        return gruppenwoche()
    if p == "/analyse/frische":
        return frische()
    if p == "/analyse/verlauf":
        return [{"woche": "2026-%02d-%02d" % (10 + (d > 30), (d - 1) % 30 + 1),
                 "gruppen": {g: 6 + (k * 3 + w) % 9 for k, (g, _, _) in enumerate(GRUPPEN)}}
                for w, d in enumerate(range(5, 61, 7))]
    if p == "/analyse/registry":
        return registry()
    if p == "/analyse/muskeln":
        return {m["id"]: {"saetze": 6, "volumen_kg": 2400, "tage_seit": 2} for m in registry()["muskeln"]}
    if p in ("/progress/prs/recent", "/progress/prs"):
        return PR
    if p == "/profil":
        return PROFIL
    if p == "/profil/geraete":
        return [{"id": g, "name": n, "ersatz": [], "ersatz_namen": [], "hinweis": ""}
                for g, n in [("langhantel", "Langhantel"), ("kurzhantel", "Kurzhanteln"), ("bank", "Flachbank"),
                             ("klimmzugstange", "Klimmzugstange"), ("kabelzug", "Kabelzug")]]
    if p == "/profil/vorlagen":
        return [{"id": "heim", "name": "Heimstudio", "beschreibung": "Erfundene Vorlage", "geraete": ["kurzhantel"]},
                {"id": "gym", "name": "Fitnessstudio", "beschreibung": "Erfundene Vorlage", "geraete": ["langhantel"]}]
    if p == "/profil/luecken":
        return [{"exercise_id": 3, "name": "Klimmzug", "fehlt": ["klimmzugstange"], "fehlt_namen": ["Klimmzugstange"],
                 "mit_ersatz": False, "ersatz_namen": []}]
    if p == "/training/jetzt":
        return JETZT
    if p == "/plans":
        return [{"id": 1, "name": PLAN["name"], "description": PLAN["description"], "is_active": True,
                 "created_at": PLAN["created_at"], "day_count": 3},
                {"id": 2, "name": "Alter Push-Pull-Plan", "description": None, "is_active": False,
                 "created_at": "2026-06-01T00:00:00", "day_count": 4}]
    if p == "/plans/vorlagen":
        return [{"id": "gk3", "name": "Ganzkörper dreimal", "beschreibung": "Erfundene Vorlage", "tage_pro_woche": 3, "passt": True},
                {"id": "ppl", "name": "Drücken, Ziehen, Beine", "beschreibung": "Erfundene Vorlage", "tage_pro_woche": 6, "passt": False}]
    if p.startswith("/plans/"):
        return PLAN
    if p == "/workouts/99":
        return Antwort(503, b'{"error": "Dienst nicht erreichbar"}')
    if p == "/workouts/7":
        return WORKOUT
    if p == "/workouts/last-weights":
        return [{"exercise_id": 1, "weight_kg": 70, "reps": 8, "set_type": "normal"}]
    if p == "/workouts/suggestions":
        return {"exercise_id": int(query.get("exercise_id", 1)), "exercise_name": "Bankdrücken",
                "suggested_weight_kg": 75, "suggested_reps": 8, "last_weight_kg": 72.5, "last_reps": 8,
                "reason": "Erfunden: letzte Einheit geschafft."}
    if p == "/workouts":
        return [{"id": 10 - i, "name": n, "started_at": "2026-11-0%dT18:00:00" % (7 - i),
                 "finished_at": "2026-11-0%dT19:00:00" % (7 - i), "rating": 4, "set_count": 15 + i}
                for i, n in enumerate(["Unterkörper", "Oberkörper B", "Oberkörper A"])]
    if p == "/exercises":
        return [uebung(u) for u in UEBUNGEN]
    if p.startswith("/exercises/") and p.endswith("/progression"):
        return PROGRESSION
    if p.startswith("/exercises/"):
        return uebung(UEBUNGEN[0])
    if p == "/progress/recommendations":
        return {"recommendations": [{"exercise_id": u[0], "exercise_name": u[1], "category": u[2],
                                     "primary_muscles": u[4], "is_compound": u[5],
                                     "reason": "Erfunden: lange nicht trainiert.", "priority_score": 0.8}
                                    for u in UEBUNGEN[:3]], "muscle_balance": {}}
    if p.startswith("/progress/exercise/") and p.endswith("/history"):
        return [{"date": "2026-11-0%d" % d, "workout_id": d, "workout_name": "Oberkörper A",
                 "sets": [satz(100 + d * 3 + k, UEBUNGEN[0], k + 1, 70 + d / 2, 8, True) for k in range(3)]}
                for d in (6, 3, 1)]
    if p.startswith("/progress/exercise/"):
        return [{"date": "2026-%02d-%02d" % (8 + w // 4, 1 + (w % 4) * 7), "estimated_1rm": 78 + w,
                 "best_set_weight": 65 + w, "best_set_reps": 8, "total_volume": 1800 + w * 50} for w in range(12)]
    if p == "/progress/strength-level":
        return KRAFT
    if p == "/progress/volume":
        return [{"week_start": "2026-10-%02d" % d, "total_volume": 9000 + d * 100, "total_sets": 40, "workouts": 3}
                for d in (6, 13, 20, 27)]
    if p == "/progress/calendar":
        return [{"date": "2026-%02d-%02d" % (9 + d // 28, 1 + d % 28), "workouts": 1, "sets": 15}
                for d in range(0, 70, 3)]
    if p == "/progress/readiness":
        return {"daily_averages": [{"date": "2026-11-0%d" % d, "avg_fatigue": 2.5, "avg_sleep": 3.5,
                                    "avg_motivation": 4, "workout_count": 1} for d in range(1, 8)],
                "sleep_correlation": {"high_avg_volume": 5200, "low_avg_volume": 4100,
                                      "high_workout_count": 6, "low_workout_count": 3},
                "fatigue_correlation": {"high_avg_volume": 3900, "low_avg_volume": 5100,
                                        "high_workout_count": 4, "low_workout_count": 5},
                "workouts_with_readiness": 9, "workouts_without_readiness": 2}
    if p == "/progress/aktivitaetsniveau":
        return {"stufe": "mäßig aktiv", "faktor": 1.55, "begruendung": "Erfunden: drei Einheiten je Woche.",
                "trainings_pro_woche": 3, "trainings_im_fenster": 12, "fenster_tage": 28,
                "an_mealprep_uebertragen": True, "belastbar": True}
    if p == "/schritte":
        return {"tage": [{"datum": "2026-11-%02d" % d, "schritte": 6000 + d * 300, "distanz_m": 4500,
                          "aktive_kcal": 300, "quelle": "uhr"} for d in range(1, 9)],
                "heute": 4200, "schnitt": 7400, "aktive_tage": 6, "erfasste_tage": 8}
    if p == "/body/metrics":
        return [{"id": i, "date": "2026-11-0%d" % (8 - i), "weight_kg": 78.5 + i * 0.2, "body_fat_pct": 16.0,
                 "waist_cm": 84, "notes": None} for i in range(5)]
    if p == "/body/trend":
        return [{"date": "2026-10-%02d" % d, "weight_kg": 79 - d / 30, "moving_avg": 79 - d / 32} for d in range(1, 31)]
    if p == "/body/mealprep-ziele":
        return {"verfuegbar": True, "kcal": 2600, "protein_g": 160, "carbs_g": 300, "fat_g": 80, "fiber_g": 35}
    if p == "/body/masse":
        defs = [("brust", "Brust", "links"), ("taille", "Taille", "mitte"), ("oberarm_l", "Oberarm links", "links")]
        return {"allgemein": "Erfundene Anleitung: morgens, entspannt, Band waagerecht.",
                "definitionen": [{"id": i, "name": n, "anleitung": "Erfundene Anleitung.", "seite": s,
                                  "bereich": "oberkoerper"} for i, n, s in defs],
                "aktuell": {"brust": {"wert_cm": 104.5, "datum": "2026-11-01", "vorher_cm": 103.0,
                                      "vorher_datum": "2026-10-01"}}}
    return None


def tab(name):
    def klick(seite):
        seite.get_by_role("button", name=name, exact=True).first.click()
    return klick


SEITEN = [
    {"name": "heute", "pfad": "/"},
    {"name": "training", "pfad": "/workout"},
    {"name": "einheit", "pfad": "/workout/7"},
    {"name": "einheit-fehler", "pfad": "/workout/99", "fehler_erwartet": True},
    {"name": "bereit", "pfad": "/workout", "schritte": [lambda s: s.get_by_role("button", name="Starten (44 min)").click()]},
    {"name": "geloescht", "pfad": "/workout/7", "schritte": [lambda s: s.get_by_label("Satz löschen").first.click()]},
    {"name": "pause", "pfad": "/workout/7", "schritte": [lambda s: s.get_by_label("Satz abhaken").first.click()]},
    {"name": "bewertung", "pfad": "/workout/7", "schritte": [tab("Beenden")]},
    {"name": "koerper", "pfad": "/koerper", "warten": 1500},
    {"name": "zahlen", "pfad": "/zahlen"},
    {"name": "zahlen-verlauf", "pfad": "/zahlen", "schritte": [tab("Verlauf")], "warten": 1800},
    {"name": "zahlen-kraft", "pfad": "/zahlen", "schritte": [tab("Kraft"), lambda s: s.select_option("select", "1")]},
    {"name": "zahlen-alltag", "pfad": "/zahlen", "schritte": [tab("Alltag")]},
    {"name": "zahlen-einheiten", "pfad": "/zahlen", "schritte": [tab("Einheiten")]},
    {"name": "koerper-brust", "pfad": "/koerper", "schritte": [tab("Brust")], "warten": 1500},
    {"name": "profil", "pfad": "/profil"},
    {"name": "plaene", "pfad": "/plans"},
    {"name": "uebungen", "pfad": "/exercises"},
    {"name": "uebung", "pfad": "/exercises/1"},
    {"name": "gewicht", "pfad": "/body", "warten": 1800},
    {"name": "gewicht-neu", "pfad": "/body", "schritte": [tab("+ Messung")]},
]
