<script lang="ts">
  import { page } from '$app/stores';
  import AuthShell from '$lib/AuthShell.svelte';

  const status = $derived($page.status);
  const message = $derived($page.error?.message ?? 'Etwas ist schiefgelaufen.');
  const title = $derived(
    status === 404 ? 'Seite nicht gefunden' : status === 403 ? 'Kein Zugriff' : 'Ein Fehler ist aufgetreten',
  );
  const hint = $derived(
    status === 404
      ? 'Diese Seite gibt es nicht (mehr). Vielleicht hilft der Weg zurück nach Hause.'
      : status === 403
        ? 'Für diesen Bereich fehlt dir die Berechtigung. Melde dich an oder geh zurück.'
        : message,
  );
</script>

<svelte:head>
  <title>{status} · Saganta</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<AuthShell>
  <div class="text-center">
    <p class="font-display text-7xl leading-none tracking-tight text-accent-400">{status}</p>
    <h1 class="mt-4 font-display text-3xl tracking-tight text-text">{title}</h1>
    <p class="mx-auto mt-3 max-w-xs text-sm leading-relaxed text-muted">{hint}</p>
    <div class="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
      <a
        href="/"
        class="w-full rounded-xl bg-accent-500 px-6 py-3 text-center text-sm font-semibold text-accent-ink shadow-sm transition-colors duration-fast ease-saganta hover:bg-accent-400 sm:w-auto"
      >
        Zur Startseite
      </a>
      <a
        href="/login"
        class="w-full rounded-xl border border-border bg-surface-2/50 px-6 py-3 text-center text-sm font-medium text-text transition-colors duration-fast ease-saganta hover:bg-surface-2 sm:w-auto"
      >
        Anmelden
      </a>
    </div>
  </div>
</AuthShell>
