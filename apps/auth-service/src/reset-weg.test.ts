/**
 * Der Weg „Passwort vergessen" -- und zwar die zwei Stellen, an denen er am
 * 2026-10-28 brach, ohne dass irgendwo ein Fehler sichtbar wurde.
 *
 * Der Befund: Der Owner stiess einen Reset an, bekam eine Erfolgsmeldung, keine
 * Mail, und in der Datenbank lag kein Token. Das Log nannte als einziges
 * `ERROR [Better Auth]: Invalid redirectURL: https://shell.home.arpa/reset`.
 *
 * Zwei unabhaengige Stufen trugen dazu bei, und beide haben hier eine
 * Gegenprobe, weil keine von ihnen einen Ablauf aendert, an dem ein
 * bestehender Test haengt:
 *
 *   1. `vertrauteZiele` -- der Anmelde-Raum fehlte in der Allowlist, gegen die
 *      better-auth `redirectTo` prueft. 403, kein Token, keine Mail.
 *   2. `resetLink` -- selbst mit bestandener Pruefung zeigte der Link in der
 *      Mail auf BETTER_AUTH_URL (`saganta.de`), und das ist seit dem
 *      2026-10-21 ein 404-Riegel.
 *
 * Beide Fehler sehen von aussen wie ein gelungener Reset aus: `/forgot` meldet
 * gegen Konto-Enumeration immer Erfolg. Genau deshalb braucht es Tests und
 * nicht nur einen Rauchtest.
 */
import { describe, expect, it } from 'vitest';
import { loginRaeume, vertrauteZiele } from './raeume.js';
import { resetLink, resetZielAus } from './email.js';

/** So baut better-auth das `url` fuer `sendResetPassword` (api/routes/password.mjs). */
function betterAuthUrl(redirectTo: string, token = 'tok123'): string {
  return `https://saganta.de/api/auth/reset-password/${token}?callbackURL=${encodeURIComponent(redirectTo)}`;
}

describe('vertrauteZiele: der Anmelde-Raum ist auch ein erlaubtes Reset-Ziel', () => {
  const eingetragen = 'http://saganta-auth:3000,https://saganta.de,https://shell.saganta.de';
  const loginUrls = 'home.arpa=https://shell.home.arpa/login';

  // Die Gegenprobe zu Stufe 1. Wird rot, sobald jemand die Ableitung aus
  // AUTH_LOGIN_URLS wieder entfernt -- etwa mit Verweis auf die (fuer die
  // Origin-Rolle richtige) Doku-Aussage, `AUTH_TRUSTED_ORIGINS` brauche kein
  // `.home`. Sie gilt fuer Origins, nicht fuer Weiterleitungsziele.
  it('nimmt den .home-Raum auf, in dem die Anmeldung stattfindet', () => {
    expect(vertrauteZiele(eingetragen, loginUrls, 'saganta.de')).toContain(
      'https://shell.home.arpa',
    );
  });

  it('behaelt jeden eingetragenen Eintrag', () => {
    const ziele = vertrauteZiele(eingetragen, loginUrls, 'saganta.de');
    for (const eintrag of eingetragen.split(',')) expect(ziele).toContain(eintrag);
  });

  it('fuehrt keinen Eintrag doppelt', () => {
    const ziele = vertrauteZiele('https://shell.home.arpa', loginUrls, 'saganta.de');
    expect(ziele.filter((z) => z === 'https://shell.home.arpa')).toHaveLength(1);
  });

  it('faellt ohne eingetragene Liste auf die Cookie-Domaene zurueck', () => {
    expect(vertrauteZiele(undefined, undefined, 'saganta.de')).toEqual(['https://saganta.de']);
  });

  it('bleibt ohne beides leer, statt https:// zu erfinden', () => {
    expect(vertrauteZiele(undefined, undefined, '')).toEqual([]);
  });

  it('uebergeht einen unbrauchbaren Login-Eintrag, statt den Start zu verhindern', () => {
    expect(loginRaeume('kaputt,home.arpa=keine-url,x.home=https://x.home/login')).toEqual([
      'https://x.home',
    ]);
  });
});

describe('resetZielAus: der Raum des Aufrufers steckt im callbackURL', () => {
  // Die Gegenprobe zu Stufe 2. Wird rot, sobald der Link wieder aus einer
  // festgeschriebenen Domaene gebaut wird statt aus dem Raum des Aufrufers.
  it('holt das Ziel aus dem url, das better-auth uebergibt', () => {
    expect(resetZielAus(betterAuthUrl('https://shell.home.arpa/reset'))).toBe(
      'https://shell.home.arpa/reset',
    );
  });

  it('nimmt NICHT die Basis des url -- die ist seit dem 2026-10-21 ein 404-Riegel', () => {
    const ziel = resetZielAus(betterAuthUrl('https://shell.home.arpa/reset'));
    expect(ziel).not.toContain('saganta.de');
  });

  it('gibt null ohne url (dann greift der Rueckfall auf WEB_BASE_URL)', () => {
    expect(resetZielAus(undefined)).toBeNull();
  });

  it('gibt null ohne callbackURL', () => {
    expect(resetZielAus('https://saganta.de/api/auth/reset-password/tok123')).toBeNull();
  });

  it('gibt null bei relativem Ziel -- in einer Mail ist ein Pfad unbrauchbar', () => {
    // better-auth laesst relative Pfade durch (`allowRelativePaths`).
    expect(resetZielAus(betterAuthUrl('/reset'))).toBeNull();
  });

  it('gibt null bei unbrauchbarem Protokoll', () => {
    expect(resetZielAus(betterAuthUrl('javascript:alert(1)'))).toBeNull();
  });
});

describe('resetLink: der fertige Link fuer die Mail', () => {
  // ⚠️ `WEB_BASE_URL` liest email.ts auf Modulebene, der Wert steht beim Import
  // fest. Diese Tests setzen ihn deshalb NICHT -- sie pruefen den Pfad, auf den
  // es ankommt (Raum des Aufrufers) und dass der Rueckfall nicht wirft. Ein
  // `process.env.…` mitten im Test waere wirkungslos und wuerde so aussehen,
  // als decke er den Rueckfall mit ab.
  it('liegt im Raum des Aufrufers und traegt den Token', () => {
    const link = resetLink('tok123', betterAuthUrl('https://shell.home.arpa/reset'));
    expect(link).toBe('https://shell.home.arpa/reset?token=tok123');
  });

  it('faellt ohne url zurueck, statt zu werfen', () => {
    expect(() => resetLink('tok123')).not.toThrow();
    expect(resetLink('tok123')).toContain('token=tok123');
  });

  it('kodiert einen Token mit Sonderzeichen', () => {
    const link = resetLink('a+b/c=', betterAuthUrl('https://shell.home.arpa/reset'));
    expect(link).toContain('token=a%2Bb%2Fc%3D');
    expect(new URL(link).searchParams.get('token')).toBe('a+b/c=');
  });
});
