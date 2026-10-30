"""Der App-Katalog bildet Adressen im Raum des Aufrufers.

Jeder Test hier faellt gegen die Fassung von vor 2026-09-13, in der die
Adressen als fertige `.de`-URLs im Quelltext standen.
"""

from app.registry import VORLAGEN, apps_fuer, ist_heim_raum, raum_von


class TestRaumVon:
    def test_nimmt_die_letzten_beiden_labels(self) -> None:
        assert raum_von("notizen.home.arpa") == "home.arpa"
        assert raum_von("kalender.saganta.de") == "saganta.de"
        assert raum_von("saganta.de") == "saganta.de"

    def test_ignoriert_port_und_grossschreibung(self) -> None:
        assert raum_von("Notizen.home.arpa:8443") == "home.arpa"

    def test_ohne_raum_kommt_none(self) -> None:
        assert raum_von("localhost") is None
        assert raum_von("localhost:3000") is None
        assert raum_von("") is None
        assert raum_von(None) is None

    def test_nackte_ip_hat_keinen_raum(self) -> None:
        # Sonst entstuende aus 192.0.2.10 der Raum "0.11" und daraus Adressen
        # wie https://notizen.0.11, also Links, die nirgends aufloesen.
        assert raum_von("192.0.2.10") is None
        assert raum_von("192.0.2.10:8080") is None


class TestIstHeimRaum:
    def test_trennt_heim_von_oeffentlich(self) -> None:
        assert ist_heim_raum("home.arpa") is True
        assert ist_heim_raum("saganta.de") is False
        assert ist_heim_raum(None) is False


class TestAppsFuer:
    def _href(self, apps: list, app_id: str) -> str | None:
        for a in apps:
            if a.id == app_id:
                return a.href
        return None

    def test_bleibt_im_raum_des_aufrufers(self) -> None:
        # Hier stand bis zum 2026-10-16 `notizen`, das seitdem heim-only ist
        # (kein DNS auf `.de`, gemessen). `post` steht in beiden Raeumen und
        # zeigt denselben Punkt: die Adresse entsteht aus dem Raum des
        # Aufrufers.
        heim = apps_fuer("shell.home.arpa")
        assert self._href(heim, "post") == "https://post.home.arpa"
        oeffentlich = apps_fuer("saganta.de")
        assert self._href(oeffentlich, "post") == "https://post.saganta.de"
        # Und der heim-only-Fall, am Beispiel von notizen.
        assert self._href(heim, "notizen") == "https://notizen.home.arpa"
        assert self._href(oeffentlich, "notizen") is None

    def test_kennt_den_kalender_sonderfall(self) -> None:
        # ⚠️ Im Heimnetz `calendar`, oeffentlich `kalender`. Ein Vertipper trifft
        # den default_server des tardis und sieht eine fremde Anmeldemaske.
        assert self._href(apps_fuer("shell.home.arpa"), "calendar") == (
            "https://calendar.home.arpa"
        )
        assert self._href(apps_fuer("saganta.de"), "calendar") == "https://kalender.saganta.de"

    def test_tagebuch_nur_im_heim(self) -> None:
        # Es liegt bewusst nicht im Tunnel. Eine Kachel im oeffentlichen Raum
        # waere eine Tuer, hinter der nichts ist.
        assert self._href(apps_fuer("shell.home.arpa"), "tagebuch") is not None
        assert self._href(apps_fuer("saganta.de"), "tagebuch") is None

    def test_ohne_host_gilt_der_oeffentliche_raum(self) -> None:
        assert self._href(apps_fuer(None), "post") == "https://post.saganta.de"

    def test_aufgaben_ist_dabei(self) -> None:
        # Sie ist die zwoelfte App und fehlte lange ganz. Im Heim-Raum.
        assert self._href(apps_fuer("shell.home.arpa"), "aufgaben") == (
            "https://aufgaben.home.arpa"
        )

    def test_die_drei_kachelnamen_ohne_dns_sind_heim_only(self) -> None:
        """Entscheid 2026-10-16, nachdem gemessen wurde.

        ``notizen``, ``aufgaben`` und ``projectdeck`` haben unter ``.saganta.de``
        weder DNS noch Tunnel-Regel (gemessen NXDOMAIN gegen 1.1.1.1, waehrend
        die uebrigen acht Namen je zwei A-Saetze tragen). Im oeffentlichen Raum
        war das eine Kachel, hinter der nichts ist -- und zwar, bei
        ``projectdeck``, seit es sie gibt: der Docstring der Registry nennt genau
        diesen Fall als Anlass fuer den Umbau vom 13.09., behoben wurde damals
        nur die Heim-Seite.

        ⚠️ Bei ``notizen`` steht zusaetzlich ein **fertiger** nginx-Vhost auf
        ``.de``, dem nur DNS fehlt. Wer die Kachel wieder oeffentlich macht,
        legt Ingress UND DNS in einem Vorgang an, sonst entsteht wieder der
        Zustand von ``ntfy.saganta.de`` am 19.09.
        """
        oeffentlich = apps_fuer("saganta.de")
        heim = apps_fuer("shell.home.arpa")
        for app_id in ("notizen", "aufgaben", "projectdeck"):
            assert self._href(oeffentlich, app_id) is None, app_id
            assert self._href(heim, app_id) is not None, app_id

    def test_im_oeffentlichen_raum_bleibt_keine_leere_kachel(self) -> None:
        """Die Gegenrichtung: alles, was oeffentlich steht, hat auch DNS.

        Die Liste ist hier **gemessen** und nicht abgeschrieben (2026-10-16,
        A- und AAAA-Saetze gegen 1.1.1.1 plus der Ingress im
        ``saganta``-Tunnel auf node1). Ein Test kann kein DNS fragen; er kann
        aber festhalten, dass der Katalog nicht ueber diese Menge hinauswaechst,
        ohne dass jemand die Messung wiederholt.
        """
        mit_dns = {
            "", "shell", "news", "kalender", "assets", "post",
            "fitness", "mealprep", "lager", "mail", "nachrichten",
        }
        for app in apps_fuer("saganta.de"):
            name = app.href.removeprefix("https://").removesuffix(".saganta.de")
            if name == "saganta.de":  # die Wurzel selbst
                name = ""
            assert name in mit_dns, (
                f"{app.id} zeigt oeffentlich auf '{name}.saganta.de'. Dieser Name "
                "stand am 2026-10-16 nicht in der gemessenen Menge. Entweder DNS "
                "und Ingress in einem Vorgang anlegen und hier ergaenzen, oder "
                "nur_heim=True setzen."
            )

    def test_keine_doppelte_id(self) -> None:
        ids = [v.id for v in VORLAGEN]
        assert len(set(ids)) == len(ids)

    def test_keine_adresse_zeigt_auf_eine_fremde_domaene(self) -> None:
        # Der Kern des Befunds: eine fremde Installation zeigte auf die Instanz
        # des Autors. Jetzt endet jede Adresse im uebergebenen Raum.
        for app in apps_fuer("saganta.beispiel"):
            assert app.href.endswith(".saganta.beispiel") or app.href == (
                "https://saganta.beispiel"
            )
