#!/usr/bin/env python3
"""Ein kurzlebiges Backend-Token fuer einen Saganta-Dienst ausstellen.

Warum es das gibt: die Saganta-Backends nehmen ausschliesslich ein
HS256-JWT mit ``iss=saganta`` und der Zielgruppe des jeweiligen Dienstes
(`saganta_dienst.auth.pruefe_bearer`). Ohne Token antwortet jeder schreibende
Weg mit ``401 Missing Authorization header``. Das Geheimnis dafuer liegt je
Dienst in seiner ``.env``, und die faellt unter die Secrets-Regel in
``die Projektregeln``: der Coding-Agent darf sie nicht lesen.

Dieses Werkzeug loest den Widerspruch, statt die Regel zu lockern: **es** liest
das Geheimnis, gibt es **nie** aus und schreibt nur das fertige Token nach
stdout. Damit bleibt der Signierschluessel unsichtbar, waehrend der Schreibweg
offen ist. Entscheid vom 2026-10-24, als Gegenvorschlag zu "Secret-Regel
lockern" ausdruecklich gewaehlt: ein Schluessel, mit dem sich Token fuer JEDEN
Dienst ausstellen lassen, ist das teurere Zugestaendnis.

⚠️ **Das Token ist selbst ein Zugangsmittel.** Es laeuft deshalb standardmaessig
nach 15 Minuten ab, und es gehoert nicht in eine Datei, ein Protokoll oder eine
Chat-Ausgabe. Richtige Verwendung ist die Variable, die gleich wieder weg ist::

    TOKEN=$(scripts/dienst-token.py projectdeck-api)
    curl -s -H "Authorization: Bearer $TOKEN" ...

Die Zielgruppe ist **nicht** frei waehlbar, sondern wird gegen die
``EXPECTED_AUDIENCE`` des Dienstes geprueft, die im Quelltext steht. Ein
Tippfehler ergaebe sonst ein syntaktisch gueltiges Token, das der Dienst mit
``Invalid token: Invalid audience`` abweist, und diese Meldung liest sich wie
ein kaputtes Geheimnis statt wie ein falscher Name.

Beispiele::

    scripts/dienst-token.py projectdeck-api
    scripts/dienst-token.py projectdeck-api --minuten 5
    scripts/dienst-token.py --dienste        # welche gehen ueberhaupt
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DIENSTE_VERZ = WURZEL / "services"

# Der Aussteller steht in der geteilten Pruefschicht und wird dort verglichen.
# Hier nicht hartkodieren, sondern von dort lesen: eine zweite Fassung dieses
# Werts waere genau die Art stiller Abweichung, an der die Pruefung spaeter
# ohne erkennbaren Grund scheitert.
AUSSTELLER_QUELLE = DIENSTE_VERZ / "_geteilt" / "saganta_dienst" / "auth.py"

# Der Mandant des Owners. Steht so in jeder Saganta-Datenbank; ein Token ohne
# ``sub`` weist die Pruefschicht mit "Token without sub" ab.
OWNER_SUB_VORGABE = "1RqWBNMIKmzOZsDMh2CcOI00zqT5kWmO"

# Geheimnisse, die als Platzhalter im Quelltext stehen. Taucht einer davon
# wirklich auf, fehlt die ``.env`` oder sie ist unvollstaendig, und ein damit
# signiertes Token wuerde von jedem Dienst abgewiesen, der seine eigene
# Platzhalter-Pruefung hat. Lieber hier abbrechen als dort raten.
PLATZHALTER = {
    "change-me-shared-with-auth-proxy",
    "change-me",
    "changeme",
    "",
}


def aussteller_lesen() -> str:
    """``AUSSTELLER`` aus der geteilten Pruefschicht holen."""
    try:
        text = AUSSTELLER_QUELLE.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"Pruefschicht nicht lesbar: {AUSSTELLER_QUELLE} ({exc})")
    treffer = re.search(r'^AUSSTELLER\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    if not treffer:
        raise SystemExit(
            f"In {AUSSTELLER_QUELLE} steht kein AUSSTELLER mehr. Die Pruefschicht "
            "hat sich geaendert, und ein geratener Wert ergibt ein Token, das "
            "mit 'Unknown issuer' abgewiesen wird."
        )
    return treffer.group(1)


def zielgruppe_suchen(dienst: str) -> str | None:
    """``EXPECTED_AUDIENCE`` des Dienstes, oder ``None``.

    ``None`` ist ein gueltiger Befund und kein Fehler: ``auth-proxy`` **stellt**
    Token aus, statt sie zu pruefen, und fuehrt deshalb keine Zielgruppe. Die
    Auflistung ueberspringt solche Dienste; nur die namentliche Anfrage bricht
    ab. Ein gemeinsames Abbrechen liess vorher ``--dienste`` nach dem ersten
    solchen Dienst sterben, und das sah nach einem kaputten Werkzeug aus statt
    nach einem Dienst, der hier nichts verloren hat.
    """
    quelle = DIENSTE_VERZ / dienst / "app" / "auth.py"
    if not quelle.exists():
        return None
    treffer = re.search(
        r'^EXPECTED_AUDIENCE\s*=\s*["\']([^"\']+)["\']',
        quelle.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    return treffer.group(1) if treffer else None


def zielgruppe_lesen(dienst: str) -> str:
    """Wie ``zielgruppe_suchen``, bricht aber ab, wenn es keine gibt.

    Gelesen statt uebergeben, damit die Zielgruppe nicht an zwei Stellen
    gepflegt werden muss. Siehe Kopfkommentar: ein falscher Name ergibt eine
    Fehlermeldung, die auf das Geheimnis zeigt statt auf sich selbst.
    """
    zielgruppe = zielgruppe_suchen(dienst)
    if zielgruppe is None:
        raise SystemExit(
            f"Dienst '{dienst}' nimmt keine Token an (keine EXPECTED_AUDIENCE "
            f"in services/{dienst}/app/auth.py). Diese gehen:\n  "
            + "\n  ".join(bekannte_dienste())
        )
    return zielgruppe


def geheimnis_lesen(dienst: str) -> str:
    """``JWT_SECRET`` aus der ``.env`` des Dienstes.

    ⚠️ Der Rueckgabewert darf nirgends protokolliert oder ausgegeben werden.
    Er verlaesst diese Funktion nur in Richtung ``jwt.encode``. Deshalb nennen
    auch die Fehlermeldungen unten nur den **Pfad** und niemals den Wert, auch
    nicht abgekuerzt: ein Praefix eines HMAC-Schluessels ist bereits eine
    Preisgabe.
    """
    pfad = DIENSTE_VERZ / dienst / ".env"
    if not pfad.exists():
        raise SystemExit(
            f"Keine .env fuer '{dienst}' unter {pfad}. Ohne Geheimnis kein Token."
        )
    wert: str | None = None
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        name, _, roh = zeile.partition("=")
        if name.strip().upper() != "JWT_SECRET":
            continue
        # Anfuehrungszeichen fallen weg, wie pydantic-settings es auch tut.
        wert = roh.strip().strip('"').strip("'")
    if wert is None:
        raise SystemExit(
            f"In {pfad} steht kein JWT_SECRET. Der Dienst laeuft dann mit dem "
            "Platzhalter aus config.py und weist jedes Token ab."
        )
    if wert in PLATZHALTER:
        raise SystemExit(
            f"Das JWT_SECRET in {pfad} ist ein Platzhalter. Ein damit "
            "signiertes Token wird abgewiesen; echtes Geheimnis eintragen."
        )
    return wert


def _b64(roh: bytes) -> str:
    """Base64url ohne Auffuellzeichen, wie es JWS verlangt (RFC 7515)."""
    return base64.urlsafe_b64encode(roh).rstrip(b"=").decode("ascii")


def hs256_token(nutzlast: dict, geheimnis: str) -> str:
    """Ein HS256-JWT aus der Standardbibliothek bauen.

    Bewusst ohne ``python-jose``, obwohl die Dienste es zum **Pruefen**
    benutzen: HS256 ist HMAC-SHA256 ueber ``kopf.nutzlast``, und das sind drei
    Zeilen aus ``hmac`` und ``base64``. Eine Fremdbibliothek waere hier der
    teurere Weg, denn dieses Werkzeug soll auf jedem Wirt laufen, auf dem man
    gerade steht. Auf host fehlte ``python-jose`` beim ersten Lauf, und auf
    dem Jetson mit Python 3.6 waere sie erst zu beschaffen.

    ``separators`` und ``sort_keys`` sind nicht Kosmetik: die Signatur gilt
    fuer **genau diese Bytes**. Leerzeichen hinter den Doppelpunkten ergaeben
    ein anderes Token, das zwar gueltig ist, aber bei jedem Vergleich mit einer
    anders erzeugten Fassung abweicht.
    """
    kopf = {"alg": "HS256", "typ": "JWT"}
    teile = ".".join(
        _b64(json.dumps(t, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        for t in (kopf, nutzlast)
    )
    signatur = hmac.new(
        geheimnis.encode("utf-8"), teile.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{teile}.{_b64(signatur)}"


def bekannte_dienste() -> list[str]:
    """Dienste, die eine Zielgruppe fuehren, also ueberhaupt Token annehmen."""
    return [
        verz.name
        for verz in sorted(DIENSTE_VERZ.iterdir())
        if verz.is_dir() and zielgruppe_suchen(verz.name) is not None
    ]


def main() -> int:
    zerleger = argparse.ArgumentParser(
        description="Kurzlebiges Backend-Token fuer einen Saganta-Dienst. "
        "Gibt NUR das Token aus, nie das Geheimnis.",
    )
    zerleger.add_argument("dienst", nargs="?", help="z. B. projectdeck-api")
    zerleger.add_argument(
        "--minuten", type=int, default=15,
        help="Laufzeit in Minuten (Vorgabe 15). Kurz halten: das Token ist ein "
             "Zugangsmittel.",
    )
    zerleger.add_argument(
        "--sub", default=OWNER_SUB_VORGABE,
        help="Mandanten-Kennung, fuer die das Token gilt.",
    )
    zerleger.add_argument(
        "--dienste", action="store_true",
        help="Nur auflisten, welche Dienste Token annehmen.",
    )
    args = zerleger.parse_args()

    if args.dienste:
        for name in bekannte_dienste():
            hat_env = (DIENSTE_VERZ / name / ".env").exists()
            print(f"{name}\t{zielgruppe_lesen(name)}\t{'env da' if hat_env else 'KEINE .env'}")
        return 0

    if not args.dienst:
        zerleger.error("Dienst fehlt. Was geht, zeigt --dienste.")
    if args.minuten < 1 or args.minuten > 240:
        zerleger.error("--minuten muss zwischen 1 und 240 liegen.")

    jetzt = datetime.now(timezone.utc)
    nutzlast = {
        "iss": aussteller_lesen(),
        "aud": zielgruppe_lesen(args.dienst),
        "sub": args.sub,
        "iat": int(jetzt.timestamp()),
        "exp": int((jetzt + timedelta(minutes=args.minuten)).timestamp()),
    }
    token = hs256_token(nutzlast, geheimnis_lesen(args.dienst))

    # Nur das Token auf stdout, damit $(...) es direkt aufnehmen kann. Alles
    # Erklaerende geht nach stderr: sonst landet es im Authorization-Kopf.
    print(token)
    print(
        f"Token fuer {args.dienst} (aud={nutzlast['aud']}, sub={args.sub[:8]}…), "
        f"gueltig {args.minuten} min. Nicht in Dateien oder Protokolle kopieren.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
