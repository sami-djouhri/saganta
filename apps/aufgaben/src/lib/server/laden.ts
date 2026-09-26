/**
 * Der gemeinsame Ladevorgang aller Aufgaben-Seiten.
 *
 * Vier Seiten brauchen dieselben vier Quellen (Aufgaben, Ziele, Projekte,
 * Notiz-Marken) und dieselbe fail-soft-Regel. Einmal geschrieben statt viermal:
 * sonst driftet die Fehlerbehandlung zwischen den Seiten auseinander, und die
 * Nebensache reisst irgendwo doch die Hauptsache mit.
 */
import { env } from '$env/dynamic/private';
import {
  backendSecret,
  bffFetch,
  bffToken,
  type Aufgabe,
  type Projekt,
  type Tagesbild,
  type Ziel,
} from '$lib/aufgaben-bff';
import { notizenZuAufgaben } from '$lib/server/notizen';

/** Heute in Berliner Wanduhrzeit, nicht in UTC.
 *
 * ★ Der Node-Prozess laeuft auf UTC. Zwischen Mitternacht und zwei Uhr Berliner
 * Zeit steht dort noch der Vortag, und die Tagesliste zeigte abends spaet den
 * falschen Tag.
 */
export function heuteInBerlin(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Berlin' }).format(new Date());
}

export interface Bestand {
  heute: string;
  aufgaben: Aufgabe[];
  ziele: Ziel[];
  projekte: Projekt[];
  tagesbild: Tagesbild | null;
  notizenNach: Record<string, { id: number; titel: string }[]>;
  fehler: { bff?: string; notizen?: boolean };
}

export async function ladeBestand(
  locals: App.Locals,
  fetcher: typeof fetch,
  opt: { mitErledigten?: boolean; mitTagesbild?: boolean } = {},
): Promise<Bestand> {
  const heute = heuteInBerlin();
  const leer: Bestand = {
    heute,
    aufgaben: [],
    ziele: [],
    projekte: [],
    tagesbild: null,
    notizenNach: {},
    fehler: {},
  };
  if (!locals.user || !env.KALENDER_BFF_BASE_URL) return leer;

  const token = bffToken(locals.user, backendSecret());
  const basis = env.KALENDER_BFF_BASE_URL;
  const pfad = opt.mitErledigten ? '/api/todos?include_completed=true' : '/api/todos';

  const [aufgabenRes, zieleRes, projekteRes, tagesbildRes] = await Promise.allSettled([
    bffFetch<Aufgabe[]>(basis, pfad, token, fetcher),
    bffFetch<Ziel[]>(basis, `/api/goals?date=${heute}`, token, fetcher),
    bffFetch<Projekt[]>(basis, '/api/projects', token, fetcher),
    opt.mitTagesbild
      ? bffFetch<Tagesbild>(basis, '/api/assistant/today', token, fetcher)
      : Promise.resolve(null),
  ]);

  const bestand: Bestand = { ...leer };
  // Die Aufgaben sind die Hauptsache: faellt ihr Abruf, wird das benannt.
  if (aufgabenRes.status === 'fulfilled' && Array.isArray(aufgabenRes.value)) {
    bestand.aufgaben = aufgabenRes.value;
  } else if (aufgabenRes.status === 'rejected') {
    bestand.fehler.bff = String(aufgabenRes.reason);
  }
  // Der Rest ist fail-soft.
  if (zieleRes.status === 'fulfilled' && Array.isArray(zieleRes.value)) {
    bestand.ziele = zieleRes.value;
  }
  if (projekteRes.status === 'fulfilled' && Array.isArray(projekteRes.value)) {
    bestand.projekte = projekteRes.value;
  }
  if (tagesbildRes.status === 'fulfilled' && tagesbildRes.value) {
    bestand.tagesbild = tagesbildRes.value as Tagesbild;
  }

  // Notiz-Marken in EINEM Aufruf, nicht je Zeile. Begruendung in
  // `lib/server/notizen.ts`.
  const { nach, stumm } = await notizenZuAufgaben(
    bestand.aufgaben.map((a) => a.id),
    locals.user,
    backendSecret(),
    fetcher,
  );
  bestand.fehler.notizen = stumm;
  bestand.notizenNach = Object.fromEntries(
    [...nach].map(([id, liste]) => [id, liste.map((n) => ({ id: n.id, titel: n.titel }))]),
  );

  return bestand;
}
