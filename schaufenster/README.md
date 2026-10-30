# Das Schaufenster auf saganta.de

Eine Startseite, je App eine eigene Seite mit Bild, dazu die Telefon-Apps, die
Einrichtung, Impressum und Datenschutz. Kein Anmeldeknopf, kein Tarif, keine
Demo.

## Stand 2026-10-30: Fragerunde und Umbau

Der Owner hat den Inhalt in vier Runden festgelegt:

| Frage | Entscheid |
|---|---|
| Zweck | beides, **Projekt zuerst**, das Angebot darunter |
| Publikum | Technisch Interessierte, Arbeitgeber, Familien |
| Tiefe | **jede App wird vorgestellt**, je App eine Unterseite |
| Bilder | Bildschirmfotos aus einem **Wegwerf-Konto im Live-System** |
| Telefon-Apps | eigener Abschnitt |
| Angebot | eigener Abschnitt mit Ablauf, ohne Preisangaben |
| Code | **bleibt öffentlich** und wird verlinkt (er liegt seit September über die Publish-Pipeline auf GitHub; „erstmal geschlossen" stand auf falscher Annahme) |
| djouhri.de | gegenseitig verlinken |
| Betreiber | nur im Impressum |
| USt-IdNr. | keine, Abschnitt entfernt |
| Ausrollen | **erst alles fertig**, dann in einem Schritt |
| Sprache | nur Deutsch |

**Gebaut wird mit `bauen.py`** aus `quelle/` (Daten in `inhalt.py`, Fragmente
daneben), weil fünfzehn Seiten mit gleichem Kopf und Fuß von Hand
auseinanderlaufen. Auf netcup liegen weiter nur fertige Dateien. Jede
Funktion in `inhalt.py` ist am Quelltext der Oberfläche belegt; SaaS-Reste
(Pro-Abzeichen, Abo, Stripe) und Halbfertiges stehen bewusst nicht drin.

**Was die Bilder zeigen können, ist gemessen, nicht angenommen.** Alle
Dienste trennen die Daten je Nutzer (`docs/MANDANTEN_BEFUND.md`), mit zwei
Folgen für das Muster-Konto: **Post bleibt leer** (die Briefe sind noch
single-tenant und für fremde Konten zu, E-Mail braucht einen echten
IMAP-Login), und die **Übersicht** zeigt „Heute" und „Offene Punkte" nur dem
Owner (`OWNER_SUB`). Für diese zwei Bilder braucht es eine eigene Lösung.

**Das Konto:** `werkzeug/muster-konto.sh --anlegen | --status | --loeschen`.
Registrierung bleibt zu, der Hash kommt von better-auth selbst, das Passwort
steht nur in einer Datei mit 600. Löschen räumt alle Dienste (über
`scripts/konto-loeschen.py`), den Kalender und die Anmeldung und greift nur
auf die feste Muster-Adresse. ⚠️ Das Anlegen ist ein Schreibzugriff auf die
Auth-Datenbank und wurde in der Sitzung vom 30.10. nicht freigegeben:
Handgriff.

## Warum es diese Seite überhaupt gibt

Am 2026-10-21 hat der Owner entschieden, dass Saganta kein SaaS-Produkt mehr ist,
sondern die private Suite seiner Familie. Die 16 `saganta.de`-Namen führen seitdem
nicht mehr ins Haus, ein 404-Riegel in `tardis/nginx.conf` ersetzt sie. Damit
war die Domain leer, und die Frage offen, was sie noch tragen soll.

**Der Ort ist netcup und nicht host.** Dort läuft schon Caddy für djouhri.de.
Eine Seite im Haus zu lassen, nur weil sie harmlos aussieht, hieße den Weg offen
zu halten, dessen Schließung der ganze Punkt war.

## Warum statisch und nicht die vorhandene Marketing-Fläche

In `apps/shell/src/routes` liegen Landing, `/apps`, `/preise`, Impressum,
Datenschutz und AGB, zusammen über 1300 Zeilen. Übernommen ist davon das
Aussehen, nicht der Text, und zwar aus zwei Gründen:

- **Der Text verkauft ein Produkt, das es nicht mehr gibt.** Die Preisseite
  spricht von „Unlimited", „monatlich kündigen" und einem Business-Tarif, in dem
  *wir* die Suite beim Kunden einrichten. Genau das hat der Entscheid vom 21.10.
  abgeschafft. `abgleich.py` hält diese Wörter von hier fern.
- **Schaufenster, Anmeldung und Dashboard sind in der shell EIN Prozess.** In
  `hooks.server.ts` stehen `/`, `/preise` und `/login` zusammen in `publicPaths`,
  und `/` rendert je nach Sitzung Landing oder Dashboard. „Nur die Frontpage offen
  lassen" war deshalb keine Einstellung, sondern eine Trennung.

Die Bauart ist fertiges HTML (seit 30.10. aus `bauen.py`), das Caddy direkt ausliefert. Kein Build,
kein Container, keine Node-Kette auf einem öffentlichen Wirt. Die Farben und die
beiden Schriften sind aus `packages/design-tokens/src/theme.css` **übernommen**,
nicht importiert: die Tokens sind eine Tailwind-Theme-Datei und brauchen einen
Build.

**Eine Kopie driftet, und diese hier driftete noch am Tag ihrer Entstehung.**
Während die Seite gebaut wurde, verschob eine parallele Sitzung `--dunkel-akzent`
um eine Stufe. Deshalb vergleicht `abgleich.py` die sechzehn übernommenen Werte
gegen die Tokens und meldet jede Abweichung. Als **Hinweis**, nicht als Fund: die
Seite ist mit einer anderen Goldstufe nicht falsch, nur nicht mehr deckungsgleich,
und hätte das dasselbe Gewicht wie ein fehlendes Impressum, würde eins von beiden
als Rauschen mitgelesen. Der Hinweis sagt außerdem, ob die Abweichung gegen
einen **noch nicht committeten** Stand steht: dann arbeitet nebenan jemand, und
es gibt nichts zu tun.

## Die Prüfungen

```bash
python3 selbsttest.py      # schlägt der Prüfer überhaupt an?
python3 abgleich.py        # die Seite gegen die Suite
python3 abgleich.py --netcup   # dazu Caddy-Logging und die Mailadressen
```

`abgleich.py` prüft acht Dinge, und jedes davon hat einen Anlass:

| Prüfung | Warum |
|---|---|
| App-Deckung in beide Richtungen | Die Seite nennt elf Apps namentlich. Dieselbe Information steht in `packages/ui/src/apps.ts`. Eine abgeschriebene Liste veraltet in beide Richtungen. |
| Die Anzahl als Wort | „Elf Apps" ist ein Zählstand auf einer öffentlichen Seite. Geprüft wird jede Stelle, an der eine Zahl vor „Apps" steht, auch mit einem Wort dazwischen. |
| Platzhalter | Eine Seite ohne Anschrift darf nicht öffentlich stehen (§ 5 DDG). `deploy.sh` bricht daran ab. |
| Fremde Inhalte, Skripte, Cookies, Formulare | `datenschutz.html` sagt zu, dass es nichts davon gibt. Jede einzelne Zusage hat ihre Prüfung, auch `<form>`: sonst macht ein später eingefügtes Kontaktformular die Erklärung falsch, ohne dass irgendwo etwas rot wird. |
| Farbdeckung gegen die Tokens | Sechzehn kopierte Werte. Meldet als Hinweis, nicht als Fund. |
| Reste des SaaS-Modells | Tarif, Abo, `/login` und Geschwister. |
| Inline-Stile | Der Caddy-Block setzt eine CSP ohne `unsafe-inline`. Ein `style`-Attribut wird dann verworfen, ohne Fehlermeldung. |
| Langer Gedankenstrich | Regel, auch in Kommentaren. |

`selbsttest.py` ist kein Beiwerk: er füttert jede dieser Prüfungen mit einem
Fall, den sie finden **muss**, und einem, bei dem sie schweigen muss. Die
Negativfälle sind der eigentliche Punkt, denn ein Prüfer, der immer grün meldet,
sieht genauso aus wie einer, der nichts zu meckern hat.

**Drei Fehler fand nicht der Prüfer, sondern das Bild**, und sie sagen etwas
über die Grenze automatischer Kontrolle:

- `index.html` trug zwei `style`-Attribute, geschrieben bevor der Caddy-Block
  seine CSP bekam. Daraus entstand die Prüfung, nicht umgekehrt.
- `datenschutz.html` sagte „besteht aus drei HTML-Dateien", es sind vier. Ein
  Zählstand im eigenen Text, genau die Sorte Drift, gegen die der Rest hier
  gebaut ist. Behoben durch Streichen der Zahl, nicht durch Korrigieren: eine
  Zahl, die niemand nachhält, wird wieder falsch.
- „keine Schaltflächen soziale Netzwerke" war schlicht falsches Deutsch.

Deshalb vor dem Ausliefern einmal rendern, nicht nur prüfen:

```bash
~/.cache/ms-playwright/chromium-1234/chrome-linux/chrome --headless --no-sandbox \
  --window-size=1100,2700 --screenshot=/tmp/sf.png \
  file://$PWD/oeffentlich/index.html
# dunkles Theme: --blink-settings=preferredColorScheme=0
```

Der Punkt der `--netcup`-Prüfungen: `datenschutz.html` behauptet „keine
Zugriffsprotokolle", und das ist keine Absichtserklärung, sondern eine Aussage
über eine Konfiguration. Caddy schreibt Zugriffe nur mit ausdrücklicher
`log`-Direktive, und die Prüfung liest nach, dass keine da ist. Dasselbe bei der
Kontaktadresse: sie wird gegen die Mailcow-Datenbank geprüft, weil eine Adresse
im Impressum, die bouncet, § 5 DDG nicht erfüllt.

## Ausliefern

```bash
bash deploy.sh            # Dateien nach netcup:/var/www/saganta
bash deploy.sh --caddy    # dazu den Vhost einfügen und Caddy neu laden
```

**Die Reihenfolge ist nicht beliebig**, und `deploy.sh` erzwingt sie statt sie zu
beschreiben:

1. **Impressum ausfüllen.** Solange `PLATZHALTER` drinsteht, bricht der Abgleich
   ab, und damit das Ausliefern.
2. **DNS umstellen** (Owner, braucht `CF_API_TOKEN` aus Vaultwarden):
   A-Record `saganta.de` und `www` auf `192.0.2.10`, PROXIED (orange), wie
   bei djouhri.de.
3. **Dann den Vhost.** Caddy holt beim Laden ein Zertifikat über eine
   HTTP-Challenge. Zeigt der Name noch nicht hierher, scheitert sie wiederholt und
   Let's Encrypt begrenzt die Versuche.

⚠️ **Bei PROXIED antworten Cloudflare-IPs, nicht die netcup-IP.** Die
DNS-Vorprüfung in `deploy.sh --caddy` schlägt dann an und verweist darauf, den
Block von Hand einzufügen. Das ist kein Fehler des Skripts: es kann von außen
nicht unterscheiden, ob der A-Record richtig steht oder fehlt, wenn ein Proxy
davorliegt.

`caddy-block.conf` ist am 2026-10-24 auf netcup gegen `caddy validate`
gelaufen und meldet „Valid configuration". ⚠️ Allein validiert scheitert er an
`import sectxt`: das Snippet steht oben im echten Caddyfile. Zum Nachprüfen die
ersten neun Zeilen davon voranstellen.

## Zwei Abhängigkeiten im Caddy-Block, die still zuschlagen

- **Der Origin-Lockdown setzt PROXIED voraus.** Steht saganta.de bei Cloudflare
  auf DNS-only, antwortet die Seite jedem mit 403, und das sieht wie ein kaputter
  Server aus. Dann den `@not_cf`-Abschnitt entfernen.
- **Die Cloudflare-IP-Liste ist vom 2026-07-31** und steht ein zweites Mal im
  Caddyfile, weil djouhri.de sie inline führt. Veraltet sie, sperrt sie ab dann
  zwei Seiten aus statt einer. Ein Snippet für beide wäre der Aufräumschritt, er
  fasst aber einen laufenden öffentlichen Vhost an.

**HSTS steht hier ohne `includeSubDomains`**, anders als bei djouhri.de. Die
Subdomains dieser Domain sind am 21.10. stillgelegt worden; eine Zusicherung über
zwei Jahre für Namen, die niemand mehr bedient, bringt nichts und verbaut den Weg,
falls einer zurückkommt.

## Offen

- **Muster-Konto anlegen** (Owner): `bash werkzeug/muster-konto.sh --anlegen`.
  Danach Beispieldaten, Bilder nach `oeffentlich/bilder/<seite>.webp`, Konto
  wieder löschen. `abgleich.py` hält die Auslieferung an, solange ein Bild fehlt.
- **Bilder für Post und Übersicht**: im Muster-Konto leer, siehe oben.
- **Anschrift im Impressum** (Owner), `quelle/impressum.html`, dann `bauen.py`.
- **DNS bei Cloudflare** (Owner, Token aus Vaultwarden).
- **djouhri.de verlinkt zurück**, sobald die Seite live ist: `href` am
  Saganta-Eintrag in `lib/projects.ts` und `PROOF_PUBLIC_LINKS` in `lib/site.ts`
  (beide am 30.10. bewusst geleert, weil saganta.de 404 antwortete).
- **`hallo@saganta.de` existiert nicht**, das Impressum in `apps/shell` nennt
  es weiter. Das Schaufenster nimmt `kontakt@`.
