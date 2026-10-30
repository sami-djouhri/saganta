import { api } from '$lib/projectdeck-api';
import type { Dashboard } from '$lib/types';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch }) => {
  if (!locals.user) return { dashboard: null };
  try {
    const dashboard = await api<Dashboard>(locals.user, '/api/dashboard', fetch);
    return { dashboard, error: null };
  } catch (err) {
    return { dashboard: null, error: String(err) };
  }
};
