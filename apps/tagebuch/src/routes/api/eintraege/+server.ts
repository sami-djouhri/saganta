/**
 * Eine Spanne auf einmal, fuer die Suche im Browser.
 *
 * Der Server sucht nicht und kann nicht suchen. Er reicht die Chiffrate eines
 * Zeitraums heraus, der Browser oeffnet sie und durchsucht sie dort. Das ist
 * der Preis der Verschluesselung und zugleich ihre Zusicherung.
 */
import { error, json } from '@sveltejs/kit';
import { ApiFehler, api, type EintragAus } from '$lib/tagebuch-api';
import type { RequestHandler } from './$types';

const DATUM = /^\d{4}-\d{2}-\d{2}$/;

export const GET: RequestHandler = async ({ locals, url, fetch }) => {
  if (!locals.user) error(401, 'Nicht angemeldet');
  const von = url.searchParams.get('von') ?? '';
  const bis = url.searchParams.get('bis') ?? '';
  if (!DATUM.test(von) || !DATUM.test(bis)) error(400, 'von und bis muessen Datumsangaben sein');

  try {
    const eintraege = await api<EintragAus[]>(
      locals.user,
      `/api/eintraege?von=${von}&bis=${bis}`,
      fetch,
    );
    return json(eintraege);
  } catch (e) {
    if (e instanceof ApiFehler) error(e.status >= 500 ? 502 : e.status, e.detail);
    throw e;
  }
};
