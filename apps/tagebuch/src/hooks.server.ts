import { createBetterAuthHandle } from '@saganta/auth';
import type { Handle } from '@sveltejs/kit';
import { getAuthConfig } from '$lib/server/auth';

/**
 * Alles hinter der Anmeldung, ohne Ausnahme.
 *
 * Die Notizen-App öffnet `/n/…` bewusst für Empfänger geteilter Notizen. Hier
 * gibt es nichts Vergleichbares und soll es nicht geben: ein Tagebuch teilt man
 * nicht, und eine öffentliche Route wäre eine Tür, die niemand braucht und die
 * bei jedem künftigen Umbau mitgedacht werden müsste.
 */
export const handle: Handle = createBetterAuthHandle({
  cfg: getAuthConfig,
  publicPaths: ['/healthz', '/robots.txt', '/favicon.ico', '/login'],
});
