import { env } from '$env/dynamic/public';

export const APP_ID = 'notizen';
export const APP_NAME = 'Notizen';

export const NAV = [
  { href: '/', label: 'Alle Notizen', icon: 'pen' },
  { href: '/freigaben', label: 'Geteilte Links', icon: 'globe' },
] as const;

/** Was von einem konfigurierten Kurz-Namen zu halten ist. */
export type KurzBasisBefund =
  | { brauchbar: true; basis: string }
  | { brauchbar: false; roh: string; grund: string };

/**
 * Prueft die Form des konfigurierten Kurz-Namens.
 *
 * Bewusst **ohne Netz**, und das ist keine Sparsamkeit: ob ein Name aufloest,
 * kann an dieser Stelle niemand beantworten. Der Server sieht eine andere
 * Namenswelt als der Browser des Nutzers (gemessen 2026-10-24 in diesem
 * Container: ``notizen.home.arpa`` ist hier ENOTFOUND und im Browser der
 * normale Weg, ``shell.home.arpa`` loest auf eine Container-Adresse im
 * cc-Netz auf und damit auf etwas anderes als draussen). Eine Namensaufloesung
 * hier wuerde also einen funktionierenden Namen verwerfen und einen
 * container-internen durchlassen: die falsche Schicht gemessen.
 *
 * Geprueft wird deshalb nur, was ohne Netz entscheidbar ist, und das faengt die
 * Tippfehler: fehlendes Schema, ein Name mit Abfrage- oder Fragmentteil, ein
 * anderes Protokoll als http(s). Die Erreichbarkeit prueft der Browser im
 * Moment des Teilens (``TeilenDialog``), und der Bestand der Konfiguration
 * steht in ``scripts/tunnel-probe.py``.
 *
 * Rueckgabe ``null`` heisst: nichts konfiguriert, der Normalfall.
 */
export function kurzBasisPruefen(roh: string | undefined | null): KurzBasisBefund | null {
  const wert = (roh ?? '').trim();
  if (!wert) return null;

  let zerlegt: URL;
  try {
    zerlegt = new URL(wert);
  } catch {
    return {
      brauchbar: false,
      roh: wert,
      grund: 'keine vollstaendige Adresse (Schema fehlt, z. B. https://n.example.org)',
    };
  }
  if (zerlegt.protocol !== 'https:' && zerlegt.protocol !== 'http:') {
    return { brauchbar: false, roh: wert, grund: `Protokoll ${zerlegt.protocol} ist keine Webadresse` };
  }
  if (zerlegt.search || zerlegt.hash) {
    // Ein Fragment waere hier besonders heikel: an diese Adresse haengt die App
    // bei verschluesselten Freigaben den Schluessel als Fragment an, und zwei
    // davon in einer Adresse ergeben einen Link, der den Schluessel verliert.
    return { brauchbar: false, roh: wert, grund: 'Abfrage- oder Fragmentteil gehoert nicht in die Basis' };
  }

  return { brauchbar: true, basis: wert.replace(/\/$/, '') };
}

/**
 * Basis der Kurz-Adressen fuer geteilte Notizen.
 *
 * Wer eine eigene Kurz-Domaene betreibt, traegt sie vollstaendig in
 * PUBLIC_NOTIZEN_KURZ_BASIS ein (z. B. `https://n.example.org`) und richtet
 * dafuer einen Vhost auf diese App ein. Ohne Eintrag bleibt der Link auf dem
 * eigenen Ursprung und zeigt auf `/n`, eine Route, die diese App selbst
 * bedient: kurz ist schoener, funktionieren muss es ueberall.
 *
 * Hier stand bis zum 2026-09-12 `host.endsWith('.saganta.de')` fest im
 * Quelltext, mit `https://n.saganta.de` als Ergebnis. Das ist derselbe Fehler,
 * den catalog.ts am 2026-09-06 fuer 17 Stellen abgelegt hat: eine fremde
 * Instanz als Vorbelegung. In jeder anderen Installation traf die Bedingung
 * nie zu, deshalb fiel es nicht auf. Getroffen haette es genau den einen
 * Betreiber, dessen Domaene so endet, und dem haette die App Links auf eine
 * Instanz ausgegeben, die ihm nicht gehoert.
 *
 * Bis zum 2026-10-24 genuegte hier ein nichtleerer Wert. Geprueft wurde also
 * das Vorhandensein und nicht die Brauchbarkeit, und die vier Tests daneben
 * pruefen genau diese Vorhandenseinspruefung, waren gruen und blieben es,
 * waehrend auf dieser Installation `https://n.saganta.de` stand, ein Name, der
 * nirgends aufloest (NXDOMAIN gegen 1.1.1.1 und gegen den AdGuard im Heimnetz).
 * Jeder ausgegebene Freigabe-Link zeigte damit ins Leere.
 */
export function freigabeBasis(origin: string): string {
  const befund = kurzBasisPruefen(env.PUBLIC_NOTIZEN_KURZ_BASIS);
  if (befund?.brauchbar) return befund.basis;
  return `${origin.replace(/\/$/, '')}/n`;
}

/**
 * Der Rueckweg, der immer traegt: der Ursprung, ueber den der Nutzer gerade da
 * ist. Er muss nicht geprueft werden, denn waere er nicht erreichbar, haette
 * der Nutzer diese Seite nicht vor sich.
 */
export function eigeneBasis(origin: string): string {
  return `${origin.replace(/\/$/, '')}/n`;
}
