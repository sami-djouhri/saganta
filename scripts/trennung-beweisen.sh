#!/usr/bin/env bash
# Beweist am laufenden Dienst, dass zwei Konten einander nicht sehen.
#
# Das Gegenstueck zu scripts/mandanten-pruefung.py: die liest den Quelltext und
# sagt, dass jede Route gebunden *aussieht*. Dieses Skript fragt den laufenden
# Dienst und sagt, was er *tut*. Beides wird gebraucht -- eine Route kann sauber
# gebunden sein und trotzdem an einem ungefilterten Join vorbei Daten zeigen.
#
# ★ Das JWT wird IM CONTAINER gestempelt, mit dem Geheimnis, das dort ohnehin in
# der Umgebung steht. Es verlaesst den Container nie und erscheint in keiner
# Ausgabe. Wer das von aussen bauen wollte, muesste das Backend-Geheimnis
# herausreichen -- genau das soll nicht passieren, nur um einen Test zu fahren.
#
# Aufruf:
#   ./trennung-beweisen.sh saganta-notizen-api notizen-api /api/notizen
#   ./trennung-beweisen.sh saganta-assets-api assets-api /api/assets
#
# Erwartet wird: beide Subs bekommen HTTP 200, und ihre Antworten sind
# verschieden bzw. die des Fremd-Subs ist leer. Ein 403 heisst, das
# ALLOWED_SUBS-Gate steht noch (dann ist der Dienst noch nicht offen).
set -euo pipefail

CONTAINER="${1:?Container, z.B. saganta-notizen-api}"
AUDIENCE="${2:?Zielgruppe (aud), z.B. notizen-api}"
PFAD="${3:-/api/notizen}"
# Optionaler vierter Parameter: JSON-Rumpf, den Konto A anlegt. Ohne ihn
# vergleicht das Skript nur zwei Leseantworten, und das ist ein schwacher
# Beweis: zwei leere Listen sind auch dann gleich, wenn gar nichts getrennt
# wird. Mit ihm wird gezeigt, was zaehlt, naemlich dass A etwas hat und B es
# nicht sieht.
ANLEGEN="${4:-}"

# Zwei erfundene Subs. Bewusst nicht der echte Owner-Sub: der Beweis soll
# zeigen, dass ein BELIEBIGES Konto seinen eigenen, leeren Raum bekommt, ohne
# dass dabei echte Daten angefasst werden.
SUB_A="pruef-konto-a-0000000000000000"
SUB_B="pruef-konto-b-1111111111111111"

echo "Dienst:     $CONTAINER"
echo "Zielgruppe: $AUDIENCE"
echo "Pfad:       $PFAD"
echo

# ★ `-i` ist Pflicht: ohne stdin kommt das Skript unten nie im Container an,
# und `docker exec` beendet sich trotzdem mit rc=0. Das sieht wie ein Lauf ohne
# Befund aus und ist ein Lauf ohne Programm.
docker exec -i -e AUD="$AUDIENCE" -e PFAD="$PFAD" -e SUB_A="$SUB_A" -e SUB_B="$SUB_B" \
  -e ANLEGEN="$ANLEGEN" "$CONTAINER" python3 - <<'PY'
import base64, hashlib, hmac, json, os, time, urllib.error, urllib.request

aud, pfad = os.environ["AUD"], os.environ["PFAD"]

# Das Geheimnis steht in der Prozessumgebung des Dienstes. Die Namen weichen
# zwischen den Diensten ab, deshalb der Reihe nach probieren.
geheim = ""
for name in ("JWT_SECRET", "SAGANTA_BACKEND_SECRET", "BACKEND_SECRET"):
    if os.environ.get(name):
        geheim = os.environ[name]
        gefunden = name
        break
if not geheim:
    raise SystemExit("Kein Backend-Geheimnis in der Umgebung dieses Dienstes gefunden.")
print(f"(Token wird im Container mit {gefunden} gestempelt, Wert bleibt hier.)\n")


def b64(roh: bytes) -> str:
    return base64.urlsafe_b64encode(roh).rstrip(b"=").decode()


def token(sub: str) -> str:
    jetzt = int(time.time())
    kopf = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    last = b64(json.dumps({
        "iss": "saganta", "sub": sub, "email": f"{sub}@pruefung.invalid",
        "groups": [], "plan": "free", "aud": aud,
        "iat": jetzt, "exp": jetzt + 120, "jti": sub[:12],
    }).encode())
    sig = b64(hmac.new(geheim.encode(), f"{kopf}.{last}".encode(), hashlib.sha256).digest())
    return f"{kopf}.{last}.{sig}"


def ruf(sub: str, methode: str = "GET", rumpf: str | None = None):
    kopf = {"Authorization": f"Bearer {token(sub)}", "Accept": "application/json"}
    daten = None
    if rumpf is not None:
        daten = rumpf.encode()
        kopf["Content-Type"] = "application/json"
    anfrage = urllib.request.Request(
        f"http://127.0.0.1:8000{pfad}", headers=kopf, data=daten, method=methode
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=10) as a:
            return a.status, a.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # Verbindung, Timeout
        return 0, str(e)


def kurz(text: str, n: int = 160) -> str:
    return text if len(text) <= n else text[:n] + "..."


anlegen = os.environ.get("ANLEGEN") or ""
sub_a, sub_b = os.environ["SUB_A"], os.environ["SUB_B"]
angelegt = False

if anlegen:
    code, rumpf = ruf(sub_a, "POST", anlegen)
    print(f"Konto A legt an:  HTTP {code}  {kurz(rumpf)}")
    angelegt = code in (200, 201)
    if not angelegt:
        print("  (Anlegen misslungen. Der Lesevergleich unten ist dann der schwache.)")
    print()

ergebnis = {}
for name, sub in (("A", sub_a), ("B", sub_b)):
    code, rumpf = ruf(sub)
    ergebnis[name] = (code, rumpf)
    print(f"Konto {name} liest: HTTP {code}  {kurz(rumpf)}")

print()
(ca, ra), (cb, rb) = ergebnis["A"], ergebnis["B"]
leer = ("[]", "{}", "", '{"items":[]}')

if ca == 403 or cb == 403:
    print("ERGEBNIS: 403 -- das ALLOWED_SUBS-Gate steht noch. Dieser Dienst ist")
    print("          noch nicht fuer mehrere Konten geoeffnet.")
elif ca != 200 or cb != 200:
    print("ERGEBNIS: unklar -- Antwortkennzahlen von Hand ansehen.")
elif angelegt:
    # ★ Der starke Fall: A hat nachweislich etwas, B darf es nicht sehen.
    a_hat = ra.strip() not in leer
    b_sieht = rb.strip() not in leer
    if a_hat and not b_sieht:
        print("ERGEBNIS: BEWIESEN. Konto A hat einen Eintrag, Konto B sieht ihn nicht.")
        print("          Die Trennung traegt ohne das Gate.")
    elif a_hat and b_sieht and ra == rb:
        print("ERGEBNIS: LECK. Konto B sieht den Eintrag von Konto A.")
        print("          Gate sofort wieder schliessen.")
    else:
        print("ERGEBNIS: unklar -- A und B antworten verschieden, aber nicht im")
        print("          erwarteten Muster. Von Hand ansehen.")
elif ra == rb and ra.strip() not in leer:
    print("ERGEBNIS: ACHTUNG -- beide Konten sehen DASSELBE, und es ist nicht leer.")
    print("          Das ist der Leck-Fall. Gate nicht oeffnen bzw. sofort zurueck.")
else:
    print("ERGEBNIS: schwacher Beweis. Beide Konten werden bedient und sehen nichts")
    print("          Fremdes, aber es lag auch nichts da. Mit viertem Parameter")
    print("          (JSON-Rumpf) wiederholen, um es wirklich zu zeigen.")

# ── Aufraeumen ───────────────────────────────────────────────────────────────
# ★ Der Beweis darf keine Spur hinterlassen. Ein Pruefskript, das Datensaetze
# liegen laesst, wird beim zweiten Lauf ungenau (die Liste ist dann nicht mehr
# leer, weil der vorige Lauf sie gefuellt hat) und beim zehnten zum Muellhaufen.
if angelegt:
    print()
    try:
        eintraege = json.loads(ra)
    except json.JSONDecodeError:
        eintraege = []
    if isinstance(eintraege, dict):
        eintraege = eintraege.get("items", [])
    weg, uebrig = 0, 0
    for eintrag in eintraege if isinstance(eintraege, list) else []:
        kennung = eintrag.get("id") if isinstance(eintrag, dict) else None
        if kennung is None:
            continue
        kopf = {"Authorization": f"Bearer {token(sub_a)}"}
        loeschen = urllib.request.Request(
            f"http://127.0.0.1:8000{pfad}/{kennung}", headers=kopf, method="DELETE"
        )
        try:
            with urllib.request.urlopen(loeschen, timeout=10):
                weg += 1
        except Exception:
            uebrig += 1
    hinweis = f", {uebrig} nicht loeschbar (von Hand ansehen)" if uebrig else ""
    print(f"Aufgeraeumt: {weg} Pruefeintrag/-eintraege entfernt{hinweis}.")
PY
