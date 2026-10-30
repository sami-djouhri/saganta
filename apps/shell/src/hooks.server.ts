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
    '/apps',
    // ⚠️ Die Seite gibt es nicht mehr, der Pfad muss aber offen bleiben: dort
    // liegt nur noch eine 301 auf `/apps`, und ohne diesen Eintrag greift der
    // Auth-Hook davor und schickt einen alten Link auf die Anmeldemaske.
    // Gemessen am 2026-10-25, Begründung in `routes/preise/+server.ts`.
    '/preise',
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
    // Native-App-Auslieferung (Auto-Updater ohne Session): Manifest, APK, das
    // Linux-Paket und seit 2026-10-25 das pacman-Repo (Datenbank + Signaturen).
    // Der Endpunkt prüft selbst, dass es genau diese Suffixe sind und dass
    // kein Pfad aus dem Verzeichnis herausführt.
    //
    // ⚠️ `pacman` bringt keine Sitzung mit. Fehlt ein Suffix hier, bekommt es
    // die Anmeldemaske statt der Datei und meldet einen Prüfsummenfehler.
    /^\/downloads\/[^/]+\.(apk|json|pkg\.tar\.zst|db|files|pub)(\.sig)?$/,
  ],
});
