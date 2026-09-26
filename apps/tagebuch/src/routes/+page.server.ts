import { error, redirect } from '@sveltejs/kit';
import { ApiFehler, api, kalender, type EintragAus, type TagAus, type TresorPaketeAus } from '$lib/tagebuch-api';
import { kontextAusEreignissen, type Tageskontext } from '$lib/kontext';
import type { PageServerLoad } from './$types';

const DATUM = /^\d{4}-\d{2}-\d{2}$/;

/** Heute in Berliner Wanduhrzeit, nicht in UTC.
 *
 * ★ `new Date().toISOString()` waere hier falsch: zwischen 00:00 und 02:00
 * Berliner Zeit steht dort noch der Vortag, und das Tagebuch oeffnete abends
 * spaet den falschen Tag. Der Kalender rechnet aus demselben Grund durchgehend
 * in Berliner Wanduhrzeit (`backend/wanduhr.py`).
 */
function heuteInBerlin(): string {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Berlin' }).format(new Date());
}

export const load: PageServerLoad = async ({ locals, url, fetch }) => {
  const user = locals.user;
  if (!user) redirect(303, '/');

  const heute = heuteInBerlin();
  const gewaehlt = url.searchParams.get('tag') ?? heute;
  if (!DATUM.test(gewaehlt)) redirect(303, '/');
  const jahr = Number(gewaehlt.slice(0, 4));

  // Der Tresor entscheidet, was die Seite ueberhaupt anzeigen kann, deshalb
  // wird sein Fehlen (404) hier zu `null` und nicht zu einem Fehler: es
  // bedeutet "noch nicht eingerichtet", und die Oberflaeche fuehrt dann durch
  // das Einrichten.
  const tresor = await api<TresorPaketeAus>(user, '/api/tresor', fetch).catch((e) => {
    if (e instanceof ApiFehler && e.status === 404) return null;
    if (e instanceof ApiFehler) error(e.status >= 500 ? 502 : e.status, e.detail);
    throw e;
  });

  const [eintrag, tage, kontext] = await Promise.all([
    api<EintragAus>(user, `/api/eintraege/${gewaehlt}`, fetch).catch((e) => {
      if (e instanceof ApiFehler && e.status === 404) return null;
      return null;
    }),
    api<TagAus[]>(user, `/api/eintraege/tage?jahr=${jahr}`, fetch).catch(() => [] as TagAus[]),
    // Fail-soft: der Kalender ist eine Gedaechtnisstuetze, kein Wirt. Faellt er
    // aus, soll man trotzdem schreiben koennen.
    kalender<{ items?: unknown }>(
      user,
      `/api/events/range?start=${gewaehlt}&end=${gewaehlt}`,
      fetch,
    )
      .then((antwort) => kontextAusEreignissen(antwort?.items))
      .catch(() => ({ tagestyp: null, termine: [] }) as Tageskontext),
  ]);

  return {
    heute,
    tag: gewaehlt,
    jahr,
    tresorVorhanden: tresor !== null,
    tresor,
    // Nur die beiden Felder, die der Browser zum Oeffnen braucht. Die
    // Zeitstempel gehoeren nicht auf die Seite.
    eintrag: eintrag ? { chiffrat: eintrag.chiffrat, iv: eintrag.iv } : null,
    tage,
    kontext,
  };
};
