import { createBetterAuthHandle } from '@saganta/auth';
import type { Handle } from '@sveltejs/kit';
import { getAuthConfig } from '$lib/server/auth';

// Jede Seite dieser App zeigt eigene Kontakte; /orte.json ist nur fuer den
// Hook oeffentlich und prueft die Anmeldung selbst.
export const handle: Handle = createBetterAuthHandle({
  cfg: getAuthConfig,
  publicPaths: ['/healthz', '/robots.txt', '/favicon.ico', '/login', '/orte.json'],
});
