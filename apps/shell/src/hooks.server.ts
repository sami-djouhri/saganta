import { createBetterAuthHandle } from '@saganta/auth';
import type { Handle } from '@sveltejs/kit';
import { getAuthConfig } from '$lib/server/auth';

export const handle: Handle = createBetterAuthHandle({
  cfg: getAuthConfig,
  // Öffentlich erreichbar ohne Login: die Auth-Seiten und die Standard-Health-/
  // Asset-Pfade. '/' bleibt offen, weil +page.server.ts Abgemeldete selbst und
  // relativ auf /login schickt (im Raum des Aufrufers).
  //
  // Seit 2026-11-01 gibt es hier keine Werbe- und Rechtsseiten mehr (`/preise`,
  // `/impressum`, `/datenschutz`, `/agb`, Entscheid 01.11.), und `/apps`
  // ist eine Download-Liste hinter der Anmeldung. Ein alter Link landet ueber
  // diesen Hook auf der Anmeldung. Saganta
  // ist privat; das oeffentliche Impressum gehoert zum Schaufenster auf netcup.
  publicPaths: [
    '/',
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
