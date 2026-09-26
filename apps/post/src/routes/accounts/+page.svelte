<script lang="ts">
  import { enhance } from '$app/forms';
  import { Button, Icon } from '@saganta/ui';
  import type { ActionData, PageData } from './$types';

  interface Props {
    data: PageData;
    form: ActionData;
  }
  let { data, form }: Props = $props();

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
  let selectedProvider = $state('gmail');
  // Preset für den gewählten Anbieter; 'custom' → manuelle Host/Port-Felder.
  const preset = $derived(data.providers.find((p) => p.key === selectedProvider));

  const actionError = $derived(form && 'error' in form ? form.error : null);
  const added = $derived(form && 'added' in form ? form.added : null);

  $effect(() => {
    if (added) showConnect = false;
  });

  function fmtDate(iso: string | null): string {
    if (!iso) return 'nie';
    const t = Date.parse(iso);
    if (Number.isNaN(t)) return '';
    return new Date(t).toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Europe/Berlin',
    });
  }
</script>

<svelte:head>
  <title>Konten · Post</title>
</svelte:head>

<header class="mb-8 flex items-start justify-between gap-4">
  <div>
    <a href="/" class="mb-2 inline-flex items-center gap-1.5 text-sm text-muted transition-colors duration-fast ease-saganta hover:text-text">
      <Icon name="arrow-left" size={15} /> Zurück zur Post
    </a>
    <h1 class="font-display text-4xl tracking-tight">Konten</h1>
    <p class="mt-2 text-sm text-muted">
      E-Mail-Konten verbinden und verwalten. Alle verbundenen Konten erscheinen gebündelt in deiner Post.
    </p>
  </div>
  <Button variant="primary" onclick={() => (showConnect = !showConnect)}>
    {showConnect ? 'Abbrechen' : 'Konto verbinden'}
  </Button>
</header>

{#if data.verbunden}
  <p class="mb-6 flex items-center gap-2 rounded-lg border border-erfolg/40 bg-erfolg/10 px-4 py-3 text-sm">
    <Icon name="circle-check" size={16} /> {data.verbunden} ist verbunden.
  </p>
{/if}

{#if data.oauthFehler}
  <p class="mb-6 rounded-lg border border-warm-700 bg-warm-700/10 px-4 py-3 text-sm text-warm-500">
    Das Verbinden wurde abgebrochen: {data.oauthFehler}
  </p>
{/if}

<!-- ★ Der sichere Weg steht ZUERST und ohne Passwortfeld.
     Er erscheint nur, wenn für den Anbieter wirklich eine Konfiguration
     hinterlegt ist: ein Knopf, der beim Anbieter in einen Fehler läuft, sieht
     aus wie ein Ausfall dieser Anwendung (siehe services/mail-api/app/oauth.py).
     Ohne Konfiguration bleibt der bestehende Weg mit App-Passwort der einzige,
     und das ist kein Mangel, sondern die ehrliche Anzeige des Zustands. -->
{#if data.oauthAnbieter.length > 0}
  <section class="mb-8 rounded-lg border border-accent-500/40 bg-accent-500/[0.05] p-4">
    <h2 class="flex items-center gap-2 font-display text-xl">
      <Icon name="shield" size={18} /> Ohne Passwort verbinden
    </h2>
    <p class="mt-1 text-sm text-muted">
      Du meldest dich beim Anbieter an und erlaubst den Zugriff dort. Hier liegt danach kein
      Passwort, und du kannst den Zugriff jederzeit im Konto des Anbieters zurückziehen.
    </p>
    <div class="mt-3 flex flex-wrap gap-2">
      {#each data.oauthAnbieter as a (a.schluessel)}
        <form method="POST" action="?/oauthStart" use:enhance>
          <input type="hidden" name="anbieter" value={a.schluessel} />
          <Button type="submit" variant="primary">Mit {a.name} verbinden</Button>
        </form>
      {/each}
    </div>
  </section>
{/if}

{#if data.failed}
  <div class="mb-6 rounded-lg border border-warm-500/40 bg-warm-500/10 px-4 py-3 text-sm text-muted">
    Mailkonten nicht erreichbar.
  </div>
{/if}

{#if actionError}
  <p class="mb-6 rounded-md border border-warm-700 bg-warm-700/10 px-3 py-2 text-sm text-warm-500">
    {actionError}
  </p>
{/if}

{#if showConnect}
  <form
    method="POST"
    action="?/add"
    use:enhance={() =>
      async ({ update }) => {
        await update();
      }}
    class="mb-8 space-y-3 rounded-lg border border-border bg-surface-2 p-4"
  >
    <h2 class="font-display text-xl">Externes Konto verbinden</h2>
    <p class="text-sm text-muted">
      Deine Zugangsdaten werden verschlüsselt gespeichert. Versand läuft über den Anbieter selbst,
      nie über Saganta. Bei Gmail/GMX/Web.de ein <span class="text-text">App-Passwort</span> verwenden.
    </p>
    <div class="grid gap-3 sm:grid-cols-2">
      <label class="space-y-1">
        <span class="text-sm text-muted">Anbieter</span>
        <select
          name="provider"
          bind:value={selectedProvider}
          class="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-text outline-none focus:border-accent-400"
        >
          {#each uniqueBy(data.providers, (x) => x.key) as p (p.key)}
            <option value={p.key}>{p.key}</option>
          {/each}
          <option value="custom">custom (manuell)</option>
        </select>
      </label>
      <label class="space-y-1">
        <span class="text-sm text-muted">E-Mail-Adresse</span>
        <input name="email" type="email" autocomplete="email" required
          class="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-text outline-none focus:border-accent-400" />
      </label>
      <label class="space-y-1">
        <span class="text-sm text-muted">App-Passwort</span>
        <input name="password" type="password" autocomplete="off" required
          class="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-text outline-none focus:border-accent-400" />
      </label>
      <label class="space-y-1">
        <span class="text-sm text-muted">Anzeigename (optional)</span>
        <input name="display_name"
          class="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-text outline-none focus:border-accent-400" />
      </label>
    </div>

    {#if preset}
      <p class="text-xs text-muted">
        IMAP {preset.imap_host}:{preset.imap_port} · SMTP {preset.smtp_host}:{preset.smtp_port}
        {#if preset.note}<br />{preset.note}{/if}
      </p>
    {:else}
      <div class="grid gap-3 sm:grid-cols-2">
        <input name="imap_host" placeholder="IMAP-Host" required
          class="rounded-md border border-border bg-surface px-2 py-1.5 text-text outline-none focus:border-accent-400" />
        <input name="imap_port" placeholder="IMAP-Port (993)" required
          class="rounded-md border border-border bg-surface px-2 py-1.5 text-text outline-none focus:border-accent-400" />
        <input name="smtp_host" placeholder="SMTP-Host" required
          class="rounded-md border border-border bg-surface px-2 py-1.5 text-text outline-none focus:border-accent-400" />
        <input name="smtp_port" placeholder="SMTP-Port (465)" required
          class="rounded-md border border-border bg-surface px-2 py-1.5 text-text outline-none focus:border-accent-400" />
      </div>
    {/if}

    <Button type="submit" variant="primary">Verbinden &amp; testen</Button>
  </form>
{/if}

{#if data.accounts.length === 0}
  <div class="rounded-lg border border-dashed border-border bg-surface-2/40 p-8 text-center">
    <p class="text-muted">Noch kein Konto verbunden.</p>
    <p class="mt-1 text-sm text-muted">Verbinde dein erstes E-Mail-Konto, um deine Post zu bündeln.</p>
  </div>
{:else}
  <ul class="space-y-2">
    {#each data.accounts as a (a.id)}
      <li class="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface-2/60 px-4 py-3 {a.enabled ? '' : 'opacity-60'}">
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <span class="truncate font-medium text-text">{a.email}</span>
            {#if a.auth_typ === 'oauth2'}
              <span
                class="inline-flex items-center gap-1 rounded-full border border-erfolg/40 px-2 py-0.5 text-xs text-erfolg"
                title="Ohne Passwort verbunden. Zugriff im Konto des Anbieters widerrufbar."
              >
                <Icon name="shield" size={11} /> ohne Passwort
              </span>
            {/if}
            {#if !a.enabled}<span class="rounded-full bg-warm-500/15 px-2 py-0.5 text-xs text-warm-500">pausiert</span>{/if}
            {#if a.last_error}
              <span title={a.last_error} class="text-warm-500"><Icon name="alert-triangle" size={14} label="Sync-Fehler" /></span>
            {/if}
          </div>
          <div class="mt-0.5 text-xs text-muted">
            {a.provider} · IMAP {a.imap_host}:{a.imap_port} · Letzte Synchronisierung: {fmtDate(a.last_sync_at)}
          </div>
        </div>
        <div class="flex items-center gap-1">
          <form method="POST" action="?/sync" use:enhance>
            <input type="hidden" name="account_id" value={a.id} />
            <button class="rounded-md p-1.5 text-muted transition-colors duration-fast ease-saganta hover:text-text" title="Jetzt synchronisieren" aria-label="Jetzt synchronisieren"><Icon name="refresh-cw" size={16} /></button>
          </form>
          <form method="POST" action="?/toggle" use:enhance>
            <input type="hidden" name="account_id" value={a.id} />
            <input type="hidden" name="enabled" value={String(!a.enabled)} />
            <button class="rounded-md p-1.5 text-muted transition-colors duration-fast ease-saganta hover:text-text" title={a.enabled ? 'Konto pausieren' : 'Konto fortsetzen'} aria-label={a.enabled ? 'Konto pausieren' : 'Konto fortsetzen'}><Icon name="power" size={16} /></button>
          </form>
          <form method="POST" action="?/delete" use:enhance>
            <input type="hidden" name="account_id" value={a.id} />
            <button class="rounded-md p-1.5 text-muted transition-colors duration-fast ease-saganta hover:text-warm-500" title="Konto entfernen" aria-label="Konto entfernen"><Icon name="x" size={16} /></button>
          </form>
        </div>
      </li>
    {/each}
  </ul>
{/if}
