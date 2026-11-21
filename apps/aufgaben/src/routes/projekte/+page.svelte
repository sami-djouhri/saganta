<script lang="ts">
  import { Icon, appUrlById, projektUrl } from '@saganta/ui';
  import { page } from '$app/stores';
  import AufgabeZeile from '$lib/components/AufgabeZeile.svelte';
  import AufgabeDialog from '$lib/components/AufgabeDialog.svelte';
  import type { Aufgabe } from '$lib/aufgaben-bff';
  import { istOffen, nachDringlichkeit } from '$lib/ordnen';
  import { projektAbschnitte } from '$lib/projektfilter';
  import { nachListe } from '$lib/zuordnung';
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();

  const heute = $derived(data.heute);
  const bereiche = $derived(nachListe(data.aufgaben, data.listen));
  // Die Projekte als Baum (seit 2026-11-15): Unterprojekte eingerueckt unter
  // ihrem Oberprojekt, ein Projekt mit zwei Eltern unter beiden; seine
  // Aufgaben stehen beim ersten Auftreten, das zweite ist nur ein Verweis.
  const abschnitte = $derived(projektAbschnitte(data.aufgaben, data.projekte));
  // Was weder Projekt noch Bereich hat. Die Bereiche stehen schon oben.
  const unzugeordnet = $derived(
    data.aufgaben.filter((a) => istOffen(a) && !a.project_id && !a.liste_id).sort(nachDringlichkeit),
  );
  const projekteNach = $derived(new Map(data.projekte.map((p) => [p.id, p])));
  const notizenBasis = $derived(appUrlById('notizen', $page.url.host));
  const deckBasis = $derived(appUrlById('projectdeck', $page.url.host));

  let bearbeitet = $state<Aufgabe | null>(null);
  const notizenZu = $derived(bearbeitet ? (data.notizenNach[bearbeitet.id] ?? []) : []);
  const fehlermeldung = $derived(
    form && typeof form === 'object' && 'fehler' in form ? String(form.fehler) : null,
  );
</script>

<svelte:head><title>Bereiche und Projekte · Aufgaben</title></svelte:head>

<div class="space-y-5">
  <header>
    <p class="font-mono text-xs uppercase tracking-widest text-muted">Saganta · Aufgaben</p>
    <h1 class="font-display text-3xl leading-tight">Bereiche und Projekte</h1>
  </header>

  {#if fehlermeldung}
    <p class="rounded-lg border border-fehler/40 bg-fehler/10 px-3 py-2 text-sm">{fehlermeldung}</p>
  {/if}

  {#if bereiche.length > 0}
    <h2 class="text-xs uppercase tracking-wider text-muted">Bereiche</h2>
    {#each bereiche as gruppe (gruppe.schluessel)}
      <section class="space-y-2">
        <h3 class="flex items-center gap-2 text-sm font-medium">
          <span class="text-muted"><Icon name={gruppe.symbol} size={15} /></span>
          <span>{gruppe.titel}</span>
          {#if gruppe.vertraulich}
            <span class="text-muted" title="nach außen nur „privater Termin“"><Icon name="lock" size={12} /></span>
          {/if}
          <span class="text-xs font-normal text-muted">{gruppe.aufgaben.length}</span>
        </h3>
        {#if gruppe.aufgaben.length > 0}
          <ul class="space-y-1.5">
            {#each gruppe.aufgaben as a (a.id)}
              <AufgabeZeile
                aufgabe={a}
                {heute}
                notizen={data.notizenNach[a.id] ?? []}
                oeffnen={(x) => (bearbeitet = x)}
              />
            {/each}
          </ul>
        {/if}
      </section>
    {/each}
    <h2 class="pt-2 text-xs uppercase tracking-wider text-muted">Projekte</h2>
  {/if}

  {#if abschnitte.length === 0 && unzugeordnet.length === 0}
    <p class="rounded-xl border border-dashed border-border bg-surface-2/30 px-6 py-10 text-center text-sm text-muted">
      Keine offene Projektaufgabe.
    </p>
  {:else}
    {#each abschnitte as ab (ab.zeile.schluessel)}
      {@const projekt = projekteNach.get(ab.zeile.slug)}
      {@const tiefe = Math.min(ab.zeile.tiefe, 4)}
      <section
        class="space-y-2 {tiefe > 0 ? 'border-l border-border pl-3 sm:pl-4' : ''}"
        style={tiefe > 0 ? `margin-left: ${(tiefe - 1) * 1 + 0.25}rem` : undefined}
        id={ab.verweis ? undefined : `projekt-${ab.zeile.slug}`}
      >
        <h3 class="flex flex-wrap items-center gap-x-2 gap-y-1 {tiefe === 0 ? 'text-base font-semibold' : 'text-sm font-medium'}">
          {#if projekt?.color}
            <span class="size-2.5 shrink-0 rounded-full" style="background-color:{projekt.color}"></span>
          {:else}
            <span class="text-muted"><Icon name="folder" size={15} /></span>
          {/if}
          <span>{ab.zeile.name}</span>
          <span class="text-xs font-normal text-muted" title="offene Aufgaben samt Unterprojekten">{ab.imTeilbaum}</span>
          {#if ab.verweis}
            <a href="#projekt-{ab.zeile.slug}" class="text-xs font-normal text-muted underline hover:text-text"
              >steht auch weiter oben</a
            >
          {/if}
          <a
            href={projektUrl(ab.zeile.slug, $page.url.host)}
            class="ml-auto inline-flex min-h-9 items-center gap-1 text-xs font-normal text-muted hover:text-akzent"
            >In ProjectDeck <Icon name="arrow-right" size={12} /></a
          >
        </h3>
        {#if ab.eigene.length > 0}
          <ul class="space-y-1.5">
            {#each ab.eigene as a (a.id)}
              <AufgabeZeile
                aufgabe={a}
                {heute}
                notizen={data.notizenNach[a.id] ?? []}
                oeffnen={(x) => (bearbeitet = x)}
              />
            {/each}
          </ul>
        {/if}
        {#if ab.angeheftet.length > 0}
          <p class="text-xs uppercase tracking-wider text-muted">Angeheftet</p>
          <ul class="space-y-1.5">
            {#each ab.angeheftet as a (a.id)}
              <AufgabeZeile
                aufgabe={a}
                {heute}
                projekt={a.project_id ? (projekteNach.get(a.project_id) ?? null) : null}
                notizen={data.notizenNach[a.id] ?? []}
                oeffnen={(x) => (bearbeitet = x)}
              />
            {/each}
          </ul>
        {/if}
      </section>
    {/each}

    {#if unzugeordnet.length > 0}
      <section class="space-y-2 pt-2">
        <h3 class="flex items-center gap-2 text-sm font-medium">
          <span class="text-muted"><Icon name="circle" size={15} /></span>
          <span>Nicht zugeordnet</span>
          <span class="text-xs font-normal text-muted">{unzugeordnet.length}</span>
        </h3>
        <ul class="space-y-1.5">
          {#each unzugeordnet as a (a.id)}
            <AufgabeZeile aufgabe={a} {heute} notizen={data.notizenNach[a.id] ?? []} oeffnen={(x) => (bearbeitet = x)} />
          {/each}
        </ul>
      </section>
    {/if}
  {/if}

  <p class="pt-2 text-xs text-muted">
    Projekte und ihre Gliederung werden in <a href={deckBasis} class="underline hover:text-akzent">ProjectDeck</a>
    geführt. Hier stehen nur die Aufgaben daran.
  </p>
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
