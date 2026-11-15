/**
 * Der Notizen-Anschluss des ProjectDecks.
 *
 * Die Mechanik liegt in `@saganta/notizen-anschluss`, hier steht nur, was dort
 * nicht stehen kann: `$env/dynamic/private` gibt es nur in einer SvelteKit-App.
 *
 * **Verknuepft wird ueber den Slug, nicht ueber die Zeilennummer.** Das ist
 * keine Geschmacksfrage: `apps/notizen/src/lib/quellen.ts` loest Projekte seit
 * dem Bau der Verknuepfungen mit `slug` auf. Wer hier die `id` nimmt, baut eine
 * Verknuepfung, die in der Notizen-App nie wieder gefunden wird, und zwar ohne
 * Fehlermeldung: die Notiz zeigt ihre Beschriftung weiter an (die ist eine
 * Kopie), nur die Gegenrichtung ist leer. Der Slug ist ausserdem der stabilere
 * der beiden Werte, er ueberlebt eine Umbenennung des Projekts.
 *
 * **Projektaufgaben brauchen hier keinen Anschluss** (Stand 2026-11-14). Seit
 * dem Umzug am 2026-11-05 liegen sie im Aufgaben-Dienst (UUID, Feld `projekt`)
 * und oeffnen sich in Saganta Aufgaben; deren Dialog traegt „Notiz dazu" mit
 * dem Typ `aufgabe`. Die Sorge vom 24.10. (Zahlen-IDs der `project_tasks` und
 * UUIDs der Kalender-Todos im selben Typ) ist damit gegenstandslos: beide
 * Bestaende gibt es nicht mehr, und ein eigener Typ `projektaufgabe` waere
 * schaedlich, weil eine Aufgabe, die ihr Projekt verliert, sonst ihren Typ
 * wechseln muesste.
 */
import { env } from '$env/dynamic/private';
import { anschlussAus, type Anschluss } from '@saganta/notizen-anschluss';

export { type NotizKurz } from '@saganta/notizen-anschluss';

export function notizAnschluss(locals: App.Locals, fetcher: typeof fetch): Anschluss | null {
  return anschlussAus(env, locals.user, fetcher);
}
