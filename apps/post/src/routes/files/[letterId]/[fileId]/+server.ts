import { error } from '@sveltejs/kit';
import { fetchLetterFile } from '$lib/post-api';
import { canAccessLetters } from '$lib/server/gate';
import type { RequestHandler } from './$types';

// Brief-Anhänge als Proxy: briefkasten ist nur intern (cc-core) erreichbar,
// der Browser bekommt die Datei über den authentifizierten BFF.
export const GET: RequestHandler = async ({ locals, params, request, fetch }) => {
  if (!locals.user) throw error(401, 'not authenticated');
  // Kritisch: Brief-Dateien sind single-tenant → Nicht-Owner dürfen sie NICHT per
  // ID abrufen (sonst Leak der Owner-Briefe). 404 statt 403 = keine Existenz-Preisgabe.
  if (!canAccessLetters(locals.user)) throw error(404, 'not found');
  const letterId = Number(params.letterId);
  const fileId = Number(params.fileId);
  if (!Number.isInteger(letterId) || !Number.isInteger(fileId)) throw error(400, 'bad id');
  const range = request.headers.get('range') ?? undefined;
  const upstream = await fetchLetterFile(fetch, letterId, fileId, range).catch(() => null);
  if (!upstream) throw error(502, 'briefkasten nicht erreichbar');

  // Content-Length/Accept-Ranges/Content-Range weiterreichen, damit der Browser
  // Fortschritt anzeigt und Range/Seek (206) funktioniert.
  const headers = new Headers({
    'Content-Type': upstream.headers.get('content-type') ?? 'application/octet-stream',
    'Content-Disposition': upstream.headers.get('content-disposition') ?? 'inline',
    'Cache-Control': 'private, max-age=300',
  });
  for (const h of ['content-length', 'accept-ranges', 'content-range']) {
    const v = upstream.headers.get(h);
    if (v) headers.set(h, v);
  }
  return new Response(upstream.body, { status: upstream.status, headers });
};
