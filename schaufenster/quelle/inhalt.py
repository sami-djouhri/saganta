"""Der Text von saganta.de, aus dem `bauen.py` die Seiten erzeugt.

Jede Funktion, die hier steht, ist am Quelltext der Oberflaeche belegt
(Erhebung 2026-10-30, neue Apps 2026-11-15, je Punkt mit Datei und Zeile, gegengeprueft an
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
    "titel": "Siebzehn Apps für den Alltag einer Familie, auf eigener Hardware",
    "beschreibung": (
        "Saganta ist eine Suite aus siebzehn Apps für Kalender, Aufgaben, Vorrat, Bücher "
        "und mehr. Sie läuft auf eigenen Rechnern im Haus."
    ),
    "anriss": (
        "Kalender, Aufgaben, Lager, Bibliothek und die übrigen teilen ein Aussehen, "
        "einen App-Wechsler und ihre Daten untereinander. Saganta läuft auf eigenen "
        "Rechnern im Haus. Die Daten verlassen es nicht."
    ),
    "bild_alt": "Die Übersicht von Saganta nach der Anmeldung, mit Beispieldaten.",
    "zusammen": (
        "Dass sie zusammen liegen, ist der Zweck: die Einkaufsliste füllt sich aus "
        "Lager und Essensplan, Geburtstage aus Kontakte stehen im Kalender, das "
        "Tagebuch zeigt die Termine des Tages, und an jedem Termin, jeder Aufgabe und "
        "jedem Projekt lässt sich direkt eine Notiz anlegen."
    ),
    "telefon": (
        "Zwölf davon gibt es zusätzlich als eigene Apps für Android, acht auch für "
        "Linux. Die meisten nehmen Einträge auch ohne Verbindung an und tragen sie "
        "nach, sobald das Telefon wieder im Heimnetz ist."
    ),
    "technik": [
        "<b>Oberflächen</b> in SvelteKit, bei den übrigen Diensten React oder einfaches JavaScript",
        "<b>Dienste</b> in Python mit FastAPI, dahinter SQLite",
        "<b>Anmeldung</b> über better-auth, Finanzen und Medien zusätzlich hinter Authelia",
        "<b>Telefon-Apps</b> in Kotlin mit Compose Multiplatform",
        "<b>Karten</b> mit MapLibre und Valhalla, offline für ganz Deutschland",
        "<b>Betrieb</b> in Docker, auf Raspberry Pis im eigenen Haus",
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
        "kurz": "Eingescannte Briefe, Verträge, Fristen",
        "beschreibung": "Die Post-App von Saganta: eingescannte Briefe, durchsuchbar, mit Verträgen und Fristen.",
        "satz": "Ein Eingang für die Briefe, die auf Papier kommen und eingescannt werden.",
        "bild_alt": "Der Posteingang mit der Übersicht über Verträge und Fristen.",
        "funktionen": [
            "Briefe scannen oder hochladen, die Texterkennung macht sie durchsuchbar",
            "Suche über Betreff und Absender und im erkannten Text",
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
        "kurz": "Vorräte, Technik und Bücher, mit Strichcode",
        "beschreibung": "Das Lager in Saganta: Vorräte, Technik und Bücher per Strichcode ein- und ausbuchen.",
        "satz": "Was im Haus ist, wo es liegt, und was bald abläuft.",
        "bild_alt": "Die Startseite des Lagers mit den bald ablaufenden Vorräten.",
        "funktionen": [
            "Bereiche von Lebensmitteln über Hausapotheke bis Garten, jeder mit seiner eigenen Frist, etwa Mindesthaltbarkeit oder Verfall",
            "Einbuchen als Lauf: ein Strichcode nach dem anderen, Menge, Frist und Preis stehen als Vorschlag da",
            "„Bald ablaufend“ auf der Startseite, Abgelaufenes lässt sich auf einmal ausbuchen",
            "Plätze als Raum, Regal, Fach und Kiste, mit gedrucktem Etikett je Platz",
            "Technik und Sachen mit Foto und Preis, Marktwert gegen Kaufpreis und ein Hinweis, wo sich Verkaufen lohnt",
            "Ein Bücherregal: erst das Fach scannen, dann die ISBN eines Buchs nach dem anderen",
            "Statistik über Ausgaben, den Preis je Laden und Verlust, dazu die Inventur",
        ],
        "verbindungen": [
            "Mindestbestand und Kaufpreise füllen die Einkaufsliste",
            "Autor, Jahr und Verlag der Bücher kommen aus Medien",
            "MealPrep plant mit dem Bestand",
        ],
        "telefon": "Das Lager gibt es auch als App fürs Telefon.",
    },
    {
        "id": "einkaufsliste",
        "seite": "einkaufsliste",
        "name": "Einkaufsliste",
        "kurz": "Was fehlt, von selbst aus Vorrat und Essensplan",
        "beschreibung": "Die Einkaufsliste von Saganta: füllt sich aus Lager und Essensplan, mit geschätztem Preis.",
        "satz": "Eine Einkaufsliste, die zum großen Teil von selbst entsteht.",
        "bild_alt": "Die Einkaufsliste nach Warengruppen, mit geschätztem Preis je Zeile.",
        "funktionen": [
            "Frei eintippen mit Menge, etwa „2 Milch, 500 g Hack“, die Warengruppe wählt die Liste selbst",
            "Beim Tippen kommen passende Produkte aus dem Lager als Vorschlag",
            "Was unter den Mindestbestand fällt oder einem geplanten Gericht fehlt, steht von selbst auf der Liste",
            "Nach Warengruppen sortiert, je Zeile ein geschätzter Preis mit dem Laden des Tiefstpreises",
            "Abgehaktes liegt „Im Korb“, Weggewischtes lässt sich sofort zurückholen",
        ],
        "verbindungen": [
            "Mindestbestand, Verbrauch und Kaufpreise kommen aus dem Lager",
            "Fehlende Zutaten kommen aus dem Wochenplan von MealPrep",
            "Zeigt, wie viel vom Budget für Lebensmittel in Finanzen diesen Monat übrig ist",
        ],
        "telefon": "Die Einkaufsliste gibt es auch als App fürs Telefon, abhaken geht auch im Laden ohne Netz.",
    },
    {
        "id": "kontakte",
        "seite": "kontakte",
        "name": "Kontakte",
        "kurz": "Menschen, Geburtstage und Jahrestage",
        "beschreibung": "Kontakte in Saganta: Telefon, Mail, Adresse, Geburtstage und Jahrestage.",
        "satz": "Ein Adressbuch, das an Geburtstage und Jahrestage denkt.",
        "bild_alt": "Die Kontaktliste mit den Geburtstagen der nächsten Tage.",
        "funktionen": [
            "Kontakte mit Telefon, Mail, Adresse, Gruppe, Geburtstag und Notiz",
            "Eigene Jahrestage, etwa der Hochzeitstag",
            "Die Startseite zeigt Geburtstage und Jahrestage der nächsten 30 Tage",
            "Suche über Name, Nummer, Mail und Ort, Filter nach Gruppe",
            "Ein Papierkorb, aus dem sich Gelöschtes zurückholen lässt",
        ],
        "verbindungen": [
            "Geburtstage und Jahrestage stehen im Kalender, mit Erinnerung am Tag und drei Tage vorher",
            "Termine aus dem Kalender lassen sich mit einem Kontakt verknüpfen",
            "Unter jedem Kontakt stehen seine Notizen, und die Wohnorte sind eine Ebene in Karten",
        ],
        "telefon": "Kontakte gibt es auch als App fürs Telefon, Änderungen gehen auch ohne Netz.",
    },
    {
        "id": "finanzen",
        "seite": "finanzen",
        "name": "Finanzen",
        "kurz": "Konten, Budgets, Prognose und Depot",
        "beschreibung": "Finanzen in Saganta: Buchungen, Budgets, Vermögensprognose und Depot.",
        "satz": "Ein Haushaltsbuch, das nach vorn rechnet: was der Monat erlaubt und wohin das Vermögen läuft.",
        "bild_alt": "Die Seite „Lage“ mit Budgets und anstehenden Fristen, mit erfundenen Zahlen.",
        "funktionen": [
            "Die Seite „Lage“ zeigt, was Aufmerksamkeit braucht, und warnt vor Kündigungsfristen",
            "Buchungen von Hand oder ein Kontoauszug als CSV",
            "Budgets je Kategorie mit Ober- und Untergrenze, Reste lassen sich ansparen",
            "Eine Vermögensprognose als Korridor für 1 bis 10 Jahre, auf Wunsch mit einem Was-wäre-wenn",
            "Eine Wunschliste, die sagt, ab wann der Überschuss einen Wunsch bezahlt",
            "Depot, Schulden, Sachwerte und verliehenes Geld",
            "Ein Jahresrückblick: wohin das Gehalt ging",
        ],
        "verbindungen": [
            "Gibt der Einkaufsliste den Rest des Lebensmittel-Budgets",
        ],
    },
    {
        "id": "medien",
        "seite": "medien",
        "name": "Medien",
        "kurz": "Filme, Serien, Bücher, Spiele und Musik",
        "beschreibung": "Medien in Saganta: die eigene Sammlung pflegen, bewerten und nachschlagen.",
        "satz": "Eine Sammlung von Filmen, Serien, Büchern, Spielen und Musik: was da ist, was fehlt, und was gefällt.",
        "bild_alt": "Die Startseite von Medien mit erfundenen Titeln.",
        "funktionen": [
            "Die Startseite zeigt, was gerade zu tun ist",
            "„Fehlt noch“: was in die Sammlung soll, getrennt nach physisch und digital, bei Serien je Staffel",
            "Je Titel festlegen, ob er physisch, digital oder in beiden Formen da sein soll",
            "Bücher auf Klick bei der Deutschen Nationalbibliothek nachschlagen",
            "Eine Rangliste aus Duellen zwischen zwei Titeln",
            "Ein Nachschlagewerk für Filme und Serien, offline, mit Seiten für Werke und Personen",
            "„Aussortieren“ schlägt Stücke vor, die gehen könnten",
        ],
        "verbindungen": [
            "Der physische Bestand kommt aus dem Lager",
            "Welche Bücher es als eBook gibt, meldet die Bibliothek",
            "Das Nachschlagewerk ist eine Quelle in Wissen",
        ],
    },
    {
        "id": "bibliothek",
        "seite": "bibliothek",
        "name": "Bibliothek",
        "kurz": "Die Hausbibliothek zum Lesen",
        "beschreibung": "Die Bibliothek von Saganta: eBooks im Browser und auf dem Telefon lesen.",
        "satz": "Die eBooks des Hauses, zum Lesen im Browser und auf dem Telefon.",
        "bild_alt": "Das Regal der Bibliothek mit erfundenen Bänden.",
        "funktionen": [
            "Das Regal nach Verfasser oder Titel durchsuchen, auch nach Sätzen im Text aller Bücher",
            "„Wo fange ich an?“ schlägt einen Band vor und begründet ihn",
            "Weiterlesen und Lesestand je Person",
            "Ein Leser mit Schriftgrad, Zeilenabstand, Satzbreite, zwei Spalten und schwarzem Papier",
            "Marken mit Notiz, Suche im Band, Vorlesen",
            "Ein Wort antippen und die Bedeutung aus dem Wiktionary lesen",
        ],
        "verbindungen": [
            "Die Bücher sind eine Quelle in Wissen",
            "Meldet Medien, welche Bücher es als eBook gibt",
        ],
        "telefon": "Die Bibliothek gibt es auch als App fürs Telefon, geladene Bücher lassen sich ohne Netz lesen.",
    },
    {
        "id": "wissen",
        "seite": "wissen",
        "name": "Wissen",
        "kurz": "Eine Suche über das Wissen im Haus",
        "beschreibung": "Wissen in Saganta: eine Suche über Wikipedia, Bücher und Anleitungen, offline.",
        "satz": "Ein Feld zum Fragen. Gesucht wird im Haus, nicht im Internet.",
        "bild_alt": "Eine Antwort mit Belegen und den Treffern darunter.",
        "funktionen": [
            "Die Antwort kommt mit Belegziffern, die Treffer stehen darunter",
            "Gesucht wird zugleich in einer Offline-Wikipedia, in Büchern, Anleitungen, Dokumenten und Filmen",
            "Treffer nach Quelle filtern, Rückfragen beziehen sich auf die vorige Frage",
            "Ein Knopf vergleicht die Quellen und zeigt, wo sie sich widersprechen",
            "Der Schalter „Survival“ sucht nur in Medizin, Wasser, Nahrung, Notfall, Reparatur und Knoten",
            "Eine Merkliste für Treffer",
        ],
        "verbindungen": [
            "Die Bücher der Bibliothek sind eine Quelle",
            "Das Nachschlagewerk aus Medien ist die Quelle „Filme & Serien“",
            "Ein Link führt zur Karte",
        ],
    },
    {
        "id": "karten",
        "seite": "karten",
        "name": "Karten",
        "kurz": "Offline-Karte mit Routen",
        "beschreibung": "Karten in Saganta: eine Karte von Deutschland mit Suche und Routen, aus dem eigenen Haus.",
        "satz": "Eine Karte mit Suche und Routen, die ohne fremden Kartendienst auskommt.",
        "bild_alt": "Eine Route auf der Karte mit Höhenprofil.",
        "funktionen": [
            "Suche nach Orten und Adressen, offline",
            "Routen mit Auto, Rad, zu Fuß, E-Scooter und Bus und Bahn, mit Zwischenhalten und „Reihenfolge optimieren“",
            "Navigation mit Ansagen, Höhenprofil und Routenfarbe nach Steigung",
            "„Wie weit komme ich?“ zeigt, was in 10, 20 oder 30 Minuten erreichbar ist",
            "Luftbild, Gelände und Häuser in 3D",
            "Ebenen für Haltestellen mit Abfahrten und für Klinik, Apotheke und Feuerwehr",
        ],
        "verbindungen": [
            "Die Wohnorte aus Kontakte sind eine eigene Ebene, jeder Punkt führt zum Kontakt",
            "Wissen verlinkt auf die Karte",
        ],
        "telefon": "Karten gibt es auch als App fürs Telefon, mit der Grundkarte von ganz Deutschland an Bord.",
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
