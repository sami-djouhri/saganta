import { createBetterAuthHandle } from '@saganta/auth';
import type { Handle } from '@sveltejs/kit';
import { getAuthConfig } from '$lib/server/auth';

export const handle: Handle = createBetterAuthHandle({
  cfg: getAuthConfig,
  // Podcast-Feed + Audio-Enclosures müssen OHNE Login erreichbar sein (Podcast-/
  // Alexa-Apps haben keine Session). Schutz allein über den unguessable feed_token.
  // `/` ist seit 2026-11-05 nicht mehr öffentlich: dort stand eine Werbeseite
  // mit Tarifen (Landing), also das am 21.10. abgeschaffte Produkt. Wie in der
  // Shell schickt der Hook Abgemeldete jetzt zur Anmeldung.
  publicPaths: [
    '/healthz',
    '/robots.txt',
    '/favicon.ico',
    '/login',
    '/tools/saganta-briefing-player.sh', // Self-Serve-Player-Download
    /^\/briefing\/feed\/[^/]+\.xml$/,
    // Audio und JSON, jeweils mit und ohne Datum (ohne Datum = neuestes Briefing).
    // `today` ist ausgenommen: /briefing/audio/today ist der Player-Proxy MIT
    // Session (liefert das Audio des eingeloggten Nutzers), ein Muster ohne diese
    // Ausnahme haette ihn versehentlich oeffentlich gemacht.
    /^\/briefing\/audio\/(?!today$)[^/]+(\/[^/]+)?$/,
    /^\/briefing\/json\/(?!today$)[^/]+(\/[^/]+)?$/,
  ],
});
