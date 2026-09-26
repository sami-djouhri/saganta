import { redirect } from '@sveltejs/kit';
import { applySetCookies, signOut } from '@saganta/auth';
import { getAuthConfig } from '$lib/server/auth';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
  redirect(303, '/');
};

export const actions: Actions = {
  default: async ({ request, cookies, url }) => {
    const cookieHeader = request.headers.get('cookie') ?? '';
    try {
      const setCookies = await signOut(getAuthConfig(), cookieHeader);
      applySetCookies(cookies, setCookies, url.host);
    } catch {
      // Auch ohne Auth-Service-Antwort lokal weiterleiten.
    }
    redirect(303, '/');
  },
};
