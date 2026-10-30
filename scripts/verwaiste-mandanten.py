#!/usr/bin/env python3
"""Findet Mandanten, die Daten haben, aber kein Konto mehr (oder nie eines hatten).

WARUM ES DAS GIBT
=================

Die Mandantentrennung ist die Frage „sieht A die Daten von B". Dieses Werkzeug
stellt die Frage danach: **was passiert mit den Daten, wenn A verschwindet.**

Gemessen am 2026-10-03: von zehn Saganta-Diensten hat **einer** einen Weg, die
Daten eines Mandanten zu loeschen (`kalender` ueber `/api/account/delete`). Fuer
die uebrigen gibt es keinen. Ein in der Anmelde-Datenbank geloeschtes Konto
hinterlaesst damit seinen vollstaendigen Bestand in notizen, tagebuch, assets,
projectdeck, news, mail, lager, mealprep, fitness und briefkasten.

Und der Rest ist nicht still. Der Pruef-Sub `neues-konto-erstbesuch-999`
stammte aus einem Beweislauf vom 2026-09-26 und bekam seither **acht Naechte
hintereinander um 04:36 ein vollstaendiges Briefing erzeugt**, samt moeglicher
Sprachausgabe: `briefing_sched.py:80` nimmt jedes `BriefingProfile` mit
`enabled`, und ob dazu noch ein Konto existiert, fragt niemand. Ein verwaister
Mandant ist also kein Datenrest, sondern ein Verbraucher, der keinem auffaellt.

Mit einem Nutzer ist das folgenlos. Ab dem zweiten ist es dreierlei: stille Last,
ein Loeschrecht, das sich nicht erfuellen laesst (DSGVO Art. 17), und ein
Bestand, der mit jedem Probierkonto waechst.

WAS ES NICHT TUT
================

Es loescht nichts. Es beantwortet die Frage, wo etwas zu loeschen waere. Das
Loeschen selbst braucht je Dienst eine Route, die ihre eigenen
Fremdschluesselketten kennt; ein Werkzeug von aussen, das in zehn Datenbanken
Zeilen entfernt, waere die schlechtere Haelfte dieser Loesung.

AUFRUF
======

    python3 scripts/verwaiste-mandanten.py          # Bericht
    python3 scripts/verwaiste-mandanten.py --json   # maschinenlesbar
"""

from __future__ import annotations

import json
import subprocess
import sys

# Container, Suchmuster fuer die Datenbank, und die Spalten, die einen Mandanten
# bezeichnen. Die Namen weichen bewusst ab (`owner_sub`, `sub`, `owner`,
# `created_by_sub`), deshalb steht hier eine Liste und kein einziger Name:
# ein Pruefer, der Eigenschaften am Namen erkennt, findet genau das nicht, was
# anders benannt ist (dieselbe Lehre wie in mandanten-probe.sh).
MANDANTEN_SPALTEN = ("owner_sub", "sub", "owner", "created_by_sub")

DIENSTE = [
    # (Container, Glob-Muster fuer die SQLite-Datei)
    ("saganta-notizen-api", "/data/*.db /app/data/*.db"),
    ("saganta-tagebuch-api", "/data/*.db /app/data/*.db"),
    ("saganta-assets-api", "/data/*.db /app/data/*.db"),
    ("saganta-projectdeck-api", "/data/*.db /app/data/*.db"),
    ("saganta-news-api", "/data/*.db /app/data/*.db"),
    ("saganta-mail-api", "/data/*.db /app/data/*.db"),
    ("saganta-shell-api", "/data/*.db /app/data/*.db"),
    # Die nativen Dienste ausserhalb dieses Repos. Sie gehoeren dazu: ihre Gates
    # sind seit dem 2026-10-03 offen, also koennen dort fremde Mandanten liegen.
    ("lager", "/app/data/*.db"),
    ("mealprep", "/app/data/*.db"),
    ("fitness", "/app/data/*.db"),
    ("kalender", "/app/data/*.db"),
    ("briefkasten", "/app/data/*.db"),
]

# Subs, die kein Konto sind und auch keines sein sollen.
# `None` steht fuer bewusst gemeinsamen Bestand (Feiertage, Seed-Rezepte,
# Uebungskatalog, Systemkalender) und ist kein Verwaister.
BEKANNT_OHNE_KONTO = {
    # Der headerlose CORE-Pfad des Kalenders laeuft auf DEFAULT_OWNER_SUB, und
    # das IST der Owner. Er steht in der Anmelde-DB, deshalb hier nichts noetig.
    #
    # `__system__` = `kalender/backend/tenant.py:SYSTEM_RUN_SUB`. Darunter
    # verbucht der Sekretaer seine eigenen Laeufe (`secretary_runs`), damit die
    # taegliche Aufraeumarbeit nicht zweimal laeuft. Kein Nutzer, sondern eine
    # Merkzeile des Dienstes ueber sich selbst. Die Mandanten-Ableitung dort
    # nimmt ihn aus genau demselben Grund aus: sonst sieht eine
    # Ein-Personen-Installation zwei Mandanten und verweigert die Ableitung, und
    # daran haengt die headerlose HA-Weckkette.
    "__system__",
}

# Das Programm, das im jeweiligen Container laeuft. Bewusst Standardbibliothek:
# in den Dienst-Images liegt kein zusaetzliches Paket, und ein `pip install` nur
# fuer eine Messung veraendert den gemessenen Zustand.
IM_CONTAINER = r"""
import glob, json, sqlite3, sys

spalten_namen = set(sys.argv[1].split(","))
muster = sys.argv[2].split()
gefunden = {}
# Zweite Kategorie, nachgetragen am 2026-10-04. Die erste Fassung zaehlte
# `NULL` grundsaetzlich als "bewusst gemeinsam" und uebersprang es. Das ist
# richtig fuer Feiertage, Seed-Rezepte, den Uebungskatalog und Systemkalender,
# und **falsch fuer eine Kontentabelle**: im `briefkasten` bedeutet
# `user.sub IS NULL` nicht "gehoert allen", sondern "lokales Konto ohne
# Saganta-Bindung", also eine zweite Anmeldetuer in dieselbe App. Gemessen gab
# es dort drei Konten, zwei davon ohne Sub, und eines von ihnen besitzt einen
# der beiden Briefe. Das Werkzeug meldete "kein Verwaister".
KONTO_TABELLEN = ("user", "users", "konto", "konten", "account", "accounts")
lokale_konten = {}
dateien = []
for m in muster:
    dateien.extend(glob.glob(m))
for pfad in sorted(set(dateien)):
    try:
        verb = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
        tabellen = [r[0] for r in verb.execute(
            "select name from sqlite_master where type='table'")]
    except Exception:
        continue
    for tabelle in tabellen:
        if tabelle.startswith("sqlite_") or tabelle.startswith("alembic"):
            continue
        try:
            spalten = [r[1] for r in verb.execute(f"pragma table_info({tabelle})")]
        except Exception:
            continue
        for spalte in spalten:
            if spalte not in spalten_namen:
                continue
            try:
                for (wert, anzahl) in verb.execute(
                    f"select {spalte}, count(*) from {tabelle} "
                    f"where {spalte} is not null group by {spalte}"
                ):
                    schluessel = str(wert)
                    eintrag = gefunden.setdefault(schluessel, {"zeilen": 0, "orte": []})
                    eintrag["zeilen"] += anzahl
                    eintrag["orte"].append(f"{tabelle}.{spalte}")
            except Exception:
                continue
            # In einer Kontentabelle ist ein leerer Sub kein gemeinsamer
            # Bestand, sondern ein Konto, das die Saganta-Anmeldung nicht kennt.
            if tabelle.lower() in KONTO_TABELLEN:
                try:
                    anzahl = verb.execute(
                        f"select count(*) from {tabelle} where {spalte} is null"
                    ).fetchone()[0]
                    if anzahl:
                        lokale_konten[f"{tabelle}.{spalte}"] = anzahl
                except Exception:
                    pass
print(json.dumps({"subs": gefunden, "lokale_konten": lokale_konten}))
"""


def lauf(befehl: list[str]) -> tuple[int, str]:
    fertig = subprocess.run(befehl, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return fertig.returncode, fertig.stdout.decode("utf-8", "replace").strip()


def konten() -> set[str]:
    """Die gueltigen Kennungen aus der better-auth-Datenbank."""
    code, nutzer = lauf(
        ["docker", "inspect", "saganta-auth-db", "--format",
         "{{range .Config.Env}}{{println .}}{{end}}"]
    )
    if code != 0:
        raise SystemExit("saganta-auth-db nicht erreichbar.")
    werte = dict(
        zeile.split("=", 1) for zeile in nutzer.splitlines() if "=" in zeile
    )
    benutzer = werte.get("POSTGRES_USER", "saganta_auth")
    datenbank = werte.get("POSTGRES_DB", "saganta_auth")
    code, ausgabe = lauf([
        "docker", "exec", "saganta-auth-db", "psql", "-U", benutzer,
        "-d", datenbank, "-tAc", 'select id from "user"',
    ])
    if code != 0:
        raise SystemExit(f"Konten nicht lesbar: {ausgabe[:200]}")
    return {z.strip() for z in ausgabe.splitlines() if z.strip()}


def subs_im_dienst(container: str, muster: str) -> dict:
    code, ausgabe = lauf([
        "docker", "exec", "-i", container, "python3", "-c", IM_CONTAINER,
        ",".join(MANDANTEN_SPALTEN), muster,
    ])
    if code != 0:
        return {}
    try:
        # Der Dienst darf vor dem JSON noch etwas ausgeben (Warnungen).
        return json.loads(ausgabe[ausgabe.index("{"):])
    except Exception:
        return {}


def leer() -> dict:
    return {"subs": {}, "lokale_konten": {}}


def main() -> int:
    echte_konten = konten()
    gueltig = echte_konten | set(BEKANNT_OHNE_KONTO)
    bericht = {}
    unerreichbar = []
    for container, muster in DIENSTE:
        code, _ = lauf(["docker", "inspect", "-f", "{{.State.Running}}", container])
        if code != 0:
            unerreichbar.append(container)
            continue
        ergebnis = subs_im_dienst(container, muster) or leer()
        gefunden = ergebnis.get("subs", {})
        verwaist = {s: d for s, d in gefunden.items() if s not in gueltig}
        bericht[container] = {
            "subs_gesamt": len(gefunden),
            "verwaist": verwaist,
            "lokale_konten": ergebnis.get("lokale_konten", {}),
        }

    if "--json" in sys.argv:
        print(json.dumps(
            {"konten": len(gueltig), "dienste": bericht, "unerreichbar": unerreichbar},
            indent=2, ensure_ascii=False,
        ))
        return 0

    # Zwei Zahlen, nicht eine: diese Zeile nannte bis zum 2026-10-04
    # `len(gueltig)` und damit die begruendete Ausnahme mit, sagte dabei aber
    # "in der Anmelde-Datenbank". Sie meldete 4, dort standen 3. Eine Zahl mit
    # falschem Nenner liest sich wie eine Messung.
    print(f"Konten in der Anmelde-Datenbank: {len(echte_konten)}"
          f"  (plus {len(BEKANNT_OHNE_KONTO)} begruendete Ausnahme(n))")
    if unerreichbar:
        print(f"Nicht erreichbar (laeuft nicht): {', '.join(unerreichbar)}")
    print()
    summe, lokal_summe = 0, 0
    for container, d in bericht.items():
        marke = "  "
        if d["verwaist"] or d["lokale_konten"]:
            marke = "!!"
        summe += len(d["verwaist"])
        lokal_summe += sum(d["lokale_konten"].values())
        print(f"{marke} {container:<26} {d['subs_gesamt']} Mandant(en) mit Daten")
        for sub, detail in sorted(d["verwaist"].items()):
            orte = ", ".join(sorted(set(detail["orte"]))[:4])
            print(f"     VERWAIST  {sub}  {detail['zeilen']} Zeilen  ({orte})")
        for ort, anzahl in sorted(d["lokale_konten"].items()):
            print(f"     OHNE SAGANTA-BINDUNG  {anzahl} Konto/Konten in {ort}")
    print()
    if summe:
        print(f"{summe} verwaiste(r) Mandant(en). Sie haben Daten und kein Konto.")
        print("Loeschen geht heute nur im kalender (/api/account/delete); fuer die")
        print("uebrigen Dienste fehlt die Route. Siehe Modulkopf.")
    else:
        print("Kein verwaister Mandant: jeder Bestand mit Sub gehoert einem Konto.")
    if lokal_summe:
        print(f"{lokal_summe} Konto/Konten ohne Saganta-Bindung. Das ist eine ZWEITE")
        print("Anmeldetuer in dieselbe App, und sie zaehlt nicht als gemeinsamer")
        print("Bestand. Pruefen, ob sie gewollt ist und ob ihre Registrierung zu ist.")
    return 1 if (summe or lokal_summe) else 0


if __name__ == "__main__":
    raise SystemExit(main())
