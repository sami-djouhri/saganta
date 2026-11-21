import { error, redirect } from '@sveltejs/kit';
import { ApiFehler, api } from '$lib/notizen-api';
import type { GesamtNetz, Notizbuch } from '$lib/types';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, url, fetch }) => {
  const user = locals.user;
  if (!user) redirect(303, '/');
  const archivierte = url.searchParams.get('archiv') === '1';
  try {
    const [netz, notizbuecher] = await Promise.all([
      api<GesamtNetz>(user, `/api/notizen/netz?archivierte=${archivierte}`, fetch),
      api<Notizbuch[]>(user, '/api/notizbuecher', fetch),
    ]);
    return {
      netz,
      notizbuecher,
      archivierte,
      fokus: Number(url.searchParams.get('fokus')) || null,
    };
  } catch (e) {
    if (e instanceof ApiFehler) error(502, 'Das Netz ließ sich gerade nicht laden.');
    throw e;
  }
};
