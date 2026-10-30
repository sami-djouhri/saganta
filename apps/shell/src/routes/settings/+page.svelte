<script lang="ts">
  import { enhance } from '$app/forms';
  import { page } from '$app/state';
  import { Button } from '@saganta/ui';
  import type { ActionData, PageData } from './$types';

  interface Props {
    data: PageData;
    form: ActionData;
  }
  let { data, form }: Props = $props();

  let saved = $derived(page.url.searchParams.get('ok') === '1');
  let submitting = $state(false);

  // Deutsch statt „Dark (Default)" / „Light": die Oberflaeche ist deutsch, und
  // welcher Wert die Vorgabe ist, gehoert nicht in die Auswahl, sondern in den
  // Text daneben. Seit 2026-09-27 ist die Vorgabe „Automatisch".
  const themes = [
    { value: 'auto', label: 'Automatisch (folgt dem Gerät)' },
    { value: 'light', label: 'Hell' },
    { value: 'dark', label: 'Dunkel' },
    { value: 'hc', label: 'Hochkontrast' },
  ];
  const locales = [
    { value: 'de-DE', label: 'Deutsch (DE)' },
    { value: 'en-US', label: 'English (US)' },
  ];

  function isValidationError(msg: string | undefined): boolean {
    if (!msg) return false;
    return /pflicht|invalid|ungültig|required|missing|leer/i.test(msg);
  }
</script>

<section class="space-y-6">
  <header class="space-y-1">
    <h1 class="font-display text-3xl">Einstellungen</h1>
    <p class="text-muted">Darstellung und Sprache. Gilt für alle Saganta-Apps.</p>
  </header>

  {#if data.user}
    <div class="flex items-center gap-4 rounded-lg border border-border bg-surface-2 p-5">
      <div class="grid size-12 shrink-0 place-items-center rounded-full bg-accent-500/15 font-display text-xl text-akzent" aria-hidden="true">
        {(data.user.name ?? data.user.email ?? '?').charAt(0).toUpperCase()}
      </div>
      <div class="min-w-0">
        {#if data.user.name}<div class="truncate font-medium text-text">{data.user.name}</div>{/if}
        <div class="truncate text-sm text-muted">{data.user.email}</div>
      </div>
    </div>
  {/if}

  {#if saved}
    <div class="rounded-md border border-erfolg/40 bg-erfolg/10 px-4 py-2 text-erfolg" role="status">
      Gespeichert.
    </div>
  {/if}

  {#if form?.error}
    {#if isValidationError(form.error)}
      <div class="rounded-md border border-warnung/40 bg-warnung/10 px-4 py-2 text-warnung" role="alert">
        <span class="font-medium">Eingabe ungültig:</span> {form.error}
      </div>
    {:else}
      <div class="rounded-md border border-fehler/40 bg-fehler/10 px-4 py-2 text-fehler" role="alert">
        <span class="font-medium">Speichern fehlgeschlagen:</span> {form.error}
      </div>
    {/if}
  {/if}

  <form
    method="POST"
    action="?/save"
    class="space-y-5 rounded-lg border border-border bg-surface-2 p-6"
    use:enhance={() => {
      submitting = true;
      return async ({ update }) => {
        await update();
        submitting = false;
      };
    }}
  >
    <div class="space-y-2">
      <label for="theme" class="block text-sm font-medium">Darstellung</label>
      <select
        id="theme"
        name="theme"
        class="min-h-11 w-full rounded-md border border-border-stark bg-surface px-3 py-2 text-text"
        value={data.settings.theme}
        aria-describedby="theme-hinweis"
      >
        {#each themes as t (t.value)}
          <option value={t.value}>{t.label}</option>
        {/each}
      </select>
      <p id="theme-hinweis" class="text-sm text-muted">
        „Automatisch" ist die Vorgabe und wechselt mit der Einstellung deines Geräts.
      </p>
    </div>

    <div class="space-y-2">
      <label for="locale" class="block text-sm font-medium">Sprache</label>
      <select
        id="locale"
        name="locale"
        class="w-full rounded-md border border-border-stark bg-surface px-3 py-2 text-text"
        value={data.settings.locale}
      >
        {#each locales as l (l.value)}
          <option value={l.value}>{l.label}</option>
        {/each}
      </select>
      <p class="text-sm text-muted">
        Wirkt bisher auf Datums- und Zahlenformate. Die Texte der Oberfläche sind noch nicht
        übersetzt.
      </p>
    </div>

    <div class="flex items-center justify-between gap-3 pt-2">
      <a href="/" class="text-sm text-muted transition-colors duration-fast ease-saganta hover:text-text">← Zurück</a>
      <Button type="submit" variant="primary" loading={submitting}>
        {submitting ? 'Speichere…' : 'Speichern'}
      </Button>
    </div>
  </form>

  <div class="rounded-lg border border-border bg-surface-2 p-6">
    <h2 class="font-display text-xl">Passwort und Konto</h2>
    <p class="mt-1 text-sm text-muted">
      Das Passwort wird nicht mehr hier geändert, sondern unter <a
        href="/konto"
        class="text-akzent underline-offset-2 hover:underline">Konto</a
      >. Dort wird es vorher noch einmal abgefragt, weil die Anmeldung lange hält und in allen
      Apps gilt.
    </p>
  </div>
</section>
