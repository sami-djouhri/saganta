import { api } from '$lib/projectdeck-api';
import type { DeadlineRisk } from '$lib/types';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch }) => {
  if (!locals.user) return { risks: [] };
  const risks = await api<DeadlineRisk[]>(locals.user, '/api/deadline-center', fetch);
  return { risks };
};
