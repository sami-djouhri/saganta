/**
 * Der Notizen-Anschluss des Kalenders.
 *
 * Die Mechanik liegt in `@saganta/notizen-anschluss`, hier steht nur, was dort
 * nicht stehen kann: `$env/dynamic/private` gibt es nur in einer SvelteKit-App.
 */
import { env } from '$env/dynamic/private';
import { anschlussAus, type Anschluss } from '@saganta/notizen-anschluss';
import type { KalenderEvent } from '$lib/kalender-bff';

export { type NotizKurz } from '@saganta/notizen-anschluss';

export function notizAnschluss(locals: App.Locals, fetcher: typeof fetch): Anschluss | null {
  return anschlussAus(env, locals.user, fetcher);
}

/**
 * Die Kennung, unter der eine Notiz an einem Termin hängt.
 *
 * **Das ist eine Entscheidung und keine Formalie, denn Serientermine haben
 * zwei Kennungen.** Eine virtuelle Instanz trägt `id` der Form
 * `reihe::JJJJ-MM-TT`, dazu `series_id` für die ganze Reihe. Die Notiz kann an
 * einem von beiden hängen, und beides ist vertretbar:
 *
 * - an der **Instanz**: „Fragen für das Gespräch am Dienstag" gehört an diesen
 *   einen Termin. Beim nächsten Vorkommen ist die Notiz nicht da, was richtig
 *   ist, weil es ein anderes Gespräch ist.
 * - an der **Reihe**: „Zugangsdaten für das Team-Meeting" gilt jedes Mal.
 *
 * Gewählt ist die **Instanz**, also schlicht die `id` des Termins, den man
 * gerade ansieht. Begründung: man notiert zu dem, was vor einem liegt, und wer
 * eine Notiz an der ganzen Reihe sucht, würde sie beim Blättern durch die Woche
 * an jedem Vorkommen wiederfinden, auch an längst vergangenen. Eine Notiz, die
 * überall auftaucht, ist schwerer wieder loszuwerden als eine, die man ein
 * zweites Mal anlegt.
 *
 * ⚠️ Wer das ändert, ändert es **hier und nur hier**. Die Kennung steckt in
 * jeder gespeicherten Verknüpfung; ein Wechsel macht die vorhandenen nicht
 * falsch, aber unsichtbar, und zwar ohne Fehlermeldung. Dann braucht es einen
 * Umzugsschritt und nicht nur eine neue Zeile.
 */
export function terminKennung(termin: KalenderEvent): string {
  return termin.id;
}
