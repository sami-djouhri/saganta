import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import { backendSecret, kalenderBffFetch, kalenderBffToken } from '$lib/kalender-bff';
import type { RequestHandler } from './$types';

/**
 * Datenexport als JSON-Download (Recht auf Datenuebertragbarkeit). Die App hat
 * den Knopf seit laengerem, im Web fehlte er; der Dienst liefert
 * `/api/account/export` fuer den angemeldeten Nutzer.
 */
export const GET: RequestHandler = async ({ locals, fetch }) => {
  if (!locals.user || !env.KALENDER_BFF_BASE_URL) error(401, 'nicht angemeldet');
  const token = kalenderBffToken(locals.user, backendSecret());
  const daten = await kalenderBffFetch<unknown>(env.KALENDER_BFF_BASE_URL, '/api/account/export', token, fetch);
  const tag = new Date().toISOString().slice(0, 10);
  return new Response(JSON.stringify(daten, null, 2), {
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Content-Disposition': `attachment; filename="saganta-kalender-export-${tag}.json"`,
      'Cache-Control': 'no-store',
    },
  });
};
