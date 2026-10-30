<script lang="ts">
  import { Icon, appUrlById, projektUrl } from '@saganta/ui';
  import { page } from '$app/stores';
  import AufgabeZeile from '$lib/components/AufgabeZeile.svelte';
  import AufgabeDialog from '$lib/components/AufgabeDialog.svelte';
  import type { Aufgabe } from '$lib/aufgaben-bff';
  import { nachProjekt } from '$lib/ordnen';
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();

  const heute = $derived(data.heute);
  const gruppen = $derived(nachProjekt(data.aufgaben, data.projekte));
  const projekteNach = $derived(new Map(data.projekte.map((p) => [p.id, p])));
  const notizenBasis = $derived(appUrlById('notizen', $page.url.host));
  const deckBasis = $derived(appUrlById('projectdeck', $page.url.host));

  let bearbeitet = $state<Aufgabe | null>(null);
  const notizenZu = $derived(bearbeitet ? (data.notizenNach[bearbeitet.id] ?? []) : []);
  const fehlermeldung = $derived(
    form && typeof form === 'object' && 'fehler' in form ? String(form.fehler) : null,
  );
</script>

<svelte:head><title>Nach Projekt · Aufgaben</title></svelte:head>

<div class="space-y-5">
  <header>
    <p class="font-mono text-xs uppercase tracking-widest text-muted">Saganta · Aufgaben</p>
    <h1 class="font-display text-3xl leading-tight">Nach Projekt</h1>
  </header>

  {#if fehlermeldung}
    <p class="rounded-lg border border-fehler/40 bg-fehler/10 px-3 py-2 text-sm">{fehlermeldung}</p>
  {/if}

  {#if gruppen.length === 0}
    <p
      class="rounded-xl border border-dashed border-border bg-surface-2/30 px-6 py-10 text-center text-sm text-muted"
    >
      Keine offene Aufgabe.
    </p>
  {:else}
    {#each gruppen as gruppe (gruppe.schluessel)}
      {@const projekt = projekteNach.get(gruppe.schluessel)}
      <section class="space-y-2">
        <h2 class="flex items-center gap-2 text-sm font-medium">
          {#if projekt?.color}
            <span class="size-2.5 shrink-0 rounded-full" style="background-color:{projekt.color}"
            ></span>
          {:else}
            <span class="text-muted"><Icon name={gruppe.symbol} size={15} /></span>
          {/if}
          <span>{gruppe.titel}</span>
          <span class="text-xs font-normal text-muted">{gruppe.aufgaben.length}</span>
          {#if projekt?.slug}
            <!-- Der Sprung ins Projekt selbst. Die Aufgaben gehoeren hierher,
                 alles Weitere zum Projekt liegt in ProjectDeck. -->
            <a
              href={projektUrl(projekt.slug, $page.url.host)}
              class="inline-flex items-center gap-1 text-xs font-normal text-muted hover:text-text"
              >In ProjectDeck <Icon name="arrow-right" size={12} /></a
            >
          {/if}
        </h2>
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
      </section>
    {/each}
  {/if}

  <p class="pt-2 text-xs text-muted">
    Projekte selbst werden in <a href={deckBasis} class="underline hover:text-text">ProjectDeck</a>
    geführt. Hier stehen nur die Aufgaben daran.
  </p>
</div>

<AufgabeDialog
  offen={bearbeitet !== null}
  aufgabe={bearbeitet}
  projekte={data.projekte}
  notizen={notizenZu}
  {notizenBasis}
  {heute}
  fehler={fehlermeldung}
  schliessen={() => (bearbeitet = null)}
/>
