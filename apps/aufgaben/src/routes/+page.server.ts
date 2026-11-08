import type { PageServerLoad } from './$types';
import { aufgabenAktionen } from '$lib/server/aktionen';
import { ladeBestand } from '$lib/server/laden';
import { alsAufgabe, dienstCtx, dienstFetch, type DienstAufgabe } from '$lib/server/aufgaben-dienst';
import type { Aufgabe } from '$lib/aufgaben-bff';

const UUID = /^[0-9a-f-]{8,36}$/i;

export const load: PageServerLoad = async ({ locals, fetch, url }) => {
  const bestand = await ladeBestand(locals, fetch, { mitTagesbild: true });
  // `?aufgabe=<id>` oeffnet den Bearbeiten-Dialog (aufgabeUrl in @saganta/ui,
  // so verlinkt das ProjectDeck). Einzeln nachgeladen, weil die Aufgabe nicht
  // in der Tagesliste stehen muss (erledigt, wartend, an einem spaeteren Tag).
  // Fremde oder unbekannte Kennung: der Dienst antwortet 404, die Seite oeffnet
  // dann einfach nichts.
  let geoeffnet: Aufgabe | null = null;
  const id = url.searchParams.get('aufgabe') ?? '';
  const dienst = dienstCtx(locals);
  if (dienst && UUID.test(id)) {
    geoeffnet = await dienstFetch<DienstAufgabe>(dienst, `/api/aufgaben/${id}`, fetch)
      .then(alsAufgabe)
      .catch(() => null);
  }
  return { ...bestand, geoeffnet };
};

export const actions = aufgabenAktionen;
