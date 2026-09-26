#!/usr/bin/env bash
# Fragt jedes Backend zweimal, als Owner und als fremder Nutzer, und vergleicht.
#
# WARUM ES DAS GIBT: scripts/mandanten-probe.sh misst die Struktur, also ob eine
# Mandantenspalte da ist. Sie kann nicht sehen, ob der Code sie auch benutzt.
# Genau dieser Fall war assets-api bis zum 30.08.2026: Spalte fehlte, und jede
# Route deklarierte brav einen Nutzer, den sie nie zum Filtern verwendete.
# Diese Probe fragt deshalb nicht den Quelltext, sondern den laufenden Dienst.
#
# ★★ WARUM VERGLICHEN WIRD UND NICHT NUR GEZAEHLT: Die erste Fassung meldete
# "Leck", sobald der Fremde ueberhaupt etwas zu sehen bekam. Sie produzierte
# damit zwei Fehlalarme, und beide waren lehrreich:
#   - news-api lieferte ihm 30 Artikel. Die sind bewusst fuer alle dieselben,
#     getrennt gehoert nur, was persoenlich ist (gelesen, gemerkt, Briefing).
#   - shell-api lieferte ihm Einstellungen, die denen des Owners glichen. Es
#     waren die Standardwerte fuer einen Nutzer ohne eigene Zeile. Sie sehen nur
#     deshalb gleich aus, weil der Owner nie etwas umgestellt hat.
# Deshalb steht jetzt an jeder Route, was erwartet wird, und die Probe vergleicht
# beide Antworten, statt eine davon zu zaehlen.
#
# ★ Was ein 403 bedeutet: das Zugangsgate (ALLOWED_SUBS) haelt den Fremden
# draussen, bevor die Datenschicht ueberhaupt gefragt wird. Das ist heute der
# Normalfall, aber es ist KEIN Beleg fuer Trennung. Die Frage ist dann nicht
# beantwortet, sondern ungestellt, und sie stellt sich beim Oeffnen des Gates.
#
# Rueckgabe: 0 = kein Leck, 1 = fremde Daten sichtbar, 2 = Messung unvollstaendig.
set -uo pipefail

FREMDER="probe-zweiter-nutzer"
# ★ Kennung kommt von aussen (seit 2026-09-05). Sie gehoert einem konkreten
# Menschen und nicht in ein Repo, das veroeffentlicht werden soll. Ohne Angabe
# bricht die Probe ab, statt gegen eine fremde oder leere Kennung zu messen und
# ein beruhigendes Ergebnis zu liefern, das nichts belegt.
OWNER="${SAGANTA_OWNER_SUB:-}"
if [[ -z $OWNER ]]; then
  echo "FEHLER: SAGANTA_OWNER_SUB ist nicht gesetzt." >&2
  echo "  Die Probe vergleicht Owner gegen Fremden. Ohne echte Owner-Kennung" >&2
  echo "  misst sie nichts. Kennung aus der Auth-DB:" >&2
  echo "    docker exec saganta-auth-db sh -lc 'psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -t -A -c \"select id, email from \\\"user\\\"\"'" >&2
  echo "  Dann: SAGANTA_OWNER_SUB=<id> bash scripts/zweiter-nutzer-probe.sh" >&2
  exit 2
fi

# Dienst : Container : Zielgruppe : Route : Erwartung (getrennt|gemeinsam)
PRUEFUNGEN=(
  "notizen-api:saganta-notizen-api:notizen-api:/api/notizen:getrennt"
  "projectdeck-api:saganta-projectdeck-api:projectdeck-api:/api/projects:getrennt"
  "projectdeck-api:saganta-projectdeck-api:projectdeck-api:/api/focus:getrennt"
  "assets-api:saganta-assets-api:assets-api:/api/assets:getrennt"
  "news-api:saganta-news-api:news-api:/api/news/feed:gemeinsam"
  "news-api:saganta-news-api:news-api:/api/news/briefing/history:getrennt"
  "mail-api:saganta-mail-api:mail-api:/api/mail/accounts:getrennt"
  "shell-api:saganta-shell-api:shell-api:/api/settings:getrennt"
)

# Routen, bei denen eine identische Antwort geprueft und harmlos ist. Wie bei
# mandanten-probe.sh gilt: jede Zeile braucht einen Grund, sonst waechst hier
# still eine Liste, die genau die Funde wegdrueckt, wegen derer es die Probe gibt.
GEPRUEFT_GLEICH=(
  "shell-api /api/settings=Standardwerte fuer einen Nutzer ohne eigene Zeile (routes_me.py, db.get auf den Primaerschluessel sub). Sie gleichen denen des Owners, weil der nie etwas umgestellt hat. Am 30.08.2026 am Code und an der Tabelle geprueft."
)

grund_gleich() {
  for eintrag in "${GEPRUEFT_GLEICH[@]}"; do
    [[ "${eintrag%%=*}" == "$1" ]] && { echo "${eintrag#*=}"; return 0; }
  done
  return 1
}

fehler=0
lecks=()
unklar=()

for eintrag in "${PRUEFUNGEN[@]}"; do
  IFS=":" read -r dienst container zielgruppe route erwartung <<< "$eintrag"
  docker inspect "$container" >/dev/null 2>&1 || { echo "$dienst: Container fehlt"; exit 2; }

  # Die Token werden IM Container gestempelt. So bleibt das Signaturgeheimnis
  # dort, wo es hingehoert, und steht in keiner Kommandozeile.
  # ★ Das -i ist Pflicht: ohne offenen Eingabekanal sieht python im Container das
  # Skript aus dem Here-Dokument nie. Beim ersten Anlauf meldete die Probe
  # daraufhin sechsmal "nicht erreichbar" und beendete sich trotzdem mit 0.
  ergebnis="$(docker exec -i "$container" python - "$OWNER" "$FREMDER" "$zielgruppe" "$route" <<'PY' 2>/dev/null
import hashlib, json, sys, time, urllib.error, urllib.request
from jose import jwt
from app.config import settings

owner, fremder, zielgruppe, route = sys.argv[1:5]


def hole(sub):
    token = jwt.encode(
        {"sub": sub, "iss": "saganta", "aud": zielgruppe, "exp": int(time.time()) + 120},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    anfrage = urllib.request.Request(
        "http://127.0.0.1:8000" + route, headers={"Authorization": "Bearer " + token}
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=15) as antwort:
            return antwort.status, antwort.read()
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read()[:80]
    except Exception as fehler:
        return 0, type(fehler).__name__.encode()


def umfang(rohdaten):
    """Wie viele Eintraege, und ein Fingerabdruck des Inhalts."""
    try:
        daten = json.loads(rohdaten)
    except ValueError:
        return -1, ""
    if isinstance(daten, dict):
        for schluessel in ("items", "results", "data", "item_ids"):
            if isinstance(daten.get(schluessel), list):
                daten = daten[schluessel]
                break
    anzahl = len(daten) if isinstance(daten, list) else (1 if daten else 0)
    abdruck = hashlib.sha256(
        json.dumps(daten, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]
    return anzahl, abdruck


code_o, roh_o = hole(owner)
code_f, roh_f = hole(fremder)
anzahl_o, abdruck_o = umfang(roh_o) if code_o == 200 else (-1, "")
anzahl_f, abdruck_f = umfang(roh_f) if code_f == 200 else (-1, "")
print(f"{code_o}\t{anzahl_o}\t{abdruck_o}\t{code_f}\t{anzahl_f}\t{abdruck_f}")
PY
)" || { echo "$dienst: Aufruf fehlgeschlagen"; exit 2; }

  IFS=$'\t' read -r code_o anzahl_o abdruck_o code_f anzahl_f abdruck_f <<< "$ergebnis"
  kennung="$dienst $route"

  if [[ -z "${code_f:-}" || "${code_f}" == "0" ]]; then
    printf '%-16s %-32s MESSUNG FEHLGESCHLAGEN\n' "$dienst" "$route"
    unklar+=("$kennung (keine Antwort)"); fehler=2; continue
  fi
  if [[ "$code_f" == "404" || "$code_f" == "401" ]]; then
    printf '%-16s %-32s HTTP %s, hier wurde nichts geprueft\n' "$dienst" "$route" "$code_f"
    unklar+=("$kennung (HTTP $code_f)"); fehler=2; continue
  fi
  if [[ "$code_f" == "403" ]]; then
    printf '%-16s %-32s 403, Gate haelt ihn draussen (ungeprueft)\n' "$dienst" "$route"
    continue
  fi
  if [[ "$code_f" != "200" ]]; then
    printf '%-16s %-32s HTTP %s\n' "$dienst" "$route" "$code_f"
    unklar+=("$kennung (HTTP $code_f)"); fehler=2; continue
  fi

  if [[ "$erwartung" == "gemeinsam" ]]; then
    printf '%-16s %-32s gemeinsam, beide sehen %s (so gewollt)\n' "$dienst" "$route" "$anzahl_f"
    continue
  fi

  if [[ "$abdruck_o" == "$abdruck_f" ]]; then
    if [[ "${anzahl_f:-0}" == "0" ]]; then
      printf '%-16s %-32s beide leer, Trennung nicht pruefbar\n' "$dienst" "$route"
      unklar+=("$kennung (keine Daten zum Vergleichen)")
    elif grund="$(grund_gleich "$kennung")"; then
      printf '%-16s %-32s identisch, aber geprueft: %s\n' "$dienst" "$route" "${grund:0:60}..."
    else
      # Identische Antworten mit Inhalt: entweder ein Leck oder Standardwerte,
      # die zufaellig gleich aussehen. Die Probe kann das nicht entscheiden und
      # behauptet es deshalb auch nicht.
      printf '%-16s %-32s IDENTISCH mit dem Owner (%s), nachsehen\n' "$dienst" "$route" "$anzahl_f"
      lecks+=("$kennung: gleiche Antwort wie der Owner")
      fehler=1
    fi
    continue
  fi

  if [[ "${anzahl_f:-0}" -gt 0 ]]; then
    printf '%-16s %-32s sieht %s eigene (Owner %s)\n' "$dienst" "$route" "$anzahl_f" "$anzahl_o"
  else
    printf '%-16s %-32s kommt durch, sieht nichts Fremdes\n' "$dienst" "$route"
  fi
done

echo
if ((${#unklar[@]})); then
  echo "Nicht beantwortet:"
  printf '  %s\n' "${unklar[@]}"
  echo
fi
if ((${#lecks[@]})); then
  echo "Nachsehen, ob hier fremde Daten sichtbar sind:"
  printf '  %s\n' "${lecks[@]}"
elif ((${#unklar[@]} == 0)); then
  echo "Kein Leck gefunden. Wo 403 steht, ist die Frage ungestellt, nicht beantwortet."
fi

exit "$fehler"
