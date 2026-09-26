import { error, redirect } from '@sveltejs/kit';
import { abschlussOAuth } from '$lib/post-api';
import type { PageServerLoad } from './$types';

/**
 * Die Rueckleitung vom Anbieter.
 *
 * ★ Sie legt das Konto an und leitet weiter; eine eigene Seite gibt es
 * absichtlich nicht. Wer hier landet, hat den Vorgang beim Anbieter schon
 * abgeschlossen und will das Ergebnis sehen, keine Zwischenseite.
 *
 * ⚠️ Der `state` wird **nicht** hier geprueft, sondern im Backend gegen den
 * angemeldeten Nutzer (`services/mail-api/app/routes_oauth.py`). Eine Pruefung
 * im Browser waere keine: sie liefe auf derselben Seite, die der Angreifer
 * aufgerufen hat.
 */
export const load: PageServerLoad = async ({ locals, url, fetch }) => {
  if (!locals.user) redirect(303, '/');

  // Der Anbieter meldet einen Abbruch als Parameter, nicht als Fehlerseite.
  // Ohne diesen Zweig sieht ein bewusstes „Abbrechen" wie ein Programmfehler aus.
  const abbruch = url.searchParams.get('error');
  if (abbruch) {
    redirect(303, `/accounts?oauth_fehler=${encodeURIComponent(abbruch)}`);
  }

  const zustand = url.searchParams.get('state') ?? '';
  const code = url.searchParams.get('code') ?? '';
  if (!zustand || !code) error(400, 'Der Anbieter hat keinen Code zurueckgegeben.');

  try {
    const konto = await abschlussOAuth(locals.user, fetch, zustand, code);
    redirect(303, `/accounts?verbunden=${encodeURIComponent(konto.email)}`);
  } catch (err) {
    // `redirect` wirft selbst; das darf hier nicht als Fehler durchgehen.
    if (err && typeof err === 'object' && 'status' in err && 'location' in err) throw err;
    redirect(303, `/accounts?oauth_fehler=${encodeURIComponent(String(err).slice(0, 200))}`);
  }
};
