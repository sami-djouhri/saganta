import { env } from '$env/dynamic/private';
import { fail } from '@sveltejs/kit';
import {
  backendSecret,
  mailApiFetch,
  mailApiToken,
  type Account,
  type Message,
  type MessageBody,
  type MessagePage,
  type ProviderPreset,
} from '$lib/mail-api';
import type { Actions, PageServerLoad } from './$types';

const EMPTY_PAGE: MessagePage = { items: [], offset: 0, limit: 0, total: 0, next_offset: null };

function ctx(locals: App.Locals) {
  if (!locals.user || !env.MAIL_API_BASE_URL) return null;
  return {
    base: env.MAIL_API_BASE_URL,
    token: mailApiToken(locals.user, backendSecret()),
  };
}

export const load: PageServerLoad = async ({ locals, fetch, url }) => {
  const failures: { api?: string } = {};
  let messages: MessagePage = EMPTY_PAGE;
  let accounts: Account[] = [];
  let providers: ProviderPreset[] = [];

  const accountId = url.searchParams.get('account') ?? '';
  const unread = url.searchParams.get('unread') === '1';
  const starred = url.searchParams.get('starred') === '1';

  const c = ctx(locals);
  if (c) {
    const params = new URLSearchParams();
    if (accountId) params.set('account_id', accountId);
    if (unread) params.set('unread', 'true');
    if (starred) params.set('starred', 'true');
    const qs = params.toString();
    try {
      [messages, accounts, providers] = await Promise.all([
        mailApiFetch<MessagePage>(c.base, `/api/mail/messages${qs ? `?${qs}` : ''}`, c.token, fetch),
        mailApiFetch<Account[]>(c.base, '/api/mail/accounts', c.token, fetch),
        mailApiFetch<ProviderPreset[]>(c.base, '/api/mail/providers', c.token, fetch),
      ]);
    } catch (err) {
      failures.api = String(err);
    }
  }

  return { messages, accounts, providers, failures, accountId, unread, starred };
};

export const actions: Actions = {
  // Konto verbinden: Backend testet IMAP-Login vor dem Speichern.
  addAccount: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { error: 'not authenticated' });
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
      const account = await mailApiFetch<Account>(c.base, '/api/mail/accounts', c.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      return { added: account };
    } catch (err) {
      return fail(400, { error: String(err) });
    }
  },

  deleteAccount: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { error: 'not authenticated' });
    const id = Number((await request.formData()).get('account_id'));
    if (!Number.isInteger(id)) return fail(400, { error: 'bad account_id' });
    try {
      await mailApiFetch(c.base, `/api/mail/accounts/${id}`, c.token, fetch, { method: 'DELETE' });
      return { deleted: id };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  sync: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { error: 'not authenticated' });
    const id = Number((await request.formData()).get('account_id'));
    if (!Number.isInteger(id)) return fail(400, { error: 'bad account_id' });
    try {
      const account = await mailApiFetch<Account>(
        c.base,
        `/api/mail/accounts/${id}/sync`,
        c.token,
        fetch,
        { method: 'POST' },
      );
      return { synced: account };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  toggleEnabled: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { error: 'not authenticated' });
    const fd = await request.formData();
    const id = Number(fd.get('account_id'));
    if (!Number.isInteger(id)) return fail(400, { error: 'bad account_id' });
    const enabled = fd.get('enabled') === 'true';
    try {
      const account = await mailApiFetch<Account>(
        c.base,
        `/api/mail/accounts/${id}/enabled`,
        c.token,
        fetch,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled }),
        },
      );
      return { toggled: account };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  setState: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { error: 'not authenticated' });
    const fd = await request.formData();
    const id = Number(fd.get('message_id'));
    if (!Number.isInteger(id)) return fail(400, { error: 'bad message_id' });
    const body: Record<string, boolean> = {};
    if (fd.has('is_read')) body.is_read = fd.get('is_read') === 'true';
    if (fd.has('is_starred')) body.is_starred = fd.get('is_starred') === 'true';
    try {
      const message = await mailApiFetch<Message>(
        c.base,
        `/api/mail/messages/${id}/state`,
        c.token,
        fetch,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        },
      );
      return { message };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // Body live nachladen (nicht gecacht).
  body: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { error: 'not authenticated' });
    const id = Number((await request.formData()).get('message_id'));
    if (!Number.isInteger(id)) return fail(400, { error: 'bad message_id' });
    try {
      const msg = await mailApiFetch<MessageBody>(
        c.base,
        `/api/mail/messages/${id}/body`,
        c.token,
        fetch,
      );
      return { opened: msg };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // Versand AUSSCHLIESSLICH über Origin-SMTP des Kontos.
  send: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { error: 'not authenticated' });
    const fd = await request.formData();
    const accountId = Number(fd.get('account_id'));
    const splitAddrs = (raw: string) =>
      raw
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
    const to = splitAddrs(String(fd.get('to') ?? ''));
    const cc = splitAddrs(String(fd.get('cc') ?? ''));
    if (!Number.isInteger(accountId)) return fail(400, { error: 'bad account_id' });
    if (to.length === 0) return fail(400, { error: 'kein Empfänger' });
    const payload = {
      account_id: accountId,
      to,
      cc,
      subject: String(fd.get('subject') ?? ''),
      body: String(fd.get('body') ?? ''),
    };
    try {
      await mailApiFetch(c.base, '/api/mail/send', c.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      return { sent: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },
};
