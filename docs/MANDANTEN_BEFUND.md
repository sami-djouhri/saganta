# Ein Konto, alle Apps: Befund und Stand

Stand 2026-09-18. Ziel (Owner): wer sich bei einer App anmeldet, ist bei allen
angemeldet, und wer bei einem Dienst ein Konto hat, hat es bei allen, spaetestens
beim ersten Aufruf des jeweiligen Dienstes.

## Was schon ging, und was wirklich fehlte

**Die Anmeldung war nie das Problem.** better-auth setzt sein Sitzungs-Cookie auf
die Registrar-Domain (`.saganta.de` / `.home.arpa`), eine Anmeldung traegt
technisch ueber alle Apps. Was fehlte, war die **Berechtigung**: 13 Dienste
trugen eine `ALLOWED_SUBS`-Allowlist mit genau einem Eintrag, dem Owner-Sub. Ein
zweites Konto war also angemeldet und bekam trotzdem ueberall 403.

Das Gate war dabei kein Versehen, sondern eine Bremse mit Grund: bei einem Teil
der Dienste lagen die Daten nicht nach Nutzern getrennt, und dann ist die
Allowlist die einzige Sperre. Wer sie oeffnet, ohne das vorher zu pruefen,
verwandelt ein 403 in ein Datenleck.

## Zwei Werkzeuge statt einer Behauptung

| Werkzeug | Frage, die es beantwortet |
|---|---|
| `scripts/mandanten-pruefung.py` | Ist im **Quelltext** jede Datenroute an einen Mandanten gebunden? |
| `scripts/trennung-beweisen.sh` | Tut der **laufende Dienst** das auch? Konto A legt an, Konto B darf es nicht sehen. |
| `scripts/gate-oeffnen.sh` | Welche Allowlist steht wo, was bedeutet sie dort, und wie kommt man zurueck? |

Beide Pruefwerkzeuge werden gebraucht. Eine Route kann sauber gebunden sein und
trotzdem an einem ungefilterten Join vorbei fremde Daten zeigen; umgekehrt
beweist ein gruener Lauf gegen zwei leere Konten gar nichts. Deshalb legt das
zweite Werkzeug etwas an, bevor es vergleicht, und raeumt es danach weg.

★ `gate-oeffnen.sh` ist das dritte, und es gibt es wegen genau des Fehlers
weiter unten: der Name `ALLOWED_SUBS` bedeutet nicht ueberall dasselbe. Die
Tabelle im Skript fuehrt je Stelle die **Bedeutung** mit (`app`, `briefe`,
`rueckfall`), und `--oeffnen` verweigert alles, was nicht `app` ist. Damit haengt
die Unterscheidung nicht mehr daran, dass der Bearbeiter im richtigen Moment an
den richtigen Kommentar denkt. `--status` zeigt Datei **und** Container
nebeneinander -- weichen sie ab, fehlt der Neustart, und es gilt der Container.
`--schliessen` spielt die Sicherung zurueck.

★ Die Pruefung stempelt ihr Token **im Container**, mit dem Geheimnis, das dort
ohnehin in der Umgebung steht. Es verlaesst den Container nie. Der bequemere Weg
waere, das Backend-Geheimnis herauszureichen, um von aussen zu testen, und das
ist genau der Weg, auf dem Geheimnisse in Protokolle wandern.

## Erledigt: fuenf Dienste offen, Trennung belegt

`notizen-api`, `tagebuch-api`, `assets-api`, `projectdeck-api` und seit dem
2026-09-19 `mail-api`. Alle fuenf halten ihre Daten selbst und filtern auf
`owner_sub` bzw. `sub`; sie pruefen das Backend-JWT (HS256, `iss`, `aud`, `sub`)
und haengen an keinem ungepruefen Header.

Gemessen nach dem Abbau: Konto A legt einen Eintrag an, Konto B bekommt HTTP 200
und eine leere Liste. Der Owner sieht unveraendert seine 10 Posten und 17
Projekte.

### mail-api brauchte einen eigenen Beweis

★★ Das allgemeine `trennung-beweisen.sh` **kann** hier nicht greifen, und es
haette das nicht gesagt. Es legt seinen Pruefsatz ueber die API an, und
`POST /api/mail/accounts` verlangt vorher einen echten IMAP-Login
(`test_connection`, bewusst vor dem Speichern). Ein erfundenes Konto kommt dort
nie durch; das Skript faellt dann auf den Vergleich zweier Leseantworten
zurueck. `mail_accounts` hat heute **0 Zeilen** -- es waere also exakt der Lauf
gewesen, der zwei leere Listen vergleicht, nichts zeigt und gruen aussieht.

`scripts/trennung-beweisen-mail.sh` schreibt den Pruefsatz deshalb direkt in die
Datenbank und liest ausschliesslich ueber die API. Fuenf Fragen, alle beantwortet:

| Gefragt | Erwartet | Gemessen |
|---|---|---|
| A liest Konten / B liest Konten | 1 / 0 | 1 / 0 |
| A liest Nachrichten / B liest Nachrichten | 1 / 0 | 1 / 0 |
| B ruft A's Nachricht **ueber die Kennung** ab | 404 | 404 |
| B schaltet A's Konto | 404 | 404 |
| B loescht A's Konto | 404 | 404 |

★ Die dritte Zeile ist die scharfe. Faellt der Join-Filter weg, laeuft der
Aufruf durch bis in den IMAP-Abruf und antwortet **502**. Ein 502 liest sich wie
eine Stoerung des Dienstes, nicht wie ein Leck -- es waere der Fehler, den
niemand meldet. Ein Listenvergleich allein haette ihn nicht gefunden.

Der Owner-Pfad danach gegengelesen: `/accounts`, `/messages` und `/providers`
antworten mit seinem Sub unveraendert HTTP 200 (0 Konten, wie vorher).
`saganta-post` haengt an diesem Backend und blieb `healthy`, ohne neue Fehler im
Protokoll.

★ **Ein Name trug zwei Bedeutungen.** Im `notizen`-BFF entschied `ALLOWED_SUBS`
nicht ueber die App, sondern darueber, wer in der Verknuepfungssuche die
**Briefe** sieht (der Briefkasten ist noch single-tenant). Wer das App-Gate
oeffnet, haette damit einem zweiten Konto die Post des Owners geoeffnet, an einer
Stelle, an der niemand danach sucht. Getrennt in `BRIEFE_ALLOWED_SUBS`, mit
Rueckfall auf den alten Namen: wer die neue Variable vergisst, behaelt die
Sperre, statt die Briefe still zu oeffnen.

## Offen: die Kette muss erst scharf werden

Die uebrigen Dienste reichen den Nutzer als `X-Saganta-Sub`-Header an einen
nativen Dienst weiter. Dass dieser Header echt ist, wird per HMAC belegt, und
diese Pruefung wurde am 2026-09-05 gebaut (Befund FCS-01). Sie ist bis heute in
**keinem** Dienst scharf: `TENANT_HEADER_ENFORCE` steht ueberall auf 0 oder gar
nicht. Solange die Allowlist auf einem Eintrag steht, ist das folgenlos. Faellt
sie, wird der Header zur blossen Behauptung, die jeder aufstellen kann, der den
Dienst im Netz erreicht.

`scripts/mandanten-kette.py` setzt die Geheimnisse ueber alle Absender hinweg.
Am 2026-09-18 ergaenzt: kalender (5 Stellen), postfach (2), fitness (1). lager,
fitness und mealprep waren bereits verkabelt, nur nicht scharf.

★ Die Zuordnung steht im Skript als Datenstruktur, nicht als Anleitung, weil an
einem Geheimnis mehrere Absender haengen: am `KALENDER_TENANT_SECRET` allein
vier. Wer einen vergisst, merkt es nicht beim Setzen, sondern erst beim
Scharfschalten, und dann antwortet genau der Weg mit 401, an den niemand gedacht
hat.

### Was dafuer noch passieren muss

1. **`kalender` neu starten** (CORE, die Weckkette haengt daran) und
   **`briefkasten`** ueber `postfach/tresor/start.sh` (der braucht das
   Tresor-Kennwort). Beides Owner-Schritte.
2. Logs auf unsignierte Absender ansehen, dann `--erzwingen`.
3. Erst danach die Gates von `aufgaben`, `kalender-bff`, `saganta-fitness`,
   `saganta-lager` und `saganta-mealprep` oeffnen, jeweils mit
   `trennung-beweisen.sh` belegt.

★ `mail-api` stand in dieser Liste und gehoerte nicht hinein: es reicht keinen
`X-Saganta-Sub` weiter, sondern haelt seine Daten selbst (`MailAccount.sub`).
Die Signaturkette entscheidet dort ueber nichts, das Gate konnte deshalb vor den
Neustarts fallen -- und ist am 2026-09-19 gefallen. `saganta-post` steht
ebenfalls nicht mehr hier: seine Allowlist ist das Briefe-Gate, kein App-Gate
(siehe oben), es faellt mit der Mandantentrennung des `briefkasten`.

## Offen: die vier gateten Vhosts

`calendar.home.arpa`, `mail.home.arpa`, `mail.saganta.de` und
`nachrichten.saganta.de` laufen im dev-portal ueber `auth_request` gegen
`shell-api:/auth/check`. Der beantwortet nur die Frage **ob** jemand angemeldet
ist, nicht **wer**. Dahinter liegt der native Dienst mit seiner schwachen
LAN-Anmeldung. Fuer mehrere Konten ist das der eigentliche Blocker: ein zweites
Konto kaeme dort in die Daten des Owners, ohne dass eine Allowlist es aufhaelt.

Der Weg dorthin ist derselbe wie oben (Sub-Header signiert durchreichen, statt
nur „angemeldet" zu pruefen), aber er beruehrt nginx und damit die
Erreichbarkeit aller vier Namen. Eigener Schritt, eigene Runde.

## Offen: drei Tabellen im nativen Kalender

17 der 20 Tabellen sind streng nach `owner_sub` getrennt. Nicht getrennt sind
`settings`, `session_notifications` und `event_reminder_log`.

`settings` ist die wichtige: dort liegt der Feed-Token, und der native Endpunkt
liefert **jedem** denselben, naemlich den des Owners. Wer ihn hat, oeffnet ueber
`token-login` den ganzen Kalender. Der `kalender-bff` haelt deshalb einen eigenen
Owner-Riegel davor (`KALENDER_OWNER_SUB`, fail-closed). Der traegt, solange nur
der Owner die App benutzt; fuer mehrere Konten muss der Feed-Token je Mandant
existieren.

## Das Konto: ein Ort, zweite Tuer davor

`/konto` in der Shell, erreichbar aus jeder App ueber das Standard-Kontomenue
der geteilten Kopfzeile. Die nativen Apps schicken dafuer in den Browser
(`KontoAdresse.fuer(serverUrl)` in `saganta-apps/:core`), statt die Verwaltung
nachzubauen.

Vor dem Bereich steht eine erneute Passwortabfrage, unabhaengig davon, wie
frisch die Anmeldung ist. Der Grund ist der einheitliche Login selbst: die
Sitzung haelt 90 Tage und gilt ueberall, ein kurz unbeaufsichtigtes Geraet
genuegte sonst, um aus einer beliebigen App heraus das Konto zu uebernehmen.

Drei Entscheidungen, die man beim Nachbauen falsch treffen wuerde:

- Die Freigabe gilt **host-only**, anders als das Sitzungs-Cookie. Ueber die
  Registrar-Domain gestreut gaelte eine einmal erteilte Freigabe in jeder App.
- Die Passwortpruefung meldet ihre Probe-Sitzung sofort wieder ab. better-auth
  hat keinen reinen Pruefendpunkt; ohne das Aufraeumen sammeln sich mit jedem
  Kontobesuch Sitzungen an, von denen jede ein gueltiger Zugang ist.
- Die alte Aktion in `/settings` wurde **entfernt**, nicht dupliziert. Ein
  zweiter, ungeschuetzter Weg zum Passwortwechsel haette die Abfrage genau so
  weit ausgehebelt, wie jemand bereit ist, ein Formular ohne die zugehoerige
  Seite abzuschicken.

## Registrierung

Bleibt zu (`AUTH_ALLOW_SIGNUP` ungesetzt, Owner-Entscheid). Die Technik wird
mehrnutzerfaehig gebaut, der Schalter bleibt liegen: aufmachen ist danach eine
Env-Zeile ohne Rebuild. So entsteht kein Zeitfenster, in dem sich jemand
registrieren kann, bevor die Trennung ueberall steht.
