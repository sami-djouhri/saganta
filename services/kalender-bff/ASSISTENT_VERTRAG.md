# KI-Chat: Aktionsvertrag (Stufe 2 gebaut)

Stand 2026-11-02, **gemessen**: Fassung 3 von `scripts/assistent-messen.py`
traf mit `homelab-smart` 8 von 8 Testsätzen, Median 19,7 s, langsamste 46 s.
Die Aufteilung unten ist das Ergebnis von drei Messungen (4/8, 4/8, 8/8). Entscheide und Begründung:
interne Notiz, Plan im ProjectDeck, Projekt
„saganta“, Aufgaben „KI-Chat Stufe 1 bis 4“.

## Grundsätze (Entscheide 02.11.)

1. **Der Dienst schreibt nie selbst.** Das Modell liefert Aktionen, der Dienst
   prüft und ergänzt sie und gibt **Vorschlagskarten** zurück. Angelegt,
   geändert oder gelöscht wird erst nach einem Tipp, und zwar über die Wege,
   die die App ohnehin benutzt (Repository, Warteschlange, Bestätigungsdialoge).
   Grund wie bei `routes_chat.py`: am Kalender hängt die Weckkette.
2. **Nur Modelle im Haus** (`ERLAUBTE_MODELLE`), das gründliche zuerst.
3. **Verlauf nur bis zum Schließen.** Die App schickt den Gesprächsverlauf bei
   jeder Nachricht mit, der Dienst speichert nichts.
4. **Je Wunsch eine Karte.** Mehrere Wünsche in einer Nachricht ergeben
   mehrere Aktionen.
5. **Unklares wird geraten, nicht erfragt.** Fehlen Tag oder Dauer, nimmt der
   Dienst die nächste passende freie Zeit mit einer üblichen Dauer und legt
   zwei Alternativen dazu.
6. **Kennungen nur aus dem Kontext.** Das Modell darf nur `id`s verwenden, die
   in der mitgeschickten Liste stehen. Eine unbekannte Kennung verwirft die
   Aktion, statt etwas Falsches zu treffen.

## Anfrage der App

```json
POST /api/assistent
{
  "verlauf": [{"rolle": "nutzer", "text": "..."}, {"rolle": "assistent", "text": "..."}],
  "nachricht": "plane morgen 2 Stunden Steuer ein und sag das Kino ab",
  "app": "kalender"
}
```

## Arbeitsteilung: das Modell versteht, Regeln rechnen

Das ist der Kern, und er ist gemessen. Das Modell rechnet keine Tage
(„Freitag“ wurde zum Mittwoch), erfindet freie Zeiten („Dienstag 00:00 bis
02:00“) und lässt unter einem erzwungenen Schema jedes optionale Feld weg.
Deshalb liefert es **nur, was ein Sprachmodell kann**:

| Feld (alle Pflicht, `null` erlaubt) | Inhalt |
|---|---|
| `art` | was getan werden soll (Liste unten) |
| `ausschnitt` | der Teil der Nachricht, der zu diesem Wunsch gehört, **wörtlich** |
| `titel` | Name eines neuen Termins oder einer Aufgabe |
| `ziel_id` | Kennung aus dem Kontext (`e-` Termin, `s-` Sitzung, `t-` Aufgabe) |
| `umfang` | bei Serien `dieser` / `ab_hier` / `alle` |
| `typ` | bei Tagestyp und Urlaub |

Tag, Uhrzeit und Dauer rechnet der Dienst aus `ausschnitt`, mit den Regeln
des Freitext-Parsers (`/api/capture` des Kalenders). Freie Zeit rechnet der
Planer (`block_vorschlaege`). Erzwungen wird das Format als `response_format`
mit JSON-Schema; die Fassung steht in `scripts/assistent-messen.py` (`SCHEMA`,
`SYSTEM` samt Beispielen) und wird für den Endpunkt übernommen.

```json
{
  "antwort": "Ein kurzer Satz an den Nutzer.",
  "aktionen": [
    {"art": "termin_anlegen", "ausschnitt": "morgen 2 Stunden Steuer", "titel": "Steuer", "ziel_id": null, "umfang": null, "typ": null},
    {"art": "termin_loeschen", "ausschnitt": "Training faellt nur diese Woche aus", "titel": null, "ziel_id": "e-3", "umfang": "dieser", "typ": null}
  ]
}
```

| `art` | was der Dienst daraus macht |
|---|---|
| `frage` | nur `antwort`; Zahlen zu freier Zeit kommen vom Planer, nicht vom Modell |
| `freie_zeit` | seit 2026-11-03: Zeitraum (heute, morgen, Tag, diese/nächste Woche, (nächstes) Wochenende, sonst 7 Tage) und Dauer nach Regeln, Zeiten aus `/api/schedule/free-slots` (8 bis 22 Uhr). Die Antwort ist die Rechnung, der Satz des Modells entfällt; keine Karte |
| `termin_anlegen` | Tag/Uhrzeit/Dauer aus dem Ausschnitt; ohne Uhrzeit bis zu 3 freie Zeiten |
| `termin_aendern` / `termin_loeschen` | `ziel_id` + `umfang`; neuer Tag/Uhrzeit aus dem Ausschnitt |
| `serie_anlegen` | Regel aus `RecurrencePreset` (noch nicht gemessen) |
| `aufgabe_anlegen` / `aufgabe_erledigt` / … | Fälligkeit aus dem Ausschnitt |
| `sitzung_verschieben` / `annehmen` / `absagen` | `ziel_id` (`s-`), neuer Tag aus dem Ausschnitt |
| `gewohnheit_wochenziel` | Stunden aus dem Ausschnitt (noch nicht gemessen) |
| `tagestyp_setzen` / `urlaub_bereich` | `typ`, Tag(e) aus dem Ausschnitt; steuert den Wecker, Karte trägt einen Hinweis |
| `tag_planen` | Planer verteilt offene Aufgaben in freie Zeit |
| `ziel_anlegen` | Tag aus dem Ausschnitt (noch nicht gemessen) |

## Antwort an die App

```json
{
  "antwort": "Zwei Vorschläge.",
  "karten": [
    {"id": "k1", "art": "termin_anlegen", "text": "Steuer, morgen", "optionen": [
      {"text": "14:00 bis 16:00", "daten": {...}}, {"text": "16:30 bis 18:30", "daten": {...}}
    ], "hinweis": null},
    {"id": "k2", "art": "termin_loeschen", "text": "Kino mit Tim absagen (heute 19:00)", "optionen": [{"text": "Absagen", "daten": {...}}]}
  ],
  "verworfen": [{"grund": "unbekannte Kennung e-999"}],
  "modell": "homelab-smart"
}
```

`daten` ist das, was die App an ihren vorhandenen Schreibweg übergibt
(`EventUpsertRequest`, `TodoUpsertRequest`, Sitzungsschritt, Tagestyp). Damit
greifen Warteschlange, Konfliktprüfung und Nachplanen wie bei jeder Eingabe von
Hand.

## Messstand und Folgen für Stufe 2

- **Modell:** `homelab-smart` (LXC 201). `homelab-fast` scheidet aus (1/8,
  Median 81 s, legte für „sag das Kino ab“ einen Termin an). Welches Modell auf
  `.21` genau läuft (die Projektregeln: gpt-oss-20b, Gateway-Config: `node17-qwen14`),
  ist für den Vertrag zweitrangig; die Messung gilt für den Alias.
- **Key:** `saganta-kalender-bff` seit 2026-11-02, Abgleich `ok`, ohne
  `homelab-large` (gamehost). Vorher hatte der Dienst gar keinen, `POST /api/chat`
  antwortete immer 503.
- **Zeit:** Median 20 s, bis 46 s. `llm_timeout_seconds` (30 s) muss für den
  Assistenten auf 90 s, und der Chat braucht eine Warteanzeige.
- **Noch nicht gemessen:** Serien anlegen, Wochenziel, Tagesziel, Urlaub über
  einen Zeitraum, Rückbezug im Verlauf („lieber 15 Uhr“). Vor Stufe 2 die
  Testsätze ergänzen.

## Stufe 2 gebaut (2026-11-03)

`POST /api/assistent` in `app/routes_assistent.py`, App 0.8.8 (Sprechblase im
Kopf, Blatt von unten, Karten). Kontext mit Kurzkennungen (`e-3`, `s-1`,
`t-1`), Zuordnung nur im Dienst; Tagestyp-Ereignisse stehen nicht im Kontext.
Arten zusätzlich: `ziel_anlegen`. Noch ohne Karte: `tag_planen`, Serien
anlegen, Wochenziel (werden als „nicht übernommen“ gemeldet).

Gemessen mit `homelab-smart`: 15 von 15 Sätzen richtig, darunter Rückbezug
(„lieber 15 Uhr“), Urlaub über einen Zeitraum, Tagesziel, „ab jetzt immer“ =
`ab_hier`. Antwortzeit 12 bis 57 s. Deshalb drei Wartezeiten: App 100 s,
`assistent_timeout_seconds` 90 s, Tardis `location = /api/assistent` 120 s
(Vorgabe 60 s hätte die langsamsten Antworten abgeschnitten).

⚠️ Eine reine Frage beantwortet das Modell selbst; Zahlen zu freier Zeit
kommen dabei noch nicht vom Planer. Offen für Stufe 3.

## Tempo (gemessen 2026-11-04)

Der Wirt (gpt-oss-20b auf LXC 201, CPU) liest rund **15 Token/s** ein. Bis zum
03.11. wurde fast jede Anfrage komplett neu eingelesen (~1830 Token, rund
2 min), BFF (90 s), Tardis (120 s) und App (100 s) gaben vorher auf. Drei
Stellschrauben, alle nötig:

- `--swa-full` am llama-server (`docker/ai-llm-node17`): erst damit wird der
  Systemtext (877 Token) wiederverwendet.
- Kontext knapp und nach Tagen gruppiert, 14 statt 21 Tage (`KONTEXT_TAGE`).
- „jetzt HH:MM" steht am **Ende** des Kontexts; vorn hätte er jede Minute den
  ganzen Rest für den Cache neu gemacht (Test `test_kontext_aendert_sich_mit_der_uhrzeit_nur_in_der_letzten_zeile`).

Ergebnis: erste Frage 44 s, weitere 19 bis 27 s (vorher in der Regel Abbruch).
⚠️ Der Wirt hat **einen** Slot und wird mit marktwatch geteilt; läuft dort
gerade etwas, wartet der Chat dahinter.

