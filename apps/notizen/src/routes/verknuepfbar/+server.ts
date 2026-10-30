import { json } from '@sveltejs/kit';
import { suchen } from '$lib/quellen';
import type { VerknuepfungsTyp } from '$lib/types';
import type { RequestHandler } from './$types';

const TYPEN: VerknuepfungsTyp[] = ['termin', 'aufgabe', 'ziel', 'projekt', 'kontakt', 'brief'];

/** Sucht Gegenstücke in Kalender, ProjectDeck und Briefkasten (siehe lib/quellen.ts). */
export const GET: RequestHandler = async ({ locals, url, fetch }) => {
  const user = locals.user;
  if (!user) return json({ fehler: 'Nicht angemeldet' }, { status: 401 });

  const suche = url.searchParams.get('q')?.trim() ?? '';
  const rohTyp = url.searchParams.get('typ');
  const typ = TYPEN.includes(rohTyp as VerknuepfungsTyp)
    ? (rohTyp as VerknuepfungsTyp)
    : undefined;

  const ergebnis = await suchen(user, suche, fetch, typ);
  return json(ergebnis);
};
