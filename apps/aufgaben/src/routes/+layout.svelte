<script lang="ts">
  import '../app.css';
  import { TopBar, Button, Icon, UpdateBanner, CommandPalette, buildAppCommands } from '@saganta/ui';
  import { page } from '$app/stores';
  import { APP_ID, APP_NAME, NAV } from '$lib/meta';
  import type { LayoutData } from './$types';

  interface Props {
    children: import('svelte').Snippet;
    data: LayoutData;
  }
  let { children, data }: Props = $props();

  let pfad = $derived($page.url.pathname);

  function aktiv(href: string): boolean {
    return href === '/' ? pfad === '/' : pfad.startsWith(href);
  }
</script>

<UpdateBanner />
<div class="min-h-dvh bg-surface text-text">
  {#if data.user}
    <TopBar app={APP_NAME} user={data.user} currentAppId={APP_ID} host={data.host}>
      {#snippet actions()}
        <form method="POST" action="/logout">
          <Button type="submit" variant="ghost" size="sm" aria-label="Abmelden" title="Abmelden">
            <Icon name="log-out" size={16} />
          </Button>
        </form>
      {/snippet}
    </TopBar>
    <CommandPalette commands={buildAppCommands(APP_ID, data.host)} />

    <div class="mx-auto flex max-w-6xl gap-6 px-4 py-6 md:px-6">
      <aside class="hidden w-48 shrink-0 md:block">
        <nav class="sticky top-20 flex flex-col gap-1" aria-label="Bereiche">
          {#each NAV as eintrag (eintrag.href)}
            <a
              href={eintrag.href}
              aria-current={aktiv(eintrag.href) ? 'page' : undefined}
              class="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors duration-fast ease-saganta {aktiv(
                eintrag.href,
              )
                ? 'bg-surface-2 font-medium text-text'
                : 'text-muted hover:bg-surface-2/60 hover:text-text'}"
            >
              <Icon name={eintrag.icon} size={16} />
              <span>{eintrag.label}</span>
            </a>
          {/each}
        </nav>
      </aside>

      <main id="main" tabindex="-1" class="min-w-0 flex-1 outline-none">
        {@render children()}
      </main>
    </div>

    <!-- Auf dem Handy steht die Navigation unten: dort ist der Daumen, und die
         Seitenleiste waere bei dieser Breite ohnehin ausgeblendet. -->
    <nav
      class="sticky bottom-0 z-20 flex border-t border-border bg-surface/90 backdrop-blur-md md:hidden"
      aria-label="Bereiche"
    >
      {#each NAV as eintrag (eintrag.href)}
        <a
          href={eintrag.href}
          aria-current={aktiv(eintrag.href) ? 'page' : undefined}
          class="flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] {aktiv(eintrag.href)
            ? 'text-accent-300'
            : 'text-muted'}"
        >
          <Icon name={eintrag.icon} size={18} />
          <span>{eintrag.label.replace('Alle Aufgaben', 'Alle').replace('Nach Projekt', 'Projekte')}</span>
        </a>
      {/each}
    </nav>
  {:else}
    <main id="main" tabindex="-1" class="mx-auto max-w-md px-6 py-24 text-center outline-none">
      <h1 class="font-display text-2xl">Saganta {APP_NAME}</h1>
      <p class="mt-2 text-muted">Bitte anmelden, um fortzufahren.</p>
      <a
        href="/"
        class="mt-6 inline-block rounded-md border border-border px-4 py-2 text-sm hover:text-text"
        >Zur Anmeldung</a
      >
    </main>
  {/if}
</div>
