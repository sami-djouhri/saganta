<script lang="ts">
  import '../app.css';
  import { goto, invalidate } from '$app/navigation';
  import { page } from '$app/state';
  import { TopBar, Icon, CommandPalette, UpdateBanner, PageContainer } from '@saganta/ui';
  import { appsFallback } from '$lib/apps';
  import type { LayoutData } from './$types';

  // Marketing-/Rechtsseiten bringen ihre eigene MarketingChrome (Vollseite) mit.
  // Auch für eingeloggte Besucher (z. B. via Konto-Menü → /apps-Downloads) dort
  // KEINE Shell-TopBar rendern, sonst doppelte Navigation. MarketingChrome zeigt
  // login-bewusst „Zur Übersicht".
  const FULL_BLEED = new Set(['/apps', '/impressum', '/datenschutz', '/agb']);
  const fullBleed = $derived(FULL_BLEED.has(page.url.pathname));

  interface Props {
    children: import('svelte').Snippet;
    data: LayoutData;
  }
  let { children, data }: Props = $props();

  let lang = $derived((data.settings?.locale ?? 'de-DE').split('-')[0] ?? 'de');

  let logoutForm: HTMLFormElement | undefined = $state();

  // Theme lokal spiegeln → sofort umschaltbar (kein Reload/FOUC). Server-Wahrheit
  // (data.settings) ist der Seed und synchronisiert nach, wenn sie sich ändert
  // (z. B. nach Speichern in /settings). Persistenz via /settings/theme-Proxy.
  let theme = $state(data.settings?.theme ?? 'auto');
  $effect(() => {
    theme = data.settings?.theme ?? 'auto';
  });

  // Reihenfolge des Knopfes: automatisch → hell → dunkel → automatisch. `auto`
  // ist seit 2026-09-27 die Vorgabe und folgt dem Betriebssystem; es muss
  // deshalb auch wieder erreichbar sein, sonst ist die Vorgabe nach dem ersten
  // Klick für immer weg. `hc` liegt bewusst nicht in dieser Runde, es gehört in
  // die Einstellungen: wer Hochkontrast braucht, wählt ihn einmal, statt bei
  // jedem dritten Klick hineinzustolpern.
  const THEME_RUNDE = ['auto', 'light', 'dark'] as const;
  const THEME_NAME: Record<string, string> = {
    auto: 'Automatisch (folgt dem System)',
    light: 'Hell',
    dark: 'Dunkel',
    hc: 'Hochkontrast',
  };
  let naechstesTheme = $derived(
    THEME_RUNDE[(THEME_RUNDE.indexOf(theme as (typeof THEME_RUNDE)[number]) + 1) % THEME_RUNDE.length] ??
      'auto',
  );

  async function toggleTheme() {
    const prev = theme;
    const next = naechstesTheme;
    theme = next; // optimistisch, sofort sichtbar
    try {
      const res = await fetch('/settings/theme', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ theme: next }),
      });
      if (!res.ok) throw new Error(String(res.status));
      // Server-Wahrheit nachziehen → Sync-$effect und ein späteres invalidateAll
      // (z. B. togglePin) rollen die Umschaltung nicht mehr zurück.
      await invalidate('app:settings');
    } catch {
      theme = prev; // Persistenz gescheitert → sichtbar zurücksetzen (kein stiller Drift)
    }
  }

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
      id: 'toggle-theme',
      label: `Darstellung: ${THEME_NAME[naechstesTheme] ?? 'Automatisch'}`,
      hint: '◐',
      run: toggleTheme,
    },
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

  // Theme sofort auch auf <html> spiegeln (nicht nur auf den Content-Wrapper),
  // damit Body-/Seitenhintergrund beim Umschalten ohne Reload mitzieht.
  $effect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  });
</script>

<UpdateBanner />

<div class="min-h-dvh bg-surface text-text" data-theme={theme}>
  <!-- Nur wenn unten KEINE TopBar gerendert wird: die bringt seit 2026-09-05
       ihren eigenen Sprunglink mit, sonst muesste man zweimal tabben. Die
       Landing und die fullBleed-Seiten haben keine TopBar und brauchen ihn hier. -->
  {#if !(data.user && !fullBleed)}
    <a
      href="#main"
      class="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-accent-500 focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-accent-ink"
    >
      Zum Inhalt springen
    </a>
  {/if}
  {#if data.user && !fullBleed}
    <TopBar app="Shell" user={data.user} currentAppId="shell" showSwitcher={false}>
      {#snippet actions()}
        <button
          type="button"
          onclick={toggleTheme}
          class="grid size-11 place-items-center text-muted transition-colors duration-fast ease-saganta hover:text-text"
          aria-label={`Darstellung ist ${THEME_NAME[theme] ?? 'Automatisch'}. Weiter zu ${
            THEME_NAME[naechstesTheme] ?? 'Automatisch'
          }.`}
          title={`Darstellung: ${THEME_NAME[theme] ?? 'Automatisch'}`}
        >
          <!-- Aussen 44 px Tippziel, innen das gewohnte 32-px-Kaestchen. -->
          <span
            class="grid size-8 place-items-center rounded-md border border-border-stark transition-colors duration-fast ease-saganta hover:bg-surface-2"
          >
            <Icon
              name={theme === 'light' ? 'sun' : theme === 'dark' ? 'moon' : 'monitor'}
              size={15}
            />
          </span>
        </button>
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
