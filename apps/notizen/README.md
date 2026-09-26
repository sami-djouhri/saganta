# saganta-notizen

Notizbücher, Markdown-Notizen mit Anhängen, Verknüpfungen zu Terminen,
Aufgaben, Zielen, Projekten, Kontakten und Briefen, und teilbare Links,
wahlweise offen oder Ende-zu-Ende-verschlüsselt.

Frontend (SvelteKit-BFF) zu `services/notizen-api`.

## Zwei Adressen, ein Container

| Adresse | Zweck |
|---|---|
| `notizen.saganta.de` | die App, hinter dem Saganta-Login |
| `n.saganta.de/<merkmal>` | die öffentliche Leseseite einer Freigabe, ohne Konto |

Beide zeigen auf denselben Container. Der nginx im `dev-portal` schreibt bei
`n.saganta.de` den Pfad intern auf `/n/<merkmal>` um; genau dieser eine Pfad ist
in `hooks.server.ts` von der Anmeldepflicht ausgenommen.

Die kurze Adresse ist kein Schmuck: ein Link zum Weitergeben wird oft abgetippt
oder bricht in Nachrichten um. `n.saganta.de/AbCdEf…` überlebt das eher als
`notizen.saganta.de/freigabe/AbCdEf…`.

★ **Die Kurz-Adresse ist optional und konfiguriert**, seit 2026-09-12. Sie steht
vollständig in `PUBLIC_NOTIZEN_KURZ_BASIS` (also `https://n.saganta.de`), und
ohne diesen Wert zeigen geteilte Links auf den eigenen Ursprung plus `/n`, den
dieselbe App bedient. Vorher stand `.saganta.de` als Bedingung im Quelltext
(`src/lib/meta.ts`): in jeder anderen Installation traf sie nie zu, und in einer,
deren Domäne so endet, hätte die App Links auf eine fremde Instanz ausgegeben.
Wer den Wert setzt, braucht auch den Vhost dafür (die drei Einträge aus
`die Projektregeln`: `server_name`, DNS-Rewrite, `ui_url`).

## Umgebung

Die echte `.env` liegt verschlüsselt im SOPS-Vault (`infra/secrets/vault/`) und
ist nicht im Repo. Diese Werte braucht sie:

| Schlüssel | Wert | Herkunft |
|---|---|---|
| `AUTH_SERVICE_URL` | `http://saganta-auth:3000` | fest |
| `AUTH_LOGIN_URL` | `https://saganta.de/login` | fest |
| `NOTIZEN_API_BASE_URL` | `http://saganta-notizen-api:8000` | fest |
| `KALENDER_BFF_BASE_URL` | `http://saganta-kalender-bff:8000` | fest |
| `PROJECTDECK_API_BASE_URL` | `http://saganta-projectdeck-api:8000` | fest |
| `BRIEFKASTEN_BASE_URL` | `http://briefkasten:8000` | fest |
| `BRIEFKASTEN_INTERNAL_TOKEN` | Geheimnis | **aus `apps/post/.env` übernehmen** |
| `ALLOWED_SUBS` | Kontoliste | **aus `apps/post/.env` übernehmen** |
| `SAGANTA_BACKEND_SECRET` | Geheimnis | **aus einer bestehenden App-`.env` übernehmen** |
| `HOST` / `PORT` | `0.0.0.0` / `3000` | fest |
| `PROTOCOL_HEADER` | `x-forwarded-proto` | fest |
| `HOST_HEADER` | `x-forwarded-host` | fest |
| `PUBLIC_NOTIZEN_KURZ_BASIS` | `https://n.saganta.de` | **optional**, nur mit eigenem Vhost |

★ Die drei übernommenen Werte werden **nicht neu erzeugt**. `SAGANTA_BACKEND_SECRET`
ist der Schlüssel, mit dem dieser BFF die kurzlebigen Backend-Token stempelt:
weicht er ab, antwortet jedes Backend mit 401. Die letzten beiden Zeilen sind
ebenfalls Pflicht: ohne sie hält `adapter-node` den eigenen Ursprung für `http://`
und lehnt jedes `POST` als Ursprungs-Konflikt ab.

## Entwicklung

```bash
pnpm --filter @saganta/notizen dev      # http://127.0.0.1:8207
pnpm --filter @saganta/notizen check    # Typen
pnpm --filter @saganta/notizen test     # Markdown-Renderer + Verschlüsselung
```

## Was hier bewusst nicht mit Bibliothek gelöst ist

**`src/lib/markdown.ts`** baut DOM-Knoten statt HTML-Zeichenketten, es gibt in
der Datei kein `innerHTML`. Damit ist das Einschleusen von Markup strukturell
ausgeschlossen und nicht nachträglich weggefiltert. Der Renderer stellt auch
fremde Inhalte auf der öffentlichen Leseseite dar; eine Filterliste wäre dort
immer nur so gut wie ihre letzte Aktualisierung. Der Preis: kein voller
Markdown-Umfang. Eingebettete Bilder aus fremden Adressen fehlen absichtlich:
sie würden dem fremden Server verraten, wer wann eine geteilte Notiz öffnet.

**`src/lib/krypto.ts`** nutzt WebCrypto (AES-GCM-256). Der Schlüssel entsteht im
Browser und geht entweder im Adress-Fragment (`#…`, wird nie an den Server
gesendet) oder über PBKDF2 aus einem Passwort. Der Server sieht in beiden Fällen
nur das Chiffrat.

**`src/lib/quellen.ts` und `src/lib/verknuepfungen.ts` sind getrennt.** Ersteres
liest Zugangsdaten über `$env/dynamic/private` und darf nie im Browser landen;
letzteres enthält nur Beschriftungen und wird von der Oberfläche gebraucht. Ein
gemeinsames Modul hätte die Server-Geheimnisse ins Browser-Bündel gezogen:
SvelteKit bricht den Build dann ab, und dieser Riegel hat die Trennung hier
erzwungen.
