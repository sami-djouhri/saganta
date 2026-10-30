/**
 * Der Tresor, durchgereicht.
 *
 * Hier laufen ausschliesslich verpackte Schluessel durch. Weder dieser Server
 * noch das Backend kann eines der Pakete oeffnen: dafuer braucht es die
 * Passphrase, und die verlaesst den Browser nicht.
 */
import { error, json } from '@sveltejs/kit';
import { ApiFehler, api, type TresorPaketeAus } from '$lib/tagebuch-api';
import type { RequestHandler } from './$types';

function fehlerWeiter(e: unknown): never {
  if (e instanceof ApiFehler) error(e.status >= 500 ? 502 : e.status, e.detail);
  throw e;
}

export const GET: RequestHandler = async ({ locals, fetch }) => {
  if (!locals.user) error(401, 'Nicht angemeldet');
  try {
    return json(await api<TresorPaketeAus>(locals.user, '/api/tresor', fetch));
  } catch (e) {
    fehlerWeiter(e);
  }
};

export const PUT: RequestHandler = async ({ locals, request, fetch }) => {
  if (!locals.user) error(401, 'Nicht angemeldet');
  try {
    const pakete = await api<TresorPaketeAus>(locals.user, '/api/tresor', fetch, {
      method: 'PUT',
      body: JSON.stringify(await request.json()),
    });
    return json(pakete, { status: 201 });
  } catch (e) {
    fehlerWeiter(e);
  }
};

export const POST: RequestHandler = async ({ locals, request, fetch }) => {
  if (!locals.user) error(401, 'Nicht angemeldet');
  try {
    return json(
      await api<TresorPaketeAus>(locals.user, '/api/tresor/passphrase', fetch, {
        method: 'POST',
        body: JSON.stringify(await request.json()),
      }),
    );
  } catch (e) {
    fehlerWeiter(e);
  }
};
