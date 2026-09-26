/**
 * Die drei Skalen an den Kalender, und sonst nichts.
 *
 * Was genau hinausgeht und warum das eine Allowlist sein muss, steht in
 * `$lib/checkin`. Diese Datei ist nur der Weg dorthin.
 */
import { error, json } from '@sveltejs/kit';
import { ApiFehler, kalender } from '$lib/tagebuch-api';
import { checkinNutzlast } from '$lib/checkin';
import type { RequestHandler } from './$types';

const DATUM = /^\d{4}-\d{2}-\d{2}$/;

export const POST: RequestHandler = async ({ locals, request, fetch }) => {
  if (!locals.user) error(401, 'Nicht angemeldet');
  const roh = (await request.json()) as Record<string, unknown>;
  const datum = typeof roh.datum === 'string' ? roh.datum : '';
  if (!DATUM.test(datum)) error(400, 'Kein gueltiges Datum');

  const nutzlast = checkinNutzlast(datum, roh);
  // Ohne eine einzige Angabe gibt es nichts zu melden. Ein leerer Check-in
  // wuerde im Kalender eine Zeile anlegen, die "keine Angabe" von "nicht
  // ausgefuellt" nicht mehr unterscheidbar macht.
  if (Object.keys(nutzlast).length === 1) return json({ gesendet: false });

  try {
    await kalender(locals.user, '/api/assistant/checkin', fetch, {
      method: 'POST',
      body: JSON.stringify(nutzlast),
    });
    return json({ gesendet: true });
  } catch (e) {
    // ★ Fail-soft mit Absicht: der Kalender ist ein Empfaenger, kein Wirt.
    // Ist er nicht erreichbar, darf das den Eintrag nicht verhindern, denn der
    // Text ist zu diesem Zeitpunkt bereits sicher gespeichert. Die Oberflaeche
    // zeigt einen Hinweis statt eines Fehlers.
    if (e instanceof ApiFehler) return json({ gesendet: false, grund: e.detail }, { status: 200 });
    throw e;
  }
};
