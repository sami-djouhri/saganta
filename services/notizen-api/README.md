# saganta-notizen-api

FastAPI + SQLite. Notizbücher, Notizen, Anhänge, Verknüpfungen und Freigaben.
Gegenstück zum BFF `apps/notizen`.

## Zwei Hausordnungen in einem Dienst

| Bereich | Zugang |
|---|---|
| `/api/…` | HS256-JWT vom BFF (`aud: notizen-api`), **jede Zeile auf `owner_sub` gefiltert** |
| `/oeffentlich/…` | ohne Konto, Zugang allein über ein unratbares Merkmal |

Die Trennung ist im Code scharf gezogen (`routes_oeffentlich.py` gegen den
Rest); die beiden Teile teilen sich nur das Datenmodell.

## Umgebung

Die echte `.env` liegt verschlüsselt im SOPS-Vault (`infra/secrets/vault/`).

| Schlüssel | Wert |
|---|---|
| `DATABASE_URL` | `sqlite:////data/notizen.db` |
| `ANHANG_VERZEICHNIS` | `/data/anhaenge` |
| `JWT_SECRET` | **identisch zu `SAGANTA_BACKEND_SECRET` in `apps/notizen/.env`** |
| `JWT_ALGORITHM` | `HS256` |
| `CORS_ORIGINS` | `https://notizen.saganta.de,https://notizen.home.arpa,https://n.saganta.de` |
| `ALLOWED_SUBS` | aus `services/projectdeck-api/.env` übernehmen |

★ Der Dienst **startet nicht**, wenn `JWT_SECRET` auf einem `change-me`-Wert
steht (`app/config.py`). Das ist Absicht: ein Dienst mit bekanntem Schlüssel
kann gefälschte Token nicht von echten unterscheiden und liefe still unsicher.
Für lokale Entwicklung `ALLOW_INSECURE_SECRETS=1`.

## Entscheidungen, die man beim Lesen sonst für Zufall hielte

**Ansehen und Öffnen sind zwei Schritte.** `GET /oeffentlich/<merkmal>` verrät
nur, ob sich etwas öffnen lässt, der Inhalt kostet ein `POST …/oeffnen`.
Messenger und Mail-Scanner rufen jeden geteilten Link automatisch für die
Vorschau ab; lieferte `GET` den Inhalt, wäre eine „einmal lesbar"-Notiz
verbraucht, bevor der Empfänger sie gesehen hat. Genau daran kranken die
üblichen Dienste dieser Art.

**Der Abrufzähler wird bedingt hochgesetzt** (ein `UPDATE … WHERE abrufe <
max_abrufe`), nicht gelesen und dann geschrieben. Zwei gleichzeitige Abrufe
könnten sonst beide gewinnen, bei „nur einmal lesbar" wäre das der Bruch der
einzigen Zusage, die diese Betriebsart macht.

**Verbraucht heißt gelöscht.** Beim letzten Abruf und beim Widerruf verschwindet
das Chiffrat aus der Zeile, statt nur einen Vermerk zu bekommen.

**Anhänge einer geöffneten Freigabe brauchen einen Zugriffsschein**
(`app/schein.py`), ein kurzlebiges, an diese Freigabe gebundenes HMAC aus dem
Öffnen-Schritt. Ohne ihn wäre der Anhang über denselben Link erreichbar wie der
Text, nur ohne Zähler, Passwort und Ablauf: die Hintertür zur eigenen Freigabe.

**Zeit ist intern naives UTC**, nicht Berlin wie im Kalender. Dort geht es um
Termine, die lokal gemeint sind; hier um Fristen, die absolut gelten und nicht
mit der Sommerzeit springen dürfen.

**Anhänge werden am Inhalt geprüft**, nicht am Dateinamen und nicht am
gemeldeten Content-Type: beides bestimmt der Absender. SVG ist nicht erlaubt:
es sieht aus wie ein Bild, ist aber ein Dokumentformat mit Skriptfähigkeit.

## Tests

```bash
python -m pytest tests/ -q      # 57 Tests
```

Die Suite deckt vor allem ab, was nach außen wirkt: Mandantengrenze (auch über
Notizbücher und die Suche), Einmal-Lesen, Ablauf, Widerruf, Passwort-Sperre nach
Fehlversuchen, und dass ein Chiffrat nach Verbrauch wirklich fort ist.
