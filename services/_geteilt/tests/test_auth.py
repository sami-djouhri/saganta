"""Die Auth-Grenze, die alle Saganta-Backends teilen.

Bis zum 02.09.2026 lag diese Pruefung acht Mal im Baum, und getestet wurde sie
an genau einer Stelle (``shell-api``). Was die anderen sieben taten, stand
nirgends geschrieben und wich an zwei Stellen ab. Deshalb pruefen die Tests hier
ausdruecklich auch das, was frueher als Dienst-Eigenheit durchging: den
Statuscode bei fehlendem Kopf und die Propagation des Mandanten.
"""
import asyncio
import time
import unittest

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from pydantic import BaseModel

from saganta_dienst.auth import (
    Me,
    aktueller_sub,
    baue_pruefer,
    pruefe_bearer,
)

GEHEIMNIS = "test-geheimnis-nur-fuer-die-testsuite"
ALGO = "HS256"
ZIELGRUPPE = "test-api"


class Einstellungen:
    """Steht fuer das ``config.settings`` eines Dienstes."""

    def __init__(self, erlaubte=()):
        self.jwt_secret = GEHEIMNIS
        self.jwt_algorithm = ALGO
        self.allowed_subs = list(erlaubte)


def token(**abweichend) -> str:
    nutzlast = {
        "sub": "nutzer-1",
        "iss": "saganta",
        "aud": ZIELGRUPPE,
        "email": "wer@example.invalid",
        "name": "Wer",
        "groups": [],
        "exp": int(time.time()) + 60,
    }
    nutzlast.update(abweichend)
    return jwt.encode(nutzlast, GEHEIMNIS, algorithm=ALGO)


def bearer(t: str) -> str:
    return f"Bearer {t}"


def pruefe(authorization, erlaubte=()):
    return pruefe_bearer(
        authorization,
        geheimnis=GEHEIMNIS,
        algorithmus=ALGO,
        zielgruppe=ZIELGRUPPE,
        erlaubte_subs=erlaubte,
    )


class PruefeBearerTest(unittest.TestCase):
    def test_gueltiges_token_kommt_durch(self):
        nutzlast = pruefe(bearer(token()))
        self.assertEqual(nutzlast["sub"], "nutzer-1")
        self.assertEqual(nutzlast["email"], "wer@example.invalid")

    def test_fehlender_kopf_ist_401_und_nicht_422(self):
        """★ Der Unterschied, der acht Dienste auseinanderlaufen liess.

        Fuenf Backends deklarierten den Kopf als Pflichtfeld und lieferten
        deshalb 422 (Validierungsfehler), zwei lieferten 401. Ein fehlender
        Anmeldekopf ist keine kaputte Anfrage, sondern eine unangemeldete.
        """
        with self.assertRaises(HTTPException) as f:
            pruefe(None)
        self.assertEqual(f.exception.status_code, 401)

    def test_leerer_kopf_ist_401(self):
        with self.assertRaises(HTTPException) as f:
            pruefe("")
        self.assertEqual(f.exception.status_code, 401)

    def test_ohne_bearer_praefix(self):
        with self.assertRaises(HTTPException) as f:
            pruefe(token())
        self.assertEqual(f.exception.status_code, 401)

    def test_abgelaufenes_token(self):
        with self.assertRaises(HTTPException) as f:
            pruefe(bearer(token(exp=int(time.time()) - 10)))
        self.assertEqual(f.exception.status_code, 401)

    def test_fremde_zielgruppe(self):
        """Ein Token fuer Dienst A darf bei Dienst B nicht gelten."""
        with self.assertRaises(HTTPException) as f:
            pruefe(bearer(token(aud="ein-anderer-dienst")))
        self.assertEqual(f.exception.status_code, 401)

    def test_fremder_aussteller(self):
        with self.assertRaises(HTTPException) as f:
            pruefe(bearer(token(iss="woanders")))
        self.assertEqual(f.exception.status_code, 401)

    def test_gefaelschte_signatur(self):
        echt = token()
        kopf, last, _ = echt.split(".")
        gefaelscht = f"{kopf}.{last}.{'a' * 43}"
        with self.assertRaises(HTTPException) as f:
            pruefe(bearer(gefaelscht))
        self.assertEqual(f.exception.status_code, 401)

    def test_token_ohne_sub(self):
        with self.assertRaises(HTTPException) as f:
            pruefe(bearer(token(sub="")))
        self.assertEqual(f.exception.status_code, 401)

    def test_owner_gate_sperrt_fremde_mit_403(self):
        """403, nicht 401: das Token ist gueltig, der Traeger nur nicht zugelassen."""
        with self.assertRaises(HTTPException) as f:
            pruefe(bearer(token(sub="fremder")), erlaubte=["nur-der-owner"])
        self.assertEqual(f.exception.status_code, 403)

    def test_owner_gate_laesst_zugelassene_durch(self):
        nutzlast = pruefe(bearer(token(sub="nur-der-owner")), erlaubte=["nur-der-owner"])
        self.assertEqual(nutzlast["sub"], "nur-der-owner")

    def test_leeres_gate_ist_offen(self):
        self.assertEqual(pruefe(bearer(token()), erlaubte=[])["sub"], "nutzer-1")


class PrueferAlsAbhaengigkeitTest(unittest.TestCase):
    """Der Weg, den die Dienste tatsaechlich nehmen: als FastAPI-Dependency."""

    def baue_app(self, einstellungen, me_klasse=Me):
        pruefer = baue_pruefer(
            zielgruppe=ZIELGRUPPE, einstellungen=einstellungen, me_klasse=me_klasse
        )
        app = FastAPI()

        @app.get("/wer")
        async def wer(me=Depends(pruefer)):
            # Genau so lesen kalender-bff und projectdeck-api den Mandanten,
            # bevor sie ihn an den nativen Kalender weiterreichen.
            return {"sub": me.sub, "sub_aus_contextvar": aktueller_sub.get()}

        return TestClient(app, raise_server_exceptions=False)

    def test_mandant_erreicht_den_handler(self):
        """★ Die Isolation gegenueber dem nativen Kalender haengt daran.

        Waere die Abhaengigkeit sync, liefe sie im Threadpool und der gesetzte
        ContextVar-Wert waere im Handler wieder weg. Der Kalender fiele dann
        still auf seine Owner-Vorgabe zurueck, statt den Mandanten zu trennen.
        """
        k = self.baue_app(Einstellungen())
        antwort = k.get("/wer", headers={"Authorization": bearer(token(sub="mandant-7"))})
        self.assertEqual(antwort.status_code, 200)
        self.assertEqual(antwort.json()["sub"], "mandant-7")
        self.assertEqual(antwort.json()["sub_aus_contextvar"], "mandant-7")

    def test_ohne_kopf_gibt_401(self):
        k = self.baue_app(Einstellungen())
        self.assertEqual(k.get("/wer").status_code, 401)

    def test_gate_wird_zur_laufzeit_gelesen(self):
        """Die Tests der Dienste stellen ``allowed_subs`` waehrend des Laufs um.

        Wuerde die Fabrik den Wert beim Bauen einfrieren, waeren alle diese
        Tests still wirkungslos und wuerden trotzdem gruen melden.
        """
        e = Einstellungen()
        k = self.baue_app(e)
        self.assertEqual(
            k.get("/wer", headers={"Authorization": bearer(token(sub="wer-auch-immer"))}).status_code,
            200,
        )
        e.allowed_subs = ["nur-der-owner"]
        self.assertEqual(
            k.get("/wer", headers={"Authorization": bearer(token(sub="wer-auch-immer"))}).status_code,
            403,
        )

    def test_eigene_me_klasse_wird_benutzt(self):
        """shell-api liefert sein eigenes ``Me`` aus ``schemas``."""

        class EigenesMe(BaseModel):
            sub: str
            email: str = ""
            name: str | None = None
            groups: list[str] = []

        pruefer = baue_pruefer(
            zielgruppe=ZIELGRUPPE, einstellungen=Einstellungen(), me_klasse=EigenesMe
        )
        me = asyncio.run(pruefer(bearer(token())))
        self.assertIsInstance(me, EigenesMe)
        self.assertEqual(me.sub, "nutzer-1")

    def test_tarif_kommt_aus_dem_token(self):
        pruefer = baue_pruefer(zielgruppe=ZIELGRUPPE, einstellungen=Einstellungen())
        me = asyncio.run(pruefer(bearer(token(plan="pro"))))
        self.assertEqual(me.plan, "pro")

    def test_token_ohne_tarif_ist_free(self):
        """★ Ein BFF, der den Claim noch nicht stempelt, darf nichts verschenken.

        Waere der Rueckfall 'pro' oder ein leerer String, den eine spaetere
        Pruefung als wahr liest, bekaeme jedes Konto waehrend eines
        Teil-Rollouts still Pro.
        """
        pruefer = baue_pruefer(zielgruppe=ZIELGRUPPE, einstellungen=Einstellungen())
        self.assertEqual(asyncio.run(pruefer(bearer(token()))).plan, "free")

    def test_erfundener_tarif_im_token_wird_free(self):
        """Ein manipuliertes oder veraltetes Token darf keinen Tarif erfinden."""
        pruefer = baue_pruefer(zielgruppe=ZIELGRUPPE, einstellungen=Einstellungen())
        for wert in ("premium", "PRO", "", None, "pro "):
            with self.subTest(wert=wert):
                me = asyncio.run(pruefer(bearer(token(plan=wert))))
                self.assertEqual(me.plan, "free")

    def test_eigene_me_klasse_ohne_plan_feld_kracht_nicht(self):
        """shell-api bringt sein eigenes ``Me`` mit, das den Tarif nicht kennt."""

        class MeOhnePlan(BaseModel):
            sub: str
            email: str = ""
            name: str | None = None
            groups: list[str] = []

        pruefer = baue_pruefer(
            zielgruppe=ZIELGRUPPE, einstellungen=Einstellungen(), me_klasse=MeOhnePlan
        )
        me = asyncio.run(pruefer(bearer(token(plan="pro"))))
        self.assertEqual(me.sub, "nutzer-1")
        self.assertFalse(hasattr(me, "plan"))

    def test_einstellungen_ohne_allowed_subs(self):
        """auth-proxy hat kein Owner-Gate; ein fehlendes Feld darf nicht krachen."""

        class OhneGate:
            jwt_secret = GEHEIMNIS
            jwt_algorithm = ALGO

        pruefer = baue_pruefer(zielgruppe=ZIELGRUPPE, einstellungen=OhneGate())
        self.assertEqual(asyncio.run(pruefer(bearer(token()))).sub, "nutzer-1")


if __name__ == "__main__":
    unittest.main()
