import { fail } from '@sveltejs/kit';
import { requestPasswordReset } from '@saganta/auth';
import { getAuthConfig } from '$lib/server/auth';
import { captchaOk, captchaEnabled } from '$lib/server/captcha';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
  return { captchaEnabled: captchaEnabled() };
};

export const actions: Actions = {
  default: async ({ request, url }) => {
    const form = await request.formData();
    const email = String(form.get('email') ?? '').trim();
    if (!email) {
      return fail(400, { email, error: 'E-Mail erforderlich.' });
    }
    if (!captchaOk(form.get('altcha') as string)) {
      return fail(400, { email, error: 'Sicherheitsprüfung fehlgeschlagen. Bitte erneut versuchen.' });
    }
    // Reset-Link führt auf die Shell-Seite /reset?token=... (siehe email.ts).
    await requestPasswordReset(getAuthConfig(), email, `${url.origin}/reset`);
    // Immer Erfolg melden (keine Account-Enumeration).
    return { sent: true, email };
  },
};
