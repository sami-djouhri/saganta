<script lang="ts">
  import { TILE_LABELS } from '$lib/meta';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
  let d = $derived(data.dashboard);

  // Bereiche, die als Kachel mit Sprungziel sinnvoll sind.
  const TILE_LINKS: Record<string, string> = {
    active_this_week: '/fokus',
    client_projects: '/kunden',
    public_candidates: '/public-pipeline',
    deadline_risks: '/deadlines',
    shutdown_check: '/shutdown',
    without_review: '/reviews',
  };

  const SEVERITY: Record<string, string> = {
    critical: 'text-fehler',
    warn: 'text-warnung',
    info: 'text-info',
  };
</script>

<div class="flex items-center justify-between">
  <h1 class="font-display text-2xl">Dashboard</h1>
  <a
    href="/projekte"
    class="rounded-md bg-accent-500 px-3 py-1.5 text-sm font-medium text-accent-ink hover:bg-accent-400"
    >Projekte verwalten</a
  >
</div>

{#if data.error}
  <p class="mt-4 rounded-lg border border-fehler/40 bg-fehler/10 px-4 py-3 text-sm text-fehler">
    Backend nicht erreichbar: {data.error}
  </p>
{:else if d}
  <p class="mt-1 text-sm text-muted">
    {d.total_projects} Projekte · {d.live_projects} aktiv im Portfolio · Woche {d.week_iso}
  </p>

  <div class="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
    {#each Object.entries(d.counts) as [key, count]}
      {@const href = TILE_LINKS[key] ?? '/projekte'}
      <a
        href={href}
        class="flex flex-col rounded-lg border border-border bg-surface-2/40 p-4 transition-colors hover:border-accent-500/60"
      >
        <span class="text-3xl font-semibold tabular-nums">{count}</span>
        <span class="mt-1 text-sm text-muted">{TILE_LABELS[key] ?? key}</span>
      </a>
    {/each}
  </div>

  <h2 class="mt-10 font-display text-xl">Warnungen & Hinweise</h2>
  {#if d.findings.length === 0}
    <p class="mt-2 text-sm text-muted">Keine offenen Befunde. 👍</p>
  {:else}
    <ul class="mt-3 divide-y divide-border rounded-lg border border-border">
      {#each d.findings as f}
        <li class="flex items-start gap-3 px-4 py-3 text-sm">
          <span class={`mt-0.5 shrink-0 font-mono text-xs ${SEVERITY[f.severity] ?? 'text-muted'}`}
            >{f.severity}</span
          >
          <div class="min-w-0">
            <a href={`/projekte/${f.slug}`} class="font-medium hover:text-text">{f.name}</a>
            <span class="text-muted">: {f.message}</span>
          </div>
        </li>
      {/each}
    </ul>
  {/if}
{:else}
  <p class="mt-4 text-muted">Bitte anmelden.</p>
{/if}
