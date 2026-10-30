import { createBetterAuthHandle } from '@saganta/auth';
import type { Handle } from '@sveltejs/kit';
import { getAuthConfig } from '$lib/server/auth';

/**
 * Die Leseseite einer Freigabe (`/n/…`) ist der einzige Teil dieser App ohne
 * Anmeldung, das ist ihr Zweck: der Empfänger hat kein Konto hier.
 *
 * Der Ausschnitt ist eng gefasst (`/n/` und darunter). Alles andere, auch die
 * Startseite, bleibt hinter dem Login. Wäre die Ausnahme weiter, würde ein
 * Tippfehler in einer künftigen Route still eine Seite öffentlich machen, und
 * das fiele niemandem auf: geschützte Seiten leiten sichtbar um, offene nicht.
 */
export const handle: Handle = createBetterAuthHandle({
  cfg: getAuthConfig,
  publicPaths: ['/healthz', '/robots.txt', '/favicon.ico', '/login', /^\/n(\/|$)/],
});
