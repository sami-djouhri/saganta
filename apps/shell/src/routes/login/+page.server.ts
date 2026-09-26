import { fail, redirect } from '@sveltejs/kit';
import {
  applySetCookies,
  resendVerificationEmail,
  sicheresZiel,
  signInEmail,
  signUpEmail,
} from '@saganta/auth';
import { getAuthConfig } from '$lib/server/auth';
import { captchaOk, captchaEnabled } from '$lib/server/captcha';
import type { Actions, PageServerLoad } from './$types';

// App-interne Pfade und absolute Ziele im eigenen Domain-Raum zulassen
// (offene-Redirect-Schutz). Der zweite Fall ist noetig, seit die Suite unter
// zwei Namen laeuft: wer aus tagebuch.home.arpa zur Anmeldung geschickt
// wird, soll danach dorthin zurueck und nicht in der Shell stranden.
// Die Pruefung liegt in @saganta/auth, damit es eine Wahrheit dafuer gibt.
function safeNext(raw: string | null, eigenerHost?: string): string {
  return sicheresZiel(raw, eigenerHost);
}

// Absoluter Callback für Verifizierungs-Mail (nach Klick → Startseite mit Banner).
function verifyCallback(origin: string): string {
  return `${origin}/?verified=1`;
}

export const load: PageServerLoad = async ({ locals, url }) => {
  // Bereits eingeloggt → direkt weiter.
  if (locals.user) {
    redirect(303, safeNext(url.searchParams.get('next'), url.host));
  }
  return {
    next: safeNext(url.searchParams.get('next'), url.host),
    captchaEnabled: captchaEnabled(),
    // Nach erfolgreichem Passwort-Reset (/reset → /login?reset=1).
    resetDone: url.searchParams.get('reset') === '1',
    // Landing-CTAs verlinken auf /login?mode=register → direkt im Register-Tab starten.
    initialMode: url.searchParams.get('mode') === 'register' ? 'register' : 'login',
    // Pricing-CTAs hängen ?plan=… an (z. B. unlimited). Slug durchreichen; das Label
    // löst die Seite über den Katalog auf. Bleibt bis zur späteren Abrechnung erhalten.
    selectedPlan: (url.searchParams.get('plan') ?? '').trim().toLowerCase() || null,
  };
};

export const actions: Actions = {
  login: async ({ request, cookies, url }) => {
    const form = await request.formData();
    const email = String(form.get('email') ?? '').trim();
    const password = String(form.get('password') ?? '');
    const next = safeNext((form.get('next') as string) ?? url.searchParams.get('next'), url.host);

    if (!email || !password) {
      return fail(400, { mode: 'login', email, error: 'E-Mail und Passwort erforderlich.' });
    }
    if (!captchaOk(form.get('altcha') as string)) {
      return fail(400, { mode: 'login', email, error: 'Sicherheitsprüfung fehlgeschlagen. Bitte erneut versuchen.' });
    }

    const result = await signInEmail(getAuthConfig(), email, password);
    if (!result.ok) {
      // Unverifizierte Mail: Verifizierung erneut anstoßen + gezielten Hinweis zeigen.
      if (result.code === 'EMAIL_NOT_VERIFIED') {
        await resendVerificationEmail(getAuthConfig(), email, verifyCallback(url.origin));
        return fail(403, {
          mode: 'login',
          email,
          unverified: true,
          error:
            'Diese E-Mail ist noch nicht bestätigt. Wir haben dir den Bestätigungslink erneut geschickt.',
        });
      }
      return fail(401, { mode: 'login', email, error: result.error ?? 'Anmeldung fehlgeschlagen.' });
    }

    applySetCookies(cookies, result.setCookies, url.host);
    redirect(303, next);
  },

  register: async ({ request, cookies, url }) => {
    const form = await request.formData();
    const email = String(form.get('email') ?? '').trim();
    const password = String(form.get('password') ?? '');
    const name = String(form.get('name') ?? '').trim();
    const next = safeNext((form.get('next') as string) ?? url.searchParams.get('next'), url.host);
    // Tarifwahl aus dem Pricing-Funnel (?plan=…). Noch keine Abrechnung verdrahtet;
    // wir behalten den Wunsch nur fürs spätere Onboarding/Billing im Blick.
    const plan = String(form.get('plan') ?? '').trim().toLowerCase() || null;
    if (plan) console.info(`[signup] gewünschter Tarif: ${plan} (${email})`);

    if (!email || !password || !name) {
      return fail(400, {
        mode: 'register',
        email,
        name,
        error: 'Name, E-Mail und Passwort erforderlich.',
      });
    }
    if (!captchaOk(form.get('altcha') as string)) {
      return fail(400, {
        mode: 'register',
        email,
        name,
        error: 'Sicherheitsprüfung fehlgeschlagen. Bitte erneut versuchen.',
      });
    }
    if (password.length < 8) {
      return fail(400, {
        mode: 'register',
        email,
        name,
        error: 'Passwort muss mindestens 8 Zeichen haben.',
      });
    }

    const result = await signUpEmail(getAuthConfig(), email, password, name);
    if (!result.ok) {
      return fail(400, {
        mode: 'register',
        email,
        name,
        error: result.error ?? 'Registrierung fehlgeschlagen.',
      });
    }

    // requireEmailVerification: Signup setzt KEINE Login-Session. Statt Redirect
    // den 'Bitte E-Mail bestätigen'-Zustand zeigen. Die Verifizierungs-Mail wurde
    // vom Auth-Service automatisch versendet (emailVerification.sendOnSignUp).
    applySetCookies(cookies, result.setCookies, url.host);
    return { registered: true, email, next };
  },

  resend: async ({ request, url }) => {
    const form = await request.formData();
    const email = String(form.get('email') ?? '').trim();
    if (!email) {
      return fail(400, { mode: 'login', error: 'E-Mail erforderlich.' });
    }
    await resendVerificationEmail(getAuthConfig(), email, verifyCallback(url.origin));
    return { resent: true, email };
  },
};
