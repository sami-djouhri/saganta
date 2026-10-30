"""Der Text von saganta.de, aus dem `bauen.py` die Seiten erzeugt.

Jede Funktion, die hier steht, ist am Quelltext der Oberflaeche belegt
(Erhebung 2026-10-30, je Punkt mit Datei und Zeile, gegengeprueft an
Stichproben). Was halb gebaut ist oder zum abgeschafften Bezahlmodell gehoert
(Pro-Abzeichen, Abo-Abschnitt, Stripe), steht bewusst NICHT hier.

`id` ist die Kennung aus `packages/ui/src/apps.ts`. `abgleich.py` vergleicht
Name und Kennung mit dem Katalog in beide Richtungen. `seite` ist der
Dateiname auf saganta.de und darf deutsch sein, weil er eine Adresse ist und
kein Bezeichner.

Regeln fuer jeden Satz hier (Owner, 2026-10-06): Produkte beim Namen nennen,
das kuerzere Wort nehmen, und der Satz muss woertlich stimmen.
"""

START = {
    "titel": "Elf Apps für den Alltag einer Familie, auf eigener Hardware",
    "beschreibung": (
        "Saganta ist eine Suite aus elf Apps für Kalender, Aufgaben, Notizen, Post "
        "und mehr. Sie läuft auf einem Rechner im eigenen Haus."
    ),
    "anriss": (
        "Kalender, Aufgaben, Notizen, Post und die übrigen teilen eine Anmeldung, "
        "ein Aussehen und ihre Daten untereinander. Saganta läuft auf einem Rechner "
        "im eigenen Haus. Die Daten verlassen es nicht."
    ),
    "bild_alt": "Die Übersicht von Saganta nach der Anmeldung, mit Beispieldaten.",
    "zusammen": (
        "Dass sie zusammen liegen, ist der Zweck: MealPrep zieht den Vorrat aus dem "
        "Lager von der Einkaufsliste ab, das Tagebuch zeigt die Termine des Tages, "
        "und an jedem Termin, jeder Aufgabe und jedem Projekt lässt sich direkt eine "
        "Notiz anlegen."
    ),
    "telefon": (
        "Kalender, Notizen, Fitness und ProjectDeck gibt es zusätzlich als eigene "
        "Apps für Android und Linux. Kalender und Fitness nehmen Einträge auch ohne "
        "Verbindung an und tragen sie nach, sobald das Telefon wieder im Heimnetz ist."
    ),
    "technik": [
        "<b>Oberflächen</b> in SvelteKit, je App eine eigene",
        "<b>Dienste</b> in Python mit FastAPI, dahinter SQLite",
        "<b>Anmeldung</b> über better-auth, einmal für alle Apps",
        "<b>Telefon-Apps</b> in Kotlin mit Compose Multiplatform",
        "<b>Betrieb</b> in Docker, auf einem Raspberry Pi 5",
        "<b>Daten</b> je Nutzer getrennt, an jedem Dienst einzeln geprüft",
    ],
    "technik_mehr": (
        'Der Quelltext steht unter der '
        '<a href="https://www.gnu.org/licenses/agpl-3.0.html" rel="noopener">AGPL-3.0</a> '
        'auf <a href="https://github.com/sami-djouhri/saganta" rel="noopener">GitHub</a>. '
        'Wie die Teile zusammenhängen, steht ausführlich in der '
        '<a href="https://djouhri.de/projekte/saganta" rel="noopener">Fallstudie</a>.'
    ),
    "privat": (
        "Saganta ist die private Suite einer Familie. Es gibt keine Anmeldung aus "
        "dem Internet und keine Registrierung. Diese Seite beschreibt die Suite, sie "
        "ist kein Zugang zu ihr."
    ),
    "anfrage": (
        "Wer so etwas für sich zuhause haben möchte, kann es einrichten lassen: auf "
        "einem eigenen Rechner, mit den eigenen Daten, ohne Zugang von außen."
    ),
}

APPS = [
    {
        "id": "calendar",
        "seite": "kalender",
        "name": "Kalender",
        "kurz": "Termine, der geplante Tag, Gewohnheiten",
        "beschreibung": "Der Kalender von Saganta: Termine, Tagesplanung und Gewohnheiten.",
        "satz": (
            "Termine planen und den Tag einteilen. Der Kalender weiß auch, wie viel Kraft "
            "heute da ist und wie viel davon schon verplant ist."
        ),
        "bild_alt": "Die Wochenansicht des Kalenders mit der Tagesplanung daneben.",
        "funktionen": [
            "Monat, Woche und Agenda, in der Wochenansicht legt ein Klick auf eine Stunde einen Termin an",
            "Termine aus einem Satz anlegen: „Vertrag kündigen am 30.09.“ wird zu einem Vorschlag für Termin oder Aufgabe",
            "„Dein Tag“: Energie, Schlaf und Verfassung eintragen, daraus ergibt sich, wie voll der Tag sein darf",
            "Die Tagesdecke: der wache Tag als lückenlose Folge von Blöcken, umzuordnen per Ziehen, auch mit dem Finger",
            "Gewohnheiten mit Wochenfortschritt. Der Kalender schlägt Zeiten vor, man nimmt an, verwirft oder startet sofort",
            "„Feierabend heute“ sagt den Rest des Tages ab und verteilt ihn auf die nächsten Tage",
            "Rückblick: wie der Tag lief und wofür die Zeit verwendet wurde",
        ],
        "verbindungen": [
            "Am Termin legt „Notiz dazu“ eine Notiz an, die mit dem Termin verknüpft ist",
            "Fristen aus Post und Artikel aus News lassen sich mit einem Klick in den Kalender übernehmen",
            "Der Tagestyp (Arbeit, frei, Urlaub) steht auch Fitness und MealPrep zur Verfügung",
        ],
        "telefon": "Den Kalender gibt es auch als App fürs Telefon, mit Offline-Betrieb.",
    },
    {
        "id": "aufgaben",
        "seite": "aufgaben",
        "name": "Aufgaben",
        "kurz": "Was heute dran ist, mit Tagesplan",
        "beschreibung": "Die Aufgaben-App von Saganta: Aufgabenliste mit Tagesplan.",
        "satz": "Eine Aufgabenliste, die von heute aus denkt: was fällig ist, was liegen bleibt, und wann es in den Tag passt.",
        "bild_alt": "Die Aufgaben für heute mit einem vorgeschlagenen Tagesplan.",
        "funktionen": [
            "„Heute“ nach überfällig, heute fällig und später geordnet, mit Anzeige, wie voll der Tag ist",
            "„Tag planen“ rechnet Uhrzeiten für die Aufgaben vor und begründet jede, übernommen wird erst auf Knopfdruck",
            "Schnell erfassen mit Priorität, Dauer und Projekt",
            "Verschieben auf morgen oder nächste Woche, und ein Hinweis bei Aufgaben, die immer wieder verschoben werden",
            "Tagesziele mit Priorität A, B und C",
            "Alle Aufgaben mit Suche und Filtern, dazu Erledigt und nach Projekt",
        ],
        "verbindungen": [
            "Projekte kommen aus ProjectDeck",
            "An jeder Aufgabe lässt sich eine Notiz anlegen oder eine vorhandene anhängen",
            "Die Aufgaben liegen in derselben Datenbank wie der Kalender",
        ],
    },
    {
        "id": "notizen",
        "seite": "notizen",
        "name": "Notizen",
        "kurz": "Notizbücher, Anhänge, Verknüpfungen",
        "beschreibung": "Die Notizen von Saganta: Markdown, Notizbücher, Anhänge und Verknüpfungen.",
        "satz": "Notizen in Markdown, geordnet in Notizbüchern und mit Tags, verknüpft mit allem, worauf sie sich beziehen.",
        "bild_alt": "Eine Notiz mit Anhang und Verknüpfungen zu Termin und Projekt.",
        "funktionen": [
            "Volltextsuche über Titel, Text und Tags",
            "Notizbücher und Tags",
            "Anheften, archivieren, Anhänge hochladen",
            "Teilen per Link mit Ablaufdatum, Passwort oder einmaligem Abruf, auf Wunsch im Browser verschlüsselt",
            "Übersicht aller geteilten Links, jeder einzeln widerrufbar",
        ],
        "verbindungen": [
            "Eine Notiz lässt sich mit einem Termin, einer Aufgabe, einem Projekt, einem Kontakt oder einem Brief verknüpfen",
            "Umgekehrt entsteht eine Notiz direkt am Termin, an der Aufgabe oder am Projekt",
        ],
        "telefon": "Die Notizen gibt es auch als App fürs Telefon, offline lesbar.",
    },
    {
        "id": "post",
        "seite": "post",
        "name": "Post",
        "kurz": "E-Mails und eingescannte Briefe",
        "beschreibung": "Die Post-App von Saganta: E-Mail-Konten und eingescannte Briefe in einem Eingang.",
        "satz": "Ein Eingang für alle E-Mail-Konten und für die Briefe, die auf Papier kommen und eingescannt werden.",
        "bild_alt": "Der Posteingang mit der Übersicht über Verträge und Fristen.",
        "funktionen": [
            "E-Mail-Konten über IMAP und SMTP verbinden, E-Mails lesen und schreiben",
            "Briefe scannen oder hochladen, die Texterkennung macht sie durchsuchbar",
            "Suche über alles, bei Briefen auch im erkannten Text",
            "Verträge und Fristen: Kündigungsfrist und Monatsbetrag auf einen Blick",
            "Briefe archivieren oder in 7, 14, 30 oder 90 Tagen wieder vorlegen lassen",
        ],
        "verbindungen": [
            "„Frist in den Kalender“ trägt eine Kündigungsfrist als Termin ein",
            "Briefe lassen sich mit Notizen verknüpfen",
        ],
    },
    {
        "id": "news",
        "seite": "news",
        "name": "News",
        "kurz": "Nachrichten und das tägliche Briefing",
        "beschreibung": "News in Saganta: Nachrichtenquellen und ein tägliches Briefing, auch zum Anhören.",
        "satz": "Nachrichten aus selbst gewählten Quellen, und jeden Morgen ein Briefing, das man lesen oder anhören kann.",
        "bild_alt": "Das Morgen-Briefing mit Wiedergabe der Sprachfassung.",
        "funktionen": [
            "Artikel nach Quelle filtern, merken, als gelesen markieren",
            "Ein tägliches Briefing nach eigenen Themen und dem eigenen Ort",
            "Jeder Punkt im Briefing lässt sich abhaken oder mit „mehr davon“ und „weniger davon“ bewerten",
            "Das Briefing als Sprachfassung, auch als privater Podcast-Feed",
            "Anbindung an Home Assistant, etwa für die Ansage am Morgen",
        ],
        "verbindungen": [
            "„Im Kalender notieren“ am Artikel und im Briefing",
        ],
    },
    {
        "id": "projectdeck",
        "seite": "projectdeck",
        "name": "ProjectDeck",
        "kurz": "Projekte, Fristen, Entscheidungen",
        "beschreibung": "ProjectDeck in Saganta: Projekte mit Status, Fristen und Entscheidungen.",
        "satz": "Eine Übersicht über eigene Projekte: wo sie stehen, was fällig ist, und ob sie weiterlaufen sollen.",
        "bild_alt": "Die Startseite von ProjectDeck mit Kennzahlen und Hinweisen.",
        "funktionen": [
            "Startseite mit Kennzahlen und Hinweisen, etwa auf überfällige Fristen",
            "Je Projekt Aufgaben, Meilensteine, Fristen und erfasste Arbeitszeit",
            "Verweise auf Domain, Repository, Installation und Dokumentation",
            "Regelmäßige Durchsicht mit einer Entscheidung: weiter, pausieren, veröffentlichen, abschalten, archivieren",
            "Ein Wochenfokus: woran diese Woche gearbeitet wird",
        ],
        "verbindungen": [
            "„Im Kalender planen“ gibt Projektaufgaben an den Kalender",
            "Am Projekt legt „Notiz dazu“ eine verknüpfte Notiz an",
            "Die Projekte stehen auch in der Aufgaben-App zur Auswahl",
        ],
        "telefon": "ProjectDeck gibt es auch als App fürs Telefon.",
    },
    {
        "id": "tagebuch",
        "seite": "tagebuch",
        "name": "Tagebuch",
        "kurz": "Tageseinträge, im Browser verschlüsselt",
        "beschreibung": "Das Tagebuch von Saganta: Einträge, die schon im Browser verschlüsselt werden.",
        "satz": (
            "Ein Tagebuch, das der Server nicht lesen kann. Jeder Eintrag wird im Browser "
            "verschlüsselt, bevor er gespeichert wird."
        ),
        "bild_alt": "Ein Tagebucheintrag mit erfundenem Text und der Jahresleiste darunter.",
        "funktionen": [
            "Eine Schreibfläche je Tag, vor und zurück blättern",
            "Stimmung, Energie und Schlaf auf einer Skala",
            "Eine Jahresleiste zeigt, an welchen Tagen geschrieben wurde",
            "Suche über das Jahr, sie läuft im Browser",
            "Passphrase und Wiederherstellungsschlüssel. Ohne beides ist ein Eintrag nicht mehr lesbar, auch nicht vom Betreiber",
        ],
        "verbindungen": [
            "Der Tagestyp und die Termine des Tages stehen als Erinnerung daneben, sie werden nicht mitgespeichert",
            "Stimmung, Energie und Schlaf gehen an den Kalender, der Text bleibt im Tagebuch",
        ],
    },
    {
        "id": "assets",
        "seite": "besitz",
        "name": "Besitz",
        "kurz": "Was man besitzt, und was es wert ist",
        "beschreibung": "Besitz in Saganta: Geräte und Wertsachen mit Kaufpreis und heutigem Marktwert.",
        "satz": "Eine Liste dessen, was man besitzt, mit dem Preis von damals und dem Wert von heute.",
        "bild_alt": "Die Besitzliste mit Marktwert, Kaufpreis und Verkaufsempfehlung.",
        "funktionen": [
            "Marktwert, Kaufpreis und die Differenz über alles",
            "„Verkaufen lohnt sich“: Dinge, die ungenutzt herumstehen und noch etwas wert sind, mit Begründung",
            "Geordnet nach Kategorie, mit Ort und ob es noch benutzt wird",
        ],
        "verbindungen": [
            "Wertsachen aus dem Lager erscheinen hier automatisch",
        ],
    },
    {
        "id": "fitness",
        "seite": "fitness",
        "name": "Fitness",
        "kurz": "Training, Pläne und Fortschritt",
        "beschreibung": "Fitness in Saganta: Krafttraining erfassen und den Fortschritt auswerten.",
        "satz": "Krafttraining erfassen und sehen, was es bringt.",
        "bild_alt": "Das Körpermodell, gefärbt nach Erholung der Muskeln.",
        "funktionen": [
            "Training nach Plan oder frei, Satz für Satz, mit Pausenuhr",
            "Trainingspläne mit Sätzen, Wiederholungen und Pausen",
            "Ein Körpermodell in 3D, gefärbt danach, welche Muskeln erholt sind",
            "Sätze und Volumen je Woche, Trainingstage, Rekorde und Schritte",
            "Je Übung der Verlauf der Maximalkraft",
            "Körpergewicht und Maße im Verlauf",
        ],
        "verbindungen": [
            "Zeigt die Tagesziele aus MealPrep und meldet dorthin, wie aktiv der Tag war",
            "Kennt den Tagestyp aus dem Kalender",
        ],
        "telefon": "Fitness gibt es auch als App fürs Telefon, mit Offline-Betrieb und Schritten aus Health Connect.",
    },
    {
        "id": "mealprep",
        "seite": "mealprep",
        "name": "MealPrep",
        "kurz": "Rezepte, Wochenplan, Einkaufsliste",
        "beschreibung": "MealPrep in Saganta: Mahlzeiten nach Zielen planen, abgestimmt auf Vorrat und Training.",
        "satz": "Mahlzeiten für die Woche planen, passend zu den eigenen Zielen und zu dem, was schon im Haus ist.",
        "bild_alt": "Der Wochenplan mit Kalorien und Eiweiß je Tag.",
        "funktionen": [
            "Wochenplan mit Kalorien und Eiweiß je Tag",
            "Jede Mahlzeit bestätigen oder gegen ein anderes Rezept tauschen, die Vorschläge zeigen, was dafür fehlt",
            "Rezepte anlegen und suchen",
            "Ein Profil mit Tagesbedarf, Allergien und Zutaten, die nie vorkommen sollen",
            "Eine Einkaufsliste aus dem Wochenplan",
        ],
        "verbindungen": [
            "Die Einkaufsliste zieht ab, was im Lager liegt, und Abhaken bucht ins Lager",
            "„Was muss diese Woche weg?“ zeigt Vorräte, die bald ablaufen",
            "Kennt das Training aus Fitness und den Tagestyp aus dem Kalender",
        ],
    },
    {
        "id": "lager",
        "seite": "lager",
        "name": "Lager",
        "kurz": "Vorräte mit Barcode und Haltbarkeit",
        "beschreibung": "Das Lager in Saganta: Vorräte per Barcode ein- und ausbuchen.",
        "satz": "Was im Haus ist, wie viel davon, und was bald abläuft.",
        "bild_alt": "Die Startseite des Lagers mit den bald ablaufenden Vorräten.",
        "funktionen": [
            "„Bald ablaufend“ auf der Startseite",
            "Ein- und Ausbuchen per Barcode, mit der Kamera oder von Hand",
            "Unbekannte Barcodes werden bei Open Food Facts nachgeschlagen",
            "Bestand, Produkte und Einkaufsliste",
            "Statistik über Verbrauch",
        ],
        "verbindungen": [
            "MealPrep plant mit dem Bestand und bucht beim Einkaufen hinein",
            "Wertsachen gehen an Besitz",
        ],
    },
]

# Seiten aus einem HTML-Fragment in quelle/<name>.html:
# (name, Titel, Beschreibung, Klasse am body)
FRAGMENTE = [
    ("telefon", "Die Telefon-Apps",
     "Kalender, Notizen, Fitness und ProjectDeck von Saganta als Apps für Android und Linux.", ""),
    ("einrichtung", "Einrichtung",
     "Saganta bei Ihnen einrichten lassen: eigener Rechner, eigene Daten, abgerechnet nach Stunden.", ""),
    ("impressum", "Impressum", "Anbieterkennzeichnung nach § 5 DDG für saganta.de.", ""),
    ("datenschutz", "Datenschutz", "Was saganta.de verarbeitet, und was nicht.", ""),
    ("404", "Nicht gefunden", None, ""),
]
