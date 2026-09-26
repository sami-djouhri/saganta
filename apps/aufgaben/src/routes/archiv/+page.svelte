<script lang="ts">
  import { Icon, appUrlById } from '@saganta/ui';
  import { page } from '$app/stores';
  import AufgabeZeile from '$lib/components/AufgabeZeile.svelte';
  import AufgabeDialog from '$lib/components/AufgabeDialog.svelte';
  import type { Aufgabe } from '$lib/aufgaben-bff';
  import { datumsEtikett } from '$lib/ordnen';
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();

  const heute = $derived(data.heute);
  const projekteNach = $derived(new Map(data.projekte.map((p) => [p.id, p])));
  const notizenBasis = $derived(appUrlById('notizen', $page.url.host));

  /**
   * Erledigtes nach Abschlusstag, neueste zuerst.
   *
   * ★ Gruppiert wird nach `completed_at`, nicht nach Faelligkeit: hier zaehlt,
   * wann etwas fertig wurde, nicht wann es faellig war. Aufgaben ohne
   * Zeitstempel (aus der Zeit vor dem Feld) landen in einer eigenen Gruppe statt
   * in „heute", was sonst die Tagesbilanz still aufblasen wuerde.
   */
  const nachTag = $derived.by(() => {
    const eimer = new Map<string, Aufgabe[]>();
    for (const a of data.aufgaben) {
      if (!a.completed && a.status !== 'done') continue;
      const tag = a.completed_at ? a.completed_at.slice(0, 10) : '';
      eimer.set(tag, [...(eimer.get(tag) ?? []), a]);
    }
    return [...eimer.entries()]
      .sort((x, y) => (y[0] || '0').localeCompare(x[0] || '0'))
      .map(([tag, aufgaben]) => ({ tag, aufgaben }));
  });

  const gesamt = $derived(nachTag.reduce((n, g) => n + g.aufgaben.length, 0));

  let bearbeitet = $state<Aufgabe | null>(null);
  const notizenZu = $derived(bearbeitet ? (data.notizenNach[bearbeitet.id] ?? []) : []);
  const fehlermeldung = $derived(
    form && typeof form === 'object' && 'fehler' in form ? String(form.fehler) : null,
  );
</script>

<svelte:head><title>Erledigt · Aufgaben</title></svelte:head>

<div class="space-y-5">
  <header class="flex flex-wrap items-end justify-between gap-3">
    <div>
      <p class="font-mono text-xs uppercase tracking-widest text-muted">Saganta · Aufgaben</p>
      <h1 class="font-display text-3xl leading-tight">Erledigt</h1>
    </div>
    <span class="text-sm text-muted">{gesamt} abgehakt</span>
  </header>

  {#if fehlermeldung}
    <p class="rounded-lg border border-fehler/40 bg-fehler/10 px-3 py-2 text-sm">{fehlermeldung}</p>
  {/if}

  {#if gesamt === 0}
    <p
      class="rounded-xl border border-dashed border-border bg-surface-2/30 px-6 py-10 text-center text-sm text-muted"
    >
      Noch nichts abgehakt.
    </p>
  {:else}
    {#each nachTag as gruppe (gruppe.tag || 'ohne')}
      <section class="space-y-2">
        <h2 class="flex items-center gap-2 text-sm font-medium">
          <span class="text-muted"><Icon name="circle-check" size={15} /></span>
          <span>{gruppe.tag ? datumsEtikett(gruppe.tag, heute) : 'Ohne Datum'}</span>
          <span class="text-xs font-normal text-muted">{gruppe.aufgaben.length}</span>
        </h2>
        <ul class="space-y-1.5">
          {#each gruppe.aufgaben as a (a.id)}
            <AufgabeZeile
              aufgabe={a}
              {heute}
              projekt={a.project_id ? (projekteNach.get(a.project_id) ?? null) : null}
              notizen={data.notizenNach[a.id] ?? []}
              zeigeDatum={false}
              oeffnen={(x) => (bearbeitet = x)}
            />
          {/each}
        </ul>
      </section>
    {/each}
  {/if}
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
