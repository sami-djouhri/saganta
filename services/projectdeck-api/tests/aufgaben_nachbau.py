"""Der Aufgaben-Dienst im Speicher, fuer die Tests dieses Dienstes.

Seine eigenen Regeln prueft `services/aufgaben-api/tests`; hier steht nur so
viel, wie die Routen des ProjectDecks brauchen.
"""

import uuid

import httpx

from app import aufgaben_dienst


def _fehler(code: int, detail: str):
    anfrage = httpx.Request("GET", "http://aufgaben-api")
    antwort = httpx.Response(code, json={"detail": detail}, request=anfrage)
    return httpx.HTTPStatusError(detail, request=anfrage, response=antwort)


class Nachbau:
    """Der Aufgaben-Dienst im Speicher, gerade genug fuer diese Routen."""

    def __init__(self):
        self.aufgaben: dict[str, dict] = {}
        self.aufrufe: list[tuple[str, str, dict]] = []
        self.aus = False

    def __call__(self, me, methode, pfad, **kw):
        self.aufrufe.append((methode, pfad, kw))
        if self.aus:
            raise aufgaben_dienst.AufgabenNichtErreichbar("aus")
        teile = pfad.strip("/").split("/")[1:]  # ohne "api"
        if teile == ["aufgaben"] and methode == "GET":
            p = kw.get("params") or {}
            if "herkunft" in p:
                return [a for a in self.aufgaben.values() if a.get("herkunft") == p["herkunft"]]
            erledigte = bool(p.get("erledigte"))
            return [a for a in self.aufgaben.values()
                    if a["erledigt"] == erledigte and ("projekt" not in p or a["projekt"] == p["projekt"])]
        if teile == ["aufgaben"] and methode == "POST":
            a = {"id": str(uuid.uuid4()), "erledigt": False, "wartet": False, "dauer_min": None,
                 "faellig": None, "projekt": None, **kw["json"]}
            self.aufgaben[a["id"]] = a
            return a
        if teile == ["projekte", "zaehlung"]:
            je: dict[str, dict[str, int]] = {}
            for a in self.aufgaben.values():
                if a["projekt"]:
                    z = je.setdefault(a["projekt"], {"offen": 0, "erledigt": 0, "hoch": 0})
                    z["erledigt" if a["erledigt"] else "offen"] += 1
                    if not a["erledigt"] and a.get("prioritaet") == "hoch":
                        z["hoch"] += 1
            return je
        if teile[:1] == ["projekte"] and teile[2:] == ["loesen"]:
            n = 0
            for a in self.aufgaben.values():
                if a["projekt"] == teile[1]:
                    a["projekt"] = None
                    n += 1
            return {"geloest": n}
        if teile[:1] == ["aufgaben"]:
            a = self.aufgaben.get(teile[1])
            if a is None:
                raise _fehler(404, "Aufgabe nicht gefunden")
            if methode == "GET":
                return a
            if methode == "PUT":
                a.update(kw["json"])
                return a
            if methode == "DELETE":
                del self.aufgaben[teile[1]]
                return None
            if teile[2:] == ["erledigt"]:
                a["erledigt"] = True
                return a
            if teile[2:] == ["offen"]:
                a["erledigt"] = False
                return a
        raise AssertionError(f"unerwarteter Aufruf {methode} {pfad}")
