<script lang="ts">
  import { enhance } from '$app/forms';
  import { Button, Icon } from '@saganta/ui';
  import type { ActionData, PageData } from './$types';

  interface Props {
    data: PageData;
    form: ActionData;
  }
  let { data, form }: Props = $props();

  // Dedup gegen Svelte-5 `each_key_duplicate`: dynamische Backend-Daten können
  // denselben id-Key doppelt liefern (z. B. Message-IDs über mehrere IMAP-Konten)
  // → Client-Hydration-Crash legt die Seite lahm. Eindeutige Keys erzwingen. (2026-06-28)
  function uniqueBy<T>(arr: readonly T[], key: (x: T) => unknown): T[] {
    const seen = new Set<unknown>();
    return arr.filter((x) => {
      const k = key(x);
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }

  let showConnect = $state(false);
  let showCompose = $state(false);
  let selectedProvider = $state('gmail');

  const failure = $derived(data.failures?.api);
  const opened = $derived(form && 'opened' in form ? form.opened : null);
  const actionError = $derived(form && 'error' in form ? form.error : null);

  function fmtDate(iso: string | null): string {
    if (!iso) return '';
    // timeZone pinnen: SSR-Container läuft auf UTC, Browser auf Europe/Berlin →
    // ohne Pinning Hydration-Mismatch (Lesson aus apps/news).
    return new Date(iso).toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Europe/Berlin',
    });
  }

  function sender(m: PageData['messages']['items'][number]): string {
    return m.from_name || m.from_addr || '(unbekannt)';
  }

  function buildHref(params: { account?: string; unread?: boolean; starred?: boolean }): string {
    const p = new URLSearchParams();
    const account = params.account ?? data.accountId;
    const unread = params.unread ?? data.unread;
    const starred = params.starred ?? data.starred;
    if (account) p.set('account', account);
    if (unread) p.set('unread', '1');
    if (starred) p.set('starred', '1');
    const qs = p.toString();
    return qs ? `/?${qs}` : '/';
  }

  const preset = $derived(data.providers.find((p) => p.key === selectedProvider));
</script>

<section class="space-y-6">
  <header class="flex flex-wrap items-end justify-between gap-3">
    <div class="space-y-1">
      <p class="font-mono text-sm uppercase tracking-widest text-muted">Saganta · Mail</p>
      <h1 class="font-display text-4xl leading-tight">Deine gebündelte Inbox.</h1>
      <p class="text-muted">
        {data.messages.total} Nachrichten aus {data.accounts.length} verbundenen Konten.
      </p>
    </div>
    <div class="flex gap-2">
      <Button
        variant="ghost"
        size="sm"
        onclick={() => (showCompose = !showCompose)}
        disabled={data.accounts.length === 0}
      >
        <Icon name="pen" size={15} /> Schreiben
      </Button>
      <Button variant="primary" size="sm" onclick={() => (showConnect = !showConnect)}>
        <Icon name="plus" size={15} /> Konto verbinden
      </Button>
    </div>
  </header>

  {#if failure}
    <p class="rounded-md border border-warm-700 bg-warm-700/10 px-3 py-2 text-sm text-warm-500">
      mail-api nicht erreichbar: {failure}
    </p>
  {/if}
  {#if actionError}
    <p class="rounded-md border border-warm-700 bg-warm-700/10 px-3 py-2 text-sm text-warm-500">
      {actionError}
    </p>
  {/if}
  {#if form && 'sent' in form && form.sent}
    <p class="rounded-md border border-accent-700 bg-accent-700/10 px-3 py-2 text-sm text-accent-300">
      Gesendet.
    </p>
  {/if}

  {#if showConnect}
    <form
      method="POST"
      action="?/addAccount"
      use:enhance={() => async ({ update }) => {
        await update();
        showConnect = false;
      }}
      class="space-y-3 rounded-lg border border-border bg-surface-2 p-4"
    >
      <h2 class="font-display text-xl">Externes Konto verbinden</h2>
      <p class="text-sm text-muted">
        Deine Zugangsdaten werden verschlüsselt gespeichert. Versand läuft über den Anbieter selbst,
        nie über Saganta.
      </p>
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="space-y-1">
          <span class="text-sm text-muted">Anbieter</span>
          <select
            name="provider"
            bind:value={selectedProvider}
            class="w-full rounded-md border border-border bg-surface px-2 py-1.5"
          >
            {#each uniqueBy(data.providers, (x) => x.key) as p (p.key)}
              <option value={p.key}>{p.key}</option>
            {/each}
            <option value="custom">custom (manuell)</option>
          </select>
        </label>
        <label class="space-y-1">
          <span class="text-sm text-muted">E-Mail-Adresse</span>
          <input
            name="email"
            type="email"
            required
            class="w-full rounded-md border border-border bg-surface px-2 py-1.5"
          />
        </label>
        <label class="space-y-1">
          <span class="text-sm text-muted">App-Passwort</span>
          <input
            name="password"
            type="password"
            required
            class="w-full rounded-md border border-border bg-surface px-2 py-1.5"
          />
        </label>
        <label class="space-y-1">
          <span class="text-sm text-muted">Anzeigename (optional)</span>
          <input
            name="display_name"
            class="w-full rounded-md border border-border bg-surface px-2 py-1.5"
          />
        </label>
      </div>

      {#if preset}
        <p class="text-xs text-muted">
          IMAP {preset.imap_host}:{preset.imap_port} · SMTP {preset.smtp_host}:{preset.smtp_port}
          {#if preset.note}<br />{preset.note}{/if}
        </p>
      {:else}
        <div class="grid gap-3 sm:grid-cols-2">
          <input name="imap_host" placeholder="IMAP-Host" required class="rounded-md border border-border bg-surface px-2 py-1.5" />
          <input name="imap_port" placeholder="IMAP-Port (993)" required class="rounded-md border border-border bg-surface px-2 py-1.5" />
          <input name="smtp_host" placeholder="SMTP-Host" required class="rounded-md border border-border bg-surface px-2 py-1.5" />
          <input name="smtp_port" placeholder="SMTP-Port (465)" required class="rounded-md border border-border bg-surface px-2 py-1.5" />
        </div>
      {/if}

      <Button type="submit" variant="primary">Verbinden &amp; testen</Button>
    </form>
  {/if}

  {#if showCompose && data.accounts.length > 0}
    <form
      method="POST"
      action="?/send"
      use:enhance={() => async ({ update }) => {
        await update();
        showCompose = false;
      }}
      class="space-y-3 rounded-lg border border-border bg-surface-2 p-4"
    >
      <h2 class="font-display text-xl">Neue Nachricht</h2>
      <label class="block space-y-1">
        <span class="text-sm text-muted">Von</span>
        <select name="account_id" class="w-full rounded-md border border-border bg-surface px-2 py-1.5">
          {#each data.accounts as a (a.id)}
            <option value={a.id}>{a.email}</option>
          {/each}
        </select>
      </label>
      <input name="to" placeholder="An (Komma-getrennt)" required class="w-full rounded-md border border-border bg-surface px-2 py-1.5" />
      <input name="cc" placeholder="Cc (optional, Komma-getrennt)" class="w-full rounded-md border border-border bg-surface px-2 py-1.5" />
      <input name="subject" placeholder="Betreff" class="w-full rounded-md border border-border bg-surface px-2 py-1.5" />
      <textarea name="body" rows="6" placeholder="Text…" class="w-full rounded-md border border-border bg-surface px-2 py-1.5"></textarea>
      <Button type="submit" variant="primary">Senden</Button>
    </form>
  {/if}

  <!-- Verbundene Konten -->
  {#if data.accounts.length > 0}
    <div class="flex flex-wrap gap-2">
      {#each data.accounts as a (a.id)}
        <div class="flex items-center gap-2 rounded-full border border-border px-3 py-1 text-sm {a.enabled
          ? ''
          : 'opacity-60'}">
          <span>{a.email}</span>
          {#if !a.enabled}<span class="text-xs text-muted">pausiert</span>{/if}
          {#if a.last_error}
            <span title={a.last_error} class="text-warm-500"><Icon name="alert-triangle" size={14} label="Sync-Fehler" /></span>
          {/if}
          <form method="POST" action="?/sync" use:enhance>
            <input type="hidden" name="account_id" value={a.id} />
            <button class="text-muted transition-colors duration-fast ease-saganta hover:text-text" title="Jetzt synchronisieren" aria-label="Jetzt synchronisieren"><Icon name="refresh-cw" size={15} /></button>
          </form>
          <form method="POST" action="?/toggleEnabled" use:enhance>
            <input type="hidden" name="account_id" value={a.id} />
            <input type="hidden" name="enabled" value={String(!a.enabled)} />
            <button class="text-muted transition-colors duration-fast ease-saganta hover:text-text" title={a.enabled ? 'Konto pausieren' : 'Konto fortsetzen'} aria-label={a.enabled ? 'Konto pausieren' : 'Konto fortsetzen'}><Icon name="power" size={15} /></button>
          </form>
          <form method="POST" action="?/deleteAccount" use:enhance>
            <input type="hidden" name="account_id" value={a.id} />
            <button class="text-muted transition-colors duration-fast ease-saganta hover:text-warm-500" title="Konto entfernen" aria-label="Konto entfernen"><Icon name="x" size={15} /></button>
          </form>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Filter -->
  <nav class="flex flex-wrap items-center gap-2 text-sm">
    <a
      href={buildHref({ account: '', unread: false, starred: false })}
      class="rounded-full border px-3 py-1 {!data.accountId && !data.unread && !data.starred
        ? 'border-accent-500 text-accent-300'
        : 'border-border text-muted hover:text-text'}"
    >
      Alle
    </a>
    <a
      href={buildHref({ unread: !data.unread })}
      class="rounded-full border px-3 py-1 {data.unread
        ? 'border-accent-500 text-accent-300'
        : 'border-border text-muted hover:text-text'}"
    >
      Ungelesen
    </a>
    <a
      href={buildHref({ starred: !data.starred })}
      class="inline-flex items-center gap-1 rounded-full border px-3 py-1 transition-colors duration-fast ease-saganta {data.starred
        ? 'border-accent-500 text-accent-300'
        : 'border-border text-muted hover:text-text'}"
    >
      <Icon name="star" size={13} filled={data.starred} /> Markiert
    </a>
  </nav>

  <!-- Geöffnete Nachricht -->
  {#if opened}
    <article class="space-y-2 rounded-lg border border-accent-700 bg-surface-2 p-4">
      <h2 class="font-display text-2xl">{opened.subject || '(kein Betreff)'}</h2>
      <p class="text-sm text-muted">{opened.from_addr} · {fmtDate(opened.date)}</p>
      {#if opened.text}
        <pre class="whitespace-pre-wrap font-sans text-sm">{opened.text}</pre>
      {:else if opened.html}
        <p class="text-sm text-muted">(nur HTML-Inhalt: Vorschau folgt)</p>
      {:else}
        <p class="text-sm text-muted">(leerer Inhalt)</p>
      {/if}
    </article>
  {/if}

  <!-- Nachrichtenliste -->
  <ul class="divide-y divide-border rounded-lg border border-border">
    {#each uniqueBy(data.messages.items, (x) => x.id) as m (m.id)}
      <li class="flex items-start gap-3 px-4 py-3 {m.is_read ? 'opacity-70' : ''}">
        <form method="POST" action="?/setState" use:enhance>
          <input type="hidden" name="message_id" value={m.id} />
          <input type="hidden" name="is_starred" value={(!m.is_starred).toString()} />
          <button class="transition-colors duration-fast ease-saganta {m.is_starred ? 'text-warm-500' : 'text-muted hover:text-text'}" title="Markieren" aria-label="Markieren">
            <Icon name="star" size={18} filled={m.is_starred} />
          </button>
        </form>
        <div class="min-w-0 flex-1">
          <form method="POST" action="?/body" use:enhance>
            <input type="hidden" name="message_id" value={m.id} />
            <button class="block w-full text-left">
              <div class="flex items-baseline justify-between gap-2">
                <span class="truncate font-medium {m.is_read ? '' : 'text-text'}">{sender(m)}</span>
                <span class="shrink-0 text-xs text-muted">{fmtDate(m.date)}</span>
              </div>
              <div class="truncate text-sm {m.is_read ? 'text-muted' : 'text-text'}">
                {m.subject || '(kein Betreff)'}
              </div>
              <div class="text-xs text-muted">{m.account_email}</div>
            </button>
          </form>
        </div>
        <form method="POST" action="?/setState" use:enhance>
          <input type="hidden" name="message_id" value={m.id} />
          <input type="hidden" name="is_read" value={(!m.is_read).toString()} />
          <button class="shrink-0 text-xs text-muted hover:text-text" title={m.is_read ? 'Als ungelesen' : 'Als gelesen'}>
            {m.is_read ? '○' : '●'}
          </button>
        </form>
      </li>
    {:else}
      <li class="px-4 py-10 text-center text-muted">
        {data.accounts.length === 0
          ? 'Noch kein Konto verbunden: oben rechts „+ Konto verbinden".'
          : 'Keine Nachrichten. Konto synchronisieren (⟳) oder Filter ändern.'}
      </li>
    {/each}
  </ul>
</section>
