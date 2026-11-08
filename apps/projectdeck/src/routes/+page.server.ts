import { api } from '$lib/projectdeck-api';
import type { AufgabeUebersicht, Finding } from '$lib/types';
import type { PageServerLoad } from './$types';

// Die Startseite beantwortet seit dem 08.11. "was ist offen" (Entscheid)
// und nicht mehr die Portfolio-Kacheln aus /api/dashboard: deren Felder (Frist,
// Kunde, Ziel-Sichtbarkeit, Wochenfokus) waren an keinem Projekt gesetzt.
// Zwei Quellen, getrennt fehlbar: faellt der Aufgaben-Dienst aus, bleiben die
// Hinweise sichtbar und umgekehrt.
export const load: PageServerLoad = async ({ locals, fetch }) => {
  if (!locals.user) return { aufgaben: [] as AufgabeUebersicht[], aufgabenFehlen: false, befunde: [] as Finding[], befundeFehlen: false };
  const u = locals.user;
  const [aufgaben, befunde] = await Promise.all([
    api<AufgabeUebersicht[]>(u, '/api/aufgaben', fetch).then(
      (a) => ({ a, fehlt: false }),
      () => ({ a: [] as AufgabeUebersicht[], fehlt: true }),
    ),
    api<Finding[]>(u, '/api/findings', fetch).then(
      (b) => ({ b, fehlt: false }),
      () => ({ b: [] as Finding[], fehlt: true }),
    ),
  ]);
  return {
    aufgaben: aufgaben.a,
    aufgabenFehlen: aufgaben.fehlt,
    befunde: befunde.b,
    befundeFehlen: befunde.fehlt,
  };
};
