import { createBetterAuthHandle } from '@saganta/auth';
import type { Handle } from '@sveltejs/kit';
import { getAuthConfig } from '$lib/server/auth';

export const handle: Handle = createBetterAuthHandle({
  cfg: getAuthConfig,
  // Öffentlich erreichbar ohne Login: die Marketing-Landing ('/'), die Auth-Seiten
  // und die Standard-Health-/Asset-Pfade. Das Dashboard rendert '/' nur, wenn
  // locals.user gesetzt ist (sonst zeigt +page die Landing).
  publicPaths: [
    '/',
    '/preise',
    '/apps',
    '/impressum',
    '/datenschutz',
    '/agb',
    '/login',
    '/forgot',
    '/reset',
    '/captcha/challenge', // same-origin PoW-Challenge fürs Captcha-Widget (kein Login)
    '/healthz',
    '/robots.txt',
    '/favicon.ico',
    // Native-App-Auslieferung (Auto-Updater ohne Session): Manifest + APK.
    /^\/downloads\/[^/]+\.(apk|json)$/,
  ],
});
