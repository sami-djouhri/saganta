import { env } from '$env/dynamic/private';
import { error, json } from '@sveltejs/kit';
import { backendSecret, kalenderBffFetch, kalenderBffToken } from '$lib/kalender-bff';
import type { RequestHandler } from './$types';

/**
 * Fruehere Titel bzw. Orte beim Tippen im Termin-Editor (seit 2026-11-21).
 * Faellt der Kalender aus, gibt es leere Listen: ein fehlender Vorschlag darf
 * das Anlegen nicht stoeren.
 */
export const GET: RequestHandler = async ({ locals, fetch, url }) => {
  if (!locals.user || !env.KALENDER_BFF_BASE_URL) error(401, 'nicht angemeldet');
  const art = url.searchParams.get('art') === 'ort' ? 'ort' : 'titel';
  const q = (url.searchParams.get('q') ?? '').trim().slice(0, 100);
  const token = kalenderBffToken(locals.user, backendSecret());
  const params = new URLSearchParams({ art, q, limit: '8' });
  try {
    return json(await kalenderBffFetch(env.KALENDER_BFF_BASE_URL, `/api/events/vorschlaege?${params}`, token, fetch));
  } catch {
    return json(art === 'ort' ? { orte: [] } : { titel: [] });
  }
};
