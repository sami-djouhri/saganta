# saganta-tagebuch-api

Ablage für Ende-zu-Ende-verschlüsselte Tageseinträge. Der Dienst verwahrt
Chiffrat, er liest es nicht.

Die Oberfläche und das Verfahren stehen in `apps/tagebuch/README.md`. Hier steht
nur, was den Dienst selbst ausmacht.

## Was er weiss

Genau drei Dinge im Klartext: welcher Mandant geschrieben hat, an welchem Tag,
und wie lang das Chiffrat ist. Es gibt kein Titel-, Auszugs- oder Textfeld, und
das ist eine Entwurfsentscheidung, keine Sparsamkeit: ein Titelfeld wäre die
aussagekräftigste Zeile des Eintrags, und sie stünde offen in der Datenbank.

## Drei Eigenschaften, die ihn von den Geschwistern unterscheiden

1. **Kein Weg nach draussen.** Er hängt allein im Netz `tagebuch-net`
   (`internal: true`). ★ Gemessen, nicht angenommen: `cc-core` allein reicht
   dafür nicht, das Netz ist nicht `internal`, und ein Dienst darin erreicht
   1.1.1.1:443. Die erste Fassung des Compose stand genau so da, mit einem
   Kommentar, der das Gegenteil behauptete.

2. **Keine Datumsangaben im Zugriffsprotokoll** (`app/zugriffsmaske.py`).
   Uvicorn schreibt jeden Pfad mit, und die Pfade hier tragen das Datum. Daraus
   liesse sich rekonstruieren, an welchen Tagen jemand geschrieben hat. Das ist
   kein Randfall: `promtail` sammelt die Ausgabe aller Container nach Loki, und
   dessen Volume liegt in der Off-Site-Sicherung. Dieselbe Kette hat den
   `feed_token` des Kalenders in 509 von 644 Zeilen ins Backup getragen.

3. **Ein Tresor je Konto, und er wird nie überschrieben.** `PUT /api/tresor`
   antwortet auf einen zweiten Versuch mit 409. Würde er ersetzen, hinge jeder
   vorhandene Eintrag an einem Datenschlüssel, den es danach nicht mehr gibt:
   alles unlesbar, ohne dass eine Zeile in `eintraege` angefasst wurde.

## Endpunkte

| Weg | Zweck |
|---|---|
| `GET /api/tresor` | die verpackten Schlüssel; 404 heisst „noch nicht eingerichtet" |
| `PUT /api/tresor` | einmalig einrichten (409 bei einem zweiten Versuch) |
| `POST /api/tresor/passphrase` | nur den Passphrase-Zweig neu verpacken, Notfallzettel bleibt gültig |
| `GET /api/eintraege/tage?jahr=` | welche Tage gefüllt sind, ohne Inhalt |
| `GET /api/eintraege?von=&bis=` | eine Spanne mit Chiffrat, höchstens 400 Tage |
| `GET/PUT/DELETE /api/eintraege/{datum}` | ein Tag, Upsert |

Jede Abfrage filtert auf `owner_sub`. Es gibt keinen Pfad ohne diesen Filter und
keine öffentliche Route.

## Prüfen

```bash
bash run-tests.sh                                   # 36 Tests, im Image
bash ../../scripts/tagebuch-vertraulichkeit-pruefen.sh   # am laufenden Dienst
```
