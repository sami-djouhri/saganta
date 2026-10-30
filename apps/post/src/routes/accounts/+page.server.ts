import { fail, redirect } from '@sveltejs/kit';
import {
  listMailAccounts,
  listMailProviders,
  addMailAccount,
  deleteMailAccount,
  syncMailAccount,
  setMailAccountEnabled,
  listOAuthAnbieter,
  startOAuth,
  type MailAccount,
  type MailProviderPreset,
  type OAuthAnbieter,
} from '$lib/post-api';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch, url }) => {
  const empty = {
    accounts: [] as MailAccount[],
    providers: [] as MailProviderPreset[],
    oauthAnbieter: [] as OAuthAnbieter[],
    verbunden: url.searchParams.get('verbunden') ?? '',
    oauthFehler: url.searchParams.get('oauth_fehler') ?? '',
    failed: false,
  };
  if (!locals.user) return empty;
  try {
    const [accounts, providers, oauthAnbieter] = await Promise.all([
      listMailAccounts(locals.user, fetch),
      listMailProviders(locals.user, fetch),
      // Fail-soft und getrennt: ist OAuth2 nicht konfiguriert, kommt eine leere
      // Liste, und die Oberflaeche zeigt den Weg schlicht nicht an. Ein Fehler
      // hier darf die Kontenliste nicht kippen.
      listOAuthAnbieter(locals.user, fetch).catch(() => [] as OAuthAnbieter[]),
    ]);
    return { ...empty, accounts, providers, oauthAnbieter, failed: false };
  } catch {
    return { ...empty, failed: true };
  }
};

export const actions: Actions = {
  /** Schritt 1 des OAuth2-Flusses: zum Anbieter weiterleiten. */
  oauthStart: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const anbieter = String(fd.get('anbieter') ?? '').trim();
    if (!anbieter) return fail(400, { error: 'Anbieter fehlt.' });
    try {
      const { url } = await startOAuth(locals.user, fetch, anbieter);
      // 303 auf eine fremde Adresse: der Nutzer meldet sich beim Anbieter an,
      // nicht hier. Zurueck kommt er ueber /oauth/rueckleitung.
      redirect(303, url);
    } catch (err) {
      if (err && typeof err === 'object' && 'status' in err && 'location' in err) throw err;
      return fail(502, { error: String(err).slice(0, 200) });
    }
  },

  // Konto verbinden: mail-api testet den IMAP-Login vor dem Speichern.
  add: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const payload: Record<string, unknown> = {
      email: String(fd.get('email') ?? '').trim(),
      password: String(fd.get('password') ?? ''),
      provider: String(fd.get('provider') ?? 'custom'),
    };
    const dn = String(fd.get('display_name') ?? '').trim();
    if (dn) payload.display_name = dn;
    for (const k of ['imap_host', 'smtp_host', 'imap_username', 'smtp_username'] as const) {
      const v = String(fd.get(k) ?? '').trim();
      if (v) payload[k] = v;
    }
    for (const k of ['imap_port', 'smtp_port'] as const) {
      const v = String(fd.get(k) ?? '').trim();
      if (v) payload[k] = Number(v);
    }
    try {
      const account = await addMailAccount(locals.user, fetch, payload);
      return { added: account };
    } catch (err) {
      return fail(400, { error: String(err) });
    }
  },

  delete: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { error: 'nicht angemeldet' });
    const id = Number((await request.formData()).get('account_id'));
    if (!Number.isInteger(id)) return fail(400, { error: 'ungültige account_id' });
    try {
      await deleteMailAccount(locals.user, fetch, id);
      return { deleted: id };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  sync: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { error: 'nicht angemeldet' });
    const id = Number((await request.formData()).get('account_id'));
    if (!Number.isInteger(id)) return fail(400, { error: 'ungültige account_id' });
    try {
      const account = await syncMailAccount(locals.user, fetch, id);
      return { synced: account };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  toggle: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = Number(fd.get('account_id'));
    if (!Number.isInteger(id)) return fail(400, { error: 'ungültige account_id' });
    const enabled = fd.get('enabled') === 'true';
    try {
      const account = await setMailAccountEnabled(locals.user, fetch, id, enabled);
      return { toggled: account };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },
};
