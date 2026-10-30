#!/usr/bin/env bash
#
# Saganta Briefing Player: spielt DEIN persönliches Morgen-Briefing über einen
# angeschlossenen Lautsprecher. Für alle: du brauchst nur deinen Feed-Token und
# ein Gerät mit Lautsprecher (Raspberry Pi, alter Laptop, Mini-PC …).
#
# Deinen Feed-Token findest du in der News-App unter „Mein Briefing" → „Auf Handy
# oder Lautsprecher hören": der Teil der Feed-URL zwischen /briefing/feed/ und .xml
#
#   Beispiel-URL: https://news.saganta.de/briefing/feed/AbC123xyz.xml
#   → Token = AbC123xyz
#
# Nutzung (einmal testen):
#   SAGANTA_FEED_TOKEN=AbC123xyz ./saganta-briefing-player.sh
#
# Automatisch jeden Morgen: per cron (siehe README.md) oder systemd-Timer.
#
# Das Audio wird nachts serverseitig erzeugt; dieses Skript LÄDT es nur und spielt
# es ab, kein Login, kein Smart-Home-Schlüssel, keine Server-Rechte nötig.

set -uo pipefail

FEED_TOKEN="${SAGANTA_FEED_TOKEN:?Bitte SAGANTA_FEED_TOKEN setzen (aus der App: Mein Briefing -> Feed-Link, Teil vor .xml)}"
BASE_URL="${SAGANTA_BASE_URL:-https://news.saganta.de}"
DATE="${SAGANTA_BRIEFING_DATE:-$(date +%F)}"
RETRIES="${SAGANTA_RETRIES:-5}"
RETRY_WAIT="${SAGANTA_RETRY_WAIT:-15}"
# ALSA-Gerät nur relevant für den aplay-Fallback (z. B. plughw:1,0 für eine USB-Karte).
ALSA_DEVICE="${BRIEFING_ALSA_DEVICE:-default}"

URL="${BASE_URL%/}/briefing/audio/${FEED_TOKEN}/${DATE}"
TMP="$(mktemp --suffix=.mp3)"
trap 'rm -f "$TMP"' EXIT

# Audio holen (nachts erzeugt), ein paar Versuche, falls die Generierung noch läuft.
ok=0
for i in $(seq 1 "$RETRIES"); do
  if curl -fsSL -o "$TMP" "$URL" && [ -s "$TMP" ]; then ok=1; break; fi
  [ "$i" -lt "$RETRIES" ] && sleep "$RETRY_WAIT"
done
if [ "$ok" -ne 1 ]; then
  echo "Kein Briefing-Audio für $DATE verfügbar ($URL)" >&2
  exit 1
fi

# Abspielen: den ersten verfügbaren MP3-fähigen Player nehmen.
# Ein bestimmtes ALSA-Gerät (z. B. plughw:1,0 für eine USB-Soundkarte) wird an die
# Player weitergereicht, die das unterstützen; sonst spielt der Player aufs Default-Gerät.
DEV_SET=0; [ "$ALSA_DEVICE" != "default" ] && DEV_SET=1
if   command -v mpg123 >/dev/null 2>&1; then
  if [ "$DEV_SET" = 1 ]; then exec mpg123 -q -a "$ALSA_DEVICE" "$TMP"; else exec mpg123 -q "$TMP"; fi
elif command -v ffplay  >/dev/null 2>&1; then exec ffplay -nodisp -autoexit -loglevel quiet "$TMP"
elif command -v mpv     >/dev/null 2>&1; then
  if [ "$DEV_SET" = 1 ]; then exec mpv --no-video --really-quiet --audio-device="alsa/$ALSA_DEVICE" "$TMP"; else exec mpv --no-video --really-quiet "$TMP"; fi
elif command -v cvlc    >/dev/null 2>&1; then exec cvlc --play-and-exit -q "$TMP"
elif command -v play     >/dev/null 2>&1; then exec play -q "$TMP"           # sox
elif command -v ffmpeg   >/dev/null 2>&1 && command -v aplay >/dev/null 2>&1; then
  exec sh -c "ffmpeg -loglevel error -i '$TMP' -f wav pipe:1 | aplay -D '$ALSA_DEVICE'"
else
  echo "Kein Audio-Player gefunden. Installiere z. B.: sudo apt install mpg123" >&2
  exit 1
fi
