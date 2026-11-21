import { json } from '@sveltejs/kit';
import { ApiFehler, api } from '$lib/notizen-api';
import type { RequestHandler } from './$types';

/** Notiztitel für die Vorschläge beim Tippen von `[[` im Editor. */
export const GET: RequestHandler = async ({ locals, url, fetch }) => {
  const user = locals.user;
  if (!user) return json({ fehler: 'Nicht angemeldet' }, { status: 401 });
  const frage = new URLSearchParams({ q: url.searchParams.get('q') ?? '', limit: '8' });
  const ohne = Number(url.searchParams.get('ohne')) || 0;
  if (ohne) frage.set('ohne', String(ohne));
  try {
    return json(await api<{ id: number; titel: string; archiviert: boolean }[]>(user, `/api/notizen/titel?${frage}`, fetch));
  } catch (e) {
    if (e instanceof ApiFehler) return json({ fehler: e.detail }, { status: 502 });
    throw e;
  }
};
