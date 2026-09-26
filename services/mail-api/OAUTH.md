# Mailkonten ohne Passwort verbinden (OAuth2)

Stand 2026-09-13. Der Code ist fertig und getestet, **aktiv ist der Weg erst
nach einer Registrierung beim Anbieter.** Diesen Schritt kann keine Software
ersetzen: er verlangt ein Konto beim Anbieter und eine Zustimmung im Namen der
Anwendung.

Bis dahin bleibt der bestehende Weg mit App-Passwort der einzige, und die
Oberfläche zeigt den OAuth-Knopf gar nicht erst an. Das ist Absicht: ein Knopf,
der beim Anbieter in einen Fehler läuft, sieht aus wie ein Ausfall dieser
Anwendung.

## Was OAuth2 besser macht

Ein App-Passwort ist kein schlechter Weg: es ist ein eigenes, einzeln
widerrufbares Geheimnis mit Zugriff nur auf Mail, und es liegt hier
Fernet-verschlüsselt. An drei Stellen ist OAuth2 trotzdem besser:

1. **Es liegt gar kein Dauer-Passwort mehr hier.** Das Zugriffstoken läuft nach
   einer Stunde ab; was bleibt, ist ein Auffrischungstoken, den der Anbieter
   jederzeit entwerten kann.
2. **Widerrufbar von der anderen Seite.** Ein Klick im Google- oder
   Microsoft-Konto. Beim App-Passwort muss man wissen, welches von mehreren zu
   dieser Anwendung gehört.
3. **Es überlebt einen Passwortwechsel.** Ein App-Passwort nicht immer, und dann
   steht in der Oberfläche ein Anmeldefehler, dessen Ursache Wochen zurückliegt.

## Schritt 1: Beim Anbieter registrieren (Owner)

### Google / Gmail

1. [console.cloud.google.com](https://console.cloud.google.com) → Projekt anlegen
2. **Gmail API** aktivieren
3. **OAuth-Zustimmungsbildschirm** einrichten (extern), eigene Adresse als
   Testnutzer eintragen
4. **Anmeldedaten → OAuth-Client-ID → Webanwendung**, als autorisierte
   Weiterleitungs-URI eintragen:
   `https://post.<deine-domaene>/oauth/rueckleitung`
5. Client-ID und Client-Geheimnis notieren

⚠️ **Der Gmail-Scope ist eingeschränkt.** Solange die Anwendung nicht von Google
überprüft ist, funktioniert der Fluss **nur für Konten, die als Testnutzer
eingetragen sind**. Für den Eigenbedarf reicht das; die Überprüfung wäre nur
nötig, um Fremde anzuschließen, und sie dauert Wochen.

### Microsoft / Outlook

1. [entra.microsoft.com](https://entra.microsoft.com) → App-Registrierungen → Neu
2. Weiterleitungs-URI (Web): `https://post.<deine-domaene>/oauth/rueckleitung`
3. **API-Berechtigungen** (delegiert): `IMAP.AccessAsUser.All`,
   `SMTP.Send`, `offline_access`
4. Unter **Zertifikate & Geheimnisse** ein Client-Geheimnis erzeugen

## Schritt 2: Eintragen

Die Werte gehören in `services/mail-api/.env`. Weil Secret-Dateien hier gegen
direkte Bearbeitung gesperrt sind, gibt es dafür das Werkzeug
`~/homelab-work/saganta-envzeilen/setzen.py` (Trockenlauf als Vorgabe):

```
OAUTH_REDIRECT_URL=https://post.<deine-domaene>/oauth/rueckleitung
OAUTH_GOOGLE_CLIENT_ID=…
OAUTH_GOOGLE_CLIENT_SECRET=…
OAUTH_MICROSOFT_CLIENT_ID=…
OAUTH_MICROSOFT_CLIENT_SECRET=…
```

Danach neu erstellen, nicht nur neu starten:

```bash
cd infra && docker compose -f docker-compose.yml \
  -f docker-compose.override.lan.yml up -d --force-recreate saganta-mail-api
```

Gegenprobe: `GET /api/mail/oauth/anbieter` muss den Anbieter jetzt nennen. Eine
leere Liste heißt, dass mindestens einer der drei Werte fehlt.

## Schritt 3: Verbinden

In der Post unter **Konten** steht dann „Ohne Passwort verbinden". Der Rest
läuft beim Anbieter.

## Was beim Bauen aufgefallen ist

Vier Stellen, an denen es still schiefgeht, alle im Code festgehalten und durch
Tests abgesichert:

- **`access_type=offline` und `prompt=consent`** sind bei Google Pflicht. Ohne
  das erste kommt gar kein Auffrischungstoken; ohne das zweite kommt bei einer
  *wiederholten* Freigabe keiner. Der Zugang stirbt dann nach einer Stunde, ohne
  dass irgendwo ein Fehler steht, und zwar nur beim zweiten Verbinden.
- **Der Scope `https://mail.google.com/` ist nötig.** Die schmaleren
  `gmail.readonly`-Scopes reichen für IMAP nicht: der Zugang wird erteilt, IMAP
  lehnt ihn trotzdem ab, und das Konto steht grün in der Liste und bleibt leer.
  Deshalb prüft der Verbinden-Fluss die IMAP-Anmeldung, bevor er speichert.
- **Microsoft kann auf 465 kein implizites TLS**, nur 587 mit STARTTLS. Wer 465
  einträgt, bekommt einen Zeitablauf ohne Fehlermeldung.
- **Manche Anbieter schicken bei der Auffrischung keinen neuen
  Auffrischungstoken.** Wer dann `None` speichert, löscht den einzigen
  Dauerzugang, und das Konto ist beim nächsten Ablauf tot.

## Bestehende Konten

Sie bleiben unverändert. Die neue Spalte `auth_typ` hat den Vorgabewert
`passwort`, und die Nachziehung in `app/db.py` fügt sie additiv hinzu. Ein
Konto, das vorher lief, läuft danach genauso.
