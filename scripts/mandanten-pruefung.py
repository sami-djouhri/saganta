#!/usr/bin/env python3
"""Prueft, ob jede Datenroute eines Backends an einen Mandanten gebunden ist.

Hintergrund: 13 Dienste tragen heute eine ``ALLOWED_SUBS``-Allowlist mit genau
einem Eintrag. Solange sie dort steht, ist sie bei manchen Diensten die einzige
Bremse -- faellt sie, sieht jedes angemeldete Konto die Daten des Owners. Bevor
ein Gate geoeffnet wird, muss deshalb nachgewiesen sein, dass die Trennung ohne
es traegt.

Das Werkzeug ist ein **Filter, kein Beweis**: es findet Routen, die keine
erkennbare Mandantenbindung haben. Jeder Treffer wird von Hand geprueft, jeder
bewusst globale Endpunkt bekommt eine Ausnahme mit Begruendung in
``AUSNAHMEN``. Was hier gruen ist, ist geprueft worden -- nicht, weil das
Skript klug ist, sondern weil jede Zeile einmal durch diese Liste musste.

Aufruf:
    python3 scripts/mandanten-pruefung.py            # alle Dienste
    python3 scripts/mandanten-pruefung.py notizen-api
Rueckgabe: 0 = jede Route gebunden oder begruendet, 1 = offene Route gefunden.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DIENSTE = WURZEL / "services"

# ★ Das geprueffte Kriterium ist der **Nutzerparameter**, nicht der sichtbare
# Filter. Grund: die Bindung laeuft bei den Proxy-Diensten nicht im Rumpf der
# Route, sondern ueber die ContextVar ``aktueller_sub``, die die Auth-Abhaengigkeit
# setzt und ``authed_kalender_client()``/``upstream()`` beim Aufruf des nativen
# Dienstes in ``X-Saganta-Sub`` uebersetzt. Eine Route mit ``me: Me = CurrentUser``
# ist damit gebunden, auch wenn ``me`` im Rumpf nie auftaucht.
#
# ★★ Der gefaehrliche Fall ist die Umkehrung: eine Route **ohne** Nutzerparameter,
# die trotzdem Daten holt. Dann ist die ContextVar leer, ``tenant_headers(None)``
# liefert ein leeres Dict, der Aufruf geht headerlos raus -- und der native Dienst
# faellt bewusst auf ``DEFAULT_OWNER_SUB`` zurueck. Das ist kein Fehler, es ist der
# CORE-Pfad (Home Assistant holt so den Tagestyp); es wird nur dann zum Leck, wenn
# eine Nutzerroute versehentlich denselben Weg nimmt. Genau danach wird hier gesucht.
NUTZER_PARAM = ("Me", "AktuellerNutzer", "Nutzer", "CurrentUser")

# Zusaetzlich akzeptierte direkte Filter -- fuer Dienste, die ihre eigene
# Datenhaltung haben und ohne Nutzerparameter in der Signatur auskommen.
BINDUNGEN = (
    "me.sub",
    "owner_sub",
    "aktueller_sub",
    "tenant_headers",
    "current_owner_sub",
    "nutzer.sub",
)

# Bewusst nicht mandantengebundene Endpunkte, je mit Grund. Schluessel ist
# "<dienst>:<funktionsname>". Wer hier etwas eintraegt, behauptet: dieser
# Endpunkt darf jedem angemeldeten Konto dasselbe zeigen.
AUSNAHMEN: dict[str, str] = {
    # -- Betriebsendpunkte ohne Nutzdaten --------------------------------------
    "*:health": "Zustand des Dienstes, keine Nutzdaten.",
    "*:healthz": "Zustand des Dienstes, keine Nutzdaten.",
    "*:health_ready": "Zustand des Dienstes, keine Nutzdaten.",
    "*:metrics": "Betriebszahlen, keine Nutzdaten.",
    "*:version": "Bauversion, keine Nutzdaten.",
    "*:readyz": "Zustand des Dienstes, keine Nutzdaten.",
    # -- Bewusst oeffentliche Zugaenge, je einzeln nachgelesen ------------------
    # Gemeinsames Muster: der Zugang haengt an einem unerratbaren Merkmal im
    # Pfad, nicht am angemeldeten Konto. Ein gefallenes ALLOWED_SUBS-Gate
    # aendert an ihnen nichts -- sie waren nie davon abhaengig.
    "news-api:public_feed": "Podcast-RSS am Feed-Token; rotierbar, kein Konto-Zugang.",
    "news-api:public_briefing": "Eigenes Briefing am Feed-Token (Skripte, Heim-Automation).",
    "news-api:public_audio": "Briefing-Audio am Feed-Token, gleicher Zugang wie der Feed.",
    "news-api:stripe_webhook": "Kein Login: Stripe weist sich per Signatur aus (verify im Rumpf).",
    "notizen-api:zustand": "Oeffentliche Freigabe am Merkmal; nur Metadaten, ratenbegrenzt.",
    "notizen-api:oeffnen": "Oeffentliche Freigabe am Merkmal; Passwort/Ablauf/Zaehler im Rumpf.",
    "notizen-api:anhang": "Anhang einer geoeffneten Freigabe, zusaetzlich Zugriffsschein-pflichtig.",
    # ★ auth_check ist KEINE Mandantenpruefung und soll auch keine sein: er
    # beantwortet nginx die Frage „ist ueberhaupt jemand angemeldet". Wer
    # dahinter was sieht, entscheidet der native Dienst -- siehe
    # docs/MANDANTEN_BEFUND.md, Abschnitt „Die vier gateten Vhosts".
    "shell-api:auth_check": "SSO-Gate fuer nginx auth_request: liefert nur 204/401, keine Daten.",
}


def ist_route(knoten: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Gibt die HTTP-Methode zurueck, wenn die Funktion eine Route ist."""
    for dek in knoten.decorator_list:
        ziel = dek.func if isinstance(dek, ast.Call) else dek
        if not isinstance(ziel, ast.Attribute):
            continue
        if ziel.attr in ("get", "post", "put", "patch", "delete"):
            wurzel = ziel.value
            if isinstance(wurzel, ast.Name) and wurzel.id in ("router", "app"):
                return ziel.attr.upper()
    return None


def hat_nutzerparameter(knoten: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Traegt die Signatur den angemeldeten Nutzer?

    Geprueft werden Annotation **und** Vorgabewert: geschrieben wird mal
    ``me: Me = CurrentUser`` und mal ``me: Me = AktuellerNutzer``, und in beiden
    Faellen ist es der Vorgabewert, der die Abhaengigkeit ausloest.
    """
    for arg in list(knoten.args.args) + list(knoten.args.kwonlyargs):
        if arg.annotation is None:
            continue
        quelle = ast.unparse(arg.annotation)
        if any(name in quelle for name in NUTZER_PARAM):
            return True
    for vorgabe in list(knoten.args.defaults) + list(knoten.args.kw_defaults):
        if vorgabe is None:
            continue
        if any(name in ast.unparse(vorgabe) for name in NUTZER_PARAM):
            return True
    return False


def hat_bindung(knoten: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    quelle = ast.unparse(knoten)
    return any(marke in quelle for marke in BINDUNGEN)


def ausnahme(dienst: str, name: str) -> str | None:
    return AUSNAHMEN.get(f"{dienst}:{name}") or AUSNAHMEN.get(f"*:{name}")


def pruefe_dienst(pfad: Path) -> list[tuple[str, str, str, int]]:
    """Liefert die offenen Routen als (datei, methode, name, zeile)."""
    dienst = pfad.name
    offen: list[tuple[str, str, str, int]] = []
    for datei in sorted((pfad / "app").rglob("*.py")):
        try:
            baum = ast.parse(datei.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for knoten in ast.walk(baum):
            if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            methode = ist_route(knoten)
            if methode is None:
                continue
            if ausnahme(dienst, knoten.name):
                continue
            if hat_nutzerparameter(knoten) or hat_bindung(knoten):
                continue
            rel = datei.relative_to(pfad).as_posix()
            offen.append((rel, methode, knoten.name, knoten.lineno))
    return offen


def main() -> int:
    gewaehlt = sys.argv[1:]
    dienste = [
        d
        for d in sorted(DIENSTE.iterdir())
        if d.is_dir() and (d / "app").is_dir() and (not gewaehlt or d.name in gewaehlt)
    ]
    if not dienste:
        print("Kein Dienst gefunden.", file=sys.stderr)
        return 2

    gesamt = 0
    for dienst in dienste:
        offen = pruefe_dienst(dienst)
        gesamt += len(offen)
        if offen:
            print(f"\n{dienst.name}: {len(offen)} Route(n) ohne erkennbare Mandantenbindung")
            for rel, methode, name, zeile in offen:
                print(f"  {methode:6} {rel}:{zeile}  {name}")
        else:
            print(f"{dienst.name}: alle Routen gebunden oder begruendet")

    print(f"\nSumme: {gesamt} offene Route(n)")
    return 1 if gesamt else 0


if __name__ == "__main__":
    raise SystemExit(main())
