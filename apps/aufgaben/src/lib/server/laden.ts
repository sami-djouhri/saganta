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
import { notizenZu } from '@saganta/notizen-anschluss';
import { alsAufgabe, dienstCtx, dienstFetch, type DienstAufgabe } from '$lib/server/aufgaben-dienst';
import { notizAnschluss } from '$lib/server/notizen';

/** Heute in Berliner Wanduhrzeit, nicht in UTC.
 *
 * Der Node-Prozess laeuft auf UTC. Zwischen Mitternacht und zwei Uhr Berliner
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
  const dienst = dienstCtx(locals);

  // Die Aufgaben kommen seit dem 2026-11-03 aus dem Aufgaben-Dienst, Ziele
  // und Tagesbild weiter aus dem Kalender. Projekte gibt es dort keine mehr
  // (der Kalender fuehrte 0); sie kommen mit dem Umzug der ProjectDeck-Aufgaben.
  const ladeAufgaben = async (): Promise<Aufgabe[]> => {
    if (!dienst) throw new Error('AUFGABEN_API_BASE_URL ist nicht gesetzt');
    const offen = await dienstFetch<DienstAufgabe[]>(dienst, '/api/aufgaben', fetcher);
    const erledigt = opt.mitErledigten
      ? await dienstFetch<DienstAufgabe[]>(dienst, '/api/aufgaben?erledigte=true', fetcher)
      : [];
    return [...offen, ...erledigt].map(alsAufgabe);
  };

  const [aufgabenRes, zieleRes, projekteRes, tagesbildRes] = await Promise.allSettled([
    ladeAufgaben(),
    bffFetch<Ziel[]>(basis, `/api/goals?date=${heute}`, token, fetcher),
    Promise.resolve([] as Projekt[]),
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
    const bild = tagesbildRes.value as Tagesbild;
    // „Bleibt liegen" rechnet der Kalender aus SEINEN Todos, und die sind seit
    // dem Umzug leer. Der Zaehler steht jetzt an der Aufgabe selbst.
    bild.backlog = bestand.aufgaben
      .filter((a) => !a.completed && (a.defer_count ?? 0) >= 3)
      .sort((a, b) => (b.defer_count ?? 0) - (a.defer_count ?? 0))
      .map((a) => ({ todo_id: a.id, title: a.title, defer_count: a.defer_count ?? 0, due_date: a.due_date ?? null }));
    bestand.tagesbild = bild;
  }

  // Notiz-Marken in EINEM Aufruf, nicht je Zeile. Begruendung in
  // `@saganta/notizen-anschluss`.
  const { nach, stumm } = await notizenZu(
    'aufgabe',
    bestand.aufgaben.map((a) => a.id),
    notizAnschluss(locals, fetcher),
  );
  bestand.fehler.notizen = stumm;
  bestand.notizenNach = Object.fromEntries(
    Object.entries(nach).map(([id, liste]) => [
      id,
      liste.map((n) => ({ id: n.id, titel: n.titel })),
    ]),
  );

  return bestand;
}
