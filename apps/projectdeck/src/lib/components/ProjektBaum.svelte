<script lang="ts">
  /**
   * Projekte als Gliederung (15.11.). Oberste Ebene als Karten, darunter die
   * Unterprojekte als Zeilen, tiefer einklappbar. Ein Projekt mit zwei Eltern
   * steht unter beiden; die Zahlen einer Karte zaehlen jedes Projekt ihres
   * Teilbaums einmal.
   */
  import type { Knoten } from '$lib/gliederung';
  import { PROJECT_STATUS } from '$lib/meta';
  import ProjektBaumZeile from './ProjektBaumZeile.svelte';

  let { knoten }: { knoten: Knoten[] } = $props();
</script>

<div class="grid gap-3 lg:grid-cols-2">
  {#each knoten as k (k.projekt.id)}
    {@const p = k.projekt}
    <section class="flex flex-col rounded-lg border border-border bg-surface-2/40">
      <a
        href={`/projekte/${p.slug}`}
        class="group flex items-start justify-between gap-3 rounded-t-lg px-4 pt-4 pb-3 transition-colors duration-fast ease-saganta hover:bg-surface-2/60"
      >
        <div class="min-w-0">
          <h2 class="truncate font-medium leading-tight">{p.name}</h2>
          <p class="mt-0.5 text-xs text-muted">
            {PROJECT_STATUS[p.status] ?? p.status}{#if k.summe.projekte}{` · ${k.summe.projekte} ${k.summe.projekte === 1 ? 'Unterprojekt' : 'Unterprojekte'}`}{/if}
          </p>
        </div>
        <div class="flex shrink-0 items-center gap-1.5 text-xs">
          {#if k.summe.ueberfaellig}
            <span class="rounded bg-fehler/15 px-1.5 py-0.5 text-fehler">{k.summe.ueberfaellig} überfällig</span>
          {/if}
          {#if k.summe.hoch}
            <span class="rounded bg-surface px-1.5 py-0.5 text-akzent">{k.summe.hoch} hoch</span>
          {/if}
          <span class="rounded bg-surface px-1.5 py-0.5 tabular-nums text-muted">{k.summe.offen} offen</span>
        </div>
      </a>
      {#if k.kinder.length}
        <ul class="border-t border-border px-2 py-1.5">
          {#each k.kinder as kind (kind.projekt.id)}
            <ProjektBaumZeile knoten={kind} tiefe={0} />
          {/each}
        </ul>
      {:else if p.next_action}
        <p class="border-t border-border px-4 py-2 text-xs text-muted line-clamp-2">→ {p.next_action}</p>
      {/if}
    </section>
  {/each}
</div>
