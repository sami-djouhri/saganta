import { fail, redirect } from '@sveltejs/kit';
import { resetPassword } from '@saganta/auth';
import { getAuthConfig } from '$lib/server/auth';
import { captchaOk, captchaEnabled } from '$lib/server/captcha';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ url }) => {
  // Token kommt aus dem Mail-Link (/reset?token=...). Fehlt er → ungültiger Aufruf.
  const token = url.searchParams.get('token') ?? '';
  return { hasToken: Boolean(token), token, captchaEnabled: captchaEnabled() };
};

export const actions: Actions = {
  default: async ({ request }) => {
    const form = await request.formData();
    const token = String(form.get('token') ?? '');
    const password = String(form.get('password') ?? '');
    const confirm = String(form.get('confirm') ?? '');

    if (!token) {
      return fail(400, { error: 'Ungültiger oder fehlender Reset-Link.' });
    }
    if (!captchaOk(form.get('altcha') as string)) {
      return fail(400, { error: 'Sicherheitsprüfung fehlgeschlagen. Bitte erneut versuchen.' });
    }
    if (password.length < 8) {
      return fail(400, { error: 'Passwort muss mindestens 8 Zeichen haben.' });
    }
    if (password !== confirm) {
      return fail(400, { error: 'Die Passwörter stimmen nicht überein.' });
    }

    const result = await resetPassword(getAuthConfig(), token, password);
    if (!result.ok) {
      return fail(400, {
        error: result.error ?? 'Zurücksetzen fehlgeschlagen, der Link ist evtl. abgelaufen.',
      });
    }

    redirect(303, '/login?reset=1');
  },
};
