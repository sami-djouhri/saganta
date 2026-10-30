/**
 * Welche Raeume der Auth-Service als Weiterleitungsziel gelten laesst.
 *
 * Eigene Datei, damit es pruefbar ist: `auth.ts` baut beim Import den
 * Postgres-Pool auf und verlangt `DATABASE_URL`, ein Test koennte es dort also
 * nur mit einer echten Datenbank anfassen.
 */

/**
 * Die Raeume, in denen man sich anmelden kann, abgeleitet aus `AUTH_LOGIN_URLS`.
 *
 * Form wie in `packages/auth` `leseLoginUrls`: `domain=https://host/login`,
 * mehrere durch Komma. Hier zaehlt nur der Origin der Adresse.
 *
 * Ein unbrauchbarer Eintrag wird uebergangen statt den Start zu verhindern --
 * dieselbe Linie wie `leseLoginUrls`: eine kaputte Zusatzangabe darf die
 * Anmeldung im Hauptraum nicht mitreissen.
 */
export function loginRaeume(roh: string | undefined): string[] {
  const raeume: string[] = [];
  for (const teil of (roh ?? '').split(',')) {
    const stelle = teil.indexOf('=');
    if (stelle < 1) continue;
    try {
      raeume.push(new URL(teil.slice(stelle + 1).trim()).origin);
    } catch {
      // uebergangen, siehe oben
    }
  }
  return raeume;
}

/**
 * Die vollstaendige Allowlist: die eingetragene Liste plus die Anmelde-Raeume.
 *
 * `trustedOrigins` hat bei better-auth ZWEI Rollen, und bis zum 2026-10-28
 * war hier nur eine bedacht. Die erste ist die Origin-Pruefung: dafuer braucht
 * die Liste tatsaechlich kein `.home`, weil die BFFs server-to-server rufen und
 * der Browser-Origin nie ankommt (so steht es auch in der die Projektregeln).
 * Die zweite ist die Pruefung von **Weiterleitungszielen**:
 * `originCheckMiddleware` haelt `body.redirectTo` gegen dieselbe Liste, und ein
 * `redirectTo` ist ein Browser-Ziel. `/forgot` uebergibt dort
 * `${url.origin}/reset`, unter `.home` also `https://shell.home.arpa/reset`
 * -- nicht gelistet, 403, kein Token, keine Mail.
 *
 * Nach aussen sah dieser Fehlschlag wie ein gelungener Reset aus: `/forgot`
 * meldet gegen Konto-Enumeration immer Erfolg, und `requestPasswordReset`
 * widerspricht erst ab Status 500. Der Owner stand am 2026-10-28 vor genau
 * diesem Bild -- Erfolgsmeldung, keine Mail, und in der Datenbank kein Token.
 *
 * Abgeleitet statt zweite Liste: wo man sich anmelden kann, dorthin darf auch
 * ein Reset-Link zeigen. Eine eigene Aufzaehlung neben `AUTH_LOGIN_URLS` waere
 * genau die Stelle, an der beim naechsten Raum einer vergessen wird -- und zwar
 * stumm, denn der Fehlschlag sieht wie ein Erfolg aus.
 */
export function vertrauteZiele(
  eingetragen: string | undefined,
  loginUrls: string | undefined,
  cookieDomain: string,
): string[] {
  // Ohne Cookie-Domaene gaebe die Vorlage `https://` ergeben, also Unsinn.
  // Dann bleibt die Liste leer, und better-auth vertraut nur der eigenen baseURL.
  const basis = eingetragen ?? (cookieDomain ? `https://${cookieDomain}` : '');
  return [
    ...new Set([...basis.split(',').map((o) => o.trim()), ...loginRaeume(loginUrls)].filter(Boolean)),
  ];
}
