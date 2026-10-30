import { json } from '@sveltejs/kit';
import { ApiFehler, oeffentlich } from '$lib/notizen-api';
import type { OeffentlicherInhalt } from '$lib/types';
import type { RequestHandler } from './$types';

/**
 * Der ausdrückliche Schritt: hier wird der Abruf gezählt und der Inhalt
 * herausgegeben. Ein `POST`, weil nichts, was automatisch Links besucht, ein
 * POST schickt: genau das trennt einen echten Leser von einer Vorschau.
 *
 * Die Weitergabe der Client-Adresse ist wichtig: das Backend bremst nach
 * Quelle, und ohne den weitergereichten Wert sähe es nur diesen Container und
 * würde alle Besucher in einen Topf werfen.
 */
export const POST: RequestHandler = async ({ params, request, fetch, getClientAddress }) => {
  let passwort: string | null = null;
  try {
    const koerper = (await request.json()) as { passwort?: unknown };
    if (typeof koerper.passwort === 'string') passwort = koerper.passwort;
  } catch {
    /* ohne Rumpf = ohne Passwort */
  }

  try {
    const inhalt = await oeffentlich<OeffentlicherInhalt>(`/${params.merkmal}/oeffnen`, fetch, {
      method: 'POST',
      body: JSON.stringify({ passwort }),
      headers: {
        'X-Forwarded-For':
          request.headers.get('x-forwarded-for') ?? getClientAddress(),
      },
    });
    return json(inhalt, { headers: { 'Cache-Control': 'no-store, private' } });
  } catch (e) {
    if (e instanceof ApiFehler) return json({ fehler: e.detail }, { status: e.status });
    throw e;
  }
};
