<script lang="ts">
  import { Icon } from '@saganta/ui';
  import { RISK_COLORS, DEADLINE_TYPE, fmtMinutes } from '$lib/meta';
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
</script>

<h1 class="font-display text-2xl">Deadline Center</h1>
<p class="mt-1 text-sm text-muted">Kunden-Hard-Deadlines zuerst, dann nach Risiko sortiert.</p>

{#if data.risks.length === 0}
  <p class="mt-6 text-sm text-muted">Keine Projekte mit Deadline.</p>
{:else}
  <ul class="mt-6 flex flex-col gap-2">
    {#each data.risks as r (r.project_id)}
      <li class={`flex flex-wrap items-center gap-3 rounded-lg border bg-surface-2/40 px-4 py-3 ${RISK_COLORS[r.risk_level] ?? 'border-border'}`}>
        <span class="font-mono text-xs uppercase">{r.risk_level}</span>
        <a href={`/projekte/${r.slug}`} class="font-medium text-text hover:underline">{r.name}</a>
        {#if r.deadline_type}<span class="text-xs text-muted">{DEADLINE_TYPE[r.deadline_type] ?? r.deadline_type}</span>{/if}
        <span class="ml-auto text-xs text-muted">
          {r.deadline_date}
          {#if r.days_until_deadline !== null}· {r.days_until_deadline}d{/if}
          · offen {fmtMinutes(r.total_remaining_minutes)}
        </span>
        {#if !r.has_schedulable_tasks}
          <span class="inline-flex items-center gap-1 text-xs text-warnung"><Icon name="alert-triangle" size={12} /> keine planbaren Tasks</span>
        {/if}
      </li>
    {/each}
  </ul>
{/if}
