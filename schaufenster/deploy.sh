#!/usr/bin/env bash
# Liefert das Schaufenster nach netcup aus.
#
# Zwei Schritte, bewusst getrennt:
#   ./deploy.sh            die Dateien nach /var/www/saganta (beruehrt nichts Laufendes)
#   ./deploy.sh --caddy    dazu den Vhost einfuegen und Caddy neu laden
#
# Der zweite Schritt ist der riskante: auf demselben Caddy haengen djouhri.de und
# die Mailcow-Oberflaeche, ein Syntaxfehler nimmt beide mit. Deshalb prueft er
# das DNS vorher, legt eine Sicherung an und validiert die Konfiguration, bevor
# er sie laedt.
set -euo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIRT="netcup"
ZIEL="/var/www/saganta"
NETCUP_IP="192.0.2.10"
# Liegt im Zielverzeichnis und entscheidet, ob `rsync --delete` dort raeumen
# darf. Ohne diese Marke koennte ein vertippter Pfad (/var/www statt
# /var/www/saganta) die security.txt des Nachbarn loeschen.
MARKE=".schaufenster"

sage() { printf '\n== %s\n' "$*"; }

sage "Abgleich gegen den App-Katalog und die Zusagen der Datenschutzseite"
python3 "$HIER/selbsttest.py"
python3 "$HIER/abgleich.py" --netcup

sage "Zielverzeichnis pruefen"
# Das Ziel darf neu sein oder die Marke tragen. Alles andere ist ein fremdes
# Verzeichnis, und `--delete` wuerde darin aufraeumen.
if ssh -o BatchMode=yes "$WIRT" "test -d $ZIEL"; then
  if ! ssh -o BatchMode=yes "$WIRT" "test -f $ZIEL/$MARKE"; then
    echo "ABBRUCH: $ZIEL auf $WIRT existiert, traegt aber kein $MARKE." >&2
    echo "Entweder ist der Pfad falsch, oder dort liegt etwas anderes." >&2
    exit 1
  fi
  echo "vorhanden und als Schaufenster markiert"
else
  ssh -o BatchMode=yes "$WIRT" "mkdir -p $ZIEL"
  echo "neu angelegt"
fi

sage "Dateien ausliefern"
# --chmod ist Pflicht, nicht Kosmetik: eine ACL im Quellbaum gibt neuen Dateien
# 660, und Caddy laeuft als eigener Nutzer. Ohne die Rechte antwortet die Seite
# mit 403, waehrend die Dateien vollstaendig und richtig an Ort und Stelle
# liegen. Gleiche Falle wie beim wake-gateway auf node1.
rsync -a --delete --chmod=F644,D755 \
  --exclude="$MARKE" \
  "$HIER/oeffentlich/" "$WIRT:$ZIEL/"
ssh -o BatchMode=yes "$WIRT" "printf 'Ausgeliefert aus saganta/schaufenster, nicht von Hand bearbeiten.\n' > $ZIEL/$MARKE && chmod 644 $ZIEL/$MARKE"
ssh -o BatchMode=yes "$WIRT" "ls -la $ZIEL | head -20"

if [[ "${1:-}" != "--caddy" ]]; then
  sage "Fertig, ohne Caddy"
  cat <<'ENDE'
Die Dateien liegen auf netcup. Erreichbar sind sie noch nicht: der Vhost fehlt.

Der naechste Schritt gehoert dem Owner, weil er zwei Dinge braucht, die hier
nicht liegen:

  1. DNS bei Cloudflare auf netcup umstellen (A-Record auf 192.0.2.10,
     PROXIED/orange, plus www). Braucht CF_API_TOKEN aus Vaultwarden.
  2. Die Pflichtangaben im Impressum. Solange dort PLATZHALTER steht, bricht
     dieses Skript vorher ab, und das ist Absicht.

Danach:  ./deploy.sh --caddy
ENDE
  exit 0
fi

sage "DNS pruefen, bevor Caddy ein Zertifikat holt"
# Ohne diese Pruefung scheitert die HTTP-Challenge wiederholt, und Let's Encrypt
# begrenzt die Versuche. Gemessen wird am oeffentlichen Namen, nicht an der
# Absicht.
aufgeloest="$(getent hosts saganta.de | awk '{print $1}' | tr '\n' ' ')"
echo "saganta.de loest auf: ${aufgeloest:-nichts}"
if [[ "$aufgeloest" != *"$NETCUP_IP"* ]]; then
  echo "ABBRUCH: saganta.de zeigt nicht auf $NETCUP_IP." >&2
  echo "Bei Cloudflare PROXIED ist das normal: dann antworten Cloudflare-IPs," >&2
  echo "und dieser Pfad ist der falsche. Den Block in diesem Fall von Hand" >&2
  echo "einfuegen, nachdem der A-Record steht (caddy-block.conf)." >&2
  exit 1
fi

sage "Caddy-Block einfuegen"
if ssh -o BatchMode=yes "$WIRT" "grep -q '^saganta\.de {' /etc/caddy/Caddyfile"; then
  echo "steht schon drin, nichts zu tun"
else
  scp -o BatchMode=yes "$HIER/caddy-block.conf" "$WIRT:/tmp/saganta-block.conf"
  ssh -o BatchMode=yes "$WIRT" bash -s <<'ENDE'
set -euo pipefail
sicherung="/etc/caddy/Caddyfile.bak-saganta-$(date +%Y%m%d-%H%M%S)"
cp /etc/caddy/Caddyfile "$sicherung"
echo "Sicherung: $sicherung"
printf '\n' >> /etc/caddy/Caddyfile
cat /tmp/saganta-block.conf >> /etc/caddy/Caddyfile
rm -f /tmp/saganta-block.conf
if ! caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile; then
  echo "ABBRUCH: Konfiguration ungueltig, Stand wird zurueckgerollt." >&2
  cp "$sicherung" /etc/caddy/Caddyfile
  exit 1
fi
systemctl reload caddy
ENDE
fi

sage "Nachmessen"
sleep 3
for u in https://saganta.de/ https://saganta.de/impressum.html https://saganta.de/gibtesnicht; do
  printf '%-42s ' "$u"
  curl -s -o /dev/null -w '%{http_code}\n' --max-time 15 "$u" || echo "keine Antwort"
done
echo
echo "Erwartet: 200, 200, 404."
