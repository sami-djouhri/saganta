<script lang="ts">
  import { untrack } from 'svelte';
  import { enhance } from '$app/forms';
  import { Button } from '@saganta/ui';
  import AuthShell from '$lib/AuthShell.svelte';
  import PasswordField from '$lib/PasswordField.svelte';
  import CaptchaField from '$lib/CaptchaField.svelte';
  import type { ActionData, PageData } from './$types';

  interface Props {
    data: PageData;
    form: ActionData;
  }
  let { data, form }: Props = $props();

  // Login/Register-Modus (user-getoggelt). Startwert aus der letzten Action
  // (no-JS-Fall: SSR nach fehlgeschlagenem Register bleibt im Register-Modus);
  // untrack = bewusst nur Initialwert, danach user-gesteuert.
  let mode = $state<'login' | 'register'>(
    untrack(() => (form?.mode === 'register' || data.initialMode === 'register' ? 'register' : 'login')),
  );
  let submitting = $state(false);

  const isRegister = $derived(mode === 'register');
  // Nach erfolgreichem Signup: Bestätigungs-Karte statt Formular.
  const registered = $derived(Boolean(form?.registered));
  // 'unverified' kommt nur aus dem login-Fehler-Branch → getypter Zugriff über Union.
  const unverified = $derived(Boolean((form as { unverified?: boolean } | null)?.unverified));
</script>

<svelte:head>
  <title>{isRegister ? 'Registrieren' : 'Anmelden'} · Saganta</title>
</svelte:head>

<AuthShell>
    <div class="mb-8 text-center">
      <a href="/" class="font-display text-4xl tracking-tight text-text">Saganta</a>
      <p class="mt-2 text-sm text-muted">
        {registered
          ? 'Fast geschafft'
          : isRegister
            ? 'Konto erstellen'
            : 'Willkommen zurück'}
      </p>
    </div>

    {#if registered}
      <!-- Post-Signup: E-Mail bestätigen -->
      <div class="rounded-2xl border border-border bg-surface-2/80 p-6 text-center shadow-xl shadow-black/30 backdrop-blur-sm">
        <div
          class="mx-auto mb-4 grid size-12 place-items-center rounded-full bg-accent-500/15 text-2xl"
          aria-hidden="true"
        >
          ✉️
        </div>
        <h2 class="font-display text-2xl text-text">Bestätige deine E-Mail</h2>
        <p class="mt-2 text-sm text-muted">
          Wir haben einen Bestätigungslink an
          <span class="text-text">{form?.email}</span> geschickt. Öffne ihn, um dein Konto zu
          aktivieren, danach kannst du dich anmelden.
        </p>

        {#if form?.resent}
          <p class="mt-4 rounded-lg border border-accent-700 bg-accent-500/10 px-3 py-2 text-sm text-akzent">
            Link erneut gesendet.
          </p>
        {/if}

        <form
          method="POST"
          action="?/resend"
          use:enhance={() => {
            submitting = true;
            return async ({ update }) => {
              await update({ reset: false });
              submitting = false;
            };
          }}
          class="mt-5"
        >
          <input type="hidden" name="email" value={form?.email ?? ''} />
          <Button type="submit" variant="ghost" size="sm" loading={submitting} class="w-full">
            Link erneut senden
          </Button>
        </form>

        <p class="mt-5 text-sm text-muted">
          <button class="text-akzent hover:underline" onclick={() => (mode = 'login')}>
            Zur Anmeldung
          </button>
        </p>
      </div>
    {:else}
      {#if data.resetDone}
        <p class="mb-4 rounded-lg border border-erfolg/40 bg-erfolg/10 px-3 py-2 text-center text-sm text-erfolg">
          Passwort geändert. Du kannst dich jetzt anmelden.
        </p>
      {/if}
      <div class="rounded-2xl border border-border bg-surface-2/80 p-6 shadow-xl shadow-black/30 backdrop-blur-sm">
        <form
          method="POST"
          action="?/{mode}"
          use:enhance={() => {
            submitting = true;
            return async ({ update }) => {
              await update();
              submitting = false;
            };
          }}
          class="flex flex-col gap-4"
        >
          <input type="hidden" name="next" value={data.next} />

          {#if isRegister}
            <label class="flex flex-col gap-1.5">
              <span class="text-sm text-muted">Name</span>
              <input
                name="name"
                type="text"
                autocomplete="name"
                required
                value={form?.name ?? ''}
                class="rounded-lg border border-border-stark bg-surface px-3 py-2 text-text outline-none transition-colors duration-fast ease-saganta focus:border-accent-400"
              />
            </label>
          {/if}

          <label class="flex flex-col gap-1.5">
            <span class="text-sm text-muted">E-Mail</span>
            <input
              name="email"
              type="email"
              autocomplete="email"
              required
              value={form?.email ?? ''}
              class="rounded-lg border border-border-stark bg-surface px-3 py-2 text-text outline-none transition-colors duration-fast ease-saganta focus:border-accent-400"
            />
          </label>

          <label class="flex flex-col gap-1.5">
            <div class="flex items-center justify-between">
              <span class="text-sm text-muted">Passwort</span>
              {#if !isRegister}
                <a href="/forgot" class="text-xs text-akzent hover:underline">Passwort vergessen?</a>
              {/if}
            </div>
            <PasswordField
              name="password"
              autocomplete={isRegister ? 'new-password' : 'current-password'}
              required
              minlength={isRegister ? 8 : undefined}
            />
          </label>

          {#if form?.error}
            <p
              class="rounded-lg border px-3 py-2 text-sm"
              class:border-accent-700={unverified}
              class:text-akzent={unverified}
              class:border-warm-700={!unverified}
              class:text-kupfer={!unverified}
              role="alert"
            >
              {form.error}
            </p>
          {/if}

          <CaptchaField enabled={data.captchaEnabled} />

          <Button type="submit" variant="primary" size="lg" loading={submitting} class="mt-2 w-full">
            {isRegister ? 'Konto erstellen' : 'Anmelden'}
          </Button>
        </form>
      </div>

      <p class="mt-6 text-center text-sm text-muted">
        {#if isRegister}
          Schon ein Konto?
          <button class="text-akzent hover:underline" onclick={() => (mode = 'login')}>Anmelden</button>
        {:else}
          Noch kein Konto?
          <button class="text-akzent hover:underline" onclick={() => (mode = 'register')}>Registrieren</button>
        {/if}
      </p>
    {/if}
</AuthShell>
