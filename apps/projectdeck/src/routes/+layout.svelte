<script lang="ts">
  import '../app.css';
  import { TopBar, UpdateBanner, CommandPalette, AppHinweis, buildAppCommands, AppRahmen } from '@saganta/ui';
  import { page } from '$app/stores';
  import { NAV } from '$lib/meta';
  import type { LayoutData } from './$types';

  interface Props {
    children: import('svelte').Snippet;
    data: LayoutData;
  }
  let { children, data }: Props = $props();
</script>

<UpdateBanner />

<div class="min-h-dvh bg-surface text-text">
  {#if data.user}
    <TopBar app="ProjectDeck" user={data.user} currentAppId="projectdeck" host={data.host} />
    <AppHinweis app="projectdeck" name="ProjectDeck" />
    <CommandPalette commands={buildAppCommands('projectdeck', data.host)} />
    <AppRahmen nav={NAV} pfad={$page.url.pathname} breite="breit">
      {@render children()}
    </AppRahmen>
  {:else}
    <main id="main" tabindex="-1" class="mx-auto max-w-md px-6 py-24 text-center outline-none">
      <h1 class="font-display text-2xl">Saganta ProjectDeck</h1>
      <p class="mt-2 text-muted">Bitte anmelden, um fortzufahren.</p>
      <a
        href="/"
        class="mt-6 inline-block rounded-md border border-border px-4 py-2 text-sm hover:text-text"
        >Zur Anmeldung</a
      >
    </main>
  {/if}
</div>
