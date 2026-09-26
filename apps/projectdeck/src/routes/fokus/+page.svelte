<script lang="ts">
  import { enhance } from '$app/forms';
  import { Button, Icon } from '@saganta/ui';
  import { PROJECT_STATUS } from '$lib/meta';
  import type { PageData, ActionData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();
  let focusIds = $state<number[]>(data.focus?.project_ids ?? []);
  let maintIds = $state<number[]>(data.focus?.maintenance_project_ids ?? []);

  function toggle(id: number) {
    if (focusIds.includes(id)) focusIds = focusIds.filter((x) => x !== id);
    else if (focusIds.length < 3) {
      focusIds = [...focusIds, id];
      maintIds = maintIds.filter((x) => x !== id); // nicht gleichzeitig Wartung
    }
  }
  function toggleMaint(id: number) {
    if (maintIds.includes(id)) maintIds = maintIds.filter((x) => x !== id);
    else {
      maintIds = [...maintIds, id];
      focusIds = focusIds.filter((x) => x !== id); // nicht gleichzeitig Hauptfokus
    }
  }
  // Dedup gegen Svelte-5 each_key_duplicate (doppelte id-Keys → Hydration-Crash).
  function uniqueBy<T>(arr: readonly T[], key: (x: T) => unknown): T[] {
    const seen = new Set<unknown>();
    return arr.filter((x) => {
      const k = key(x);
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }
  // schedulebare Kandidaten = nicht eingefroren/archiviert/shutdown
  let candidates = $derived(
    uniqueBy(
      data.projects.filter((p) => !['frozen', 'archived', 'shutdown'].includes(p.status)),
      (p) => p.id,
    ),
  );
</script>

<h1 class="font-display text-2xl">Weekly Focus</h1>
<p class="mt-1 text-sm text-muted">
  Maximal 3 Hauptprojekte für diese Woche{data.focus ? ` (${data.focus.week_iso})` : ''},
  bewusster Schutz gegen Überplanung. <span class="text-text">{focusIds.length}/3</span> gewählt.
</p>

{#if form && 'error' in form && form.error}
  <p class="mt-3 text-sm text-fehler">{form.error}</p>
{/if}
{#if form && 'ok' in form && form.ok}
  <p class="mt-3 text-sm text-erfolg">Fokus gespeichert.</p>
{/if}

<form method="POST" action="?/save" use:enhance class="mt-6">
  <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
    {#each candidates as p (p.id)}
      {@const on = focusIds.includes(p.id)}
      <button
        type="button"
        onclick={() => toggle(p.id)}
        class="flex flex-col items-start gap-1 rounded-lg border px-4 py-3 text-left transition-colors duration-fast ease-saganta {on
          ? 'border-accent-500 bg-accent-500/10'
          : 'border-border bg-surface-2/40 hover:border-accent-500/40'}"
      >
        <span class="flex items-center gap-1.5 font-medium">
          {#if on}<Icon name="star" size={14} filled class="text-accent-400" />{/if}{p.name}
        </span>
        <span class="text-xs text-muted">{PROJECT_STATUS[p.status] ?? p.status}</span>
      </button>
    {/each}
  </div>
  {#each focusIds as id}<input type="hidden" name="focus" value={id} />{/each}

  <h2 class="mt-8 font-display text-lg">
    Wartung <span class="text-sm font-normal text-muted">(laufende Pflege, kein 3er-Limit)</span>
  </h2>
  <p class="mt-1 text-sm text-muted">
    Projekte, die nebenher weiterlaufen: bekommen Wartungsblöcke ohne den Fokus zu belegen.
  </p>
  <div class="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
    {#each candidates as p (p.id)}
      {@const on = maintIds.includes(p.id)}
      <button
        type="button"
        onclick={() => toggleMaint(p.id)}
        class="flex flex-col items-start gap-1 rounded-lg border px-4 py-3 text-left transition-colors duration-fast ease-saganta {on
          ? 'border-warm-500/60 bg-warm-500/10'
          : 'border-border bg-surface-2/40 hover:border-warm-500/40'}"
      >
        <span class="flex items-center gap-1.5 font-medium">
          {#if on}<span class="text-warm-500" aria-hidden="true">●</span>{/if}{p.name}
        </span>
        <span class="text-xs text-muted">{PROJECT_STATUS[p.status] ?? p.status}</span>
      </button>
    {/each}
  </div>
  {#each maintIds as id}<input type="hidden" name="maint" value={id} />{/each}

  <Button type="submit" variant="primary" class="mt-5">Wochenfokus speichern</Button>
</form>
