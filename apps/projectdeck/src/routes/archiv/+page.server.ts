import { api } from '$lib/projectdeck-api';
import type { Project } from '$lib/types';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch }) => {
  if (!locals.user) return { projects: [] };
  const [archived, shutdown] = await Promise.all([
    api<Project[]>(locals.user, '/api/projects?status=archived', fetch),
    api<Project[]>(locals.user, '/api/projects?status=shutdown', fetch),
  ]);
  return { projects: [...archived, ...shutdown] };
};
