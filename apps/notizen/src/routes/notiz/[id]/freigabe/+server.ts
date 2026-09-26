import { json } from '@sveltejs/kit';
import { ApiFehler, api } from '$lib/notizen-api';
import type { Freigabe } from '$lib/types';
import type { RequestHandler } from './$types';

/**
 * Freigabe anlegen: als eigener Endpunkt statt als Formular-Aktion.
 *
 * Grund: bei der verschlüsselten Variante entsteht das Chiffrat im Browser.
 * Ein normales Formular würde den Klartext mitschicken; hier schickt die Seite
 * nur das Ergebnis der Verschlüsselung. Der Klartext verlässt den Browser in
 * diesem Fall überhaupt nicht.
 */
export const POST: RequestHandler = async ({ locals, params, request, fetch }) => {
  const user = locals.user;
  if (!user) return json({ fehler: 'Nicht angemeldet' }, { status: 401 });

  const wunsch = (await request.json()) as Record<string, unknown>;
  try {
    const freigabe = await api<Freigabe>(user, `/api/freigaben/notizen/${params.id}`, fetch, {
      method: 'POST',
      body: JSON.stringify(wunsch),
    });
    return json(freigabe, { status: 201 });
  } catch (e) {
    if (e instanceof ApiFehler) return json({ fehler: e.detail }, { status: e.status });
    throw e;
  }
};
