<script lang="ts">
  import { enhance } from '$app/forms';
  import { Button, Icon } from '@saganta/ui';
  import ProjectGrid from '$lib/components/ProjectGrid.svelte';
  import { PROJECT_STATUS, PROJECT_TYPES, VISIBILITY } from '$lib/meta';
  import type { PageData, ActionData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();
  let showCreate = $state(false);

  const ACHSEN = [
    { titel: 'Art', feld: 'type' as const, labels: PROJECT_TYPES },
    { titel: 'Stand', feld: 'status' as const, labels: PROJECT_STATUS },
  ];

  let gefiltert = $derived(Boolean(data.filter?.type || data.filter?.status));

  /** Wie oft kommt jeder Wert vor, und zwar ueber ALLE Projekte.
   *
   * Bewusst `data.alleProjekte` und nicht `data.projects`: sobald ein Filter
   * greift, enthaelt letzteres nur noch die Treffer, und die Leiste zeigte
   * dann neben jedem anderen Eintrag eine 0. Eine Zahl, die sich durch das
   * Anschauen aendert, ist schlimmer als keine.
   */
  function zaehle(feld: 'type' | 'status'): [string, number][] {
    const zaehler = new Map<string, number>();
    for (const p of data.alleProjekte ?? data.projects) {
      const wert = p[feld];
      zaehler.set(wert, (zaehler.get(wert) ?? 0) + 1);
    }
    return [...zaehler.entries()].sort((a, b) => b[1] - a[1]);
  }
</script>

<div class="flex items-center justify-between">
  <h1 class="font-display text-2xl">Projekte</h1>
  <Button variant="primary" size="sm" onclick={() => (showCreate = !showCreate)}>
    {#if showCreate}Abbrechen{:else}<Icon name="plus" size={15} /> Neues Projekt{/if}
  </Button>
</div>

{#if showCreate}
  <form
    method="POST"
    action="?/create"
    use:enhance
    class="mt-4 grid gap-3 rounded-lg border border-border bg-surface-2/40 p-4 sm:grid-cols-2"
  >
    {#if form?.error}
      <p class="sm:col-span-2 text-sm text-fehler">{form.error}</p>
    {/if}
    <label class="flex flex-col gap-1 text-sm sm:col-span-2">
      <span class="text-muted">Name</span>
      <input
        name="name"
        required
        class="rounded-md border border-border bg-surface px-3 py-2"
        placeholder="z. B. Djouhri.de"
      />
    </label>
    <label class="flex flex-col gap-1 text-sm">
      <span class="text-muted">Typ</span>
      <select name="type" class="rounded-md border border-border bg-surface px-3 py-2">
        {#each Object.entries(PROJECT_TYPES) as [v, l]}<option value={v}>{l}</option>{/each}
      </select>
    </label>
    <label class="flex flex-col gap-1 text-sm">
      <span class="text-muted">Status</span>
      <select name="status" class="rounded-md border border-border bg-surface px-3 py-2">
        {#each Object.entries(PROJECT_STATUS) as [v, l]}<option value={v}>{l}</option>{/each}
      </select>
    </label>
    <label class="flex flex-col gap-1 text-sm">
      <span class="text-muted">Sichtbarkeit</span>
      <select name="visibility" class="rounded-md border border-border bg-surface px-3 py-2">
        {#each Object.entries(VISIBILITY) as [v, l]}<option value={v}>{l}</option>{/each}
      </select>
    </label>
    <label class="flex flex-col gap-1 text-sm">
      <span class="text-muted">Priorität (1=höchste)</span>
      <input
        name="priority"
        type="number"
        min="1"
        max="5"
        value="3"
        class="rounded-md border border-border bg-surface px-3 py-2"
      />
    </label>
    <label class="flex flex-col gap-1 text-sm sm:col-span-2">
      <span class="text-muted">Nächste Aktion (optional)</span>
      <input name="next_action" class="rounded-md border border-border bg-surface px-3 py-2" />
    </label>
    <div class="sm:col-span-2">
      <Button type="submit" variant="primary">Anlegen</Button>
    </div>
  </form>
{/if}

<!--
  Filterleiste. Der Server konnte schon nach `type` und `status` filtern und gab
  `data.filter` zurueck, es gab nur nie eine Oberflaeche dafuer: bei einem
  Projekt faellt das nicht auf, bei siebzehn schon.

  Zwei Achsen, zwei Zeilen, je beschriftet. In einer Reihe gemischt sieht es aus
  wie eine Liste gleichartiger Filter, und "Eingefroren" steht zweimal darin:
  einmal als Art des Projekts, einmal als sein Stand. Das sind zwei
  verschiedene Fragen, und die Beschriftung ist der ganze Unterschied.

  Reine Links statt Knoepfe mit JS: der Filter steht damit in der Adresse, ist
  teilbar und ueberlebt ein Neuladen.
-->
<div class="mt-4 flex flex-col gap-2 rounded-lg border border-border bg-surface-2/20 p-3">
  <div class="flex flex-wrap items-center gap-2">
    <span class="w-14 shrink-0 text-[11px] uppercase tracking-wide text-muted">Alle</span>
    <a
      href="/projekte"
      class="rounded-md border px-2 py-1 text-xs {gefiltert
        ? 'border-border text-muted'
        : 'border-accent-500/60 bg-surface-2'}"
    >
      {data.projects.length} Projekte
    </a>
  </div>
  {#each ACHSEN as achse (achse.feld)}
    {@const werte = zaehle(achse.feld)}
    {#if werte.length}
      <div class="flex flex-wrap items-center gap-2">
        <span class="w-14 shrink-0 text-[11px] uppercase tracking-wide text-muted">{achse.titel}</span>
        {#each werte as [wert, anzahl] (wert)}
          <a
            href="/projekte?{achse.feld}={wert}"
            class="rounded-md border px-2 py-1 text-xs {data.filter?.[achse.feld] === wert
              ? 'border-accent-500/60 bg-surface-2'
              : 'border-border text-muted'}"
          >
            {achse.labels[wert] ?? wert}
            <span class="text-[10px] opacity-70">{anzahl}</span>
          </a>
        {/each}
      </div>
    {/if}
  {/each}
</div>

<div class="mt-6">
  <ProjectGrid projects={data.projects} empty="Noch keine Projekte, leg dein erstes an." />
</div>
