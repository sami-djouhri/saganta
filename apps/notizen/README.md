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

Beide zeigen auf denselben Container. Der nginx im `tardis` schreibt bei
`n.saganta.de` den Pfad intern auf `/n/<merkmal>` um; genau dieser eine Pfad ist
in `hooks.server.ts` von der Anmeldepflicht ausgenommen.

Die kurze Adresse ist kein Schmuck: ein Link zum Weitergeben wird oft abgetippt
oder bricht in Nachrichten um. `n.saganta.de/AbCdEf…` überlebt das eher als
`notizen.saganta.de/freigabe/AbCdEf…`.

**Die Kurz-Adresse ist optional und konfiguriert**, seit 2026-09-12. Sie steht
vollständig in `PUBLIC_NOTIZEN_KURZ_BASIS`, und ohne diesen Wert zeigen geteilte
Links auf den eigenen Ursprung plus `/n`, den dieselbe App bedient. Vorher stand
`.saganta.de` als Bedingung im Quelltext (`src/lib/meta.ts`): in jeder anderen
Installation traf sie nie zu, und in einer, deren Domäne so endet, hätte die App
Links auf eine fremde Instanz ausgegeben.

⚠️⚠️ **Auf dieser Installation steht der Wert auf `https://n.saganta.de`, und
dieser Name löst nirgends auf** (gemessen 2026-10-16 und erneut 2026-10-24:
NXDOMAIN gegen 1.1.1.1 *und* gegen den AdGuard im Heimnetz, kein Eintrag im
`saganta`-Tunnel). Genau davor warnt `infra/notizen-env-anlegen.sh` am Ende
seiner Ausgabe, und genau deshalb schreibt dieses Skript die Zeile **nicht** in
die angelegte Datei; sie wurde später von Hand ergänzt.

**Seit dem 2026-10-24 bricht das keinen Link mehr, und das ist der
eigentliche Punkt dieser Zeile.** Der Teilen-Dialog probt die Basis, bevor er
die Adresse als die eine ausgibt, die es gibt (`src/lib/erreichbar.ts`);
antwortet sie nicht, steht dort der eigene Ursprung, der nachweislich trägt. Die
Probe läuft **im Browser** und nirgendwo sonst: der Container sieht eine andere
Namenswelt (gemessen, `notizen.home.arpa` ist dort ENOTFOUND und im Browser
der normale Weg), eine Namensauflösung im Server hätte also einen
funktionierenden Namen verworfen.

⚠️ Warum das trotzdem zu beheben ist: bei einer **verschlüsselten** Freigabe mit
Schlüssel im Fragment ist die beim Anlegen angezeigte Adresse der einzige Ort,
an dem der Schlüssel existiert. Bis zum 24.10. zeigte sie auf einen toten Namen,
und wer den Dialog schloss, ohne das zu prüfen, hatte ein Chiffrat ohne
Schlüssel: endgültig unlesbar, auch für den Owner, mit einer Erfolgsmeldung
davor. Dieselbe Fehlerklasse wie der Tagebuch-Befund vom 16.10.

**Gefunden wird es jetzt auch ohne Zufall.** `scripts/tunnel-probe.py` hat
seit dem 24.10. eine fünfte Quelle: was eine App selbst als Adresse ausgibt,
gemessen an der Umgebung des laufenden Containers. Vorher kam die Namensliste
aus Ingress und Vhost, also aus dem **Weg**, und `n.saganta.de` fiel nur auf,
weil zufällig noch ein Vhost dafür existierte. Die Sonde meldet dafür jetzt
`KAPUTTE LINKS: eine App gibt diesen Namen aus, DNS fehlt`.

Behebung ist eine Zeile, und sie gehört dem Owner, weil `.env` nicht vom Coding-Agenten
angefasst wird:

```bash
sed -i '/^PUBLIC_NOTIZEN_KURZ_BASIS=/d' apps/notizen/.env
cd infra && docker compose -f docker-compose.yml \
  -f docker-compose.override.lan.yml up -d --build --force-recreate notizen
```

Danach lauten geteilte Links `https://notizen.home.arpa/n/<Merkmal>` und
funktionieren im Heimnetz. Das passt zum Entscheid vom 2026-10-16, die
Notizen heim-only zu halten (`services/shell-api/app/registry.py`). Wer die
Kurz-Adresse wirklich öffentlich will, legt Tunnel-Ingress **und** DNS in
**einem** Vorgang an (Landminen-Regel in der Haupt-`die Projektregeln`) und prüft mit
`python3 scripts/tunnel-probe.py` nach, dass der Name als `vollstaendig` gilt.

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
| `PUBLIC_NOTIZEN_KURZ_BASIS` | **leer lassen** | optional; nur mit Vhost **und** DNS **und** Tunnel-Ingress. Ein hier eingetragener Name ohne DNS macht jeden Freigabe-Link unaufrufbar, siehe oben |

Die drei übernommenen Werte werden **nicht neu erzeugt**. `SAGANTA_BACKEND_SECRET`
ist der Schlüssel, mit dem dieser BFF die kurzlebigen Backend-Token stempelt:
weicht er ab, antwortet jedes Backend mit 401. Die letzten beiden Zeilen sind
ebenfalls Pflicht: ohne sie hält `adapter-node` den eigenen Ursprung für `http://`
und lehnt jedes `POST` als Ursprungs-Konflikt ab.

## Entwicklung

```bash
pnpm --filter @saganta/notizen dev      # http://127.0.0.1:8207
pnpm --filter @saganta/notizen check    # Typen
pnpm --filter @saganta/notizen test     # 52: Markdown, Verschlüsselung, Adressbildung
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

**Die Adresse einer Freigabe entsteht an EINER Stelle.** `freigabeBasis` in
`src/lib/meta.ts` bildet sie, der Server reicht sie durch, und der Teilen-Dialog
bekommt sie als Prop. Bis zum 2026-10-24 baute der Dialog sie selbst aus
`location.origin` neu: vier Ausgabestellen, drei aus derselben Quelle. Dazu
prüfte `freigabeBasis` nur, ob ein Wert **da** ist, nicht ob er **brauchbar**
ist, und die vier Tests daneben prüften genau diese Vorhandenseinsprüfung. Alle
grün, während jeder ausgegebene Link ins Leere zeigte.

Die Formprüfung (`kurzBasisPruefen`) kann die Erreichbarkeit **nicht**
beantworten und gibt es auch nicht vor: `https://n.saganta.de` ist wohlgeformt
und war genau der tote Name. Sie fängt Tippfehler (fehlendes Schema, ein
Fragmentteil in der Basis, ein anderes Protokoll). Ein Test hält diese Grenze
fest, damit sie später niemand für eine Erreichbarkeitsprüfung hält.

**`src/lib/quellen.ts` und `src/lib/verknuepfungen.ts` sind getrennt.** Ersteres
liest Zugangsdaten über `$env/dynamic/private` und darf nie im Browser landen;
letzteres enthält nur Beschriftungen und wird von der Oberfläche gebraucht. Ein
gemeinsames Modul hätte die Server-Geheimnisse ins Browser-Bündel gezogen:
SvelteKit bricht den Build dann ab, und dieser Riegel hat die Trennung hier
erzwungen.
