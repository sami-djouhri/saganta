<script lang="ts">
  import { Icon } from '@saganta/ui';
  import { RISK_COLORS, DEADLINE_TYPE, fmtMinutes } from '$lib/meta';
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
</script>

<h1 class="font-display text-2xl">Fristen</h1>
<p class="mt-1 text-sm text-muted">Feste Kundentermine zuerst, dann nach Risiko sortiert.</p>

{#if data.risks.length === 0}
  <p class="mt-6 text-sm text-muted">Kein Projekt hat eine Frist.</p>
{:else}
  <ul class="mt-6 flex flex-col gap-2">
    {#each data.risks as r (r.project_id)}
      <li class={`flex flex-wrap items-center gap-3 rounded-lg border bg-surface-2/40 px-4 py-3 ${RISK_COLORS[r.risk_level] ?? 'border-border'}`}>
        <span class="font-mono text-xs uppercase">{r.risk_level}</span>
        <a href={`/projekte/${r.slug}`} class="font-medium text-text hover:underline">{r.name}</a>
        {#if r.deadline_type}<span class="text-xs text-muted">{DEADLINE_TYPE[r.deadline_type] ?? r.deadline_type}</span>{/if}
        <span class="ml-auto text-xs text-muted">
          <!-- Seit 2026-10-16 steht hier auch ein Projekt OHNE eigene Deadline,
               wenn darin etwas ueberfaellig ist. Ohne diese Abfrage stuende an
               der Stelle wortwoertlich "null". -->
          {r.deadline_date ?? 'keine Projekt-Frist'}
          {#if r.days_until_deadline !== null}· {r.days_until_deadline}d{/if}
          · offen {fmtMinutes(r.total_remaining_minutes)}
        </span>
        {#if r.overdue_tasks > 0}
          <span class="inline-flex items-center gap-1 text-xs text-warnung"><Icon name="alert-triangle" size={12} /> {r.overdue_tasks} Aufgabe(n) überfällig</span>
        {/if}
        {#if r.overdue_milestones > 0}
          <span class="inline-flex items-center gap-1 text-xs text-warnung"><Icon name="alert-triangle" size={12} /> {r.overdue_milestones} Meilenstein(e) überfällig</span>
        {/if}
        {#if r.open_tasks_without_estimate > 0}
          <!-- Der Grund, aus dem "offen 0 min" keine gute Nachricht ist.
               Bewusst ohne Icon: `Icon` kennt nur eine feste Liste von Namen
               und faellt bei einem unbekannten auf ein Glyph zurueck. -->
          <span class="text-xs text-muted">{r.open_tasks_without_estimate} ohne Aufwandsangabe</span>
        {/if}
        {#if !r.has_schedulable_tasks}
          <span class="inline-flex items-center gap-1 text-xs text-warnung"><Icon name="alert-triangle" size={12} /> keine planbaren Aufgaben</span>
        {/if}
      </li>
    {/each}
  </ul>
{/if}
