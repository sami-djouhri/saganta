import { api } from '$lib/projectdeck-api';
import type { Project } from '$lib/types';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch }) => {
  if (!locals.user) return { projects: [] };
  const projects = await api<Project[]>(locals.user, '/api/projects?type=client', fetch);
  return { projects };
};
