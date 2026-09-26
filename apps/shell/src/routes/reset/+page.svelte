<script lang="ts">
  import { enhance } from '$app/forms';
  import { Button } from '@saganta/ui';
  import AuthShell from '$lib/AuthShell.svelte';
  import PasswordField from '$lib/PasswordField.svelte';
  import CaptchaField from '$lib/CaptchaField.svelte';
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();
  let submitting = $state(false);
</script>

<svelte:head>
  <title>Neues Passwort · Saganta</title>
</svelte:head>

<AuthShell>
    <div class="mb-8 text-center">
      <a href="/" class="font-display text-4xl tracking-tight text-text">Saganta</a>
      <p class="mt-2 text-sm text-muted">Neues Passwort setzen</p>
    </div>

    {#if !data.hasToken}
      <div class="rounded-2xl border border-warm-700 bg-surface-2 p-6 text-center">
        <h2 class="font-display text-2xl text-text">Link ungültig</h2>
        <p class="mt-2 text-sm text-muted">
          Dieser Reset-Link ist unvollständig oder abgelaufen. Fordere einen neuen an.
        </p>
        <p class="mt-5 text-sm text-muted">
          <a href="/forgot" class="text-accent-400 hover:underline">Neuen Link anfordern</a>
        </p>
      </div>
    {:else}
      <div class="rounded-2xl border border-border bg-surface-2 p-6 shadow-sm">
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
          <input type="hidden" name="token" value={data.token} />

          <label class="flex flex-col gap-1.5">
            <span class="text-sm text-muted">Neues Passwort</span>
            <PasswordField name="password" autocomplete="new-password" required minlength={8} />
          </label>

          <label class="flex flex-col gap-1.5">
            <span class="text-sm text-muted">Passwort bestätigen</span>
            <PasswordField name="confirm" autocomplete="new-password" required minlength={8} />
          </label>

          {#if form?.error}
            <p class="rounded-lg border border-warm-700 bg-surface px-3 py-2 text-sm text-warm-500" role="alert">
              {form.error}
            </p>
          {/if}

          <CaptchaField enabled={data.captchaEnabled} />

          <Button type="submit" variant="primary" size="lg" loading={submitting} class="mt-2 w-full">
            Passwort speichern
          </Button>
        </form>
      </div>
    {/if}
</AuthShell>
