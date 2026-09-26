import { env } from '$env/dynamic/private';
import {
  backendSecret,
  shellApiFetch,
  shellApiToken,
  type ShellApiSettings,
} from '$lib/shell-api';
import { setThemeCookie, THEME_COOKIE_NAME } from '@saganta/auth';
import type { LayoutServerLoad } from './$types';

const DEFAULT_SETTINGS: ShellApiSettings = {
  theme: 'dark',
  locale: 'de-DE',
  pinned_apps: [],
};

export const load: LayoutServerLoad = async ({ locals, fetch, depends, cookies, url }) => {
  // Invalidierbar machen: der TopBar-Theme-Toggle zieht diesen Load nach erfolgreichem
  // Persist gezielt neu (invalidate('app:settings')), damit Server-Wahrheit == UI und
  // ein späteres invalidateAll die optimistische Umschaltung nicht zurückrollt.
  depends('app:settings');

  let settings: ShellApiSettings = DEFAULT_SETTINGS;

  if (locals.user && env.SHELL_API_BASE_URL) {
    const token = shellApiToken(locals.user, backendSecret());
    try {
      settings = await shellApiFetch<ShellApiSettings>(
        env.SHELL_API_BASE_URL,
        '/api/settings',
        token,
        fetch,
      );
    } catch {
      // bewusst still: Layout darf nicht an Settings-Fehlern scheitern; Default greift
    }
  }

  // Suite-weites Theme seeden: sobald eingeloggt und das Cookie noch nicht dem
  // gespeicherten Theme entspricht, setzen, damit alle App-Subdomains schon ohne
  // vorherigen Toggle „aus einem Guss" rendern.
  if (locals.user && cookies.get(THEME_COOKIE_NAME) !== settings.theme) {
    setThemeCookie(cookies, url.hostname, url.protocol === 'https:', settings.theme);
  }

  return { user: locals.user, settings };
};
