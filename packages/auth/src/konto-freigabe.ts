/**
 * Erneute Passwortabfrage vor Konto-Aenderungen (Step-up).
 *
 * **Warum ueberhaupt.** Die Saganta-Sitzung haelt 90 Tage und gilt in allen
 * Apps. Das ist bequem und richtig, bedeutet aber: ein kurz unbeaufsichtigtes
 * Geraet reicht, um in einer beliebigen App auf „Konto" zu tippen. Was dort
 * moeglich ist, ist nicht mehr harmlos (Passwort aendern, spaeter Abo und
 * Kuendigung). Deshalb steht vor diesem einen Bereich eine zweite Tuer, und
 * zwar unabhaengig davon, wie lange die Anmeldung schon laeuft.
 *
 * **Warum nicht einfach die Sitzung erneuern.** Ein zweites `sign-in` wuerde
 * eine zweite Sitzung in der Datenbank anlegen. Nach ein paar Wochen
 * Kontobesuchen stehen dort Dutzende Karteileichen, von denen jede ein
 * gueltiger Zugang ist. Die Pruefung hier meldet die dabei entstandene Sitzung
 * deshalb sofort wieder ab und gibt nur „stimmt" oder „stimmt nicht" zurueck.
 *
 * **Der Nachweis ist ein signierter Zettel, kein Serverzustand.** Er haengt am
 * `sub`, laeuft nach `FREIGABE_DAUER_S` ab und wird mit demselben Geheimnis
 * signiert, mit dem die Backend-Token gestempelt werden. Ein Zettel fuer ein
 * anderes Konto passt nicht, und ein abgelaufener wird nicht mehr angenommen.
 */
import { createHmac, timingSafeEqual } from 'node:crypto';
import type { Cookies } from '@sveltejs/kit';
import type { BetterAuthConfig } from './better-auth.js';

/** Name des Freigabe-Cookies. Bewusst ohne `session` im Namen. */
export const FREIGABE_COOKIE = 'saganta_konto_frei';

/**
 * Wie lange eine Freigabe traegt.
 *
 * Zehn Minuten sind lang genug, um ein Passwort zu aendern und danach noch die
 * Abo-Seite anzusehen, und kurz genug, dass ein offen stehender Laptop nicht
 * den Rest des Tages ein offenes Konto bedeutet.
 */
export const FREIGABE_DAUER_S = 600;

/**
 * Prueft ein Passwort, ohne eine Sitzung zu hinterlassen.
 *
 * better-auth kennt keinen reinen „stimmt dieses Passwort"-Endpunkt; der
 * uebliche Weg ist ein `sign-in`, dessen Ergebnis man verwirft. Genau das
 * passiert hier, samt Aufraeumen: die Cookies der Probe-Anmeldung werden nicht
 * an den Browser gereicht, sondern benutzt, um dieselbe Sitzung sofort wieder
 * abzumelden.
 */
export async function pruefePasswort(
  cfg: BetterAuthConfig,
  email: string,
  passwort: string,
): Promise<{ ok: boolean; fehler?: string }> {
  let antwort: Response;
  try {
    antwort = await fetch(`${cfg.authServiceUrl}/api/auth/sign-in/email`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        accept: 'application/json',
        origin: new URL(cfg.authServiceUrl).origin,
      },
      body: JSON.stringify({ email, password: passwort }),
    });
  } catch {
    // Fail-closed: ist der Auth-Dienst nicht erreichbar, gibt es keine
    // Freigabe. Die Alternative waere, im Stoerungsfall durchzuwinken.
    return { ok: false, fehler: 'Anmeldedienst nicht erreichbar.' };
  }

  if (!antwort.ok) {
    return { ok: false, fehler: 'Passwort stimmt nicht.' };
  }

  // Die Probe-Sitzung sofort wieder einsammeln. Schlaegt das fehl, bleibt eine
  // Karteileiche zurueck; das ist unschoen, aber kein Grund, die Freigabe zu
  // verweigern, denn das Passwort war ja richtig.
  const kekse = antwort.headers.getSetCookie?.() ?? [];
  const kopf = kekse.map((k) => k.split(';')[0]).join('; ');
  if (kopf) {
    try {
      await fetch(`${cfg.authServiceUrl}/api/auth/sign-out`, {
        method: 'POST',
        headers: {
          cookie: kopf,
          'content-type': 'application/json',
          origin: new URL(cfg.authServiceUrl).origin,
        },
      });
    } catch {
      // bewusst still: siehe oben
    }
  }

  return { ok: true };
}

function unterschrift(sub: string, gueltigBis: number, geheimnis: string): string {
  return createHmac('sha256', geheimnis).update(`${sub}.${gueltigBis}`).digest('base64url');
}

/** Stellt den Freigabe-Zettel aus und legt ihn als Cookie ab. */
export function setzeFreigabe(
  cookies: Cookies,
  sub: string,
  geheimnis: string,
  sicher: boolean,
): void {
  const gueltigBis = Math.floor(Date.now() / 1000) + FREIGABE_DAUER_S;
  const wert = `${gueltigBis}.${unterschrift(sub, gueltigBis, geheimnis)}`;
  cookies.set(FREIGABE_COOKIE, wert, {
    path: '/',
    httpOnly: true,
    sameSite: 'lax',
    secure: sicher,
    maxAge: FREIGABE_DAUER_S,
    // ★ Bewusst **ohne** `domain`: die Freigabe gilt host-only, also nur auf
    // der Shell. Sie ueber die Registrar-Domain zu streuen wie das
    // Sitzungs-Cookie waere bequemer und genau falsch: eine Freigabe, die man
    // einmal erteilt hat, gaelte dann in jeder App der Suite.
  });
}

/** Ist eine gueltige Freigabe fuer diesen `sub` vorhanden? */
export function hatFreigabe(cookies: Cookies, sub: string, geheimnis: string): boolean {
  const roh = cookies.get(FREIGABE_COOKIE);
  if (!roh) return false;
  const trenner = roh.indexOf('.');
  if (trenner < 1) return false;

  const gueltigBis = Number(roh.slice(0, trenner));
  const mitgeschickt = roh.slice(trenner + 1);
  if (!Number.isFinite(gueltigBis) || gueltigBis < Math.floor(Date.now() / 1000)) return false;

  const erwartet = unterschrift(sub, gueltigBis, geheimnis);
  // Laengengleich vergleichen: `timingSafeEqual` wirft bei ungleicher Laenge,
  // statt abzulehnen.
  if (mitgeschickt.length !== erwartet.length) return false;
  return timingSafeEqual(Buffer.from(mitgeschickt), Buffer.from(erwartet));
}

/** Nimmt die Freigabe zurueck (nach Passwortwechsel oder auf Wunsch). */
export function loescheFreigabe(cookies: Cookies): void {
  cookies.delete(FREIGABE_COOKIE, { path: '/' });
}

/**
 * Die Konto-Adresse im Domain-Raum des Aufrufers.
 *
 * ★ Gleiche Falle wie bei der Anmeldung: wer unter `notizen.home.arpa` auf
 * „Konto" tippt und nach `https://saganta.de/konto` geschickt wird, landet in
 * einem Raum, in dem sein Sitzungs-Cookie nicht gilt, und steht vor einer
 * Anmeldemaske statt vor seinem Konto. Die Ableitung ist deshalb dieselbe wie
 * bei `anmeldeadresseFuer`, nur fuer einen anderen Pfad.
 *
 * `basis` ist die Vorgabe (etwa `https://saganta.de`), `raeume` die Zuordnung
 * aus `AUTH_KONTO_URLS` im Format `home.arpa=https://shell.home.arpa`.
 */
export function kontoadresseFuer(
  anfrageHost: string | undefined,
  basis: string,
  raeume: Record<string, string> = {},
): string {
  const pfad = '/konto';
  if (!anfrageHost) return `${basis}${pfad}`;
  const host = (anfrageHost.split(':')[0] ?? anfrageHost).trim().toLowerCase();
  for (const [domain, adresse] of Object.entries(raeume)) {
    if (host === domain || host.endsWith('.' + domain)) {
      return `${adresse.replace(/\/$/, '')}${pfad}`;
    }
  }
  return `${basis.replace(/\/$/, '')}${pfad}`;
}
