<script lang="ts">
  import { Icon, appUrlById } from '@saganta/ui';
  import { page } from '$app/stores';
  import AufgabeZeile from '$lib/components/AufgabeZeile.svelte';
  import AufgabeDialog from '$lib/components/AufgabeDialog.svelte';
  import SchnellErfassen from '$lib/components/SchnellErfassen.svelte';
  import type { Aufgabe } from '$lib/aufgaben-bff';
  import { PRIORITAETEN, PRIO_STIL, istOffen, nachDringlichkeit } from '$lib/ordnen';
  import { zuordnungVon } from '$lib/zuordnung';
  import { filterSlugs, passtZuProjekten } from '$lib/projektfilter';
  import ProjektOptionen from '$lib/components/ProjektOptionen.svelte';
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();

  const heute = $derived(data.heute);
  const projekteNach = $derived(new Map(data.projekte.map((p) => [p.id, p])));
  const listenNach = $derived(new Map(data.listen.map((l) => [l.id, l])));
  const notizenBasis = $derived(appUrlById('notizen', $page.url.host));

  // Die Filter leben im Browser, nicht in der Adresse: sie sind eine Sicht auf
  // dieselbe Liste, kein eigener Ort. Ein Neuladen setzt sie bewusst zurueck.
  let suche = $state('');
  let prio = $state<string>('');
  let projekt = $state<string>('');
  let nurUndatiert = $state(false);
  // Ein Oberprojekt zeigt seine Unterprojekte mit (Entscheid U7); der
  // Schalter engt auf das Projekt selbst ein.
  let nurDieses = $state(false);

  const projektSlug = $derived(projekt.startsWith('projekt:') ? projekt.slice('projekt:'.length) : '');
  const hatUnterprojekte = $derived(!!projektSlug && (data.teilbaum[projektSlug]?.length ?? 0) > 1);
  const projektSlugs = $derived(projektSlug ? filterSlugs(projektSlug, nurDieses, data.teilbaum) : null);

  const gefiltert = $derived(
    data.aufgaben
      .filter(istOffen)
      .filter((a) => !prio || a.priority === prio)
      .filter((a) => !projekt || (projektSlugs ? passtZuProjekten(a, projektSlugs) : zuordnungVon(a) === projekt))
      .filter((a) => !nurUndatiert || !a.due_date)
      .filter((a) => {
        const s = suche.trim().toLowerCase();
        if (!s) return true;
        return (
          a.title.toLowerCase().includes(s) || (a.description ?? '').toLowerCase().includes(s)
        );
      })
      .slice()
      .sort(nachDringlichkeit),
  );

  const aktiveFilter = $derived(!!suche.trim() || !!prio || !!projekt || nurUndatiert);

  let bearbeitet = $state<Aufgabe | null>(null);
  const notizenZu = $derived(bearbeitet ? (data.notizenNach[bearbeitet.id] ?? []) : []);
  const fehlermeldung = $derived(
    form && typeof form === 'object' && 'fehler' in form ? String(form.fehler) : null,
  );
</script>

<svelte:head><title>Alle Aufgaben</title></svelte:head>

<div class="space-y-5">
  <header class="flex flex-wrap items-end justify-between gap-3">
    <div>
      <p class="font-mono text-xs uppercase tracking-widest text-muted">Saganta · Aufgaben</p>
      <h1 class="font-display text-3xl leading-tight">Alle Aufgaben</h1>
    </div>
    <span class="text-sm text-muted"
      >{gefiltert.length}{aktiveFilter ? ` von ${data.aufgaben.filter(istOffen).length}` : ''} offen</span
    >
  </header>

  {#if data.fehler.bff}
    <div class="rounded-lg border border-warnung/40 bg-warnung/10 p-3 text-sm">
      <p class="flex items-center gap-2 font-medium">
        <Icon name="alert-triangle" size={15} /> Die Aufgaben sind gerade nicht erreichbar.
      </p>
      <p class="mt-1 font-mono text-xs text-muted">{data.fehler.bff}</p>
    </div>
  {/if}

  {#if fehlermeldung}
    <p class="rounded-lg border border-fehler/40 bg-fehler/10 px-3 py-2 text-sm">{fehlermeldung}</p>
  {/if}

  <SchnellErfassen projekte={data.projekte} listen={data.listen} {heute} />

  <!-- Filterleiste -->
  <div class="flex flex-wrap items-center gap-2">
    <div
      class="flex min-h-11 min-w-48 flex-1 items-center gap-2 rounded-md border border-border-stark bg-surface-2 px-3 focus-within:border-accent-500 sm:min-h-9"
    >
      <span class="text-muted"><Icon name="search" size={15} /></span>
      <input
        bind:value={suche}
        placeholder="Suchen…"
        aria-label="Aufgaben durchsuchen"
        class="min-w-0 flex-1 bg-transparent text-sm outline-none"
      />
      {#if suche}
        <button
          type="button"
          onclick={() => (suche = '')}
          class="text-muted hover:text-text"
          aria-label="Suche leeren"><Icon name="x" size={14} /></button
        >
      {/if}
    </div>

    <select
      bind:value={prio}
      aria-label="Nach Priorität filtern"
      class="min-h-11 rounded-md border border-border-stark bg-surface-2 px-2 text-sm sm:min-h-9"
    >
      <option value="">Jede Priorität</option>
      {#each PRIORITAETEN as p (p)}
        <option value={p}>{PRIO_STIL[p]?.label}</option>
      {/each}
    </select>

    {#if data.projekte.length > 0 || data.listen.length > 0}
      <select
        bind:value={projekt}
        aria-label="Nach Bereich oder Projekt filtern"
        class="min-h-11 max-w-full rounded-md border border-border-stark bg-surface-2 px-2 text-sm sm:min-h-9"
      >
        <option value="">Jeder Bereich, jedes Projekt</option>
        {#if data.listen.length > 0}
          <optgroup label="Bereiche">
            {#each data.listen as l (l.id)}
              <option value="liste:{l.id}">{l.name}</option>
            {/each}
          </optgroup>
        {/if}
        {#if data.projekte.length > 0}
          <optgroup label="Projekte">
            <ProjektOptionen projekte={data.projekte} praefix="projekt:" />
          </optgroup>
        {/if}
      </select>
    {/if}

    {#if hatUnterprojekte}
      <button
        type="button"
        onclick={() => (nurDieses = !nurDieses)}
        aria-pressed={nurDieses}
        title={nurDieses ? 'Unterprojekte wieder einschließen' : 'Unterprojekte ausblenden'}
        class="inline-flex min-h-11 items-center gap-1.5 rounded-md border px-3 text-sm sm:min-h-9 {nurDieses
          ? 'border-accent-500 bg-accent-500/10 text-akzent'
          : 'border-border-stark text-muted hover:text-text'}"
      >
        <Icon name="folder" size={14} /> Nur dieses Projekt
      </button>
    {/if}

    <button
      type="button"
      onclick={() => (nurUndatiert = !nurUndatiert)}
      aria-pressed={nurUndatiert}
      class="inline-flex min-h-11 items-center gap-1.5 rounded-md border px-3 text-sm sm:min-h-9 {nurUndatiert
        ? 'border-accent-500 bg-accent-500/10 text-akzent'
        : 'border-border-stark text-muted hover:text-text'}"
    >
      <Icon name="inbox" size={14} /> Nur Vorrat
    </button>
  </div>

  {#if hatUnterprojekte && !nurDieses}
    {@const anzahl = (data.teilbaum[projektSlug]?.length ?? 1) - 1}
    <p class="-mt-2 text-xs text-muted">
      Mit {anzahl === 1 ? 'einem Unterprojekt' : `${anzahl} Unterprojekten`}. Angeheftete Aufgaben zählen mit.
    </p>
  {/if}

  {#if gefiltert.length === 0}
    <p class="rounded-xl border border-dashed border-border bg-surface-2/30 px-6 py-10 text-center text-sm text-muted">
      {aktiveFilter ? 'Kein Treffer für diese Filter.' : 'Keine offene Aufgabe.'}
    </p>
  {:else}
    <ul class="space-y-1.5">
      {#each gefiltert as a (a.id)}
        <AufgabeZeile
          aufgabe={a}
          {heute}
          projekt={a.project_id ? (projekteNach.get(a.project_id) ?? null) : null}
              liste={a.liste_id ? (listenNach.get(a.liste_id) ?? null) : null}
          notizen={data.notizenNach[a.id] ?? []}
          oeffnen={(x) => (bearbeitet = x)}
        />
      {/each}
    </ul>
  {/if}
</div>

<AufgabeDialog
  offen={bearbeitet !== null}
  aufgabe={bearbeitet}
  projekte={data.projekte} listen={data.listen}
  notizen={notizenZu}
  {notizenBasis}
  {heute}
  fehler={fehlermeldung}
  schliessen={() => (bearbeitet = null)}
/>
