<script lang="ts">
  import { enhance } from '$app/forms';
  import { page } from '$app/stores';
  import { Icon, appUrlById, aufgabeUrl } from '@saganta/ui';
  import { PROJECT_STATUS, fmtMinutes } from '$lib/meta';
  import type { AufgabeUebersicht } from '$lib/types';
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();

  const host = $derived($page.url.host);
  let suche = $state('');

  let gefiltert = $derived(
    data.aufgaben.filter((t) => {
      const q = suche.trim().toLowerCase();
      if (!q) return true;
      return (
        t.titel.toLowerCase().includes(q) ||
        (t.notiz ?? '').toLowerCase().includes(q) ||
        t.project_name.toLowerCase().includes(q)
      );
    }),
  );

  // Nach Projekt gruppiert, die Projekte in der Reihenfolge ihrer dringendsten
  // Aufgabe. Die Liste kommt schon nach Prioritaet sortiert vom Dienst, die
  // erste Zeile eines Projekts legt also seinen Platz fest.
  let gruppen = $derived.by(() => {
    const m = new Map<number, { name: string; status: string; slug: string; aufgaben: AufgabeUebersicht[] }>();
    for (const t of gefiltert) {
      let g = m.get(t.project_id);
      if (!g) {
        g = { name: t.project_name, status: t.project_status, slug: t.projekt ?? '', aufgaben: [] };
        m.set(t.project_id, g);
      }
      if (!g.aufgaben.some((x) => x.id === t.id)) g.aufgaben.push(t);
    }
    return [...m.entries()];
  });
</script>

<h1 class="font-display text-2xl">Offene Punkte</h1>
<p class="mt-1 text-sm text-muted">
  Alle offenen Aufgaben aus allen Projekten, nach Projekt geordnet. Ein Klick öffnet die Aufgabe in
  <a href={appUrlById('aufgaben', host)} class="underline hover:text-text">Saganta Aufgaben</a>.
</p>

<div class="mt-4 flex flex-wrap items-center gap-3">
  <input
    type="search"
    bind:value={suche}
    placeholder="Suchen in Titel, Notiz und Projekt"
    aria-label="Offene Punkte durchsuchen"
    class="min-w-64 flex-1 rounded-md border border-border-stark bg-surface px-3 py-2 text-sm"
  />
  <span class="text-xs text-muted">{gefiltert.length} von {data.aufgaben.length}</span>
</div>

{#if form && typeof form === 'object' && 'error' in form}
  <p class="mt-3 text-sm text-fehler" role="alert">Abhaken ging nicht: {form.error}</p>
{/if}

{#if data.fehlt}
  <p class="mt-6 rounded border border-warnung/40 bg-warnung/10 px-3 py-2 text-sm text-warnung">
    Der Aufgaben-Dienst antwortet gerade nicht.
  </p>
{:else if data.aufgaben.length === 0}
  <p class="mt-6 text-sm text-muted">Keine offenen Punkte.</p>
{:else if gruppen.length === 0}
  <p class="mt-6 text-sm text-muted">Nichts passt zu diesem Filter.</p>
{:else}
  <div class="mt-6 flex flex-col gap-6">
    {#each gruppen as [pid, g] (pid)}
      <section>
        <h2 class="flex items-baseline gap-2 text-sm font-semibold">
          <a href={`/projekte/${g.slug}`} class="text-text hover:underline">{g.name}</a>
          <span class="text-xs font-normal text-muted">{PROJECT_STATUS[g.status] ?? g.status} · {g.aufgaben.length} offen</span>
        </h2>
        <ul class="mt-2 divide-y divide-border rounded-lg border border-border">
          {#each g.aufgaben as t (t.id)}
            <li class="flex items-start gap-3 px-3 py-2 text-sm {t.wartet ? 'opacity-60' : ''}">
              <form method="POST" action="?/abhaken" use:enhance class="pt-0.5">
                <input type="hidden" name="id" value={t.id} />
                <input type="hidden" name="project_id" value={t.project_id} />
                <button class="relative block text-muted transition-colors duration-fast ease-saganta before:absolute before:-inset-3 before:content-[''] hover:text-text" title="Erledigt" aria-label="Als erledigt abhaken"><Icon name="square" size={18} /></button>
              </form>
              <div class="min-w-0 flex-1">
                <a href={aufgabeUrl(t.id, host)} class="hover:underline" title="In Saganta Aufgaben öffnen">{t.titel}</a>
                {#if t.notiz}
                  <p class="mt-0.5 line-clamp-3 whitespace-pre-line text-xs text-muted">{t.notiz}</p>
                {/if}
              </div>
              <span class="shrink-0 text-xs text-muted">
                {t.prioritaet}{#if t.wartet} · wartet{/if}{#if t.faellig} · fällig {t.faellig}{/if}{#if t.dauer_min} · {fmtMinutes(t.dauer_min)}{/if}
              </span>
            </li>
          {/each}
        </ul>
      </section>
    {/each}
  </div>
{/if}
