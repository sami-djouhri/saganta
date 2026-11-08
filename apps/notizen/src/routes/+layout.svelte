<script lang="ts">
  import '../app.css';
  import { TopBar, UpdateBanner, CommandPalette, buildAppCommands, AppRahmen } from '@saganta/ui';
  import { page } from '$app/stores';
  import { APP_NAME, NAV } from '$lib/meta';
  import type { LayoutData } from './$types';

  interface Props {
    children: import('svelte').Snippet;
    data: LayoutData;
  }
  let { children, data }: Props = $props();

  let pfad = $derived($page.url.pathname);
  // Die öffentliche Leseseite bekommt kein App-Gerüst: der Empfänger hat hier
  // kein Konto, und eine Navigationsleiste mit Kontomenü wäre für ihn nur eine
  // Sammlung von Türen, die alle verschlossen sind.
  let oeffentlich = $derived(pfad.startsWith('/n/'));
</script>

{#if oeffentlich}
  <div class="min-h-dvh bg-surface text-text">
    {@render children()}
  </div>
{:else}
  <UpdateBanner />
  <div class="min-h-dvh bg-surface text-text">
    {#if data.user}
      <TopBar app={APP_NAME} user={data.user} currentAppId="notizen" host={data.host} />
      <CommandPalette commands={buildAppCommands('notizen', data.host)} />
      <AppRahmen nav={NAV} pfad={$page.url.pathname} breite="breit">
        {@render children()}
      </AppRahmen>
    {:else}
      <main id="main" tabindex="-1" class="mx-auto max-w-md px-6 py-24 text-center outline-none">
        <h1 class="font-display text-2xl">Saganta Notizen</h1>
        <p class="mt-2 text-muted">Bitte anmelden, um fortzufahren.</p>
        <a
          href="/"
          class="mt-6 inline-block rounded-md border border-border px-4 py-2 text-sm hover:text-text"
          >Zur Anmeldung</a
        >
      </main>
    {/if}
  </div>
{/if}
