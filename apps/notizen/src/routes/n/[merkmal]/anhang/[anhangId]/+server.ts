import { error } from '@sveltejs/kit';
import { apiBase } from '$lib/notizen-api';
import type { RequestHandler } from './$types';

/**
 * Anhang einer geöffneten Freigabe durchreichen.
 *
 * Der Zugriffsschein aus dem Öffnen-Schritt wird unverändert weitergegeben:
 * ohne ihn weist das Backend ab. Der BFF prüft ihn bewusst nicht selbst: zwei
 * Stellen, die dieselbe Regel kennen, laufen früher oder später auseinander.
 */
export const GET: RequestHandler = async ({ params, url, fetch }) => {
  const schein = url.searchParams.get('schein') ?? '';
  const ziel =
    `${apiBase()}/oeffentlich/${encodeURIComponent(params.merkmal)}` +
    `/anhang/${encodeURIComponent(params.anhangId)}?schein=${encodeURIComponent(schein)}`;

  const antwort = await fetch(ziel);
  if (!antwort.ok) {
    error(antwort.status === 401 ? 401 : 404, 'Anhang nicht abrufbar');
  }

  const kopf = new Headers();
  for (const feld of [
    'content-type',
    'content-length',
    'content-disposition',
    'x-content-type-options',
    'content-security-policy',
  ]) {
    const wert = antwort.headers.get(feld);
    if (wert) kopf.set(feld, wert);
  }
  kopf.set('Cache-Control', 'no-store, private');
  return new Response(antwort.body, { status: 200, headers: kopf });
};
