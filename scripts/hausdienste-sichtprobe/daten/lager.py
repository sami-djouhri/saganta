"""Erfundene Daten fuer lager. Kein Posten, Platz oder Stueck stammt aus dem echten Bestand."""
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from probe import Antwort  # noqa: E402

BUILD = Path("/tmp/sichtprobe-build/lager")
WURZELN = [("/", BUILD)]
HEUTE = "2026-11-08"

GRUENDE = [{"schluessel": k, "name": n} for k, n in
           [("im_einsatz", "Im Einsatz"), ("reparatur", "In Reparatur"), ("verkauf_vorbereiten", "Verkauf vorbereiten")]]


def satz(s, text, n=0, blockiert=False):
    return {"schluessel": s, "text": text, "anzahl": n, "blockiert": blockiert}


def bereich(k, name, bauart, satz_, frist=None, bereit=True):
    return {"schluessel": k, "name": name, "bauart": bauart, "frist": frist, "orte": ["Küche", "Keller"],
            "kategorien": ["Konserven", "Nudeln", "Gewürze"], "bereit": bereit, "gruende": GRUENDE,
            "satz": satz_, "titel_verweis": None}


BEREICHE = [
    bereich("lebensmittel", "Lebensmittel", "vorrat", satz("vorbei", "2 Posten sind über dem MHD.", 2, True), "MHD"),
    bereich("getraenke", "Getränke & Keller", "vorrat", satz("bald", "1 Posten läuft in den nächsten 7 Tagen ab.", 1), "MHD"),
    bereich("haushalt", "Haushalt & Drogerie", "vorrat", satz("knapp", "3 Produkte liegen unter dem Mindestbestand.", 3)),
    bereich("apotheke", "Hausapotheke", "vorrat", satz("ruhig", "6 Posten, nichts läuft bald ab.", 6), "Verfall"),
    bereich("garten", "Garten & Saatgut", "vorrat", satz("leer", "Nichts auf Lager. Posten kommen über Einbuchen herein."), "Keimfähig bis"),
    bereich("werkstatt", "Werkstatt-Material", "fundort", satz("spaeter", "Kommt mit Stufe 6: wo es liegt."), bereit=False),
    bereich("technik", "Technik & Sachen", "stueck", satz("verkauf", "2 Stücke lohnen den Verkauf.", 2)),
    bereich("medien", "Filme & Medien", "exemplar", satz("einlagern", "3 Stücke warten aufs Einlagern.", 3)),
    bereich("kleidung", "Kleidung & Schuhe", "kiste", satz("ruhig", "4 Kisten, alle beschriftet.", 4)),
    bereich("saison", "Saison & Deko", "kiste", satz("leer", "Noch keine Kiste. Kisten stehen an einem Platz und tragen ihren Inhalt.")),
]


def platz(i, kennung, name, art, eltern, pfad, bereich_=None, inhalt=None, kinder=0, posten=0, sachen=0):
    return {"id": i, "kennung": kennung, "name": name, "art": art, "eltern_id": eltern, "pfad": pfad,
            "inhalt": inhalt, "bereich": bereich_, "kinder": kinder, "posten": posten, "sachen": sachen}


PLAETZE = [
    platz(1, "L-001", "Küche", "raum", None, "Küche", kinder=2),
    platz(2, "L-002", "Vorratsschrank", "regal", 1, "Küche › Vorratsschrank", kinder=2, posten=4),
    platz(3, "L-003", "Oberes Fach", "fach", 2, "Küche › Vorratsschrank › Oberes Fach", posten=3),
    platz(4, "L-004", "Unteres Fach", "fach", 2, "Küche › Vorratsschrank › Unteres Fach", posten=1),
    platz(5, "L-005", "Keller", "raum", None, "Keller", kinder=3),
    platz(6, "L-006", "Schwerlastregal", "regal", 5, "Keller › Schwerlastregal", kinder=1, sachen=3),
    platz(7, "L-007", "Winterkiste", "kiste", 5, "Keller › Winterkiste", "kleidung", "Mützen, Schals, zwei Paar Handschuhe"),
    platz(8, "L-008", "Sommerkiste", "kiste", 5, "Keller › Sommerkiste", "kleidung", None),
    platz(9, "L-009", "Arbeitszimmer", "raum", None, "Arbeitszimmer", sachen=4),
]


def posten(i, name, menge, einheit, mhd, tage, platz_id=3):
    p = next(x for x in PLAETZE if x["id"] == platz_id)
    return {"id": i, "product_id": 100 + i, "product_name": name, "quantity": menge, "unit": einheit,
            "mhd": mhd, "purchase_date": "2026-10-20", "location": p["name"], "platz_id": platz_id,
            "platz_kennung": p["kennung"], "platz_pfad": p["pfad"], "days_until_expiry": tage,
            "opened_at": "2026-11-01T10:00:00" if i == 2 else None, "preis": 1.49, "eingangsmenge": menge,
            "einkauf_id": None}


POSTEN = [
    posten(1, "Joghurt Natur (Beispiel)", 2, "Stück", "2026-11-05", -3),
    posten(2, "Haferdrink ungesüßt", 1, "l", "2026-11-07", -1),
    posten(3, "Tomaten passiert", 3, "Packung", "2026-11-12", 4, 4),
    posten(4, "Spaghetti Nr. 5 aus Hartweizengrieß in der Großpackung", 1500, "g", "2027-08-01", 266),
    posten(5, "Kichererbsen", 4, "Dose", "2028-01-01", 419),
    posten(6, "Salz", 500, "g", None, None),
]


def produkt(i, name, kat, mindest=None):
    return {"id": i, "name": name, "bereich": "lebensmittel", "barcode": "4000000000%03d" % i, "category": kat,
            "default_unit": "Stück", "nutrition_per_100": None, "typical_pack_sizes": [1], "shelf_life_type": "mhd",
            "shelf_life_days_default": 14, "image_url": None, "synonyms": [], "min_stock": mindest,
            "min_stock_unit": "Stück" if mindest else None}


PRODUKTE = [produkt(100 + p["id"], p["product_name"], ["Kühlung", "Kühlung", "Konserven", "Nudeln", "Konserven", "Gewürze"][k],
                    2 if k == 4 else None) for k, p in enumerate(POSTEN)]


def sache(i, name, platz_id, verbleib="eingelagert", grund=None, **extra):
    p = next((x for x in PLAETZE if x["id"] == platz_id), None)
    d = {"id": i, "kennung": "S-%04d" % i, "name": name, "titel_id": None, "teil": None, "edition": None,
         "medium": None, "medientyp": None, "category": "Computer", "brand": "Beispielmarke", "model": "Modell X",
         "serial": "SN-BEISPIEL-%d" % i, "barcode": None, "condition": "Gut", "status": "aktiv", "bereich": "technik",
         "location": p["name"] if p else "", "platz_id": platz_id if p else None, "platz_kennung": p["kennung"] if p else None,
         "platz_pfad": p["pfad"] if p else "", "verbleib": verbleib, "shopfloor_grund": grund,
         "usage_status": "daily_use" if grund == "im_einsatz" else "reserve", "in_active_use": grund == "im_einsatz",
         "purchase_date": "2024-03-01", "purchase_price": 199.0, "purchase_source": "Beispielladen",
         "purchase_url": None, "warranty_end": "2027-03-01", "estimated_resale_value": 90.0,
         "market_value_eur": 85.0, "market_value_at": "2026-11-01T08:00:00", "effective_market_value": 85.0,
         "resale_confidence": "mittel", "sell_decision": "behalten", "sell_reason": None, "desired_min_profit": None,
         "manual_pin": False, "estimated_profit": None, "ebay_item_id": None, "ebay_watch_query": None,
         "external_refs": {}, "notes": None, "foto": None, "einkauf_id": None,
         "created_at": "2026-10-01T10:00:00", "updated_at": "2026-11-01T10:00:00"}
    d.update(extra)
    return d


SACHEN = [
    sache(1, "Beispiel-Laptop 14 Zoll", 9, "shopfloor", "im_einsatz"),
    sache(2, "Externe Festplatte 2 TB", 6),
    sache(3, "Alter Tablet-Rechner", 6, sell_decision="verkaufen", sell_reason="Erfunden: lohnt den Verkauf"),
    sache(4, "Funkkopfhörer", 0, "vermisst"),
    sache(5, "Ersatz-Netzteil 65 W", 6),
]


def dinge_fuer(pid):
    d = [{"art": "posten", "id": p["id"], "name": p["product_name"], "bereich": "lebensmittel",
          "detail": f'{p["quantity"]} {p["unit"]}', "platz_id": pid, "platz_pfad": p["platz_pfad"],
          "shopfloor_grund": None, "kennung": None, "foto": None, "mhd": p["mhd"]}
         for p in POSTEN if p["platz_id"] == pid]
    d += [{"art": "sache", "id": s["id"], "name": s["name"], "bereich": "technik", "detail": s["condition"],
           "platz_id": pid, "platz_pfad": s["platz_pfad"], "shopfloor_grund": None, "kennung": s["kennung"],
           "foto": None, "mhd": None} for s in SACHEN if s["platz_id"] == pid]
    return d


def seite(items):
    return {"items": items, "total": len(items), "offset": 0, "limit": 100}


def api(methode, pfad, query, body):
    if not pfad.startswith("/api/"):
        if pfad.startswith("/assets/") or pfad.startswith("/vendor/") or "." in pfad.rsplit("/", 1)[-1]:
            return None
        return Antwort(200, (BUILD / "index.html").read_bytes(), "text/html; charset=utf-8")
    p = pfad[4:]
    if methode != "GET":
        return {"ok": True}
    if p == "/bereiche":
        return BEREICHE
    if p == "/stock":
        items = POSTEN[:1] if query.get("limit") == "1" else POSTEN
        return {**seite(items), "total": len(POSTEN)}
    if p == "/products":
        return {**seite(PRODUKTE[:1] if query.get("limit") == "1" else PRODUKTE), "total": len(PRODUKTE)}
    if p == "/stats/expiry-forecast":
        return [{"product_name": x["product_name"], "quantity": x["quantity"], "unit": x["unit"], "mhd": x["mhd"],
                 "days_left": x["days_until_expiry"],
                 "urgency": "abgelaufen" if (x["days_until_expiry"] or 99) < 0 else "bald",
                 "location": x["location"]} for x in POSTEN[:3]]
    if p == "/stats/low-stock":
        return [{"product_id": 105, "product_name": "Kichererbsen", "current_stock": 1, "min_stock": 2,
                 "min_stock_unit": "Dose", "deficit": 1}]
    if p == "/stats/consumption":
        return [{"product_id": 100 + i, "product_name": x["product_name"], "total_amount": 3 + i, "unit": x["unit"],
                 "event_count": 2 + i} for i, x in enumerate(POSTEN[:4])]
    if p == "/stats/waste":
        return {"total_events": 2, "total_amount": 3, "by_product": [
            {"product_id": 101, "product_name": "Joghurt Natur (Beispiel)", "total_amount": 2, "unit": "Stück", "event_count": 1}]}
    if p.startswith("/stats/categor") or p.startswith("/analytics"):
        return [{"category": k, "active_items": 4, "expired_in_stock": 1 if k == "Kühlung" else 0,
                 "waste_percent": 12.5 if k == "Kühlung" else 0, "waste_unit": "Stück", "events_total": 8,
                 "events_discarded": 1, "by_unit": []} for k in ("Kühlung", "Konserven", "Nudeln")]
    if p == "/plaetze":
        return PLAETZE
    if p.startswith("/plaetze/"):
        pid = int(p.rsplit("/", 1)[-1])
        pl = next((x for x in PLAETZE if x["id"] == pid), PLAETZE[0])
        return {"platz": pl, "unterplaetze": [x for x in PLAETZE if x["eltern_id"] == pl["id"]], "dinge": dinge_fuer(pl["id"])}
    if p == "/shopfloor":
        return {"anzahl": 3, "gruppen": [
            {"grund": None, "name": "Noch nicht eingelagert", "dinge": dinge_fuer(3)[:2]},
            {"grund": "im_einsatz", "name": "Im Einsatz", "dinge": [
                {"art": "sache", "id": 1, "name": SACHEN[0]["name"], "bereich": "technik", "detail": "Gut",
                 "platz_id": 9, "platz_pfad": "Arbeitszimmer", "shopfloor_grund": "im_einsatz", "kennung": "S-0001",
                 "foto": None, "mhd": None}]}]}
    if p == "/electronics/portfolio":
        return {"total_assets": 5, "market_value_total": 425.0, "valued_count": 5, "purchase_total": 995.0,
                "delta_vs_purchase": -570.0, "delta_count": 5,
                "categories": [{"category": "Computer", "count": 5, "market_value": 425.0}],
                "resale_recommendations": [{"asset_id": 3, "name": "Alter Tablet-Rechner", "market_value_eur": 85.0,
                                            "reason": "Erfunden: Wert fällt"}]}
    if p == "/electronics":
        if query.get("abgegangen") == "true":
            return seite([sache(9, "Verkaufter Monitor", 0, "weg", status="verkauft")])
        return seite(SACHEN)
    if p == "/einkaeufe":
        return [{"id": 1, "bereich": "lebensmittel", "am": "2026-11-07T17:00:00", "laden": "Beispielmarkt",
                 "gesamt": 23.4, "posten": 6, "sachen": 0, "einzelpreise": 18.9, "ohne_preis": 2, "verteilt": {}}]
    if p == "/shopping-list":
        return [{"product_id": 105, "product_name": "Kichererbsen", "suggested_quantity": 2, "unit": "Dose",
                 "reason": "unter Mindestbestand", "current_stock": 1}]
    if p == "/medien/titel":
        return []
    return None


def klick(name):
    def k(seite_):
        seite_.get_by_role("button", name=name).first.click()
    return k


SEITEN = [
    {"name": "start", "pfad": "/"},
    {"name": "vorrat", "pfad": "/b/lebensmittel"},
    {"name": "bestand", "pfad": "/b/lebensmittel/bestand"},
    {"name": "einbuchen", "pfad": "/b/lebensmittel/einbuchen"},
    {"name": "ausbuchen", "pfad": "/b/lebensmittel/ausbuchen"},
    {"name": "produkte", "pfad": "/b/lebensmittel/produkte"},
    {"name": "statistik", "pfad": "/b/lebensmittel/statistik"},
    {"name": "statistik-kategorien", "pfad": "/b/lebensmittel/statistik", "schritte": [klick("Kategorien")]},
    {"name": "produkt-bearbeiten", "pfad": "/b/lebensmittel/produkte", "schritte": [klick("Salz")]},
    {"name": "bestand-auswahl", "pfad": "/b/lebensmittel/bestand", "schritte": [klick("Mehrere auswählen")]},
    {"name": "lauf", "pfad": "/b/lebensmittel/lauf"},
    {"name": "technik", "pfad": "/b/technik"},
    {"name": "kisten", "pfad": "/b/kleidung"},
    {"name": "plaetze", "pfad": "/plaetze"},
    {"name": "platz", "pfad": "/plaetze/2"},
    {"name": "shopfloor", "pfad": "/shopfloor"},
    {"name": "lagern", "pfad": "/lagern"},
    {"name": "einkaufsliste", "pfad": "/einkaufsliste"},
]
