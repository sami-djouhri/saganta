import { env } from '$env/dynamic/private';
import { error, json } from '@sveltejs/kit';
import { backendSecret, kalenderBffFetch, kalenderBffToken } from '$lib/kalender-bff';
import type { RequestHandler } from './$types';

/** Adressvorschläge beim Tippen. Der Browser erreicht den BFF nicht selbst. */
export const GET: RequestHandler = async ({ locals, fetch, url }) => {
  if (!locals.user || !env.KALENDER_BFF_BASE_URL) error(401, 'nicht angemeldet');
  const q = (url.searchParams.get('q') ?? '').trim().slice(0, 200);
  if (q.length < 3) return json({ treffer: [] });
  const token = kalenderBffToken(locals.user, backendSecret());
  try {
    return json(
      await kalenderBffFetch(env.KALENDER_BFF_BASE_URL, `/api/places/adressen/suche?q=${encodeURIComponent(q)}`, token, fetch),
    );
  } catch {
    return json({ treffer: [], fehler: true });
  }
};
