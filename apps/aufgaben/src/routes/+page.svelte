<script lang="ts">
  import { enhance } from '$app/forms';
  import { Icon, appUrlById } from '@saganta/ui';
  import { page } from '$app/stores';
  import AufgabeZeile from '$lib/components/AufgabeZeile.svelte';
  import AufgabeDialog from '$lib/components/AufgabeDialog.svelte';
  import Tagesplan from '$lib/components/Tagesplan.svelte';
  import SchnellErfassen from '$lib/components/SchnellErfassen.svelte';
  import type { Aufgabe, Planung } from '$lib/aufgaben-bff';
  import { dauer, demnaechst, pool, tagesGruppen } from '$lib/ordnen';
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();

  const heute = $derived(data.heute);
  const gruppen = $derived(tagesGruppen(data.aufgaben, heute));
  const vorrat = $derived(pool(data.aufgaben, heute));
  const kommend = $derived(demnaechst(data.aufgaben, heute));
  const projekteNach = $derived(new Map(data.projekte.map((p) => [p.id, p])));
  const kapazitaet = $derived(data.tagesbild?.capacity ?? null);
  const frei = $derived(data.tagesbild?.free_minutes ?? 0);
  const liegen = $derived(data.tagesbild?.backlog ?? []);
  const offeneAnzahl = $derived(gruppen.reduce((n, g) => n + g.aufgaben.length, 0));

  const notizenBasis = $derived(appUrlById('notizen', $page.url.host));
  const kalenderBasis = $derived(appUrlById('calendar', $page.url.host));

  // Der Bearbeiten-Dialog. Bewusst ein lokaler Zustand und kein Routenwechsel:
  // eine Aufgabe zu oeffnen soll die Liste nicht verlassen.
  let bearbeitet = $state<Aufgabe | null>(null);
  const notizenZu = $derived(bearbeitet ? (data.notizenNach[bearbeitet.id] ?? []) : []);

  const plan = $derived(
    form && typeof form === 'object' && 'plan' in form ? (form.plan as Planung) : null,
  );
  const planFestgelegt = $derived(
    !!(form && typeof form === 'object' && 'festgelegt' in form && form.festgelegt),
  );
  const fehlermeldung = $derived(
    form && typeof form === 'object' && 'fehler' in form ? String(form.fehler) : null,
  );

  // Die Stufen der Tageskapazitaet, farblich codiert. Dieselbe Bedeutung wie im
  // Kalender, damit ein Blick genuegt.
  const STUFE: Record<string, { label: string; klasse: string; symbol: string }> = {
    geladen: { label: 'Geladen', klasse: 'border-erfolg/40 bg-erfolg/10 text-erfolg', symbol: 'zap' },
    normal: { label: 'Normal', klasse: 'border-info/40 bg-info/10 text-info', symbol: 'gauge' },
    geschont: {
      label: 'Geschont',
      klasse: 'border-warnung/40 bg-warnung/10 text-warnung',
      symbol: 'battery',
    },
    erschöpft: {
      label: 'Erschöpft',
      klasse: 'border-fehler/40 bg-fehler/10 text-fehler',
      symbol: 'armchair',
    },
  };
  const stufe = $derived(STUFE[kapazitaet?.level ?? 'normal'] ?? STUFE.normal!);
</script>

<svelte:head><title>Heute · Aufgaben</title></svelte:head>

<div class="space-y-6">
  <header class="flex flex-wrap items-end justify-between gap-3">
    <div>
      <p class="font-mono text-xs uppercase tracking-widest text-muted">Saganta · Aufgaben</p>
      <h1 class="font-display text-3xl leading-tight">Heute</h1>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      {#if kapazitaet}
        <span
          class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium {stufe.klasse}"
          title={kapazitaet.reason}
        >
          <Icon name={stufe.symbol} size={13} />{stufe.label}
        </span>
      {/if}
      {#if frei > 0}
        <span class="inline-flex items-center gap-1.5 text-xs text-muted">
          <Icon name="clock" size={13} />{dauer(frei)} frei
        </span>
      {/if}
    </div>
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

  <!-- Planen steht oben, weil es der erste Griff des Tages ist: rechnen lassen,
       dann entscheiden. -->
  <Tagesplan {plan} festgelegt={planFestgelegt} {heute} poolGroesse={vorrat.length} />

  <SchnellErfassen projekte={data.projekte} {heute} />

  {#if liegen.length > 0}
    <section class="rounded-lg border border-warnung/40 bg-warnung/[0.07] p-3">
      <h2 class="flex items-center gap-2 text-sm font-medium text-warnung">
        <Icon name="chevrons-right" size={15} /> Bleibt liegen
      </h2>
      <ul class="mt-1.5 space-y-0.5 text-xs text-warnung/80">
        {#each liegen.slice(0, 3) as b (b.todo_id)}
          <li>{b.title} · {b.defer_count}× verschoben</li>
        {/each}
      </ul>
      <p class="mt-1.5 text-xs text-muted">
        {liegen.length > 3 ? `+${liegen.length - 3} weitere. ` : ''}Heute dranbleiben oder bewusst
        streichen.
      </p>
    </section>
  {/if}

  <!-- Der Tag selbst -->
  {#if offeneAnzahl === 0}
    <section
      class="rounded-xl border border-dashed border-border bg-surface-2/30 px-6 py-10 text-center"
    >
      <span class="inline-flex text-muted"><Icon name="circle-check" size={28} /></span>
      <p class="mt-3 text-sm text-muted">Heute steht nichts an.</p>
      {#if vorrat.length > 0}
        <p class="mt-1 text-xs text-muted">
          {vorrat.length}
          {vorrat.length === 1 ? 'Aufgabe wartet' : 'Aufgaben warten'} im Vorrat.
        </p>
      {/if}
    </section>
  {:else}
    {#each gruppen as gruppe (gruppe.schluessel)}
      <section class="space-y-2">
        <h2 class="flex items-center gap-2 text-sm font-medium">
          <span
            class="text-muted {gruppe.schluessel === 'ueberfaellig' ? 'text-fehler' : ''}"
            ><Icon name={gruppe.symbol} size={15} /></span
          >
          <span class={gruppe.schluessel === 'ueberfaellig' ? 'text-fehler' : ''}
            >{gruppe.titel}</span
          >
          <span class="text-xs font-normal text-muted">{gruppe.aufgaben.length}</span>
        </h2>
        <ul class="space-y-1.5">
          {#each gruppe.aufgaben as a (a.id)}
            <AufgabeZeile
              aufgabe={a}
              {heute}
              projekt={a.project_id ? (projekteNach.get(a.project_id) ?? null) : null}
              notizen={data.notizenNach[a.id] ?? []}
              zeigeDatum={gruppe.schluessel !== 'heute'}
              oeffnen={(x) => (bearbeitet = x)}
            />
          {/each}
        </ul>
      </section>
    {/each}
  {/if}

  <!-- Tagesziele: wenige, grobe Absichten. Bewusst getrennt von den Aufgaben,
       weil sie eine andere Frage beantworten („woran erkenne ich heute Abend,
       dass der Tag gut war?"). -->
  <section class="space-y-2 rounded-xl border border-border bg-surface-2/40 p-4">
    <h2 class="flex items-center gap-2 text-sm font-medium">
      <span class="text-muted"><Icon name="target" size={15} /></span> Tagesziele
    </h2>
    {#if data.ziele.length === 0}
      <p class="text-sm text-muted">Keine Ziele für heute.</p>
    {:else}
      <ul class="space-y-1">
        {#each data.ziele as z (z.id)}
          <li
            class="flex items-center gap-2 rounded-lg border border-border bg-surface-2/60 px-3 py-2"
          >
            <span
              class="shrink-0 rounded border px-1.5 py-0.5 font-mono text-[10px] {z.priority === 'A'
                ? 'border-accent-500/60 text-accent-300'
                : 'border-border text-muted'}">{z.priority}</span
            >
            <span
              class="min-w-0 flex-1 truncate text-sm {z.status === 'achieved'
                ? 'text-muted line-through'
                : ''}">{z.title}</span
            >
            <form method="POST" action="?/zielLoeschen" use:enhance>
              <input type="hidden" name="id" value={z.id} />
              <button
                type="submit"
                class="text-muted hover:text-fehler"
                aria-label="Ziel „{z.title}“ löschen"><Icon name="x" size={15} /></button
              >
            </form>
          </li>
        {/each}
      </ul>
    {/if}
    <form
      method="POST"
      action="?/zielAnlegen"
      use:enhance
      class="flex flex-wrap items-center gap-2 pt-1"
    >
      <input type="hidden" name="datum" value={heute} />
      <input
        name="titel"
        placeholder="Ziel für heute…"
        required
        class="min-w-0 flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-sm outline-none focus:border-accent-500"
      />
      <select
        name="prio"
        aria-label="Priorität"
        class="rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
      >
        <option value="A">A</option>
        <option value="B" selected>B</option>
        <option value="C">C</option>
      </select>
      <button
        type="submit"
        class="inline-flex items-center gap-1.5 rounded-md border border-accent-500 px-3 py-1.5 text-sm text-accent-300 hover:bg-accent-500/10"
        ><Icon name="plus" size={14} /> Ziel</button
      >
    </form>
  </section>

  <!-- Blick nach vorn und Vorrat, beide eingeklappt: sie sind Kontext, nicht
       die Arbeit von heute. -->
  {#if kommend.length > 0}
    <details class="group rounded-xl border border-border bg-surface-2/40">
      <summary class="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm">
        <span class="text-muted"><Icon name="calendar-clock" size={15} /></span>
        <span class="font-medium">Diese Woche</span>
        <span class="text-xs text-muted">{kommend.length}</span>
        <span class="flex-1"></span>
        <Icon
          name="chevron-down"
          size={15}
          class="text-muted transition-transform duration-200 group-open:rotate-180"
        />
      </summary>
      <ul class="space-y-1.5 border-t border-border px-4 py-3">
        {#each kommend as a (a.id)}
          <AufgabeZeile
            aufgabe={a}
            {heute}
            projekt={a.project_id ? (projekteNach.get(a.project_id) ?? null) : null}
            notizen={data.notizenNach[a.id] ?? []}
            oeffnen={(x) => (bearbeitet = x)}
          />
        {/each}
      </ul>
    </details>
  {/if}

  {#if vorrat.length > 0}
    <details class="group rounded-xl border border-border bg-surface-2/40">
      <summary class="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm">
        <span class="text-muted"><Icon name="inbox" size={15} /></span>
        <span class="font-medium">Vorrat</span>
        <span class="text-xs text-muted">{vorrat.length} ohne Termin</span>
        <span class="flex-1"></span>
        <Icon
          name="chevron-down"
          size={15}
          class="text-muted transition-transform duration-200 group-open:rotate-180"
        />
      </summary>
      <div class="border-t border-border px-4 py-3">
        <p class="mb-2 text-xs text-muted">
          Aus diesem Vorrat schöpft „Tag planen“. Eine Aufgabe mit geschätzter Dauer lässt sich
          einplanen, eine ohne nicht.
        </p>
        <ul class="space-y-1.5">
          {#each vorrat.slice(0, 25) as a (a.id)}
            <AufgabeZeile
              aufgabe={a}
              {heute}
              projekt={a.project_id ? (projekteNach.get(a.project_id) ?? null) : null}
              notizen={data.notizenNach[a.id] ?? []}
              oeffnen={(x) => (bearbeitet = x)}
            />
          {/each}
        </ul>
        {#if vorrat.length > 25}
          <p class="mt-2 text-center text-xs text-muted">
            <a href="/alle" class="underline hover:text-text"
              >Alle {vorrat.length} Aufgaben im Vorrat ansehen</a
            >
          </p>
        {/if}
      </div>
    </details>
  {/if}

  {#if data.fehler.notizen}
    <!-- Ehrlich benennen, was fehlt: sonst sieht ein Ausfall der Notizen-App aus
         wie „keine Notiz verknuepft". -->
    <p class="text-xs text-muted">
      Die Notizen-App antwortet gerade nicht. Verknüpfte Notizen werden deshalb nicht angezeigt.
    </p>
  {/if}

  <p class="pt-2 text-xs text-muted">
    Termine liegen im <a href={kalenderBasis} class="underline hover:text-text">Kalender</a>,
    Notizen in <a href={notizenBasis} class="underline hover:text-text">Notizen</a>.
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
