<script lang="ts">
  import '../app.css';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { TopBar, Icon, CommandPalette, UpdateBanner, PageContainer } from '@saganta/ui';
  import { appsFallback } from '$lib/apps';
  import type { LayoutData } from './$types';

  interface Props {
    children: import('svelte').Snippet;
    data: LayoutData;
  }
  let { children, data }: Props = $props();

  let lang = $derived((data.settings?.locale ?? 'de-DE').split('-')[0] ?? 'de');

  let logoutForm: HTMLFormElement | undefined = $state();

  // Befüllt aus dem statischen $lib/apps-Fallback → Palette ist immer
  // navigierbar, auch wenn shell-api beim Laden nicht erreichbar war.
  const commands = $derived([
    ...appsFallback(page.url.host).map((app) => ({
      id: `app-${app.id}`,
      label: `Öffnen: ${app.name}`,
      hint: app.tags.includes('core') ? 'App' : undefined,
      run: () => {
        window.location.href = app.href;
      },
    })),
    { id: 'nav-home', label: 'Startseite', hint: 'Shell', run: () => goto('/') },
    { id: 'nav-settings', label: 'Einstellungen', hint: '⚙', run: () => goto('/settings') },
    {
      id: 'nav-logout',
      label: 'Abmelden',
      hint: '⏻',
      run: () => logoutForm?.requestSubmit(),
    },
  ]);

  $effect(() => {
    document.documentElement.lang = lang;
  });
</script>

<UpdateBanner />

<div class="min-h-dvh bg-surface text-text">
  <!-- Nur wenn unten KEINE TopBar gerendert wird: die bringt seit 2026-09-05
       ihren eigenen Sprunglink mit, sonst muesste man zweimal tabben. Die
       Anmeldeseiten haben keine TopBar und brauchen ihn hier. -->
  {#if !data.user}
    <a
      href="#main"
      class="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-accent-500 focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-accent-ink"
    >
      Zum Inhalt springen
    </a>
  {/if}
  {#if data.user}
    <TopBar app="Übersicht" user={data.user} currentAppId="shell" showSwitcher={false}>
      {#snippet actions()}
        <button
          type="button"
          onclick={() =>
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }))}
          class="hidden min-h-11 items-center gap-1.5 rounded-md border border-border-stark px-2 text-xs text-muted transition-colors duration-fast ease-saganta hover:text-text sm:inline-flex"
          aria-label="Befehlspalette öffnen"
          title="Befehlspalette (⌘K)"
        >
          <Icon name="search" size={14} />
          <kbd class="font-mono">⌘K</kbd>
        </button>
      {/snippet}
      {#snippet menu()}
        <a
          href="/konto"
          role="menuitem"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text transition-colors duration-fast ease-saganta hover:bg-surface"
        >
          <Icon name="user" size={16} /> Konto
        </a>
        <a
          href="/apps"
          role="menuitem"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text transition-colors duration-fast ease-saganta hover:bg-surface"
        >
          <Icon name="download" size={16} /> Apps & Downloads
        </a>
        <a
          href="/settings"
          role="menuitem"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text transition-colors duration-fast ease-saganta hover:bg-surface"
        >
          <Icon name="settings" size={16} /> Einstellungen
        </a>
        <form method="POST" action="/logout" bind:this={logoutForm}>
          <button
            type="submit"
            role="menuitem"
            class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-text transition-colors duration-fast ease-saganta hover:bg-surface"
          >
            <Icon name="log-out" size={16} /> Abmelden
          </button>
        </form>
      {/snippet}
    </TopBar>
    <CommandPalette {commands} />
    <PageContainer breite="breit">
      {@render children()}
    </PageContainer>
  {:else}
    <main id="main" tabindex="-1" class="outline-none">
      {@render children()}
    </main>
  {/if}
</div>
