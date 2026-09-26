import { env } from '$env/dynamic/public';

export const APP_ID = 'notizen';
export const APP_NAME = 'Notizen';

export const NAV = [
  { href: '/', label: 'Alle Notizen', icon: 'pen' },
  { href: '/freigaben', label: 'Geteilte Links', icon: 'globe' },
] as const;

/** Basis der Kurz-Adressen für geteilte Notizen. */
export function freigabeBasis(origin: string): string {
  // Wer eine eigene Kurz-Domäne betreibt, trägt sie vollständig in
  // PUBLIC_NOTIZEN_KURZ_BASIS ein (z. B. `https://n.example.org`) und richtet
  // dafür einen Vhost auf diese App ein. Ohne Eintrag bleibt der Link auf dem
  // eigenen Ursprung und zeigt auf `/n`, eine Route, die diese App selbst
  // bedient: kurz ist schöner, funktionieren muss es überall.
  //
  // ★★ Hier stand bis zum 2026-09-12 `host.endsWith('.saganta.de')` fest im
  // Quelltext, mit `https://n.saganta.de` als Ergebnis. Das ist derselbe Fehler,
  // den catalog.ts am 2026-09-06 für 17 Stellen abgelegt hat: eine fremde
  // Instanz als Vorbelegung. In jeder anderen Installation traf die Bedingung
  // nie zu, deshalb fiel es nicht auf. Getroffen hätte es genau den einen
  // Betreiber, dessen Domäne so endet, und dem hätte die App Links auf eine
  // Instanz ausgegeben, die ihm nicht gehört.
  const eigene = (env.PUBLIC_NOTIZEN_KURZ_BASIS ?? '').trim().replace(/\/$/, '');
  if (eigene) return eigene;
  return `${origin.replace(/\/$/, '')}/n`;
}
