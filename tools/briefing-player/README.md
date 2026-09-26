# Saganta Briefing Player

Spiel dein persönliches Morgen-Briefing automatisch über einen Lautsprecher,
egal ob du ein Smart-Home hast oder nicht. Das ist **für alle** gedacht, nicht nur
für den Server-Betreiber.

Es gibt drei Wege, dein Briefing morgens zu hören. Nimm den, der zu dir passt:

## 1. Podcast-App / Alexa (am einfachsten, kein Extra-Gerät)

1. Öffne die News-App → **Mein Briefing** → **„Auf Handy oder Lautsprecher hören"**.
2. Kopiere den Feed-Link (`https://news.saganta.de/briefing/feed/DEIN-TOKEN.xml`).
3. Füge ihn in deiner Podcast-App hinzu (Apple Podcasts, Pocket Casts, AntennaPod …)
   oder als **Alexa Flash Briefing** bzw. per Routine auf deinem Smart-Speaker.
4. Fertig: jeden Morgen liegt die neue Folge bereit / spielt automatisch.

Der Link ist privat (nur dein Token). Gib ihn nicht weiter; du kannst ihn in der
App jederzeit neu erzeugen, falls er doch mal rausfällt.

## 2. Eigener Lautsprecher (Raspberry Pi, alter Laptop, Mini-PC)

Für „dumme" Boxen ohne Alexa: ein kleines Skript lädt dein Briefing und spielt es ab.

```bash
# einmalig: Player installieren (Debian/Raspberry Pi OS)
sudo apt install -y mpg123 curl
curl -fsSL https://news.saganta.de/tools/saganta-briefing-player.sh -o ~/saganta-briefing-player.sh
chmod +x ~/saganta-briefing-player.sh

# testen (Token aus der App: Mein Briefing -> Feed-Link, Teil vor .xml)
SAGANTA_FEED_TOKEN=DEIN-TOKEN ~/saganta-briefing-player.sh
```

**Jeden Morgen um 06:30 automatisch**: per cron (`crontab -e`):

```cron
30 6 * * *  SAGANTA_FEED_TOKEN=DEIN-TOKEN /home/pi/saganta-briefing-player.sh >> /home/pi/briefing.log 2>&1
```

Oder per systemd-Timer: siehe `examples/` in diesem Ordner.

### Optionen (Umgebungsvariablen)
| Variable | Default | Zweck |
|----------|---------|-------|
| `SAGANTA_FEED_TOKEN` |: (Pflicht) | Dein privater Feed-Token |
| `SAGANTA_BASE_URL` | `https://news.saganta.de` | Basis-URL (bei eigener Domain anpassen) |
| `BRIEFING_ALSA_DEVICE` | `default` | Nur für den `aplay`-Fallback (z. B. `plughw:1,0` für eine USB-Soundkarte) |
| `SAGANTA_RETRIES` / `SAGANTA_RETRY_WAIT` | `5` / `15` | Wiederholversuche, falls das Audio morgens noch generiert wird |

Der Player nimmt automatisch den ersten gefundenen Player: `mpg123`, `ffplay`,
`mpv`, `cvlc`, `sox play` oder `ffmpeg → aplay`.

## 3. In-App anhören (ohne Setup)

In der News-App unter **Mein Briefing** gibt es einen Play-Button: direkt im Browser,
auf jedem Gerät, ganz ohne Einrichtung.

---

**Wie es funktioniert:** Das Briefing-Audio wird nachts serverseitig für jeden Nutzer
erzeugt. Feed und Audio sind über eine öffentliche, aber unerratbare Token-URL
erreichbar (Cloudflare), kein Login, kein Smart-Home-Schlüssel, keine Server-Rechte.
Damit hat **jeder** denselben Weg zum Morgen-Briefing wie der Betreiber selbst.
