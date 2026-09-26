#!/usr/bin/env bash
# Beweist die Mandantentrennung von mail-api am laufenden Dienst.
#
# ★★ WARUM NICHT DAS ALLGEMEINE trennung-beweisen.sh: das legt seinen Pruefsatz
# ueber die API an, und `POST /api/mail/accounts` verlangt vorher einen echten
# IMAP-Login (`test_connection`, bewusst VOR dem Speichern). Ein erfundenes Konto
# kommt dort nie durch. Das allgemeine Skript faellt damit auf den Vergleich
# zweier LEERER Listen zurueck -- und `mail_accounts` hat heute 0 Zeilen, es
# waere also genau der Lauf, der nichts zeigt und gruen aussieht.
#
# Deshalb wird der Pruefsatz hier direkt in die Datenbank geschrieben. Gelesen
# wird trotzdem ausschliesslich ueber die API: der zu pruefende Weg ist der, den
# ein Browser nimmt, nicht der, den das Pruefskript nimmt.
#
# ★ Die schaerfste Frage steht unten als Punkt 5, nicht als Listenvergleich:
# was passiert, wenn Konto B eine FREMDE Nachrichten-Kennung direkt aufruft.
# Faellt der Join-Filter weg, laeuft der Aufruf in den IMAP-Abruf und antwortet
# 502. Ein 502 liest sich wie eine Stoerung des Dienstes, nicht wie ein Leck --
# es waere der Fehler, den niemand meldet. Erwartet wird 404.
#
# ★ Das Konto wird mit enabled=0 angelegt: der Abgleich-Schleifer (poll_loop,
# alle 300 s) wuerde es sonst greifen und gegen einen erfundenen IMAP-Host
# laufen. Auf die gepruefen Listen hat das keinen Einfluss, beide filtern nicht
# nach `enabled`.
set -euo pipefail

CONTAINER="${1:-saganta-mail-api}"

echo "Dienst: $CONTAINER"
echo

docker exec -i "$CONTAINER" python3 - <<'PY'
import base64, hashlib, hmac, json, os, sqlite3, time, urllib.error, urllib.request

AUD = "mail-api"
SUB_A = "pruef-konto-a-0000000000000000"
SUB_B = "pruef-konto-b-1111111111111111"
DB = "/data/mail.db"

geheim = os.environ.get("JWT_SECRET", "")
if not geheim:
    raise SystemExit("Kein JWT_SECRET in der Umgebung dieses Dienstes.")
print("(Token wird im Container gestempelt, das Geheimnis bleibt hier.)\n")


def b64(roh: bytes) -> str:
    return base64.urlsafe_b64encode(roh).rstrip(b"=").decode()


def token(sub: str) -> str:
    jetzt = int(time.time())
    kopf = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    last = b64(json.dumps({
        "iss": "saganta", "sub": sub, "email": f"{sub}@pruefung.invalid",
        "groups": [], "plan": "free", "aud": AUD,
        "iat": jetzt, "exp": jetzt + 180, "jti": sub[:12],
    }).encode())
    sig = b64(hmac.new(geheim.encode(), f"{kopf}.{last}".encode(), hashlib.sha256).digest())
    return f"{kopf}.{last}.{sig}"


def ruf(sub: str, pfad: str, methode: str = "GET", rumpf: str | None = None):
    kopf = {"Authorization": f"Bearer {token(sub)}", "Accept": "application/json"}
    daten = None
    if rumpf is not None:
        daten = rumpf.encode()
        kopf["Content-Type"] = "application/json"
    a = urllib.request.Request(f"http://127.0.0.1:8000{pfad}", headers=kopf, data=daten, method=methode)
    try:
        with urllib.request.urlopen(a, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


db = sqlite3.connect(DB)
vorher = db.execute("select count(*) from mail_accounts").fetchone()[0]
print(f"mail_accounts vor dem Lauf: {vorher}")
if vorher:
    print("  (Es liegen echte Konten. Der Lauf legt daneben, loescht nur sein eigenes.)")

# ── Pruefsatz anlegen ────────────────────────────────────────────────────────
db.execute(
    "insert into mail_accounts (sub,email,provider,display_name,imap_host,imap_port,"
    "imap_username,smtp_host,smtp_port,smtp_username,secret_cipher,auth_typ,enabled,created_at) "
    "values (?,?,?,?,?,?,?,?,?,?,?,?,0,datetime('now'))",
    (SUB_A, "pruefung-a@pruefung.invalid", "custom", "Pruefkonto A",
     "imap.pruefung.invalid", 993, "pruefung-a@pruefung.invalid",
     "smtp.pruefung.invalid", 465, "pruefung-a@pruefung.invalid",
     "nicht-entschluesselbar-pruefsatz", "passwort"),
)
konto_id = db.execute("select last_insert_rowid()").fetchone()[0]
db.execute(
    "insert into mail_messages (account_id,folder,uid,subject,from_addr,from_name,"
    "to_addr,snippet,date,is_read,is_starred,fetched_at) "
    "values (?,'INBOX','99001','Pruefnachricht A','absender@pruefung.invalid','Absender',"
    "'pruefung-a@pruefung.invalid','Dies ist ein Pruefsatz.',datetime('now'),0,0,datetime('now'))",
    (konto_id,),
)
db.commit()
nachricht_id = db.execute(
    "select id from mail_messages where account_id=?", (konto_id,)
).fetchone()[0]
print(f"Angelegt: Konto {konto_id} fuer A, Nachricht {nachricht_id}.\n")

befunde = []

try:
    # 1/2 Kontoliste ---------------------------------------------------------
    ca, ra = ruf(SUB_A, "/api/mail/accounts")
    cb, rb = ruf(SUB_B, "/api/mail/accounts")
    na = len(json.loads(ra)) if ca == 200 else -1
    nb = len(json.loads(rb)) if cb == 200 else -1
    print(f"1) Konten   A: HTTP {ca}, {na} Eintrag/Eintraege")
    print(f"   Konten   B: HTTP {cb}, {nb} Eintrag/Eintraege")
    if ca == 403 or cb == 403:
        befunde.append("403 -- das ALLOWED_SUBS-Gate steht noch, der Dienst ist nicht offen")
    else:
        befunde.append(None if (na >= 1 and nb == 0) else f"Kontoliste unerwartet (A={na}, B={nb})")

    # 3/4 Nachrichtenliste (Join ueber account_id) ---------------------------
    ca, ra = ruf(SUB_A, "/api/mail/messages")
    cb, rb = ruf(SUB_B, "/api/mail/messages")
    ta = json.loads(ra).get("total", -1) if ca == 200 else -1
    tb = json.loads(rb).get("total", -1) if cb == 200 else -1
    print(f"2) Nachrichten A: HTTP {ca}, total {ta}")
    print(f"   Nachrichten B: HTTP {cb}, total {tb}")
    befunde.append(None if (ta >= 1 and tb == 0) else f"Nachrichtenliste unerwartet (A={ta}, B={tb})")

    # 5 Der scharfe Fall: B ruft die fremde Kennung direkt auf ----------------
    cb, rb = ruf(SUB_B, f"/api/mail/messages/{nachricht_id}/body")
    print(f"3) B ruft Nachricht {nachricht_id} direkt ab: HTTP {cb}")
    if cb == 404:
        befunde.append(None)
    elif cb == 502:
        befunde.append("LECK: B kam am Besitzfilter vorbei und landete im IMAP-Abruf (502)")
    else:
        befunde.append(f"unerwartet: HTTP {cb} statt 404 ({rb[:120]})")

    # 6 Schreibender Zugriff auf ein fremdes Konto ---------------------------
    cb, rb = ruf(SUB_B, f"/api/mail/accounts/{konto_id}/enabled", "POST", '{"enabled": true}')
    print(f"4) B schaltet fremdes Konto {konto_id}: HTTP {cb}")
    befunde.append(None if cb == 404 else f"LECK: B darf ein fremdes Konto schalten (HTTP {cb})")

    # 7 Loeschen eines fremden Kontos ----------------------------------------
    cb, rb = ruf(SUB_B, f"/api/mail/accounts/{konto_id}", "DELETE")
    print(f"5) B loescht fremdes Konto {konto_id}: HTTP {cb}")
    befunde.append(None if cb == 404 else f"LECK: B darf ein fremdes Konto loeschen (HTTP {cb})")
finally:
    # ── Aufraeumen ──────────────────────────────────────────────────────────
    # Ueber die API als Besitzer, damit zugleich belegt ist, dass A sein eigenes
    # Konto los wird. Danach wird nachgezaehlt statt vertraut.
    ca, _ = ruf(SUB_A, f"/api/mail/accounts/{konto_id}", "DELETE")
    db2 = sqlite3.connect(DB)
    rest_k = db2.execute("select count(*) from mail_accounts where sub in (?,?)", (SUB_A, SUB_B)).fetchone()[0]
    rest_n = db2.execute("select count(*) from mail_messages where account_id=?", (konto_id,)).fetchone()[0]
    nachher = db2.execute("select count(*) from mail_accounts").fetchone()[0]
    print(f"\nAufgeraeumt: A loescht sein Konto (HTTP {ca}); "
          f"Pruefkonten uebrig {rest_k}, Pruefnachrichten uebrig {rest_n}.")
    print(f"mail_accounts nach dem Lauf: {nachher} (vorher {vorher})")
    if rest_k or rest_n or nachher != vorher:
        print("⚠️ Reste vorhanden -- von Hand ansehen.")

print()
fehler = [b for b in befunde if b]
if fehler:
    print("ERGEBNIS: NICHT BEWIESEN")
    for f in fehler:
        print(f"  - {f}")
    raise SystemExit(1)
print("ERGEBNIS: BEWIESEN. Konto A hat ein Konto und eine Nachricht, Konto B sieht")
print("          beides nicht, kommt auch ueber die direkte Kennung nicht heran und")
print("          darf fremde Konten weder schalten noch loeschen.")
PY
