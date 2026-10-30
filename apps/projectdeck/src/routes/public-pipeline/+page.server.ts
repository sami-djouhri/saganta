import { api } from '$lib/projectdeck-api';
import type { Dashboard } from '$lib/types';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch }) => {
  if (!locals.user) return { projects: [] };
  const d = await api<Dashboard>(locals.user, '/api/dashboard', fetch);
  return { projects: d.tiles.public_candidates ?? [] };
};
