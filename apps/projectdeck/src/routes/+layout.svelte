<script lang="ts">
  import '../app.css';
  import {
    TopBar,
    Button,
    Icon,
    UpdateBanner,
    CommandPalette,
    AppHinweis,
    buildAppCommands,
  } from '@saganta/ui';
  import { page } from '$app/stores';
  import { NAV } from '$lib/meta';
  import type { LayoutData } from './$types';

  interface Props {
    children: import('svelte').Snippet;
    data: LayoutData;
  }
  let { children, data }: Props = $props();

  let path = $derived($page.url.pathname);
  function active(href: string): boolean {
    return href === '/' ? path === '/' : path.startsWith(href);
  }
</script>

<UpdateBanner />

<div class="min-h-dvh bg-surface text-text">
  {#if data.user}
    <TopBar app="ProjectDeck" user={data.user} currentAppId="projectdeck" host={data.host}>
      {#snippet actions()}
        <form method="POST" action="/logout">
          <Button type="submit" variant="ghost" size="sm" aria-label="Abmelden" title="Abmelden">
            <Icon name="log-out" size={16} />
          </Button>
        </form>
      {/snippet}
    </TopBar>
    <AppHinweis app="projectdeck" name="ProjectDeck" />
    <CommandPalette commands={buildAppCommands('projectdeck', data.host)} />
    <div class="mx-auto flex max-w-7xl gap-6 px-4 py-6 md:px-6">
      <aside class="hidden w-52 shrink-0 md:block">
        <nav class="sticky top-6 flex flex-col gap-1">
          {#each NAV as item}
            <a
              href={item.href}
              class="flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors duration-fast ease-saganta {active(
                item.href,
              )
                ? 'bg-surface-2 text-text'
                : 'text-muted hover:bg-surface-2/60 hover:text-text'}"
            >
              <span class="opacity-70"><Icon name={item.icon} size={16} /></span>
              <span>{item.label}</span>
            </a>
          {/each}
        </nav>
      </aside>
      <main id="main" tabindex="-1" class="min-w-0 flex-1 outline-none">
        {@render children()}
      </main>
    </div>
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
