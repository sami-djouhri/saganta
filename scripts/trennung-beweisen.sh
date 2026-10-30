#!/usr/bin/env bash
# Beweist am laufenden Dienst, dass zwei Konten einander nicht sehen.
#
# Das Gegenstueck zu scripts/mandanten-pruefung.py: die liest den Quelltext und
# sagt, dass jede Route gebunden *aussieht*. Dieses Skript fragt den laufenden
# Dienst und sagt, was er *tut*. Beides wird gebraucht -- eine Route kann sauber
# gebunden sein und trotzdem an einem ungefilterten Join vorbei Daten zeigen.
#
# Das JWT wird IM CONTAINER gestempelt, mit dem Geheimnis, das dort ohnehin in
# der Umgebung steht. Es verlaesst den Container nie und erscheint in keiner
# Ausgabe. Wer das von aussen bauen wollte, muesste das Backend-Geheimnis
# herausreichen -- genau das soll nicht passieren, nur um einen Test zu fahren.
#
# Aufruf:
#   ./trennung-beweisen.sh saganta-notizen-api notizen-api /api/notizen
#   ./trennung-beweisen.sh saganta-assets-api assets-api /api/assets
#   PORT=8085 VERFAHREN=header GEHEIMNIS=KALENDER_TENANT_SECRET \
#     ./trennung-beweisen.sh kalender - /api/contacts '{"name":"..."}'
#
# Erwartet wird: beide Subs bekommen HTTP 200, und ihre Antworten sind
# verschieden bzw. die des Fremd-Subs ist leer. Ein 403 heisst, das
# ALLOWED_SUBS-Gate steht noch (dann ist der Dienst noch nicht offen).
#
# ZWEI VERFAHREN, und bis zum 2026-10-02 kannte das Skript nur eines.
# Es sprach fest Bearer-JWT auf Port 8000. Damit deckte es genau die Dienste ab,
# deren Gate schon offen ist, und **keinen** der fuenf noch geschlossenen: die
# nativen Dienste nehmen den signierten Header ``X-Saganta-Sub`` (`tenant_auth.py`),
# und der Kalender lauscht auf 8085. Ein Pruefwerkzeug, das die ungeklaerten
# Faelle nicht erreicht, bestaetigt nur das schon Geklaerte.
#   VERFAHREN=jwt     (Vorgabe) Bearer-HS256 gegen JWT_SECRET/SAGANTA_BACKEND_SECRET
#   VERFAHREN=header  X-Saganta-Sub + X-Saganta-Sub-Sig = hex(HMAC-SHA256(secret, sub))
#   GEHEIMNIS=<NAME>  erzwingt eine bestimmte Umgebungsvariable als Geheimnis
#   PORT=<n>          abweichender Port im Container (Vorgabe 8000)
#   ANMELDUNG=<pfad>  vorgeschaltete Anmeldung je Konto, etwa /api/auth/gate-login
#
# ANMELDUNG gibt es wegen des Kalenders: dort ist der signierte Header die
# Mandanten-Aussage, aber die Datenrouten haengen zusaetzlich an einer eigenen
# Sitzung (``get_current_user``). Der signierte Header allein bekommt dort 401,
# und das sieht wie eine funktionierende Trennung aus, obwohl gar nichts
# gemessen wurde. `gate-login` tauscht den Header gegen eine Sitzung fuer genau
# diesen Mandanten; erst danach ist die Frage ueberhaupt gestellt.
set -euo pipefail

CONTAINER="${1:?Container, z.B. saganta-notizen-api}"
AUDIENCE="${2:?Zielgruppe (aud), z.B. notizen-api; bei VERFAHREN=header ein -}"
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

VERFAHREN="${VERFAHREN:-jwt}"
PORT="${PORT:-8000}"
GEHEIMNIS="${GEHEIMNIS:-}"
ANMELDUNG="${ANMELDUNG:-}"

echo "Dienst:     $CONTAINER (Port $PORT)"
echo "Verfahren:  $VERFAHREN"
[[ $VERFAHREN == jwt ]] && echo "Zielgruppe: $AUDIENCE"
[[ -n $ANMELDUNG ]] && echo "Anmeldung:  $ANMELDUNG"
echo "Pfad:       $PFAD"
echo

# `-i` ist Pflicht: ohne stdin kommt das Skript unten nie im Container an,
# und `docker exec` beendet sich trotzdem mit rc=0. Das sieht wie ein Lauf ohne
# Befund aus und ist ein Lauf ohne Programm.
docker exec -i -e AUD="$AUDIENCE" -e PFAD="$PFAD" -e SUB_A="$SUB_A" -e SUB_B="$SUB_B" \
  -e ANLEGEN="$ANLEGEN" -e VERFAHREN="$VERFAHREN" -e PORT="$PORT" \
  -e GEHEIMNIS="$GEHEIMNIS" -e ANMELDUNG="$ANMELDUNG" "$CONTAINER" python3 - <<'PY'
import base64, hashlib, hmac, json, os, time, urllib.error, urllib.request

aud, pfad = os.environ["AUD"], os.environ["PFAD"]
verfahren = os.environ.get("VERFAHREN") or "jwt"
port = int(os.environ.get("PORT") or 8000)

# Das Geheimnis steht in der Prozessumgebung des Dienstes. Die Namen weichen
# zwischen den Diensten ab, deshalb der Reihe nach probieren. Bei VERFAHREN=header
# ist es das Mandanten-Geheimnis des Zieldienstes, nicht das Backend-Geheimnis.
kandidaten = (
    [os.environ["GEHEIMNIS"]] if os.environ.get("GEHEIMNIS")
    else [n for n in os.environ if n.endswith("_TENANT_SECRET")] if verfahren == "header"
    else ["JWT_SECRET", "SAGANTA_BACKEND_SECRET", "BACKEND_SECRET"]
)
geheim = ""
for name in kandidaten:
    if os.environ.get(name):
        geheim = os.environ[name]
        gefunden = name
        break
if not geheim:
    raise SystemExit(
        "Kein passendes Geheimnis in der Umgebung dieses Dienstes gefunden. "
        f"Gesucht: {', '.join(kandidaten) or '(nichts)'}"
    )
print(f"(Im Container mit {gefunden} gestempelt, Wert bleibt hier.)\n")


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


def mandanten_kopf(sub: str) -> dict:
    """Der signierte Header, den die nativen Dienste pruefen.

    Die Signatur haengt an genau diesem Sub (``tenant_auth.py``), eine
    abgefangene laesst sich nicht auf einen fremden umhaengen. Das Geheimnis
    verlaesst den Container nicht, es wird hier drin benutzt.
    """
    sig = hmac.new(geheim.encode(), sub.encode(), hashlib.sha256).hexdigest()
    return {"X-Saganta-Sub": sub, "X-Saganta-Sub-Sig": sig}


sitzungen: dict = {}


class OhneWeiterleitung(urllib.request.HTTPRedirectHandler):
    """Eine Anmeldung, die mit 302 antwortet, verliert ihr Cookie an jeden
    Client, der der Weiterleitung folgt: ``urlopen`` liefert dann die Antwort des
    ZIELS, und das ``Set-Cookie`` der 302 ist weg. Genau daran scheiterte der
    erste Lauf gegen ``gate-login``, und er sah dabei aus wie eine abgelehnte
    Anmeldung statt wie ein Fehler des Pruefers."""

    def redirect_request(self, *_a, **_k):
        return None


_oeffner = urllib.request.build_opener(OhneWeiterleitung)


def anmelden(sub: str) -> None:
    """Holt eine Sitzung fuer diesen Mandanten, falls der Dienst eine verlangt."""
    pfad_anmeldung = os.environ.get("ANMELDUNG") or ""
    if not pfad_anmeldung or sub in sitzungen:
        return
    anfrage = urllib.request.Request(
        f"http://127.0.0.1:{port}{pfad_anmeldung}", headers=mandanten_kopf(sub)
    )
    try:
        with _oeffner.open(anfrage, timeout=10) as a:
            gesetzt = a.headers.get_all("Set-Cookie") or []
    except urllib.error.HTTPError as e:
        gesetzt = e.headers.get_all("Set-Cookie") or []
    for zeile in gesetzt:
        if zeile.startswith("session_token="):
            sitzungen[sub] = zeile.split(";", 1)[0].split("=", 1)[1]
            return
    # Kein Token: nicht stillschweigend weiterlaufen, sonst misst der Lauf
    # danach nur die fehlende Anmeldung und meldet sie als Trennung.
    raise SystemExit(
        f"Anmeldung ueber {pfad_anmeldung} lieferte kein session_token fuer {sub}."
    )


def ruf(sub: str, methode: str = "GET", rumpf: str | None = None, pfad_: str | None = None):
    anmelden(sub)
    kopf = {"Accept": "application/json"}
    if verfahren == "header":
        kopf.update(mandanten_kopf(sub))
    else:
        kopf["Authorization"] = f"Bearer {token(sub)}"
    if sub in sitzungen:
        kopf["Cookie"] = f"session_token={sitzungen[sub]}"
    daten = None
    if rumpf is not None:
        daten = rumpf.encode()
        kopf["Content-Type"] = "application/json"
    anfrage = urllib.request.Request(
        f"http://127.0.0.1:{port}{pfad_ or pfad}", headers=kopf, data=daten, method=methode
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


def hat_inhalt(text: str) -> bool:
    """Traegt diese Antwort Datensaetze?

    Hier stand bis zum 2026-10-02 ein Vergleich gegen vier Zeichenketten
    (``"[]"``, ``"{}"``, ``""``, ``'{"items":[]}'``). Eine leere Seite einer
    blaetternden Liste sieht aber so aus::

        {"items":[],"total":0,"offset":0,"limit":200}

    und ist keine davon. Das Werkzeug meldete deshalb bei lager den **starken**
    Fall (A hat etwas, B sieht nichts) als „unklar -- von Hand ansehen". Es ist
    genau das Muster, das FastAPI fuer blaetternde Listen erzeugt, also gerade
    bei den Diensten, deren Gate noch zu ist. Ein Pruefer, dessen bester
    Ausgang unerreichbar ist, verschiebt die Entscheidung immer auf den
    Menschen und wird damit uebergangen.

    Jetzt wird geparst statt verglichen. Ein unparsbarer Rumpf faellt auf den
    alten Weg zurueck, damit eine Textantwort nicht als leer gilt.
    """
    text = text.strip()
    try:
        wert = json.loads(text)
    except Exception:
        return text not in ("", "[]", "{}")
    if isinstance(wert, list):
        return len(wert) > 0
    if isinstance(wert, dict):
        # Blaetternde Huellen tragen die Daten in einem Listenfeld. Der Name
        # weicht je Dienst ab, deshalb erst die gelaeufigen, dann irgendeine
        # Liste; ein Zaehlfeld wie `total` entscheidet NICHT, weil es fehlen darf.
        for schluessel in ("items", "results", "data", "entries", "eintraege"):
            if isinstance(wert.get(schluessel), list):
                return len(wert[schluessel]) > 0
        for v in wert.values():
            if isinstance(v, list):
                return len(v) > 0
        return len(wert) > 0
    return bool(wert)


def eintraege_aus(text: str) -> list:
    """Die Datensaetze einer Leseantwort als Liste von Abbildungen."""
    try:
        wert = json.loads(text)
    except Exception:
        return []
    if isinstance(wert, dict):
        for schluessel in ("items", "results", "data", "entries", "eintraege"):
            if isinstance(wert.get(schluessel), list):
                wert = wert[schluessel]
                break
        else:
            wert = next((v for v in wert.values() if isinstance(v, list)), [wert])
    return [e for e in wert if isinstance(e, dict)] if isinstance(wert, list) else []


def leck(anlege_rumpf: str, anlege_antwort: str, fremde_antwort: str):
    """Steht der von A angelegte Eintrag in der Antwort von B?

    So faellt auch der **teilweise** Leck auf: B sieht den Eintrag von A
    zusammen mit eigenen oder gemeinsamen Daten. Der frueher einzige Test
    ``ra == rb`` verlangte Gleichheit der ganzen Antwort und haette genau diesen
    Fall durchgelassen.

    Verglichen wird **je Datensatz**, nicht per Textsuche im ganzen Rumpf.
    Die erste Fassung suchte am 2026-10-02 die Zeichenkette ``"id":46`` und
    meldete bei mealprep ein LECK, das keines war: die 46 war die Kennung einer
    verschachtelten Zutat in einem fremden Rezept. Eine Kennung ist nur dort
    eindeutig, wo sie herkommt, und ein Rumpf voller Unterobjekte hat viele.
    """
    try:
        kennung = json.loads(anlege_antwort).get("id")
    except Exception:
        kennung = None
    zeichen = []
    try:
        for v in (json.loads(anlege_rumpf) or {}).values():
            if isinstance(v, str) and len(v) >= 8:
                zeichen.append(v)
    except Exception:
        pass
    for e in eintraege_aus(fremde_antwort):
        if kennung is not None and e.get("id") == kennung:
            return f"Datensatz mit id {kennung}"
        for z in zeichen:
            if any(w == z for w in e.values() if isinstance(w, str)):
                return f"Feldwert {z!r}"
    return None


anlegen = os.environ.get("ANLEGEN") or ""
sub_a, sub_b = os.environ["SUB_A"], os.environ["SUB_B"]
angelegt = False
angelegt_rumpf = ""

if anlegen:
    code, rumpf = ruf(sub_a, "POST", anlegen)
    print(f"Konto A legt an:  HTTP {code}  {kurz(rumpf)}")
    angelegt = code in (200, 201)
    if angelegt:
        angelegt_rumpf = rumpf
    else:
        print("  (Anlegen misslungen. Der Lesevergleich unten ist dann der schwache.)")
    print()

ergebnis = {}
for name, sub in (("A", sub_a), ("B", sub_b)):
    code, rumpf = ruf(sub)
    ergebnis[name] = (code, rumpf)
    print(f"Konto {name} liest: HTTP {code}  {kurz(rumpf)}")

print()
(ca, ra), (cb, rb) = ergebnis["A"], ergebnis["B"]

if ca == 403 or cb == 403:
    print("ERGEBNIS: 403 -- das ALLOWED_SUBS-Gate steht noch. Dieser Dienst ist")
    print("          noch nicht fuer mehrere Konten geoeffnet.")
elif ca != 200 or cb != 200:
    print("ERGEBNIS: unklar -- Antwortkennzahlen von Hand ansehen.")
elif angelegt:
    # Der starke Fall: A hat nachweislich etwas, B darf es nicht sehen.
    a_hat = hat_inhalt(ra)
    b_sieht = hat_inhalt(rb)
    # Der angelegte Eintrag selbst, nicht nur „irgendwas". Ein Dienst mit
    # gemeinsamen Stammdaten (etwa fitness-Uebungen) laesst B zu Recht etwas
    # sehen; entscheidend ist, ob **dieser** Eintrag darunter ist.
    fremdes = leck(anlegen, angelegt_rumpf, rb)
    if fremdes:
        print("ERGEBNIS: LECK. Konto B sieht den Eintrag von Konto A.")
        print(f"          Erkannt an: {fremdes}")
        print("          Gate sofort wieder schliessen.")
    elif a_hat and not b_sieht:
        print("ERGEBNIS: BEWIESEN. Konto A hat einen Eintrag, Konto B sieht ihn nicht.")
        print("          Die Trennung traegt ohne das Gate.")
    elif a_hat and b_sieht:
        print("ERGEBNIS: BEWIESEN mit Vorbehalt. Konto B sieht Daten, aber NICHT den")
        print("          Eintrag von Konto A. Pruefen, ob das Gesehene bewusst")
        print("          gemeinsam ist (Stammdaten) -- dann ist es in Ordnung.")
    else:
        print("ERGEBNIS: unklar -- Konto A sieht seinen eigenen Eintrag nicht.")
        print("          Das ist kein Trennungsproblem, sondern eines der Route.")
elif ra == rb and hat_inhalt(ra):
    # Ohne angelegten Eintrag laesst sich „gemeinsam gewollt" von „Leck" nicht
    # unterscheiden, und diese Zeile behauptete bis zum 2026-10-02 den Leck-Fall.
    # Am Kalender traf sie damit die acht **System-Kalender**, die absichtlich
    # allen gehoeren (``owner_sub IS NULL``, eigene Kalender sind per 403
    # verboten): ein Fehlalarm, der zum Schliessen eines richtigen Gates geraten
    # haette. Ein Pruefer, der haeufig falsch Alarm schlaegt, wird abgeschaltet.
    print("ERGEBNIS: UNENTSCHIEDEN -- beide Konten sehen DASSELBE, und es ist nicht")
    print("          leer. Das ist entweder ein Leck ODER bewusst gemeinsamer")
    print("          Bestand (Systemkalender, Stammdaten, Feiertage).")
    print("          Nicht entscheidbar ohne angelegten Eintrag: mit viertem")
    print("          Parameter (JSON-Rumpf) wiederholen. Schlaegt das Anlegen mit")
    print("          403 fehl, ist der Bestand per Entwurf gemeinsam.")
else:
    print("ERGEBNIS: schwacher Beweis. Beide Konten werden bedient und sehen nichts")
    print("          Fremdes, aber es lag auch nichts da. Mit viertem Parameter")
    print("          (JSON-Rumpf) wiederholen, um es wirklich zu zeigen.")

# ── Aufraeumen ───────────────────────────────────────────────────────────────
# Der Beweis darf keine Spur hinterlassen. Ein Pruefskript, das Datensaetze
# liegen laesst, wird beim zweiten Lauf ungenau (die Liste ist dann nicht mehr
# leer, weil der vorige Lauf sie gefuellt hat) und beim zehnten zum Muellhaufen.
#
# Hier loeschte das Skript bis zum 2026-10-02 **alles, was Konto A lesen
# konnte**, nicht den angelegten Eintrag. Das stimmt nur, solange A ein leerer
# Mandant ist und der Dienst keine gemeinsamen Daten hat. Bei `fitness` ist
# beides nicht so: der Uebungskatalog ist bewusst gemeinsam, A liest ihn mit,
# und der Lauf vom 2026-10-02 schickte **50 DELETE** auf echte Uebungen des
# Owners. Gehalten hat sie `ExerciseService._eigener_eintrag`, also eine
# bewusste Schranke im Zieldienst, kein Zufall. Genau darin liegt der Fehler:
# ein Pruefwerkzeug darf seine Harmlosigkeit nicht davon abhaengig machen, dass
# der geprueften Dienst eine solche Schranke hat. Derselbe Lauf an einem Dienst
# ohne sie haette den Bestand vernichtet, den er schuetzen soll.
# Zweite Haelfte desselben Fehlers: der eigene Eintrag (id 168) war in A's
# Leseantwort gar nicht enthalten und blieb deshalb liegen. Das Werkzeug loeschte
# also 50 fremde Eintraege zu viel und den eigenen nicht.
# Jetzt wird genau die Kennung aus der Anlege-Antwort entfernt, und nur sie.
if angelegt:
    print()
    try:
        kennung = json.loads(angelegt_rumpf).get("id")
    except Exception:
        kennung = None
    if kennung is None:
        print("Aufraeumen: der Dienst nannte keine `id`. Nichts geloescht,")
        print(f"            Pruefeintrag von Hand entfernen ({pfad}).")
    else:
        # Ueber denselben Weg wie das Anlegen, damit das Aufraeumen auch im
        # Header-Verfahren und auf einem abweichenden Port greift.
        code, rumpf = ruf(sub_a, "DELETE", pfad_=f"{pfad}/{kennung}")
        if 200 <= code < 300:
            print(f"Aufgeraeumt: Pruefeintrag {kennung} entfernt.")
        else:
            print(f"Aufraeumen MISSLUNGEN fuer {kennung}: HTTP {code} {kurz(rumpf, 80)}")
            print(f"            Von Hand entfernen: DELETE {pfad}/{kennung}")
PY
