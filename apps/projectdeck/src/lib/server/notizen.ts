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
 * ⚠️ **Projektaufgaben haengen hier bewusst NICHT dran** (Stand 2026-10-24).
 * Gemessen: die Aufgaben der Kalender-Engine tragen UUIDs (`VARCHAR(36)`), die
 * `project_tasks` des ProjectDecks fortlaufende Zahlen (1, 2, 3). Beide wuerden
 * unter demselben Verknuepfungstyp `aufgabe` liegen, also in einem Namensraum,
 * in dem sie heute nur deshalb nicht kollidieren, weil eine UUID nie „7" ist.
 * Das ist Zufall und kein Entwurf: stellte eine der beiden Seiten je ihre
 * Kennungen um, vermischten sich zwei Bestaende still. Ein Knopf an der
 * Projektaufgabe braucht daher zuerst einen eigenen Typ (`projektaufgabe`),
 * und das ist eine Datenmodell-Entscheidung und keine Zeile Oberflaeche.
 */
import { env } from '$env/dynamic/private';
import { anschlussAus, type Anschluss } from '@saganta/notizen-anschluss';

export { type NotizKurz } from '@saganta/notizen-anschluss';

export function notizAnschluss(locals: App.Locals, fetcher: typeof fetch): Anschluss | null {
  return anschlussAus(env, locals.user, fetcher);
}
