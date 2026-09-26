# Saganta Tagebuch

Ein Eintrag je Tag. Der Text wird im Browser verschlüsselt und verlässt ihn nur
verschlossen. Der Server verwahrt ihn, ohne ihn lesen zu können.

Erreichbar unter **https://tagebuch.home.arpa** (LAN und WireGuard).

## Was es ist, und was es bewusst nicht ist

Es ist eine Schreibfläche mit einer Datumsleiste. Es ist **kein** Notizbuch
(dafür gibt es `apps/notizen`) und **keine** Auswertung.

Bewusst nicht gebaut:

- **Kein LLM liest mit**, auch kein lokales. Das war eine ausdrückliche
  Entscheidung, keine Auslassung. Der Dienst hat deshalb auch keinen Weg ins
  Internet: er hängt allein im internen Netz `tagebuch-net`.
- **Keine Suche auf dem Server.** Sie bräuchte Klartext. Gesucht wird im
  Browser über die entschlüsselten Einträge.
- **Kein Wissens-Adapter, kein Event, kein Vault-Sync, keine Push-Nachricht mit
  Inhalt.** Das Tagebuch ist an nichts angeschlossen, was mitliest.
- **Kein Teilen.** Anders als bei den Notizen gibt es keine öffentliche Route.
- **Nicht im Tunnel.** `exposure: local_only`. Von unterwegs kann man nicht
  schreiben. Das ist der Preis der Owner-Regel „kein Fernzugang ins Heimnetz",
  und es ist eine bewusste Entscheidung, keine Lücke.

## Die eine Stelle, an der etwas hinausgeht

Beim Speichern gehen **drei Zahlen** an den Kalender: Stimmung, Energie,
Schlaf, als `daily_checkins` über `kalender-bff`. Dort steuern sie die
Tagesplanung (`daily_energy.compute_day_capacity`). Der Freitext geht diesen
Weg nie.

Das ist der Grund, warum das Tagebuch überhaupt an den Kalender angeschlossen
ist: die Reflexionsschicht dort (`daily_reviews`, `daily_checkins`,
`activity_feedback`) existierte seit Juli 2026 und war am 06.09.2026 mit **0
Zeilen** vollständig ungenutzt. Ihr fehlte keine Funktion, ihr fehlte ein Ort,
an dem man freiwillig schreibt. Eine vierte Erfassungsfläche danebenzustellen
hätte das nicht geändert.

⚠️ **Diese drei Zahlen liegen im Kalender im Klartext.** Wer die
Kalender-Datenbank liest, sieht „06.09.: Stimmung mies", aber nicht, warum.
Das ist die bewusste Naht dieses Entwurfs.

Die Allowlist dafür steht in `src/lib/checkin.ts`, mit Test daneben. Sie ist
eine Allowlist und kein Durchreicher, weil das Ziel-Schema im Kalender ein
Freitextfeld `note` kennt.

## Das Verfahren

Ein Datenschlüssel (DEK, AES-GCM-256) verschlüsselt alle Einträge. Er liegt auf
dem Server nur verpackt, und zwar zweimal: unter der Passphrase und unter dem
Wiederherstellungsschlüssel. Beide öffnen dasselbe.

- Ein Passphrasenwechsel verschnürt ein Paket neu, er verschlüsselt nicht den
  Bestand neu.
- Ein Passwortwechsel entwertet den ausgedruckten Notfallzettel **nicht**.
- Der Schlüssel liegt zur Laufzeit **nur im Arbeitsspeicher**, nie in
  `sessionStorage`. Nach jedem Neuladen ist die Passphrase erneut nötig; beim
  Blättern zwischen Tagen nicht, weil SvelteKit im Client navigiert.

★ **Passphrase und Wiederherstellungsschlüssel beide verloren heisst: Einträge
verloren.** Endgültig, auch aus jeder Sicherung. Das ist kein Mangel des
Verfahrens, sondern seine Bedingung.

★ **Es braucht einen sicheren Kontext.** `crypto.subtle` gibt der Browser nur
unter https frei. Über `http://IP:Port` fehlt es, und ohne die ausdrückliche
Prüfung in `krypto.ts` sähe der Fehler wie eine falsche Passphrase aus. Genau
diese Verwechslung hat beim Posteingang auf djouhri.de viel Zeit gekostet.

## Prüfen

```bash
# Logik (40 Tests, PBKDF2 mit der echten Rundenzahl, deshalb ~10 s)
pnpm --filter @saganta/tagebuch test

# Verdrahtung am laufenden Dienst: Egress, Klartext auf der Platte,
# Zugriffsprotokoll. Legt einen Testeintrag am 1901-01-01 an und raeumt ihn ab.
bash ../../scripts/tagebuch-vertraulichkeit-pruefen.sh

# Backend (36 Tests, laufen im Image, nicht gegen den Quellbaum)
bash ../../services/tagebuch-api/run-tests.sh
```

## Bauen und ausrollen

```bash
cd ../../infra
docker compose -f docker-compose.yml -f docker-compose.override.lan.yml \
  up -d --build tagebuch-api
docker compose -f docker-compose.yml -f docker-compose.override.lan.yml \
  up -d --build tagebuch
```

Einmalig vorher: `bash infra/tagebuch-env-anlegen.sh` (übernimmt die
bestehenden Geheimnisse, würfelt keine neuen).
