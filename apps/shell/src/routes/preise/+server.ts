import { redirect } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

// Die Preisseite ist am 2026-10-25 entfallen: Saganta ist seit dem
// Privat-Entscheid vom 21.10. nichts, was man bucht. Hier bleibt nur eine
// dauerhafte Weiterleitung auf die App-Übersicht.
//
// Sie ist nicht Höflichkeit gegenüber alten Lesezeichen, sondern die
// Behebung eines gemessenen Zustands. Nach dem Löschen der Route antwortete
// `/preise` mit **303 auf `https://saganta.de/login`**: der Auth-Hook greift
// vor dem Router, und weil der Pfad nicht mehr in `publicPaths` stand, hielt
// er ihn für geschützt. Ein alter Link führte damit nach draußen auf genau den
// Namen, der seit dem 21.10. mit 404 antwortet -- und auf dem Weg dorthin sah
// es wie ein Rechteproblem aus, nicht wie eine abgeschaffte Seite.
//
// Von drei möglichen Zuständen ist das der schlechteste:
//   404                → ehrlich, aber der Link bricht sichtbar
//   303 auf /login     → sieht aus wie „du bist abgemeldet" (war der Fall)
//   301 auf /apps      → landet beim Nächstliegenden, und das ist diese Datei
//
// ⚠️ Der Pfad muss dafür in `publicPaths` (hooks.server.ts) stehen, sonst
// kommt der Hook dem Router zuvor und der 303 ist zurück.
//
// Dasselbe Muster wie `lesen.home.arpa`, das seit der Umbenennung dauerhaft
// auf `bibliothek` weiterleitet.
export const GET: RequestHandler = () => {
  redirect(301, '/apps');
};
