import { env } from '$env/dynamic/private';
import { redirect } from '@sveltejs/kit';
import { backendSecret, kalenderBffFetch, kalenderBffToken } from '$lib/kalender-bff';
import type { PageServerLoad } from './$types';

/**
 * Suche ueber Termine, Aufgaben, Tagesziele und Kontakte (seit 2026-11-08,
 * Gleichstand-Luecke 3). Der BFF reichte `/api/search` seit dem Bau der App
 * durch, im Web gab es dafuer keine Oberflaeche.
 */
export interface Treffer {
  kind: 'event' | 'todo' | 'goal' | 'contact' | string;
  kind_label?: string;
  id: string;
  title: string;
  date: string | null;
}

export const load: PageServerLoad = async ({ locals, fetch, url }) => {
  if (!locals.user || !env.KALENDER_BFF_BASE_URL) redirect(303, '/');
  const q = (url.searchParams.get('q') ?? '').trim().slice(0, 100);
  if (!q) return { q, treffer: [] as Treffer[], fehler: null };
  try {
    const antwort = await kalenderBffFetch<{ results?: Treffer[] }>(
      env.KALENDER_BFF_BASE_URL,
      `/api/search?q=${encodeURIComponent(q)}&limit=25`,
      kalenderBffToken(locals.user, backendSecret()),
      fetch,
    );
    return { q, treffer: antwort.results ?? [], fehler: null };
  } catch {
    return { q, treffer: [] as Treffer[], fehler: 'Die Suche hat gerade nicht geantwortet.' };
  }
};
