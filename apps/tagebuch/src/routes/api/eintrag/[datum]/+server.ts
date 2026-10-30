/**
 * Ein Tag: holen, speichern, loeschen.
 *
 * Was hier durchlaeuft, ist Chiffrat. Dieser Server liest es nicht und kann es
 * nicht lesen.
 */
import { error, json } from '@sveltejs/kit';
import { ApiFehler, api, type EintragAus } from '$lib/tagebuch-api';
import type { RequestHandler } from './$types';

const DATUM = /^\d{4}-\d{2}-\d{2}$/;

function fehlerWeiter(e: unknown): never {
  if (e instanceof ApiFehler) error(e.status >= 500 ? 502 : e.status, e.detail);
  throw e;
}

export const GET: RequestHandler = async ({ locals, params, fetch }) => {
  if (!locals.user) error(401, 'Nicht angemeldet');
  if (!DATUM.test(params.datum)) error(400, 'Kein gueltiges Datum');
  try {
    return json(await api<EintragAus>(locals.user, `/api/eintraege/${params.datum}`, fetch));
  } catch (e) {
    fehlerWeiter(e);
  }
};

export const PUT: RequestHandler = async ({ locals, params, request, fetch }) => {
  if (!locals.user) error(401, 'Nicht angemeldet');
  if (!DATUM.test(params.datum)) error(400, 'Kein gueltiges Datum');
  const daten = (await request.json()) as { chiffrat?: unknown; iv?: unknown };
  // Nur die drei Felder weiterreichen, die der Vertrag kennt. Ein
  // durchgereichtes Objekt waere der Weg, auf dem irgendwann doch ein
  // Klartextfeld mitwandert, ohne dass es jemandem auffaellt.
  if (typeof daten.chiffrat !== 'string' || typeof daten.iv !== 'string') {
    error(400, 'chiffrat und iv fehlen');
  }
  try {
    return json(
      await api<EintragAus>(locals.user, `/api/eintraege/${params.datum}`, fetch, {
        method: 'PUT',
        body: JSON.stringify({
          chiffrat: daten.chiffrat,
          iv: daten.iv,
          schluessel_version: 1,
        }),
      }),
    );
  } catch (e) {
    fehlerWeiter(e);
  }
};

export const DELETE: RequestHandler = async ({ locals, params, fetch }) => {
  if (!locals.user) error(401, 'Nicht angemeldet');
  if (!DATUM.test(params.datum)) error(400, 'Kein gueltiges Datum');
  try {
    await api(locals.user, `/api/eintraege/${params.datum}`, fetch, { method: 'DELETE' });
    return new Response(null, { status: 204 });
  } catch (e) {
    fehlerWeiter(e);
  }
};
