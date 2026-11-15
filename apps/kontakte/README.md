# Saganta Kontakte

Kontakte mit Telefon, Mail, Adresse, Geburtstag, Jahrestagen und Gruppe,
verknüpft mit Terminen und Notizen. Seit 2026-11-07 (Entscheid 06.11.:
eigene App, Web und APK).

| Teil | Ort |
|---|---|
| Oberfläche | `apps/kontakte` (SvelteKit), `kontakte.home.arpa`, auf Abruf über den Wecker (`wake-gateway:8173`) |
| Dienst | `services/kontakte-api` (FastAPI, SQLite im Volume `kontakte-data`) |
| Android | `saganta-apps/app-kontakte-android` + `feature-kontakte`, gegen `kontakte-api.home.arpa` |

## Wie Geburtstage in den Kalender kommen

Der Dienst ist die eine Quelle. Nach jeder Änderung an Name, Geburtstag oder
Jahrestagen schickt er den **ganzen** Stand des Kontos an den kalender-bff
(`PUT /api/contacts/abgleich`). Der Kalender hält davon nur einen Spiegel
(Tabelle `contacts`, eine Zeile je Geburtstag oder Jahrestag), erzeugt die
Termine im Kalender „Geburtstage“ und erinnert über ntfy am Tag und drei Tage
vorher, jeweils ab 08:00.

- Antwortet der Kalender nicht, bleibt die Änderung gespeichert, und der
  Dienst holt den Abgleich nach (Merker `abgleich_offen`, alle zehn Minuten).
  Die Oberfläche zeigt den Rückstand an.
- Der Geburtstag trägt im Spiegel die Kennung des Kontakts, ein Jahrestag eine
  feste, aus Kontakt, Bezeichnung und Datum errechnete. Sonst kämen die
  Erinnerungen nach jeder Änderung ein zweites Mal.
- Die Schreibrouten für Kontakte am kalender-bff antworten seither mit 410: was
  dort geschrieben würde, verschwände beim nächsten Abgleich.

## Wohnort auf der Karte (seit 2026-11-15)

Ein Kontakt mit Adresse bekommt `lat`/`lon` (`services/kontakte-api/app/orte.py`).
Aufgeloest wird allein ueber die Offline-Adresssuche auf node1
(`ADRESSSUCHE_URL`, Vorgabe `http://192.0.2.10:8144/adressen`), nie ueber
einen fremden Geocoder. Am besten in der Form „Straße Nr, PLZ Ort“: mit Komma
geht es strukturiert Ort > Straße > Hausnummer, sonst ueber die freie Suche.
`ort_genauigkeit` sagt `adresse`, `strasse`, `ort` oder `hand`.

- Gesucht wird beim Speichern und, falls die Adresssuche nicht antwortet, im
  Hintergrundlauf (15 s nach dem Start, dann alle zehn Minuten). Das holt
  auch den Altbestand nach.
- Nur eine **geaenderte** Adresse loest eine neue Suche aus. Die App
  schickt beim Speichern alle Felder mit; sonst ginge ein von Hand gesetzter
  Punkt (`lat`+`lon` im PATCH) beim naechsten Speichern verloren.
- Kein Adresstext im Protokoll: der Dienst loggt nur Zahlen, sein
  Fehlertext traegt nie die URL, und der nginx auf node1 protokolliert
  `/adressen/` ohne Query.
- Die Karte ist die Ebene „Kontakte“ in `karten.home.arpa`. Der Browser
  holt `kontakte.home.arpa/orte.json` mit dem Saganta-Cookie; CORS gibt die
  Antwort nur an diese eine Herkunft frei (`src/lib/karten.ts`). Der Pfad ist
  im Auth-Hook oeffentlich und antwortet ohne Anmeldung mit 401 samt
  Anmeldeadresse, weil eine Weiterleitung im `fetch` nicht von „schlaeft“ zu
  unterscheiden waere.

## Umzug aus dem Kalender

`POST /api/umzug/kalender` (Knopf „Aus dem Kalender übernehmen“ in der leeren
Liste) übernimmt die Kontakte aus dem Kalender mit **denselben Kennungen**,
idempotent über `herkunft = kalender:<id>`. Verknüpfungen aus den Notizen
(Typ `kontakt`) bleiben damit gültig.

## Einrichten

```bash
bash infra/kontakte-env-anlegen.sh      # beide .env, Geheimnis übernommen, nie ausgegeben
cd infra && docker compose -f docker-compose.yml -f docker-compose.override.lan.yml \
  up -d --build kontakte-api kontakte
bash scripts/tests-im-image.sh kontakte-api
```

Löschen legt in den Papierkorb (30 Tage), wie in den anderen Apps.
