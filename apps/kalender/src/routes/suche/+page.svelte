<script lang="ts">
  import type { PageData } from './$types';
  import type { Treffer } from './+page.server';

  let { data }: { data: PageData } = $props();

  const GRUPPEN: { kind: string; titel: string }[] = [
    { kind: 'event', titel: 'Termine' },
    { kind: 'todo', titel: 'Aufgaben' },
    { kind: 'goal', titel: 'Tagesziele' },
    { kind: 'contact', titel: 'Kontakte' },
  ];

  function datum(iso: string | null): string {
    if (!iso) return '';
    const [j, m, t] = iso.slice(0, 10).split('-');
    return `${Number(t)}.${Number(m)}.${j}`;
  }

  /**
   * Termin: Woche des Termins, `termin` oeffnet ihn dort. Bei einer Serie ist das
   * Datum der Beginn der Reihe; dann zeigt die Woche das erste Vorkommen.
   * Tagesziel und Aufgabe: die Woche ihres Tages. Kontakte haben keinen Ort im
   * Kalender (gepflegt in Saganta Kontakte), daher kein Link.
   */
  function ziel(t: Treffer): string | null {
    if (!t.date) return null;
    const woche = `/?view=week&week=${t.date.slice(0, 10)}`;
    return t.kind === 'event' ? `${woche}&termin=${encodeURIComponent(t.id)}` : woche;
  }

  const gruppen = $derived(
    GRUPPEN.map((g) => ({ ...g, liste: data.treffer.filter((t) => t.kind === g.kind) })).filter(
      (g) => g.liste.length > 0,
    ),
  );
</script>

<svelte:head><title>Suche · Kalender</title></svelte:head>

<section class="mx-auto max-w-2xl space-y-6 px-4 py-6">
  <header class="flex items-center justify-between gap-3">
    <div>
      <p class="font-mono text-xs uppercase tracking-widest text-muted">Saganta · Kalender</p>
      <h1 class="font-display text-3xl">Suche</h1>
    </div>
    <a href="/" class="rounded-lg border border-border-stark px-4 py-2 text-sm text-muted hover:text-text">Zurück</a>
  </header>

  <form method="GET" class="flex gap-2" role="search">
    <input
      type="search"
      name="q"
      value={data.q}
      maxlength="100"
      placeholder="Termin, Aufgabe, Ziel oder Kontakt"
      aria-label="Suchbegriff"
      class="min-h-11 flex-1 rounded-lg border border-border-stark bg-surface px-3 text-text"
    />
    <button type="submit" class="min-h-11 rounded-lg bg-accent-500 px-4 text-sm font-medium text-accent-ink hover:bg-accent-400">Suchen</button>
  </form>

  {#if data.fehler}
    <p class="text-sm text-kupfer">{data.fehler}</p>
  {:else if data.q && data.treffer.length === 0}
    <p class="text-sm text-muted">Nichts gefunden für „{data.q}“.</p>
  {/if}

  {#each gruppen as g (g.kind)}
    <div class="space-y-2">
      <h2 class="font-mono text-xs uppercase tracking-wider text-muted">{g.titel}</h2>
      <ul class="divide-y divide-border rounded-xl border border-border bg-surface-2/60">
        {#each g.liste as t (t.kind + t.id)}
          {@const link = ziel(t)}
          <li>
            {#if link}
              <a href={link} class="flex items-baseline justify-between gap-3 px-4 py-3 hover:bg-surface-2">
                <span class="min-w-0 truncate">{t.title}</span>
                <span class="shrink-0 font-mono text-xs tabular-nums text-muted">{datum(t.date)}</span>
              </a>
            {:else}
              <div class="flex items-baseline justify-between gap-3 px-4 py-3">
                <span class="min-w-0 truncate">{t.title}</span>
                <span class="shrink-0 text-xs text-muted">{t.kind === 'contact' ? 'in Saganta Kontakte' : ''}</span>
              </div>
            {/if}
          </li>
        {/each}
      </ul>
    </div>
  {/each}
</section>
