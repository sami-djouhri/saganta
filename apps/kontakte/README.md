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
