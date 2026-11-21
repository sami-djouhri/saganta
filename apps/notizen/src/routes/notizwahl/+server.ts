import { json } from '@sveltejs/kit';
import { ApiFehler, api } from '$lib/notizen-api';
import type { NotizKurz } from '$lib/types';
import type { RequestHandler } from './$types';

/**
 * Eigene Notizen zum Verbinden: mit `q` die Volltextsuche, ohne die zuletzt
 * geänderten. `ohne` nimmt die angesehene Notiz aus der Liste.
 */
export const GET: RequestHandler = async ({ locals, url, fetch }) => {
  const user = locals.user;
  if (!user) return json({ fehler: 'Nicht angemeldet' }, { status: 401 });
  const q = url.searchParams.get('q')?.trim() ?? '';
  const ohne = Number(url.searchParams.get('ohne')) || 0;
  const frage = new URLSearchParams({ limit: '30', archivierte: 'true' });
  if (q) frage.set('q', q);
  try {
    const liste = await api<NotizKurz[]>(user, `/api/notizen?${frage}`, fetch);
    return json(
      liste
        .filter((n) => n.id !== ohne)
        .map((n) => ({ id: n.id, titel: n.titel, ausschnitt: n.ausschnitt, archiviert: n.archiviert })),
    );
  } catch (e) {
    if (e instanceof ApiFehler) return json({ fehler: e.detail }, { status: 502 });
    throw e;
  }
};
