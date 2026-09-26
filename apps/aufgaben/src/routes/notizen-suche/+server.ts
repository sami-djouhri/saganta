import { json } from '@sveltejs/kit';
import { backendSecret } from '$lib/aufgaben-bff';
import { notizenSuchen } from '$lib/server/notizen';
import type { RequestHandler } from './$types';

/**
 * Notiz-Suche fuer den Anhaengen-Dialog.
 *
 * Laeuft ueber den eigenen Server, nicht direkt aus dem Browser zur notizen-api:
 * das Backend-Token wird hier gestempelt und darf den Server nie verlassen.
 */
export const GET: RequestHandler = async ({ locals, url, fetch }) => {
  if (!locals.user) return json({ treffer: [] }, { status: 401 });
  const suche = (url.searchParams.get('q') ?? '').slice(0, 200);
  const treffer = await notizenSuchen(suche, locals.user, backendSecret(), fetch);
  return json({ treffer });
};
