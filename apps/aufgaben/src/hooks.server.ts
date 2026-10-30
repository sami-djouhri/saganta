import { createBetterAuthHandle } from '@saganta/auth';
import type { Handle } from '@sveltejs/kit';
import { getAuthConfig } from '$lib/server/auth';

// Kein oeffentlicher Teil: jede Seite dieser App zeigt eigene Aufgaben.
export const handle: Handle = createBetterAuthHandle({
  cfg: getAuthConfig,
  publicPaths: ['/healthz', '/robots.txt', '/favicon.ico', '/login'],
});
