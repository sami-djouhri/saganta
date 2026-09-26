import { api } from '$lib/projectdeck-api';
import type { Dashboard } from '$lib/types';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch }) => {
  if (!locals.user) return { projects: [], findings: [] };
  const d = await api<Dashboard>(locals.user, '/api/dashboard', fetch);
  return {
    projects: d.tiles.without_review ?? [],
    findings: d.findings.filter((f) => f.bucket === 'without_review'),
  };
};
