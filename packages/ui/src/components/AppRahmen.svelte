<script lang="ts" module>
  export interface NavEintrag {
    href: string;
    label: string;
    icon: string;
    /** Kurzname fuer die Fussleiste am Handy, wenn `label` dort zu lang ist. */
    kurz?: string;
  }
</script>

<script lang="ts">
  /**
   * Seitenleiste am PC, Fussleiste am Handy, dazwischen der Inhalt.
   *
   * Bis 2026-11-08 hatte jede App mit Bereichen ihre eigene Fassung, und sie
   * waren auseinandergelaufen: aufgaben und kontakte hatten unten eine
   * Fussleiste, notizen und projectdeck nicht. Dort war die Seitenleiste unter
   * 768 px ausgeblendet und sonst nichts da, Papierkorb, Freigaben und neun
   * ProjectDeck-Bereiche waren am Handy nur ueber die Adresszeile erreichbar.
   *
   * Mehr als fuenf Eintraege passen nicht nebeneinander auf 360 px; dann zeigt
   * die Fussleiste die ersten vier und „Mehr" fuer den Rest.
   */
  import Icon from './Icon.svelte';

  interface Props {
    nav: readonly NavEintrag[];
    /** Aktueller Pfad (`$page.url.pathname`). */
    pfad: string;
    /** Breite des ganzen Rahmens; Gitter und Boards brauchen mehr. */
    breite?: 'standard' | 'breit';
    children: import('svelte').Snippet;
  }
  let { nav, pfad, breite = 'standard', children }: Props = $props();

  const PLAETZE = 5;
  let unten = $derived(nav.length > PLAETZE ? nav.slice(0, PLAETZE - 1) : nav);
  let rest = $derived(nav.length > PLAETZE ? nav.slice(PLAETZE - 1) : []);
  let mehrOffen = $state(false);
  let restAktiv = $derived(rest.some((e) => aktiv(e.href)));

  function aktiv(href: string): boolean {
    return href === '/' ? pfad === '/' : pfad === href || pfad.startsWith(href + '/');
  }

  // Nach jedem Seitenwechsel ist das Mehr-Feld zu.
  $effect(() => {
    void pfad;
    mehrOffen = false;
  });
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && (mehrOffen = false)} />

<!-- pb-24 am Handy: Platz fuer die feste Fussleiste, sonst laege sie ueber
     dem letzten Eintrag. -->
<div
  class="mx-auto flex gap-6 px-4 pt-6 pb-24 md:px-6 md:pb-6 {breite === 'breit' ? 'max-w-7xl' : 'max-w-6xl'}"
>
  <aside class="hidden w-52 shrink-0 md:block">
    <nav class="sticky top-20 flex flex-col gap-1" aria-label="Bereiche">
      {#each nav as eintrag (eintrag.href)}
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

<!-- Am Handy steht die Navigation unten: dort ist der Daumen. Fest statt
     klebend: klebend stand sie bei kurzen Seiten mitten im Bild, direkt unter
     dem letzten Eintrag. -->
<nav
  class="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden"
  aria-label="Bereiche"
>
  {#if mehrOffen}
    <div
      class="absolute inset-x-2 bottom-full mb-2 overflow-hidden rounded-xl border border-border bg-surface-2 p-1.5 shadow-lg"
    >
      {#each rest as eintrag (eintrag.href)}
        <a
          href={eintrag.href}
          aria-current={aktiv(eintrag.href) ? 'page' : undefined}
          class="flex min-h-11 items-center gap-3 rounded-md px-3 text-sm {aktiv(eintrag.href)
            ? 'bg-surface font-medium text-akzent'
            : 'text-text'}"
        >
          <Icon name={eintrag.icon} size={18} />
          <span>{eintrag.label}</span>
        </a>
      {/each}
    </div>
  {/if}
  <div class="flex">
    {#each unten as eintrag (eintrag.href)}
      <a
        href={eintrag.href}
        aria-current={aktiv(eintrag.href) ? 'page' : undefined}
        class="flex min-h-14 flex-1 flex-col items-center justify-center gap-1 text-xs {aktiv(
          eintrag.href,
        )
          ? 'text-akzent'
          : 'text-muted'}"
      >
        <Icon name={eintrag.icon} size={20} />
        <span>{eintrag.kurz ?? eintrag.label}</span>
      </a>
    {/each}
    {#if rest.length}
      <button
        type="button"
        onclick={() => (mehrOffen = !mehrOffen)}
        aria-expanded={mehrOffen}
        class="flex min-h-14 flex-1 flex-col items-center justify-center gap-1 text-xs {restAktiv ||
        mehrOffen
          ? 'text-akzent'
          : 'text-muted'}"
      >
        <Icon name="menu" size={20} />
        <span>Mehr</span>
      </button>
    {/if}
  </div>
</nav>
