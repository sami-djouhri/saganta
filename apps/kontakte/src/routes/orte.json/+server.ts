/**
 * Die Kontakte als Punkte, fuer die Ebene „Kontakte“ in karten.home.arpa.
 *
 * Die Karte holt das aus dem Browser, mit dem Saganta-Cookie (es gilt fuer
 * ganz home.arpa). Darum CORS fuer genau diese eine Herkunft, mit
 * Credentials, und nur hier. Die Karte selbst erfaehrt nichts ueber
 * Kontakte; node1 sieht die Daten nie.
 *
 * Oeffentlicher Pfad im Auth-Hook, damit eine fehlende Anmeldung als 401
 *   mit Anmeldeadresse ankommt statt als 303: eine Weiterleitung auf eine
 *   fremde Herkunft wird im `fetch` zu einem undurchsichtigen Fehler, der von
 *   „Dienst schlaeft“ nicht zu unterscheiden ist (dieselbe Lehre wie /spur/).
 */
import { json } from '@sveltejs/kit';
import { anmeldeadresseFuer } from '@saganta/auth';
import { getAuthConfig } from '$lib/server/auth';
import { dienst, dienstCtx } from '$lib/server/dienst';
import { kartenKoepfe } from '$lib/karten';
import type { Orte } from '$lib/typen';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ locals, fetch, request, url }) => {
  const koepfe = kartenKoepfe(request.headers.get('origin'));
  const ctx = dienstCtx(locals);
  if (!ctx) {
    const anmelden = anmeldeadresseFuer(getAuthConfig(), url.host);
    return json({ anmelden }, { status: 401, headers: koepfe });
  }
  try {
    const orte = await dienst<Orte>(ctx, '/api/orte', fetch);
    return json(orte, { headers: koepfe });
  } catch {
    return json({ fehler: 'Der Kontakte-Dienst antwortet nicht.' }, { status: 502, headers: koepfe });
  }
};
