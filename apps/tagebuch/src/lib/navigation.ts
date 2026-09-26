/**
 * Die Regeln, nach denen im Tagebuch geblaettert wird.
 *
 * Herausgezogen aus `+page.svelte`, damit sie pruefbar sind. Der Anlass ist ein
 * Fehler, der sich genau daran gezeigt hat, dass dieselbe Regel an **zwei**
 * Stellen stand und nur an einer stimmte: die Pfeil-Navigation sperrte die
 * Zukunft, die Jahresleiste verlinkte jeden Tag des Jahres. Wer dort in die
 * Zukunft klickte, fand den Vorwaerts-Knopf ausgegraut vor, ohne zu wissen,
 * warum. Eine Regel, ein Ort.
 */
import { verschieben } from './datum';

/** Darf man von hier aus vorwaerts? Heute ist der letzte Tag. */
export function vorwaertsMoeglich(tag: string, heute: string): boolean {
  return tag < heute;
}

/** Ist dieser Tag noch nicht gewesen? Dann gibt es dort nichts zu erinnern. */
export function istKuenftig(tag: string, heute: string): boolean {
  return tag > heute;
}

/**
 * Das Ziel eines Sprungs, gedeckelt auf heute.
 *
 * ★ Der Deckel ist noetig, weil ein Sprung ueber mehrere Tage sonst ueber das
 * Ziel hinausschiessen kann: eine Woche vorwaerts von vorgestern landete in
 * fuenf Tagen Zukunft, obwohl jeder einzelne Tagesschritt dorthin gesperrt
 * gewesen waere.
 */
export function sprungZiel(tag: string, tage: number, heute: string): string {
  const ziel = verschieben(tag, tage);
  return ziel > heute ? heute : ziel;
}
