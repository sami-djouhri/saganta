/**
 * Das Konto: ein Ort, und eine zweite Tuer davor.
 *
 * Bis 2026-09-18 lag die Passwortaenderung unter `/settings`, zwischen Theme
 * und Sprache. Das vermischte zwei verschiedene Dinge: das Aussehen aendert
 * jeder gern mal eben, das Konto nicht. Seit die Suite mehrere Konten traegt,
 * ist die Trennung keine Ordnungsfrage mehr, sondern eine Sicherheitsfrage.
 *
 * ★ Die Sitzung haelt 90 Tage und gilt in **allen** Apps (das ist der Sinn des
 * einheitlichen Logins). Genau deshalb reicht sie hier nicht: wer ein kurz
 * unbeaufsichtigtes Geraet in die Hand bekommt, koennte sonst aus einer
 * beliebigen App heraus das Passwort aendern und das Konto uebernehmen. Vor
 * diesem Bereich steht deshalb eine erneute Passwortabfrage, unabhaengig davon,
 * wie frisch die Anmeldung ist.
 */
import { env } from '$env/dynamic/private';
import { fail, redirect } from '@sveltejs/kit';
import {
  changePassword,
  applySetCookies,
  hatFreigabe,
  loescheFreigabe,
  pruefePasswort,
  setzeFreigabe,
} from '@saganta/auth';
import { backendSecret } from '$lib/shell-api';
import { getAuthConfig } from '$lib/server/auth';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, cookies }) => {
  if (!locals.user) throw redirect(303, '/login?next=/konto');

  return {
    // Ob die zweite Tuer offen ist, entscheidet der Server. Die Seite zeigt
    // danach entweder die Passwortabfrage oder das Konto, aber die Aktionen
    // pruefen es unabhaengig davon noch einmal selbst: eine Oberflaeche, die
    // etwas nicht anzeigt, hat es nicht verboten.
    freigegeben: hatFreigabe(cookies, locals.user.sub, backendSecret()),
    konto: {
      email: locals.user.email,
      name: locals.user.name ?? null,
      plan: locals.user.plan ?? 'free',
    },
  };
};

export const actions: Actions = {
  /** Zweite Tuer: Passwort erneut eingeben. */
  freischalten: async ({ request, locals, cookies, url }) => {
    if (!locals.user) return fail(401, { fehler: 'Nicht angemeldet.' });

    const daten = await request.formData();
    const passwort = String(daten.get('passwort') ?? '');
    if (!passwort) return fail(400, { fehler: 'Bitte das Passwort eingeben.' });

    const ergebnis = await pruefePasswort(getAuthConfig(), locals.user.email, passwort);
    if (!ergebnis.ok) {
      return fail(400, { fehler: ergebnis.fehler ?? 'Passwort stimmt nicht.' });
    }

    setzeFreigabe(cookies, locals.user.sub, backendSecret(), url.protocol === 'https:');
    throw redirect(303, '/konto');
  },

  /** Freigabe von Hand zurueckziehen (Knopf „Konto wieder sperren"). */
  sperren: async ({ cookies }) => {
    loescheFreigabe(cookies);
    throw redirect(303, '/konto');
  },

  passwortAendern: async ({ request, locals, cookies, url }) => {
    if (!locals.user) return fail(401, { pwFehler: 'Nicht angemeldet.' });
    // ★ Zweite Pruefung, unabhaengig von dem, was die Seite anzeigt. Ein
    // Formular laesst sich auch ohne die Oberflaeche abschicken.
    if (!hatFreigabe(cookies, locals.user.sub, backendSecret())) {
      return fail(403, { pwFehler: 'Bitte zuerst das Passwort eingeben.' });
    }

    const daten = await request.formData();
    const aktuell = String(daten.get('aktuellesPasswort') ?? '');
    const neu = String(daten.get('neuesPasswort') ?? '');
    const bestaetigung = String(daten.get('bestaetigung') ?? '');

    if (!aktuell || !neu) return fail(400, { pwFehler: 'Bitte beide Passwoerter angeben.' });
    if (neu.length < 8) {
      return fail(400, { pwFehler: 'Das neue Passwort braucht mindestens 8 Zeichen.' });
    }
    if (neu !== bestaetigung) {
      return fail(400, { pwFehler: 'Die Wiederholung stimmt nicht mit dem neuen Passwort ueberein.' });
    }
    if (neu === aktuell) {
      return fail(400, { pwFehler: 'Das neue Passwort ist dasselbe wie das alte.' });
    }

    const ergebnis = await changePassword(
      getAuthConfig(),
      request.headers.get('cookie') ?? '',
      aktuell,
      neu,
      true, // alle anderen Sitzungen beenden
    );
    if (!ergebnis.ok) {
      return fail(400, { pwFehler: ergebnis.error ?? 'Passwort aendern fehlgeschlagen.' });
    }

    // better-auth stellt beim Beenden der anderen Sitzungen ein frisches
    // Cookie aus, sonst waere man gleich selbst abgemeldet.
    applySetCookies(cookies, ergebnis.setCookies, url.host);
    // ★ Freigabe danach zurueckziehen. Wer das Passwort gewechselt hat, hat
    // seinen Kontobesuch erledigt; ein weiter offener Bereich waere eine
    // Bequemlichkeit ohne Gegenwert.
    loescheFreigabe(cookies);

    throw redirect(303, '/konto?pwOk=1');
  },
};
