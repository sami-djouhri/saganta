import { error } from '@sveltejs/kit';
import { apiRoh } from '$lib/notizen-api';
import type { RequestHandler } from './$types';

/**
 * Anhang durchreichen.
 *
 * Das Backend ist nur im internen Netz erreichbar, der Browser kommt nicht
 * direkt hin. Die Kopfzeilen des Backends (Content-Disposition, nosniff,
 * Content-Security-Policy) werden dabei **übernommen und nicht neu erfunden**:
 * sie sind der Grund, warum ein Anhang beim Empfänger nicht als Seite im
 * eigenen Ursprung landet.
 */
export const GET: RequestHandler = async ({ locals, params, fetch }) => {
  const user = locals.user;
  if (!user) error(401, 'Nicht angemeldet');

  const antwort = await apiRoh(
    user,
    `/api/notizen/${params.id}/anhaenge/${params.anhangId}`,
    fetch,
  );
  if (!antwort.ok) error(antwort.status === 404 ? 404 : 502, 'Anhang nicht abrufbar');

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
  kopf.set('Cache-Control', 'private, max-age=300');
  return new Response(antwort.body, { status: 200, headers: kopf });
};
