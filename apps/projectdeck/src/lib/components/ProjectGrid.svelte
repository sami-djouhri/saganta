<script lang="ts">
  import type { Project } from '$lib/types';
  import { PROJECT_STATUS, PROJECT_TYPES, fmtMinutes } from '$lib/meta';

  interface Props {
    projects: Project[];
    empty?: string;
  }
  let { projects, empty = 'Keine Projekte.' }: Props = $props();

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
</script>

{#if projects.length === 0}
  <p class="rounded-lg border border-border bg-surface-2/40 px-4 py-6 text-sm text-muted">{empty}</p>
{:else}
  <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
    {#each uniqueBy(projects, (x) => x.id) as p (p.id)}
      <a
        href={`/projekte/${p.slug}`}
        class="group flex flex-col gap-2 rounded-lg border border-border bg-surface-2/40 p-4 transition-colors hover:border-accent-500/60"
      >
        <div class="flex items-start justify-between gap-2">
          <span class="font-medium leading-tight group-hover:text-text">{p.name}</span>
          <span class="shrink-0 rounded border border-border px-1.5 py-0.5 text-[10px] uppercase text-muted"
            >P{p.priority}</span
          >
        </div>
        {#if p.domain}
          <span class="truncate text-[11px] text-muted">{p.domain}</span>
        {/if}
        <div class="flex flex-wrap gap-1 text-[11px] text-muted">
          <span class="rounded bg-surface px-1.5 py-0.5">{PROJECT_TYPES[p.type] ?? p.type}</span>
          <span class="rounded bg-surface px-1.5 py-0.5">{PROJECT_STATUS[p.status] ?? p.status}</span>
          {#if p.open_tasks}
            <span class="rounded bg-surface px-1.5 py-0.5">{p.open_tasks} offen</span>
          {/if}
        </div>
        {#if p.next_action}
          <p class="line-clamp-2 text-xs text-muted">→ {p.next_action}</p>
        {/if}
        <!-- Fusszeile nur, wenn sie etwas zu sagen hat. Sie stand vorher immer
             da und war bei den meisten Projekten leer: `mt-auto` schob sie nach
             unten und zog jede Kachel um eine leere Zeile auseinander. -->
        {#if p.deadline_date || p.weekly_time_budget_minutes}
          <div class="mt-auto flex items-center justify-between text-[11px] text-muted">
            <span>{p.deadline_date ? `⏱ ${p.deadline_date}` : ''}</span>
            <span>{p.weekly_time_budget_minutes ? fmtMinutes(p.weekly_time_budget_minutes) + '/Wo' : ''}</span>
          </div>
        {/if}
      </a>
    {/each}
  </div>
{/if}
