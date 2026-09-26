#!/usr/bin/env bash
# tagebuch-vertraulichkeit-pruefen.sh prueft am LAUFENDEN Dienst, dass das
# Tagebuch haelt, was es zusichert.
#
# Warum es diesen Test zusaetzlich zu den Testsuiten gibt: die pruefen die
# Logik, hier geht es um die Verdrahtung. Netz, Rechte, Protokolle, das
# tatsaechliche Dateisystem. Genau die Dinge, die in einer Testumgebung immer
# stimmen und im Betrieb trotzdem falsch sein koennen. Der Egress-Riegel war
# beim ersten Versuch genau so ein Fall: der Kommentar im Compose behauptete
# ihn, gemessen war er offen.
#
# Der Test schreibt in ein Datum weit vor jeder denkbaren Nutzung (1901-01-01)
# und bricht ab, wenn dort wider Erwarten etwas steht. Er raeumt hinter sich
# auf, auch wenn er unterwegs abbricht.
#
# Aufruf:  bash scripts/tagebuch-vertraulichkeit-pruefen.sh

set -euo pipefail

cd "$(dirname "$0")/.."

CONTAINER_APP="saganta-tagebuch"
CONTAINER_API="saganta-tagebuch-api"
TESTTAG="1901-01-01"
MARKE="KLARTEXTPROBE-$$-DARF-NIRGENDS-STEHEN"

fehler=0
meld_ok()   { echo "   OK      $*"; }
meld_bad()  { echo "   FEHLER  $*"; fehler=$((fehler + 1)); }

echo "== 1. Laufen beide Container? =="
for c in "$CONTAINER_APP" "$CONTAINER_API"; do
  zustand="$(docker inspect --format '{{.State.Health.Status}}' "$c" 2>/dev/null || echo fehlt)"
  if [ "$zustand" = healthy ]; then meld_ok "$c ist healthy"; else meld_bad "$c: $zustand"; fi
done

echo
echo "== 2. Kein Weg nach draussen =="
# Die Zusicherung des Netzes `tagebuch-net` (internal). Gemessen statt geglaubt:
# cc-core allein reicht dafuer NICHT, das ist nicht internal.
ergebnis="$(docker exec "$CONTAINER_API" python -c "
import socket
offen = []
for ziel, port in [('1.1.1.1', 443), ('8.8.8.8', 53)]:
    s = socket.socket(); s.settimeout(4)
    try:
        s.connect((ziel, port)); offen.append(f'{ziel}:{port}')
    except Exception:
        pass
    finally:
        s.close()
print(','.join(offen))
" 2>/dev/null || echo FEHLER)"
if [ -z "$ergebnis" ]; then
  meld_ok "der Dienst erreicht das Internet nicht"
else
  meld_bad "der Dienst erreicht $ergebnis (tagebuch-net nicht internal?)"
fi

echo
echo "== 3. Nimmt der Dienst Klartext an? (der eigentliche Test) =="
# Das Token wird im Container gestempelt, wie es der BFF tut. Das Geheimnis
# liegt dort als Umgebungsvariable und wird nirgends ausgegeben.
docker exec -i -e TESTTAG="$TESTTAG" -e MARKE="$MARKE" "$CONTAINER_API" python - <<'PY'
import base64, hashlib, hmac, json, os, sys, time, urllib.error, urllib.request

geheim = os.environ["JWT_SECRET"]
subs = [s.strip() for s in os.environ.get("ALLOWED_SUBS", "").split(",") if s.strip()]
sub = subs[0] if subs else "vertraulichkeitsprobe"
tag = os.environ["TESTTAG"]
marke = os.environ["MARKE"]


def b64(roh: bytes) -> str:
    return base64.urlsafe_b64encode(roh).decode().rstrip("=")


def token() -> str:
    jetzt = int(time.time())
    kopf = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    rumpf = b64(json.dumps({
        "iss": "saganta", "sub": sub, "email": "", "groups": [],
        "aud": "tagebuch-api", "iat": jetzt, "exp": jetzt + 120,
    }).encode())
    sig = b64(hmac.new(geheim.encode(), f"{kopf}.{rumpf}".encode(), hashlib.sha256).digest())
    return f"{kopf}.{rumpf}.{sig}"


BASIS = "http://127.0.0.1:8000"


def ruf(methode, pfad, koerper=None):
    daten = json.dumps(koerper).encode() if koerper is not None else None
    anfrage = urllib.request.Request(f"{BASIS}{pfad}", data=daten, method=methode)
    anfrage.add_header("Authorization", f"Bearer {token()}")
    if daten:
        anfrage.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(anfrage) as a:
            roh = a.read()
            return a.status, (json.loads(roh) if roh else None)
    except urllib.error.HTTPError as e:
        return e.code, None


# Sicherung: niemals einen echten Eintrag ueberschreiben.
status, _ = ruf("GET", f"/api/eintraege/{tag}")
if status != 404:
    print(f"   ABBRUCH  am {tag} steht bereits etwas (HTTP {status}), nichts angefasst")
    sys.exit(3)

# Absichtlich mit Klartextfeldern neben dem Chiffrat. Der Dienst darf sie
# ignorieren; taeten sie es nicht, stuende der Text gleich in der Datenbank.
status, antwort = ruf("PUT", f"/api/eintraege/{tag}", {
    "chiffrat": base64.b64encode(b"nur-ein-platzhalter").decode(),
    "iv": base64.b64encode(b"123456789012").decode(),
    "titel": marke,
    "text": marke,
    "note": marke,
    "stimmung": marke,
})
if status != 200:
    print(f"   FEHLER   Schreiben scheiterte mit HTTP {status}")
    sys.exit(1)
if antwort and any(marke in str(v) for v in antwort.values()):
    print("   FEHLER   die Antwort gibt einen Klartextwert zurueck")
    sys.exit(1)
print("   OK      der Dienst nimmt den Eintrag an und gibt kein Klartextfeld zurueck")
PY
rc=$?
if [ "$rc" = 3 ]; then echo "   (Test uebersprungen)"; exit 3; fi
[ "$rc" = 0 ] || fehler=$((fehler + 1))

echo
echo "== 4. Steht die Marke irgendwo auf der Platte? =="
# ★ Alle Dateien, nicht nur die .db: SQLite laeuft im WAL-Modus, frisch
# Geschriebenes steht zuerst in der -wal-Datei. Ein Test, der nur die .db
# durchsucht, findet nichts und beweist damit nichts.
treffer="$(docker exec -e MARKE="$MARKE" "$CONTAINER_API" python -c "
import glob, os
marke = os.environ['MARKE'].encode()
gefunden = []
for pfad in glob.glob('/data/*'):
    try:
        with open(pfad, 'rb') as f:
            if marke in f.read():
                gefunden.append(pfad)
    except OSError:
        pass
print(','.join(gefunden))
")"
if [ -z "$treffer" ]; then
  meld_ok "die Marke steht in keiner Datei unter /data (inkl. WAL)"
else
  meld_bad "die Marke steht in: $treffer"
fi

echo
echo "== 5. Was steht im Zugriffsprotokoll? =="
protokoll="$(docker logs --since 5m "$CONTAINER_API" 2>&1 || true)"
if printf '%s' "$protokoll" | grep -q "$MARKE"; then
  meld_bad "die Marke steht im Protokoll"
else
  meld_ok "die Marke steht nicht im Protokoll"
fi
if printf '%s' "$protokoll" | grep -q "$TESTTAG"; then
  meld_bad "das Datum $TESTTAG steht unmaskiert im Protokoll (zugriffsmaske.py wirkt nicht)"
else
  meld_ok "das Datum ist maskiert"
fi
if printf '%s' "$protokoll" | grep -q '/api/eintraege/<datum>'; then
  meld_ok "die Route bleibt im Protokoll erkennbar"
else
  # Gegenrichtung: ein Filter, der alles verschluckt, waere kein Gewinn.
  meld_bad "die Route ist im Protokoll nicht mehr erkennbar"
fi

echo
echo "== 6. Aufraeumen =="
docker exec -i -e TESTTAG="$TESTTAG" "$CONTAINER_API" python - <<'PY'
import base64, hashlib, hmac, json, os, time, urllib.error, urllib.request

geheim = os.environ["JWT_SECRET"]
subs = [s.strip() for s in os.environ.get("ALLOWED_SUBS", "").split(",") if s.strip()]
sub = subs[0] if subs else "vertraulichkeitsprobe"


def b64(roh: bytes) -> str:
    return base64.urlsafe_b64encode(roh).decode().rstrip("=")


jetzt = int(time.time())
kopf = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
rumpf = b64(json.dumps({
    "iss": "saganta", "sub": sub, "email": "", "groups": [],
    "aud": "tagebuch-api", "iat": jetzt, "exp": jetzt + 120,
}).encode())
sig = b64(hmac.new(geheim.encode(), f"{kopf}.{rumpf}".encode(), hashlib.sha256).digest())
token = f"{kopf}.{rumpf}.{sig}"

anfrage = urllib.request.Request(
    f"http://127.0.0.1:8000/api/eintraege/{os.environ['TESTTAG']}", method="DELETE"
)
anfrage.add_header("Authorization", f"Bearer {token}")
try:
    with urllib.request.urlopen(anfrage) as a:
        print(f"   OK      Testeintrag entfernt (HTTP {a.status})")
except urllib.error.HTTPError as e:
    print(f"   {'OK      Testeintrag war schon weg' if e.code == 404 else f'FEHLER  HTTP {e.code}'}")
PY

echo
if [ "$fehler" -eq 0 ]; then
  echo "== Alles in Ordnung. =="
else
  echo "== $fehler Befund(e). Das Tagebuch haelt seine Zusicherung nicht. =="
  exit 1
fi
