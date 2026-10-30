import type { PageServerLoad } from './$types';
import { aufgabenAktionen } from '$lib/server/aktionen';
import { ladeBestand } from '$lib/server/laden';

export const load: PageServerLoad = async ({ locals, fetch }) => {
  return ladeBestand(locals, fetch, { mitErledigten: false });
};

export const actions = aufgabenAktionen;
