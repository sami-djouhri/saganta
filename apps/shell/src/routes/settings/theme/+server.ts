import { env } from '$env/dynamic/private';
import { json, error } from '@sveltejs/kit';
import {
  backendSecret,
  shellApiFetch,
  shellApiToken,
  type ShellApiSettings,
} from '$lib/shell-api';
import { setThemeCookie } from '@saganta/auth';
import type { RequestHandler } from './$types';

// Schlanker Persist-Proxy für den Theme-Umschalter in der TopBar. Setzt NUR das
// Theme (partielles PATCH: shell-api SettingsPatch hat alle Felder optional, wie
// beim togglePin-Muster in ../+page.server.ts). Locale/Pins bleiben unberührt.
const THEMES = new Set(['dark', 'light', 'hc']);

export const POST: RequestHandler = async ({ request, locals, fetch, cookies, url }) => {
  if (!locals.user) throw error(401, 'nicht angemeldet');
  if (!env.SHELL_API_BASE_URL) throw error(503, 'shell-api ist nicht konfiguriert');

  const body = (await request.json().catch(() => null)) as { theme?: string } | null;
  const theme = body?.theme ?? '';
  if (!THEMES.has(theme)) throw error(400, `Unbekanntes Theme: ${theme}`);

  // Suite-weit propagieren (alle App-Subdomains lesen dieses Cookie fürs Theme).
  setThemeCookie(cookies, url.hostname, url.protocol === 'https:', theme);

  const token = shellApiToken(locals.user, backendSecret());
  try {
    await shellApiFetch<ShellApiSettings>(env.SHELL_API_BASE_URL, '/api/settings', token, fetch, {
      method: 'PATCH',
      body: JSON.stringify({ theme }),
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (err) {
    throw error(502, String(err));
  }

  return json({ theme });
};
