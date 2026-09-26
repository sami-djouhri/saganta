/**
 * Cross-App-Deep-Links: der EINE Ort, an dem App-übergreifende Intents als URL
 * gebaut werden. So bleibt die Verknüpfung zwischen Apps typsicher und zentral
 * pflegbar (ändert sich eine Ziel-Route, nur hier anfassen).
 *
 * ★ Jede Funktion nimmt den Host der laufenden Anfrage entgegen. Ohne ihn
 * entsteht ein Link in den öffentlichen Raum, und das ist aus dem Heimnetz
 * heraus ein Sprung durch den Tunnel in einen anderen Cookie-Raum. Siehe die
 * Begründung in `apps.ts`.
 */
import { appUrlById } from './apps';

/**
 * Universeller Kalender-Intent: schickt einen Freitext (und optional ein
 * Zieldatum) an den Kalender-Quick-Capture, der ihn beim Laden vorbefüllt.
 * Beispiel: kalenderCaptureUrl('Vertrag Fitnessstudio kündigen', '2026-09-30').
 */
export function kalenderCaptureUrl(text: string, isoDate?: string, host?: string | null): string {
  const params = new URLSearchParams({ capture: text });
  if (isoDate) params.set('date', isoDate);
  return `${appUrlById('calendar', host)}/?${params.toString()}`;
}

/** Eine einzelne Aufgabe in der Aufgaben-App. */
export function aufgabeUrl(id: string, host?: string | null): string {
  return `${appUrlById('aufgaben', host)}/?aufgabe=${encodeURIComponent(id)}`;
}

/** Ein Projekt in ProjectDeck. `slug` ist dessen Adress-Merkmal. */
export function projektUrl(slug: string, host?: string | null): string {
  return `${appUrlById('projectdeck', host)}/projekte/${encodeURIComponent(slug)}`;
}

/** Eine Notiz in der Notizen-App. */
export function notizUrl(id: string | number, host?: string | null): string {
  return `${appUrlById('notizen', host)}/notiz/${encodeURIComponent(String(id))}`;
}
