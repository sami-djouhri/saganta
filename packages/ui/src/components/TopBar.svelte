<script lang="ts">
  import AppSwitcher from './AppSwitcher.svelte';
  import Icon from './Icon.svelte';
  import { appUrlById } from '../apps';

  interface Props {
    app: string;
    user?: { email: string; name?: string };
    shellUrl?: string;
    /** id der aktiven App (für den App-Wechsler-Highlight). */
    currentAppId?: string;
    /** App-Wechsler-Grid in der TopBar zeigen (Default an). */
    showSwitcher?: boolean;
    /**
     * Host der laufenden Anfrage (`page.url.host`). Hält alle Sprünge aus dieser
     * Leiste im Raum des Aufrufers, siehe `apps.ts`.
     */
    host?: string | null;
    actions?: import('svelte').Snippet;
    /** Optionaler Account-Dropdown-Inhalt (z. B. Einstellungen/Abmelden). Ohne
     *  menu rendert die TopBar das Standard-Konto-Menue (siehe unten). */
    menu?: import('svelte').Snippet;
  }
  let {
    app,
    user,
    shellUrl,
    currentAppId,
    showSwitcher = true,
    host,
    actions,
    menu,
  }: Props = $props();

  // Ohne ausdrückliche `shellUrl` die Shell im Raum des Aufrufers.
  let shellBasis = $derived(shellUrl ?? appUrlById('shell', host));

  let open = $state(false);
  let wrap: HTMLDivElement | undefined = $state();

  function onWindowClick(e: MouseEvent) {
    if (open && wrap && !wrap.contains(e.target as Node)) open = false;
  }
  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') open = false;
  }
</script>

<svelte:window onclick={onWindowClick} onkeydown={onKeydown} />

<!--
  Standard-Konto-Menue fuer jede App, die kein eigenes `menu` mitbringt.

  Bis 2026-08-29 blieb das Nutzer-Badge ohne `menu` ein toter Indikator. Genau so
  war es in kalender, post, news, notizen und projectdeck: sie uebergeben alle nur
  `actions`. Damit fuehrte aus einer angemeldeten Sub-App kein einziger Weg zur
  Downloads-Seite, und wer ueber das Handy dort landete, erfuhr nie, dass es die
  App auch nativ gibt.

  Bewusst absolute URLs auf die Shell: die Sub-Apps liegen auf eigenen Hostnamen,
  ein relativer Pfad zeigte dort ins Leere. Abmelden steht hier NICHT drin, das
  bringt jede App als eigene Route mit.
-->
{#snippet standardMenu()}
  <a
    href="{shellBasis}/konto"
    role="menuitem"
    class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text transition-colors duration-fast ease-saganta hover:bg-surface"
  >
    <Icon name="user" size={16} /> Konto
  </a>
  <a
    href="{shellBasis}/apps"
    role="menuitem"
    class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text transition-colors duration-fast ease-saganta hover:bg-surface"
  >
    <Icon name="download" size={16} /> Apps & Downloads
  </a>
  <a
    href="{shellBasis}/settings"
    role="menuitem"
    class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text transition-colors duration-fast ease-saganta hover:bg-surface"
  >
    <Icon name="settings" size={16} /> Einstellungen
  </a>
{/snippet}

<!--
  Sprung zum Inhalt, erstes fokussierbares Element der Seite. Sichtbar wird er
  nur bei Tastatur-Fokus.

  Er sitzt hier und nicht im Layout jeder App, weil die TopBar ohnehin in allen
  acht Apps als oberstes Element steht. Bis 2026-09-05 hatte ihn ausschliesslich
  die shell: in den anderen sieben Apps musste man sich auf jeder Seite erneut
  durch App-Wechsler, Logo und Konto-Menue tabben, bevor der Inhalt kam. Das
  Sprungziel liefert PageContainer als `<main id="main">`.
-->
<a
  href="#main"
  class="sr-only rounded-lg bg-accent-500 px-4 py-2 text-sm font-semibold text-accent-ink focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50"
>
  Zum Inhalt springen
</a>

<header
  class="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-surface/80 px-4 backdrop-blur-md"
>
  <div class="flex items-center gap-2.5">
    {#if showSwitcher}
      <AppSwitcher {currentAppId} {host} />
    {/if}
    <a
      href={shellBasis}
      class="flex items-center gap-2 text-text"
      aria-label="Zurück zur Saganta-Übersicht"
    >
      <span class="font-display text-xl">Saganta</span>
      <span class="text-muted">/</span>
      <span class="font-medium">{app}</span>
    </a>
  </div>
  <div class="flex items-center gap-3">
    {@render actions?.()}
    {#if user}
      <div class="relative" bind:this={wrap}>
        <button
          type="button"
          onclick={() => (open = !open)}
          class="flex items-center gap-2 rounded-md border border-border px-2 py-1 text-sm transition-colors duration-fast ease-saganta hover:bg-surface-2"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-label="Konto-Menü"
        >
          <span class="size-2 rounded-full bg-erfolg" aria-hidden="true"></span>
          <span class="max-w-40 truncate text-muted">{user.name ?? user.email}</span>
          <span
            class="text-muted transition-transform duration-fast ease-saganta"
            class:rotate-180={open}
            aria-hidden="true">▾</span
          >
        </button>
        {#if open}
          <div
            role="menu"
            class="absolute right-0 top-full z-40 mt-1.5 w-60 overflow-hidden rounded-xl border border-border bg-surface-2 shadow-lg"
          >
            <div class="border-b border-border px-4 py-3">
              {#if user.name}<div class="truncate font-medium text-text">{user.name}</div>{/if}
              <div class="truncate text-xs text-muted">{user.email}</div>
            </div>
            <div class="p-1.5" onclick={() => (open = false)} role="none">
              {#if menu}
                {@render menu()}
              {:else}
                {@render standardMenu()}
              {/if}
            </div>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</header>
