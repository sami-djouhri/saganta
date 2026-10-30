import { error } from '@sveltejs/kit';
import { ApiFehler, oeffentlich } from '$lib/notizen-api';
import type { OeffentlicherZustand } from '$lib/types';
import type { PageServerLoad } from './$types';

/**
 * Nur der Zustand, nicht der Inhalt.
 *
 * Diese Seite wird von allem abgerufen, was einen Link zu Gesicht bekommt:
 * Messenger-Vorschauen, Sicherheitsscanner in Mail-Systemen, der Verlauf des
 * Browsers. Deshalb steht hier nichts, was vertraulich wäre, und deshalb zählt
 * ein Aufruf hier auch nicht gegen ein „nur einmal lesbar".
 */
export const load: PageServerLoad = async ({ params, fetch, setHeaders }) => {
  setHeaders({
    'Cache-Control': 'no-store, private',
    // Keine Vorschaubilder, keine Aufnahme in Suchmaschinen.
    'X-Robots-Tag': 'noindex, nofollow, noarchive',
  });

  try {
    const zustand = await oeffentlich<OeffentlicherZustand>(`/${params.merkmal}`, fetch);
    return { merkmal: params.merkmal, zustand };
  } catch (e) {
    if (e instanceof ApiFehler) {
      if (e.status === 404) error(404, 'Diesen Link gibt es nicht.');
      if (e.status === 429) error(429, 'Zu viele Anfragen. Bitte kurz warten.');
      error(502, 'Der Dienst antwortet gerade nicht.');
    }
    throw e;
  }
};
