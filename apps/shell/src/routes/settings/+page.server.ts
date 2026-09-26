import { env } from '$env/dynamic/private';
import { error, fail, redirect } from '@sveltejs/kit';
import {
  backendSecret,
  shellApiFetch,
  shellApiToken,
  type ShellApiSettings,
} from '$lib/shell-api';
import { setThemeCookie } from '@saganta/auth';
import type { Actions, PageServerLoad } from './$types';

const THEMES = new Set(['dark', 'light', 'hc']);
const LOCALES = new Set(['de-DE', 'en-US']);

export const load: PageServerLoad = async ({ locals, fetch }) => {
  if (!locals.user) throw redirect(303, '/login?next=/settings');
  if (!env.SHELL_API_BASE_URL) {
    throw error(503, 'shell-api ist nicht konfiguriert (SHELL_API_BASE_URL fehlt).');
  }

  const token = shellApiToken(locals.user, backendSecret());
  const settings = await shellApiFetch<ShellApiSettings>(
    env.SHELL_API_BASE_URL,
    '/api/settings',
    token,
    fetch,
  );

  return { settings };
};

export const actions: Actions = {
  save: async ({ request, locals, fetch, cookies, url }) => {
    if (!locals.user) return fail(401, { error: 'no session' });
    if (!env.SHELL_API_BASE_URL) return fail(503, { error: 'shell-api not configured' });

    const data = await request.formData();
    const theme = String(data.get('theme') ?? '');
    const locale = String(data.get('locale') ?? '');
    if (!THEMES.has(theme)) return fail(400, { error: `Unbekanntes Theme: ${theme}` });
    if (!LOCALES.has(locale)) return fail(400, { error: `Unbekanntes Locale: ${locale}` });

    // Suite-weit propagieren: alle App-Subdomains lesen dieses Cookie fürs Theme.
    setThemeCookie(cookies, url.hostname, url.protocol === 'https:', theme);

    const token = shellApiToken(locals.user, backendSecret());
    try {
      await shellApiFetch<ShellApiSettings>(
        env.SHELL_API_BASE_URL,
        '/api/settings',
        token,
        fetch,
        {
          method: 'PATCH',
          body: JSON.stringify({ theme, locale }),
          headers: { 'Content-Type': 'application/json' },
        },
      );
    } catch (err) {
      return fail(502, { error: String(err) });
    }

    throw redirect(303, '/settings?ok=1');
  },

  // ★ Die Aktion `changePassword` lag bis 2026-09-18 hier und ist nach `/konto`
  // gewandert, wo vorher das Passwort erneut abgefragt wird. Sie wurde dabei
  // **entfernt** und nicht bloss dupliziert: ein zweiter, ungeschuetzter Weg
  // zum Passwortwechsel haette die neue Abfrage genau so weit ausgehebelt, wie
  // jemand bereit ist, ein Formular ohne die zugehoerige Seite abzuschicken.
};
