"""Der App-Katalog, den das Launchpad anzeigt.

**Die Adressen entstehen aus dem Raum des Aufrufers, sie stehen nicht fertig
hier.** Bis 2026-09-13 taten sie das, mit `https://<name>.saganta.de` fest im
Quelltext, und das hatte drei Folgen:

1. `projectdeck.saganta.de` gibt es nicht (kein DNS, kein Ingress, kein Vhost).
   Die Kachel fuehrte ins Leere, seit es sie gibt.
2. Wer unter `*.home.arpa` arbeitete, wurde vom Launchpad durch den Tunnel
   nach draussen geschickt, in einen anderen Cookie-Raum.
3. Eine fremde Installation dieser Software zeigte auf die Instanz des Autors.

Jeder Eintrag beschreibt deshalb nur seine **Unterdomaene**; ``apps_fuer(raum)``
setzt daraus die Adresse zusammen. Gegenstueck im Frontend ist
``packages/ui/src/apps.ts``, das dieselbe Regel fuer den App-Wechsler traegt.

**Beide muessen dieselben Namen kennen, und geprueft wird das mit
``scripts/app-katalog-abgleich.py``.** Hier stand bis zum 2026-10-16 "die
Pruefung dazu steht in ``tests/test_registry.py``" -- dort stand sie nicht, es
gab keinen Test, der die TS-Datei ueberhaupt anfasst. Eine zugesicherte
Pruefung, die es nicht gibt, ist schlechter als keine, weil man sich beim
Aendern auf sie verlaesst. Der Abgleich liegt bewusst in einem Skript und nicht
im Test: im Image liegt ``packages/`` nicht, der Test muesste also
ueberspringen, und ein Waechter, der im Normalfall ueberspringt, meldet nie
etwas.

⚠️ **Punkt 1 unten gilt weiter, auch nach dem Umbau vom 13.09.** Er war nur auf
der Heim-Seite behoben: ``notizen``, ``aufgaben`` und ``projectdeck`` hatten
unter ``.saganta.de`` weder DNS noch Tunnel-Regel und fuehrten dort weiter ins
Leere. Seit dem 2026-10-16 tragen alle drei ``nur_heim=True``
(Entscheid), gemessen gegen DNS und den Ingress.
"""

from dataclasses import dataclass

from .schemas import AppEntry

#: Raum, wenn der Aufrufer keinen mitgibt. Haelt das Verhalten fuer alte Clients.
STANDARD_RAUM = "saganta.de"


@dataclass(frozen=True)
class AppVorlage:
    """Ein Katalog-Eintrag ohne festgelegte Adresse."""

    id: str
    name: str
    description: str
    icon: str
    #: Unterdomaene im oeffentlichen Raum. Leer = Wurzel der Domaene.
    sub: str
    tags: tuple[str, ...] = ()
    #: Abweichende Unterdomaene im Heim-Raum. Nur, wo die Namen auseinanderlaufen.
    sub_heim: str | None = None
    #: Nur im Heim-Raum vorhanden (bewusst nicht im Tunnel).
    nur_heim: bool = False


VORLAGEN: list[AppVorlage] = [
    AppVorlage(
        id="calendar",
        name="Kalender",
        description="Termine, Tagestypen und Gewohnheiten.",
        # ⚠️ Der eine echte Namensunterschied: oeffentlich `kalender`, im
        # Heimnetz `calendar`. Ein Vertipper trifft den default_server des
        # tardis und landet auf einer fremden Anmeldemaske.
        sub="kalender",
        sub_heim="calendar",
        icon="calendar",
        tags=("core", "productivity"),
    ),
    AppVorlage(
        id="aufgaben",
        name="Aufgaben",
        description=(
            "Aufgaben, Tagesziele und der geplante Tag. Verknuepft mit Projekten, "
            "Notizen und Terminen."
        ),
        sub="aufgaben",
        # Heim-only, Entscheid 2026-10-16. Es gibt kein
        # `aufgaben.saganta.de`: kein DNS, keine Tunnel-Regel, kein Vhost
        # (gemessen NXDOMAIN). Die Kachel fuehrte im oeffentlichen Raum
        # ins Leere, seit es sie gibt -- genau der Fall, den der Umbau vom
        # 13.09. fuer `projectdeck` beschrieb und nur auf der Heim-Seite
        # behob.
        nur_heim=True,
        icon="list-todo",
        tags=("core", "productivity"),
    ),
    AppVorlage(
        id="news",
        name="News",
        description="Nachrichtenquellen und das persoenliche Briefing.",
        sub="news",
        icon="newspaper",
        tags=("core", "family"),
    ),
    AppVorlage(
        id="post",
        name="Post",
        description=(
            "E-Mails und Briefe in einer Inbox. Konten verwalten, Briefkasten "
            "scannen, Vertraege und Fristen."
        ),
        sub="post",
        icon="inbox",
        tags=("core", "productivity"),
    ),
    AppVorlage(
        id="notizen",
        name="Notizen",
        description=(
            "Notizbuecher und Markdown-Notizen mit Anhaengen. Verknuepfbar mit Terminen, "
            "Aufgaben, Projekten, Kontakten und Briefen; teilbar per Link, wahlweise "
            "Ende-zu-Ende-verschluesselt."
        ),
        sub="notizen",
        # Heim-only, Entscheid 2026-10-16. Hier ist der Zustand
        # heikler als bei den anderen beiden: ein nginx-Vhost fuer
        # `notizen.saganta.de` ist **fertig gebaut**, es fehlen nur DNS und
        # Tunnel-Regel (gemessen NXDOMAIN). Dieselbe Lage wie bei
        # `ntfy.saganta.de` am 19.09.: ein halb fertiger Weg ist keine
        # Vorbereitung, sondern eine Landmine, weil ein spaeter
        # dazukommender CNAME ihn unbemerkt scharf macht.
        nur_heim=True,
        icon="file-text",
        tags=("core", "productivity"),
    ),
    AppVorlage(
        id="projectdeck",
        name="ProjectDeck",
        description="Projekte, Entscheidungen und Deadlines im Blick.",
        sub="projectdeck",
        # Heim-only, Entscheid 2026-10-16. Der Docstring oben
        # nennt genau diese Kachel als Anlass fuer den Umbau vom 13.09.;
        # behoben wurde damals nur die Heim-Seite, im oeffentlichen Raum
        # fuehrte sie weiter ins Leere. `projectdeck-api.saganta.de` hat
        # DNS und Tunnel-Regel, die App selbst nicht -- der API-Name
        # antwortet am Edge mit 404 und ist kein Weg hierher.
        nur_heim=True,
        icon="layout-dashboard",
        tags=("core", "productivity"),
    ),
    AppVorlage(
        id="tagebuch",
        name="Tagebuch",
        description="Ein Eintrag je Tag, im Browser verschluesselt. Nur im Heimnetz.",
        # Steht bewusst nicht im Tunnel (Entscheid, siehe
        # apps/tagebuch/README.md). Frueher stand hier eine feste
        # `.home`-Adresse, die von unterwegs ins Leere fuehrte. Jetzt wird die
        # Kachel ausserhalb des Heim-Raums gar nicht erst ausgeliefert.
        sub="tagebuch",
        nur_heim=True,
        icon="book",
        tags=("core", "productivity"),
    ),
    AppVorlage(
        id="assets",
        name="Besitz",
        description="Geraete, Garantien und Marktwerte.",
        sub="assets",
        icon="box",
        tags=("productivity",),
    ),
    AppVorlage(
        id="mealprep",
        name="Mealprep",
        description=(
            "Rezepte, Wochenplan, Makros. Erzeugt die Einkaufsliste aus Plan und Bestand."
        ),
        sub="mealprep",
        icon="utensils",
        tags=("core", "productivity"),
    ),
    AppVorlage(
        id="lager",
        name="Lager",
        description="Haushaltsinventar mit FIFO, Mindestbestand und Barcode.",
        sub="lager",
        icon="archive",
        tags=("core", "productivity"),
    ),
    AppVorlage(
        id="fitness",
        name="Fitness",
        description=(
            "Training, Fortschritt und Ziele. Koppelt Makros und Energiebedarf mit Mealprep."
        ),
        sub="fitness",
        icon="dumbbell",
        tags=("core", "productivity"),
    ),
]


def raum_von(host: str | None) -> str | None:
    """Der Raum eines Hosts: die letzten beiden Labels.

    Rein syntaktisch und ohne Liste erlaubter Domaenen. Der Wert bildet nur
    **eigene** Geschwister-Adressen und entscheidet nichts ueber Vertrauen.

    Eine nackte IP ergibt ``None``: aus ``192.0.2.10`` entstuende sonst der
    Raum ``0.11`` und daraus Adressen wie ``https://notizen.0.11``, also Links,
    die nirgends aufloesen.
    """
    if not host:
        return None
    name = host.strip().strip("[]").lower()
    if ":" in name:
        kopf, _, schwanz = name.rpartition(":")
        # IPv6 hat mehrere Doppelpunkte; nur ein abschliessender Port zaehlt.
        if schwanz.isdigit() and kopf:
            name = kopf
        else:
            return None
    teile = [t for t in name.split(".") if t]
    if len(teile) < 2:
        return None
    if all(t.isdigit() for t in teile):
        return None
    return ".".join(teile[-2:])


def ist_heim_raum(raum: str | None) -> bool:
    return bool(raum) and raum.endswith(".home")  # type: ignore[union-attr]


def adresse(vorlage: AppVorlage, raum: str) -> str:
    sub = (vorlage.sub_heim or vorlage.sub) if ist_heim_raum(raum) else vorlage.sub
    return f"https://{sub}.{raum}" if sub else f"https://{raum}"


def apps_fuer(host: str | None = None) -> list[AppEntry]:
    """Die Apps, die es im Raum dieses Hosts wirklich gibt.

    Ein Eintrag, hinter dem nichts steht, ist schlimmer als ein fehlender: er
    sieht aus wie ein kaputter Dienst, und man sucht den Fehler an der falschen
    Stelle.
    """
    raum = raum_von(host) or STANDARD_RAUM
    heim = ist_heim_raum(raum)
    return [
        AppEntry(
            id=v.id,
            name=v.name,
            description=v.description,
            href=adresse(v, raum),
            icon=v.icon,
            tags=list(v.tags),
        )
        for v in VORLAGEN
        if heim or not v.nur_heim
    ]


#: Rueckwaertskompatibler Name fuer Aufrufer ohne Raum-Kenntnis.
DEFAULT_APPS: list[AppEntry] = apps_fuer(None)
