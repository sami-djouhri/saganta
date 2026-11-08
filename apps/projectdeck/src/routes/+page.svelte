<script lang="ts">
  import { page } from '$app/stores';
  import { aufgabeUrl } from '@saganta/ui';
  import { PRIO_RANG } from '$lib/meta';
  import type { AufgabeUebersicht } from '$lib/types';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
  const host = $derived($page.url.host);

  const SEVERITY: Record<string, string> = {
    critical: 'text-fehler',
    warn: 'text-warnung',
    info: 'text-info',
  };
  const STUFE: Record<string, string> = { critical: 'Kritisch', warn: 'Achtung', info: 'Info' };

  // Wie viele Projekte ausgeklappt oben stehen; der Rest folgt als kurze Zeile.
  const OBEN = 8;
  const JE_PROJEKT = 3;

  // Je Projekt: Zahl offen, Zahl hoch, die dringendsten drei. Sortiert nach
  // "hoch", dann nach Zahl offen. Wartende zaehlen mit, stehen aber hinten,
  // weil man an ihnen gerade nichts tun kann.
  let projekte = $derived.by(() => {
    const m = new Map<string, { slug: string; name: string; offen: number; hoch: number; aufgaben: AufgabeUebersicht[] }>();
    for (const a of data.aufgaben) {
      const slug = a.projekt ?? '';
      let g = m.get(slug);
      if (!g) {
        g = { slug, name: a.project_name, offen: 0, hoch: 0, aufgaben: [] };
        m.set(slug, g);
      }
      if (g.aufgaben.some((x) => x.id === a.id)) continue;
      g.offen += 1;
      if (a.prioritaet === 'hoch') g.hoch += 1;
      g.aufgaben.push(a);
    }
    for (const g of m.values()) {
      g.aufgaben.sort(
        (x, y) => Number(x.wartet) - Number(y.wartet) || (PRIO_RANG[x.prioritaet] ?? 1) - (PRIO_RANG[y.prioritaet] ?? 1),
      );
    }
    return [...m.values()].sort((x, y) => y.hoch - x.hoch || y.offen - x.offen || x.name.localeCompare(y.name));
  });

  let summeHoch = $derived(projekte.reduce((n, g) => n + g.hoch, 0));

  // `geaendert_am` liefert der Aufgaben-Dienst erst seit dem 08.11.; fehlt
  // es, bleibt der Abschnitt weg, statt eine Reihenfolge zu erfinden.
  let zuletzt = $derived(
    data.aufgaben
      .filter((a) => a.geaendert_am)
      .sort((x, y) => (y.geaendert_am ?? '').localeCompare(x.geaendert_am ?? ''))
      .slice(0, 6),
  );

  function wann(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
  }
</script>

<div class="flex flex-wrap items-center justify-between gap-3">
  <h1 class="font-display text-2xl">Was ist offen</h1>
  <div class="flex gap-2 text-sm">
    <a href="/aufgaben" class="rounded-md border border-border-stark px-3 py-1.5 text-muted hover:text-text">Alle offenen Punkte</a>
    <a href="/projekte" class="rounded-md bg-accent-500 px-3 py-1.5 font-medium text-accent-ink hover:bg-accent-400">Projekte</a>
  </div>
</div>

{#if data.aufgabenFehlen}
  <p class="mt-4 rounded border border-warnung/40 bg-warnung/10 px-3 py-2 text-sm text-warnung">
    Der Aufgaben-Dienst antwortet gerade nicht. Die Aufgaben sind nicht verloren, nur nicht abrufbar.
  </p>
{:else if projekte.length === 0}
  <p class="mt-4 text-sm text-muted">Keine offenen Aufgaben in irgendeinem Projekt.</p>
{:else}
  <p class="mt-1 text-sm text-muted">
    {data.aufgaben.length} offen in {projekte.length} Projekten{summeHoch ? `, davon ${summeHoch} mit Priorität hoch` : ''}.
  </p>

  <div class="mt-6 grid gap-3 lg:grid-cols-2">
    {#each projekte.slice(0, OBEN) as g (g.slug)}
      <section class="rounded-lg border border-border bg-surface-2/40 p-4">
        <div class="flex items-baseline justify-between gap-2">
          <a href={`/projekte/${g.slug}`} class="font-medium hover:underline">{g.name}</a>
          <span class="shrink-0 text-xs text-muted tabular-nums">
            {#if g.hoch}<span class="text-akzent">{g.hoch} hoch</span> · {/if}{g.offen} offen
          </span>
        </div>
        <ul class="mt-2 flex flex-col gap-1 text-sm">
          {#each g.aufgaben.slice(0, JE_PROJEKT) as a (a.id)}
            <li class="flex items-start gap-2 {a.wartet ? 'opacity-60' : ''}">
              <span class="mt-1.5 size-1.5 shrink-0 rounded-full {a.prioritaet === 'hoch' ? 'bg-akzent' : 'bg-border-stark'}" aria-hidden="true"></span>
              <a href={aufgabeUrl(a.id, host)} class="min-w-0 flex-1 truncate hover:underline" title={a.titel}>{a.titel}</a>
              {#if a.wartet}<span class="shrink-0 text-xs text-muted">wartet</span>{/if}
            </li>
          {/each}
        </ul>
        {#if g.offen > JE_PROJEKT}
          <a href={`/projekte/${g.slug}`} class="mt-2 inline-block text-xs text-muted hover:text-text">und {g.offen - JE_PROJEKT} weitere</a>
        {/if}
      </section>
    {/each}
  </div>

  {#if projekte.length > OBEN}
    <h2 class="mt-6 text-sm font-semibold text-muted">Weitere Projekte mit offenen Punkten</h2>
    <ul class="mt-2 flex flex-wrap gap-2 text-sm">
      {#each projekte.slice(OBEN) as g (g.slug)}
        <li>
          <a href={`/projekte/${g.slug}`} class="inline-flex gap-1.5 rounded-md border border-border px-2 py-1 hover:border-accent-500/60">
            {g.name}
            <span class="text-xs text-muted tabular-nums">{#if g.hoch}<span class="text-akzent">{g.hoch}</span>/{/if}{g.offen}</span>
          </a>
        </li>
      {/each}
    </ul>
  {/if}

  {#if zuletzt.length}
    <h2 class="mt-10 font-display text-xl">Zuletzt geändert</h2>
    <ul class="mt-3 divide-y divide-border rounded-lg border border-border text-sm">
      {#each zuletzt as a (a.id)}
        <li class="flex items-center gap-3 px-3 py-2">
          <a href={aufgabeUrl(a.id, host)} class="min-w-0 flex-1 truncate hover:underline" title={a.titel}>{a.titel}</a>
          <a href={`/projekte/${a.projekt}`} class="shrink-0 text-xs text-muted hover:text-text">{a.project_name}</a>
          <span class="shrink-0 text-xs text-muted tabular-nums">{wann(a.geaendert_am ?? '')}</span>
        </li>
      {/each}
    </ul>
  {/if}
{/if}

<h2 class="mt-10 font-display text-xl">Hinweise</h2>
{#if data.befundeFehlen}
  <p class="mt-2 text-sm text-warnung">Die Hinweise sind gerade nicht abrufbar.</p>
{:else if data.befunde.length === 0}
  <p class="mt-2 text-sm text-muted">Keine offenen Hinweise.</p>
{:else}
  <ul class="mt-3 divide-y divide-border rounded-lg border border-border">
    {#each data.befunde as f, i (i)}
      <li class="flex items-start gap-3 px-4 py-3 text-sm">
        <span class={`mt-0.5 shrink-0 text-xs font-medium ${SEVERITY[f.severity] ?? 'text-muted'}`}>{STUFE[f.severity] ?? f.severity}</span>
        <div class="min-w-0">
          <a href={`/projekte/${f.slug}`} class="font-medium hover:text-text">{f.name}</a>
          <span class="text-muted">: {f.message}</span>
        </div>
      </li>
    {/each}
  </ul>
{/if}
