/**
 * Beschriftungen und Zieladressen der Verknüpfungstypen.
 *
 * Bewusst getrennt von `quellen.ts`: das dortige Suchen liest Zugangsdaten über
 * `$env/dynamic/private` und darf deshalb nie im Browser landen. Diese Datei
 * enthält nur Beschriftungen und Adressbildung; ein gemeinsames Modul hätte die
 * Server-Geheimnisse in das Browser-Bündel gezogen. (SvelteKit bricht den Build
 * dann ab; genau dieser Riegel hat die Trennung hier erzwungen.)
 */

import { appUrlById } from '@saganta/ui';
import type { VerknuepfungsTyp } from './types';

export const TYP_BESCHRIFTUNG: Record<VerknuepfungsTyp, string> = {
  termin: 'Termin',
  aufgabe: 'Aufgabe',
  ziel: 'Ziel',
  projekt: 'Projekt',
  kontakt: 'Kontakt',
  brief: 'Brief',
};

// Nur Namen aus der Icon-Registry in `@saganta/ui`. Ein unbekannter Name fällt
// dort nicht auf ein Ersatzsymbol zurück, sondern schreibt sich selbst als Text
// in die Seite, und das sieht aus wie ein Anzeigefehler.
export const TYP_SYMBOL: Record<VerknuepfungsTyp, string> = {
  termin: 'calendar',
  aufgabe: 'square-check',
  ziel: 'target',
  projekt: 'layout-dashboard',
  kontakt: 'users',
  brief: 'inbox',
};

/**
 * Adresse, unter der ein verknüpftes Gegenstück in seiner App liegt.
 *
 * ★★ **Zwei der sechs Adressen zeigten ins Leere**, von Anfang an und ohne dass
 * es je einen Fehler gab (Stand vor 2026-09-13):
 *
 *  - `aufgabe` und `ziel` gingen auf `kalender.saganta.de/aufgaben`. Diese Route
 *    hat es in der Kalender-App **nie gegeben**; sie hat genau eine Seite. Der
 *    Klick landete auf der Kalender-Startseite, was wie ein verlorener Bezug
 *    aussieht, aber ein falscher Link war.
 *  - `projekt` ging auf `projectdeck.saganta.de`, einen Hostnamen **ohne
 *    DNS-Eintrag und ohne Tunnel-Regel**. Der Browser kam nicht einmal an.
 *  - `kontakt` ging auf `kalender.saganta.de/kontakte`, ebenfalls ohne Route.
 *
 * Dazu standen alle sechs fest auf `.de`, also führten sie aus dem Heimnetz
 * heraus durch den Tunnel in einen anderen Cookie-Raum.
 *
 * Jetzt entstehen sie über den geteilten Katalog im Raum des Aufrufers, und die
 * Ziele gibt es: Aufgaben und Ziele in der neuen Aufgaben-App, Kontakte im
 * Kalender (dort existiert die Route). `host` ist der Host der laufenden
 * Anfrage, nicht der des Ziels.
 */
export function zielAdresse(
  typ: VerknuepfungsTyp,
  ref: string,
  host?: string | null,
): string | null {
  switch (typ) {
    case 'termin':
      return `${appUrlById('calendar', host)}/?termin=${encodeURIComponent(ref)}`;
    case 'aufgabe':
      return `${appUrlById('aufgaben', host)}/?aufgabe=${encodeURIComponent(ref)}`;
    case 'ziel':
      // Ziele haben keine Einzelseite: sie gelten fuer einen Tag und stehen auf
      // der Tagesansicht. Dorthin zu zeigen ist richtiger, als eine Adresse zu
      // erfinden, die es nicht gibt.
      return `${appUrlById('aufgaben', host)}/`;
    case 'projekt':
      return `${appUrlById('projectdeck', host)}/projekte/${encodeURIComponent(ref)}`;
    case 'kontakt':
      // ★ **Bewusst kein Link.** Der BFF kann Kontakte (`routes_contacts.py`),
      // aber es gibt in Saganta keine Oberflaeche dafuer: die Kalender-App hat
      // genau eine Seite. Eine Adresse zu bilden, hinter der nichts steht, ist
      // schlechter als gar keine: der unverlinkte Eintrag zeigt weiterhin, worauf
      // sich die Notiz bezieht, und behauptet nicht, man koenne dorthin.
      // (Dasselbe Muster wie 2026-09-12, „Adressen ohne Ziel sind leer, nicht
      // erfunden".) Sobald es eine Kontaktseite gibt, gehoert sie hierher.
      return null;
    case 'brief':
      return `${appUrlById('post', host)}/?brief=${encodeURIComponent(ref)}`;
    default:
      return null;
  }
}
