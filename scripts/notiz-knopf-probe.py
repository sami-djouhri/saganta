#!/usr/bin/env python3
"""Prueft, dass der Knopf „Notiz dazu" in jeder App auch eine Gegenseite hat.

WARUM ES DIESE PROBE GIBT. Seit dem 2026-10-24 steht der Knopf in drei Apps,
und zwar als EINE Komponente (`packages/ui/src/components/NotizenBlock.svelte`)
mit der Vorgabe `action="?/notizDazu"`. Ob eine App diese Aktion anbietet,
steht aber in jeder App einzeln, in ihrer `+page.server.ts`. Das ist genau die
Stelle, an der die drei auseinanderlaufen koennen, und zwar lautlos:

  Der Knopf wird gerendert, der Dialog oeffnet, man tippt eine Notiz, klickt
  „Notiz anlegen" -- und SvelteKit antwortet 404, weil es keine Aktion dieses
  Namens gibt. Mit `use:enhance` passiert sichtbar: nichts. Die Komponente
  sieht dabei vollkommen richtig aus, denn sie IST richtig.

Zweitens die HTML-Falle: der Block bringt sein eigenes `<form>` mit. Steht er
innerhalb eines anderen Formulars, ist das ungueltiges HTML. Der Browser bricht
die Verschachtelung stillschweigend auf, die Felder landen am aeusseren
Formular, und abgeschickt wird die falsche Aktion mit den falschen Werten. Auch
hier: keine Fehlermeldung, nirgends. Beide Oberflaechen, in die der Block
eingebaut wurde (Termin-Editor und Projektansicht), waren vorher ein einziges
grosses `<form>`; die Falle ist also nicht theoretisch.

Geprueft wird am Quelltext und nicht am laufenden Dienst, und das ist hier
keine Bequemlichkeit: ueber HTTP laesst sich eine fehlende Aktion ohne
angemeldete Sitzung nicht von einer vorhandenen unterscheiden. Der
Anmelde-Hook leitet beide Faelle auf `/login` um, bevor SvelteKit die Aktion
ueberhaupt aufloest (am 2026-10-24 gemessen: beide Namen, auch ein frei
erfundener, antworten mit derselben 303).

Aufruf:  scripts/notiz-knopf-probe.py [--selbsttest]
Ende:    rc=0 alles gedeckt, rc=1 Luecke gefunden, rc=2 nichts gefunden
"""

import pathlib
import re
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent
KOMPONENTE = "NotizenBlock"
VORGABE_AKTION = "notizDazu"


def ohne_kommentare(text: str) -> str:
    """HTML- und JS-Kommentare entfernen.

    Noetig, weil an beiden Einbaustellen ein Kommentar steht, der die
    Formular-Falle erklaert und dabei `<form>` erwaehnt. Wer ihn mitzaehlt,
    meldet eine Verschachtelung, die es nicht gibt. Dieselbe Lehre wie in
    `reiter-probe.py`.
    """
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?<![:/])//[^\n]*", "", text)


def aktion_von(aufruf: str) -> str:
    """Den Aktionsnamen aus einem `<NotizenBlock …>`-Aufruf lesen."""
    treffer = re.search(r"""aktion=['"]\?/([A-Za-z0-9_]+)['"]""", aufruf)
    if treffer:
        return treffer.group(1)
    # `aktion={ausdruck}` koennen wir nicht statisch lesen; das ist eine
    # bewusste Lücke und wird als solche gemeldet, nicht als Erfolg.
    if re.search(r"aktion=\{", aufruf):
        return "?dynamisch"
    return VORGABE_AKTION


def bloecke(text: str):
    """Alle `<NotizenBlock …>`-Aufrufe mit ihrer Position zurueckgeben."""
    for m in re.finditer(rf"<{KOMPONENTE}\b[^>]*?/?>", text, flags=re.S):
        yield m.start(), m.group(0)


def in_offenem_formular(text: str, bis: int) -> bool:
    """Steht die Position innerhalb eines `<form>`?

    Gezaehlt wird, nicht gesucht: an der Einbaustelle koennen mehrere
    Formulare davor geoeffnet UND geschlossen worden sein.
    """
    kopf = text[:bis]
    return len(re.findall(r"<form\b", kopf)) > len(re.findall(r"</form>", kopf))


def seiten_die_einbinden(app: pathlib.Path, datei: pathlib.Path) -> list[pathlib.Path]:
    """Die `+page.svelte`-Dateien, über die `datei` erreichbar ist.

    Entweder ist sie selbst eine Seite, oder eine Seite bindet sie ein, auch
    ueber Zwischenschritte (Termin-Editor und Aufgaben-Dialog liegen beide in
    `lib/`, nicht in einer Route).
    """
    if datei.name == "+page.svelte":
        return [datei]

    gesucht = {datei.name}
    seiten: list[pathlib.Path] = []
    # Mehrere Runden, damit auch eine Kette über zwei Zwischenschritte traegt.
    for _ in range(5):
        neu = set()
        for kandidat in sorted((app / "src").rglob("*.svelte")):
            roh = kandidat.read_text(encoding="utf-8")
            if not any(re.search(rf"\b{re.escape(n)}\b", roh) for n in gesucht):
                continue
            if kandidat.name == "+page.svelte":
                if kandidat not in seiten:
                    seiten.append(kandidat)
            elif kandidat.name not in gesucht:
                neu.add(kandidat.name)
        if not neu:
            break
        gesucht |= neu
    return seiten


def _namen_aus(roh: str) -> set[str]:
    """Aktionsnamen aus einem `actions`-Objektliteral lesen."""
    ab = roh.find("Actions = {")
    if ab < 0:
        ab = roh.find("export const actions")
    if ab < 0:
        return set()
    return set(re.findall(r"^\s{2}([A-Za-z0-9_]+)\s*:\s*async", roh[ab:], flags=re.M))


def aktionen_der_seite(seite: pathlib.Path) -> set[str] | None:
    """Die Aktionsnamen der `+page.server.ts` neben einer Seite.

    `None` heisst: es gibt dort gar keine `+page.server.ts`, also auch keine
    einzige Aktion. Das ist ein anderer Befund als „Aktion fehlt" und wird
    getrennt gemeldet.

    Der Indirektion wird gefolgt, und das war der erste eigene Messfehler
    dieser Probe. Die Aufgaben-App definiert ihre Aktionen EINMAL in
    `lib/server/aktionen.ts` und schreibt in allen vier Seiten nur
    `export const actions = aufgabenAktionen` (richtig so: sonst waere derselbe
    Block viermal kopiert). Eine Probe, die nur nach einem Objektliteral sucht,
    meldet dort vier fehlende Aktionen, die es gibt. Vier Fehlbefunde sehen aus
    wie ein Fund, und ein Pruefer, dessen rote Zeile man wegerklaeren muss,
    ist schlechter als keiner.
    """
    server = seite.parent / "+page.server.ts"
    if not server.is_file():
        return None
    roh = ohne_kommentare(server.read_text(encoding="utf-8"))

    namen = _namen_aus(roh)

    # `export const actions = <bezeichner>` → dem Import folgen.
    zuweisung = re.search(r"export\s+const\s+actions\s*(?::[^=]+)?=\s*([A-Za-z0-9_]+)\s*;", roh)
    if zuweisung:
        bezeichner = zuweisung.group(1)
        quelle = re.search(
            rf"""import\s*\{{[^}}]*\b{re.escape(bezeichner)}\b[^}}]*\}}\s*from\s*['"]([^'"]+)['"]""",
            roh,
        )
        if quelle:
            pfad = quelle.group(1)
            # `$lib/...` zeigt auf `src/lib/...` der jeweiligen App.
            app = seite
            while app.name != "src" and app.parent != app:
                app = app.parent
            kandidaten = []
            if pfad.startswith("$lib/"):
                kandidaten.append(app / "lib" / f"{pfad[len('$lib/'):]}.ts")
            elif pfad.startswith("."):
                kandidaten.append((seite.parent / f"{pfad}.ts").resolve())
            for k in kandidaten:
                if k.is_file():
                    namen |= _namen_aus(ohne_kommentare(k.read_text(encoding="utf-8")))
    return namen


def pruefe() -> tuple[list[str], int]:
    maengel: list[str] = []
    geprueft = 0

    for app in sorted((WURZEL / "apps").iterdir()):
        if not (app / "src").is_dir():
            continue
        for datei in sorted((app / "src").rglob("*.svelte")):
            roh = datei.read_text(encoding="utf-8")
            if f"<{KOMPONENTE}" not in roh:
                continue
            sauber = ohne_kommentare(roh)
            rel = datei.relative_to(WURZEL)

            for pos, aufruf in bloecke(sauber):
                geprueft += 1

                if in_offenem_formular(sauber, pos):
                    maengel.append(
                        f"{rel}: {KOMPONENTE} steht INNERHALB eines <form>. "
                        "Ungueltiges HTML, der Browser bricht es auf und die "
                        "Felder landen am aeusseren Formular."
                    )

                for pflicht in ("typ", "ref"):
                    if not re.search(rf"\b{pflicht}=", aufruf):
                        maengel.append(f"{rel}: {KOMPONENTE} ohne `{pflicht}=`.")

                aktion = aktion_von(aufruf)
                if aktion == "?dynamisch":
                    maengel.append(
                        f"{rel}: `aktion={{…}}` ist nicht statisch pruefbar. "
                        "Bitte den Namen ausschreiben, damit diese Probe greift."
                    )
                    continue

                seiten = seiten_die_einbinden(app, datei)
                if not seiten:
                    maengel.append(
                        f"{rel}: keine `+page.svelte` bindet das ein. Entweder "
                        "toter Code oder die Probe findet die Kette nicht."
                    )
                    continue

                for seite in seiten:
                    vorhanden = aktionen_der_seite(seite)
                    srel = seite.relative_to(WURZEL)
                    if vorhanden is None:
                        maengel.append(
                            f"{srel}: bindet {KOMPONENTE} ein, hat aber keine "
                            "`+page.server.ts` und damit keine Aktion "
                            f"`{aktion}`. Der Knopf endet in einer 404."
                        )
                    elif aktion not in vorhanden:
                        maengel.append(
                            f"{srel}: Aktion `{aktion}` fehlt (vorhanden: "
                            f"{', '.join(sorted(vorhanden)) or 'keine'}). Der "
                            "Knopf wird gerendert und endet in einer 404."
                        )
    return maengel, geprueft


def selbsttest() -> int:
    """Erkennt die Probe die Faelle, gegen die sie gebaut ist?

    Ohne diesen Teil ist ein „Bestanden" nicht zu unterscheiden von „sucht am
    falschen Ort". Genau diese Verwechslung hat am 2026-10-24 drei Pruefer
    gruen gemeldet, waehrend jeder ausgegebene Link ins Leere zeigte.
    """
    faelle = [
        ("Vorgabe-Aktion wird angenommen", aktion_von(f"<{KOMPONENTE} typ=\"termin\" />") == VORGABE_AKTION),
        ("eigene Aktion wird gelesen", aktion_von(f"<{KOMPONENTE} aktion=\"?/meinWeg\" />") == "meinWeg"),
        ("dynamische Aktion wird gemeldet", aktion_von(f"<{KOMPONENTE} aktion={{x}} />") == "?dynamisch"),
        ("Block im Formular wird erkannt", in_offenem_formular("<form> <NotizenBlock", 8) is True),
        ("Block nach dem Formular ist in Ordnung", in_offenem_formular("<form></form> <NotizenBlock", 20) is False),
        (
            "zwei geschlossene Formulare davor sind in Ordnung",
            in_offenem_formular("<form></form><form></form> X", 27) is False,
        ),
        (
            "Kommentar mit <form> zaehlt nicht mit",
            in_offenem_formular(ohne_kommentare("<!-- <form> --> X"), 5) is False,
        ),
        ("Aufruf wird gefunden", len(list(bloecke(f"<{KOMPONENTE} typ=\"x\" />"))) == 1),
        # Die beiden Formen, in denen Aktionen in dieser Suite vorkommen. Der
        # zweite Fall war der erste Fehlbefund dieser Probe (vier gemeldete
        # Luecken, die es nicht gab).
        (
            "Objektliteral wird gelesen",
            _namen_aus("export const actions: Actions = {\n  notizDazu: async ({}) => {},\n}")
            == {"notizDazu"},
        ),
        (
            "zugewiesene Aktionen werden im Quellmodul gefunden",
            # Am echten Baum gemessen, nicht an einem Nachbau: der Nachbau
            # wuerde auch dann bestehen, wenn die Pfadaufloesung fuer `$lib/`
            # daneben liegt.
            (aktionen_der_seite(WURZEL / "apps/aufgaben/src/routes/+page.svelte") or set())
            >= {"notizDazu", "planen"},
        ),
    ]
    schlecht = [name for name, ok in faelle if not ok]
    for name, ok in faelle:
        print(f"   {'ok  ' if ok else 'FEHL'} {name}")
    if schlecht:
        print(f"\nSelbsttest FEHLGESCHLAGEN: {len(schlecht)} von {len(faelle)}")
        return 1
    print(f"\nSelbsttest bestanden ({len(faelle)} Faelle).")
    return 0


def main() -> int:
    if "--selbsttest" in sys.argv:
        return selbsttest()

    maengel, geprueft = pruefe()
    if geprueft == 0:
        print(
            f"FEHLER: kein einziger <{KOMPONENTE}>-Aufruf gefunden. Entweder ist "
            "der Knopf nirgends eingebaut, oder diese Probe sucht am falschen "
            "Ort. Beides ist ein Befund, kein Bestehen.",
            file=sys.stderr,
        )
        return 2
    if maengel:
        print(f"{len(maengel)} Befund(e) bei {geprueft} Einbaustelle(n):\n", file=sys.stderr)
        for m in maengel:
            print(f"  - {m}", file=sys.stderr)
        return 1
    print(
        f"Bestanden: {geprueft} Einbaustelle(n) von {KOMPONENTE}, jede mit "
        "vorhandener Aktion und keine innerhalb eines Formulars."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
