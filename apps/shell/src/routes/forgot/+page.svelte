<script lang="ts">
  import { enhance } from '$app/forms';
  import { Button } from '@saganta/ui';
  import CaptchaField from '$lib/CaptchaField.svelte';
  import type { ActionData, PageData } from './$types';

  let { form, data }: { form: ActionData; data: PageData } = $props();
  let submitting = $state(false);
  const sent = $derived(Boolean(form?.sent));
</script>

<svelte:head>
  <title>Passwort vergessen · Saganta</title>
</svelte:head>

<div class="grid min-h-dvh place-items-center px-6 py-12">
  <div class="w-full max-w-sm">
    <div class="mb-8 text-center">
      <a href="/" class="font-display text-4xl tracking-tight text-text">Saganta</a>
      <p class="mt-2 text-sm text-muted">Passwort zurücksetzen</p>
    </div>

    {#if sent}
      <div class="rounded-2xl border border-border bg-surface-2 p-6 text-center">
        <div class="mx-auto mb-4 grid size-12 place-items-center rounded-full bg-accent-500/15 text-2xl" aria-hidden="true">✉️</div>
        <h2 class="font-display text-2xl text-text">Prüf dein Postfach</h2>
        <p class="mt-2 text-sm text-muted">
          Falls ein Konto zu <span class="text-text">{form?.email}</span> existiert, haben wir einen
          Link zum Zurücksetzen geschickt. Der Link ist 1 Stunde gültig.
        </p>
        <p class="mt-5 text-sm text-muted">
          <a href="/login" class="text-accent-400 hover:underline">Zur Anmeldung</a>
        </p>
      </div>
    {:else}
      <div class="rounded-2xl border border-border bg-surface-2 p-6 shadow-sm">
        <p class="mb-4 text-sm text-muted">
          Gib deine E-Mail-Adresse ein. Wir senden dir einen Link, mit dem du ein neues Passwort
          setzen kannst.
        </p>
        <form
          method="POST"
          use:enhance={() => {
            submitting = true;
            return async ({ update }) => {
              await update();
              submitting = false;
            };
          }}
          class="flex flex-col gap-4"
        >
          <label class="flex flex-col gap-1.5">
            <span class="text-sm text-muted">E-Mail</span>
            <input
              name="email"
              type="email"
              autocomplete="email"
              required
              value={form?.email ?? ''}
              class="rounded-lg border border-border bg-surface px-3 py-2 text-text outline-none transition-colors duration-fast ease-saganta focus:border-accent-400"
            />
          </label>

          {#if form?.error}
            <p class="rounded-lg border border-warm-700 bg-surface px-3 py-2 text-sm text-warm-500" role="alert">
              {form.error}
            </p>
          {/if}

          <CaptchaField enabled={data.captchaEnabled} />

          <Button type="submit" variant="primary" size="lg" loading={submitting} class="mt-2 w-full">
            Link senden
          </Button>
        </form>
      </div>

      <p class="mt-6 text-center text-sm text-muted">
        <a href="/login" class="text-accent-400 hover:underline">Zurück zur Anmeldung</a>
      </p>
    {/if}
  </div>
</div>
