/**
 * Der Notizen-Anschluss dieser App.
 *
 * Hier stand bis zum 2026-10-24 die ganze Mechanik: Token stempeln, Aufrufe
 * bauen, Fehler verschlucken, Label kuerzen. Sie ist nach
 * `@saganta/notizen-anschluss` gewandert, weil ab jetzt **drei** Apps denselben
 * Weg brauchen (Kalender, Aufgaben, ProjectDeck) und drei Kopien genau an den
 * Stellen auseinanderlaufen, die man nicht sieht: eine kuerzt das Label anders,
 * eine schickt zwei Aufrufe statt einem, eine meldet einen Ausfall als leeren
 * Bestand.
 *
 * Was hier bleibt, ist der Teil, der **nicht** wandern kann: `$env/dynamic/private`
 * gibt es nur in einer SvelteKit-App. Eine Zeile Konfiguration je App statt
 * einer Kopie der Logik je App.
 */
import { env } from '$env/dynamic/private';
import { anschlussAus, type Anschluss } from '@saganta/notizen-anschluss';

export { type NotizKurz } from '@saganta/notizen-anschluss';

/**
 * Der Anschluss fuer diese Anfrage, oder `null`, wenn er nicht konfiguriert
 * ist. `null` ist kein Fehler: die Oberflaeche zeigt den Knopf dann nicht.
 */
export function notizAnschluss(locals: App.Locals, fetcher: typeof fetch): Anschluss | null {
  return anschlussAus(env, locals.user, fetcher);
}
