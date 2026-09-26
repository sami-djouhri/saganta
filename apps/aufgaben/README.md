# Saganta Aufgaben

Aufgaben, Tagesziele und die Tagesplanung. Entstanden am 2026-09-13 durch
Auslagerung aus der Kalender-App.

## Warum es diese App gibt

Die Kalender-Startseite trug **dreizehn Baustellen**: Monats-, Wochen- und
Agenda-Ansicht, Termin-Editor, Tages-Detail, adaptiver Sekretaer mit Check-in,
Vorschlaegen und Tagesplanung, Gewohnheiten, Schnellerfassung, Feierabend,
Einblicke, Zeitverteilung, Legende, Tagesziele und offene Aufgaben. Ein
Kalender, auf dem man den Kalender suchen musste.

Getrennt wurde entlang der Frage, die eine Flaeche beantwortet:

| Frage | Ort |
|---|---|
| Wann ist was? | Kalender |
| Was ist zu tun, und wann mache ich es? | Diese App |
| Was habe ich mir dazu notiert? | Notizen |
| Woran arbeite ich laenger? | ProjectDeck |

## ★ Eigene Oberflaeche, keine eigene Datenbank

Aufgaben, Ziele und Projekte liegen weiter in der **einen** Kalender-Engine
(`kalender:8085`) und werden ueber denselben `kalender-bff` gelesen und
geschrieben, den auch die Kalender-App benutzt. Das ist kein Zwischenschritt,
sondern die Entscheidung: eine Aufgabe mit Zeitfenster **ist** ein Termin, und
die Tagesplanung greift auf beides zugleich zu. Eine zweite Aufgaben-Datenbank
haette zwei Wahrheiten ergeben und die Verknuepfung Aufgabe/Termin ueber eine
App-Grenze gezwungen.

Folgen davon:

- Es gibt **kein** `aufgaben-api` und **kein** Volume.
- Was der Kalender an Aufgaben anzeigt (die Zaehlung auf der Kachel) und was
  hier steht, ist derselbe Bestand, nicht eine Kopie.
- Faellt der `kalender-bff` aus, ist diese App leer und sagt das auch.

## Weniger Vorschlaege, mehr Rueckfrage

Der Kalender zeigte bis zu sechs Vorschlaege nebeneinander („Was jetzt?"), jeder
mit Dauer, Energiestufe und Begruendung. Sie sahen nach Assistenz aus, waren
aber nur Text: keiner liess sich annehmen. Wer etwas davon wollte, musste es
selbst als Termin anlegen.

Hier gibt es stattdessen **einen Knopf, eine Vorschau, eine Frage**: „Tag
planen" laesst die Engine die freien Fenster suchen, den Aufwand gegen die
heutige Kapazitaet halten und eine Belegung vorschlagen (`commit=false`).
Angenommen wird sie erst auf Bestaetigung (`commit=true`). Was **nicht**
eingeplant werden konnte, steht mit Grund daneben; ohne diese Zeile sieht ein
zu voller Tag genauso aus wie ein leerer Vorrat.

Der Anstoss selbst ist nicht abgeschafft, sondern auf einen reduziert: im
Kalender steht weiter „Naheliegend jetzt" mit dem staerksten Vorschlag.

## Verknuepfungen

- **Notizen** hangen an einer Aufgabe ueber die Tabelle `verknuepfungen` der
  `notizen-api` (`typ: aufgabe`, `ref: <todo-id>`). Gefuehrt wird sie **dort**,
  diese App liest sie nur von der anderen Seite. Eine gespiegelte Tabelle haette
  beim Loeschen einer Notiz eine Karteileiche hinterlassen.
  ★ Gelesen wird ueber `/api/notizen/verknuepft?typ=aufgabe&refs=a,b,c`, eine
  Route, die fuer genau diesen Fall entstanden ist: ein Aufruf je Zeile waere bei
  sechzig offenen Aufgaben ein Sturm von sechzig Anfragen.
- **Projekte** kommen aus derselben Engine (`project_id` an der Aufgabe). Die
  Projektansicht verlinkt ins ProjectDeck, fuehrt die Projekte aber nicht.
- **Termine** entstehen aus der Planung und liegen im Kalender.

## Betrieb

```bash
# .env anlegen (uebernimmt das Backend-Geheimnis, wuerfelt es NICHT neu)
bash infra/aufgaben-env-anlegen.sh

cd infra && docker compose -f docker-compose.yml \
  -f docker-compose.override.lan.yml up -d --build aufgaben
```

Erreichbar unter `https://aufgaben.home.arpa`. Dafuer braucht es **drei**
Eintraege ausserhalb dieses Repos, sonst ist der Name nur halb da:

1. `server_name aufgaben.home.arpa` im dev-portal-Vhost (gesetzt)
2. DNS-Rewrite in AdGuard (`docker/adguard/rewrite-setzen.sh`)
3. `ui_url` in der control-map fuers Launchpad (gesetzt)

## Tests

```bash
pnpm --filter @saganta/aufgaben test    # Ordnung und Gruppierung
pnpm --filter @saganta/aufgaben check   # Typen
```

Geprueft wird die Logik, nicht die Darstellung: Sortierung, Gruppierung,
Faelligkeit, Pool-Abgrenzung und die Datumsrechnung. Letztere rechnet
ausschliesslich auf Zeichenketten, weil `new Date('2026-03-29')` UTC-Mitternacht
ist und eine Tagesrechnung an den beiden Zeitumstellungen im Jahr sonst um einen
Tag danebenliegt (dieselbe Entscheidung wie in `apps/tagebuch/src/lib/datum.ts`).
