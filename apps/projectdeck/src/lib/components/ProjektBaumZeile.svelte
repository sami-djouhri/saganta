<script lang="ts">
  import type { Knoten } from '$lib/gliederung';
  import ProjektBaumZeile from './ProjektBaumZeile.svelte';

  let { knoten, tiefe }: { knoten: Knoten; tiefe: number } = $props();
  let offen = $state(false);
  const p = $derived(knoten.projekt);
  const mehrereEltern = $derived((p.eltern_ids?.length ?? 0) > 1);
</script>

<li>
  <div class="flex items-center gap-1" style:padding-left={`${tiefe * 1.1}rem`}>
    {#if knoten.kinder.length}
      <button
        type="button"
        class="grid h-6 w-6 shrink-0 place-items-center rounded text-muted transition-transform duration-fast ease-saganta hover:text-text"
        style:transform={offen ? 'rotate(90deg)' : 'none'}
        aria-expanded={offen}
        aria-label={offen ? `${p.name} zuklappen` : `${p.name} aufklappen`}
        onclick={() => (offen = !offen)}>›</button
      >
    {:else}
      <span class="h-6 w-6 shrink-0" aria-hidden="true"></span>
    {/if}
    <a
      href={`/projekte/${p.slug}`}
      class="flex min-w-0 flex-1 items-center justify-between gap-2 rounded px-1.5 py-1 text-sm transition-colors duration-fast ease-saganta hover:bg-surface-2"
    >
      <span class="flex min-w-0 items-center gap-1.5">
        <span class="truncate">{p.name}</span>
        {#if mehrereEltern}
          <span class="shrink-0 text-xs text-muted" title="Steht auch unter einem anderen Oberprojekt">⇄</span>
        {/if}
      </span>
      <span class="flex shrink-0 items-center gap-1.5 text-xs tabular-nums">
        {#if knoten.summe.ueberfaellig}<span class="text-fehler">{knoten.summe.ueberfaellig}!</span>{/if}
        {#if knoten.summe.hoch}<span class="text-akzent">{knoten.summe.hoch}↑</span>{/if}
        <span class="text-muted">{knoten.summe.offen}</span>
      </span>
    </a>
  </div>
  {#if offen && knoten.kinder.length}
    <ul>
      {#each knoten.kinder as kind (kind.projekt.id)}
        <ProjektBaumZeile knoten={kind} tiefe={tiefe + 1} />
      {/each}
    </ul>
  {/if}
</li>
