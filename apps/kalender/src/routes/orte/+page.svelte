<script lang="ts">
  import { enhance } from '$app/forms';
  import { Icon } from '@saganta/ui';
  import type { ActionData, PageData } from './$types';
  import type { Ort } from './+page.server';

  interface Props {
    data: PageData;
    form: ActionData;
  }
  let { data, form }: Props = $props();

  const ART: Record<Ort['kind'], string> = {
    zuhause: 'Zuhause',
    arbeit: 'Arbeit',
    schule: 'Schule',
    einkauf: 'Einkauf',
    sonstiges: 'Sonstiges',
  };
  // Die Genauigkeit steht dabei, weil sie über die Wegzeit entscheidet: eine
  // Route zum Ortsmittelpunkt kann um Kilometer danebenliegen.
  const GENAU: Record<string, string> = {
    strasse: 'nur Straße, Wegzeit ungenau',
    ort: 'nur Ort, Wegzeit grob',
  };

  interface Treffer {
    text: string;
    lat: number;
    lon: number;
    genauigkeit: string;
  }

  let id = $state('');
  const startArt: Ort['kind'] = data.orte.some((o) => o.kind === 'zuhause') ? 'arbeit' : 'zuhause';
  let kind = $state<Ort['kind']>(startArt);
  let name = $state(ART[startArt]);
  let address = $state('');
  let lat = $state<number | null>(null);
  let lon = $state<number | null>(null);
  let genau = $state('');
  let treffer = $state<Treffer[]>([]);
  let keinTreffer = $state(false);
  let busy = $state(false);
  let warten: ReturnType<typeof setTimeout> | undefined;

  const hatZuhause = $derived(data.orte.some((o) => o.kind === 'zuhause'));
  const ohneLage = $derived(address.trim() !== '' && lat === null);

  function leeren() {
    id = '';
    kind = hatZuhause ? 'arbeit' : 'zuhause';
    name = ART[kind];
    address = '';
    lat = lon = null;
    genau = '';
    treffer = [];
  }

  function aendern(o: Ort) {
    id = o.id;
    kind = o.kind;
    name = o.name;
    address = o.address ?? '';
    lat = o.lat;
    lon = o.lon;
    genau = '';
    treffer = [];
    document.getElementById('ort-name')?.focus();
  }

  function artGewechselt() {
    // Vorbelegen nur, solange niemand selbst einen Namen getippt hat.
    if (!name || Object.values(ART).includes(name)) name = ART[kind];
  }

  function adresseGetippt() {
    // Getippter Text ohne Auswahl: die alte Lage passt nicht mehr dazu.
    lat = lon = null;
    genau = '';
    clearTimeout(warten);
    const q = address.trim();
    if (q.length < 3) {
      treffer = [];
      keinTreffer = false;
      return;
    }
    warten = setTimeout(async () => {
      try {
        const r = await fetch(`/orte/adressen?q=${encodeURIComponent(q)}`);
        const j = (await r.json()) as { treffer?: Treffer[] };
        treffer = (j.treffer ?? []).slice(0, 8);
        keinTreffer = treffer.length === 0;
      } catch {
        treffer = [];
      }
    }, 300);
  }

  function waehlen(t: Treffer) {
    address = t.text;
    lat = t.lat;
    lon = t.lon;
    genau = GENAU[t.genauigkeit] ?? '';
    treffer = [];
    keinTreffer = false;
  }

  function planText(p: NonNullable<NonNullable<ActionData>['plan']>): string {
    const n = (z: number, ein: string, mehr: string) => `${z} ${z === 1 ? ein : mehr}`;
    let t =
      `Für die nächsten sieben Tage: ${n(p.hinwege, 'Arbeits- oder Schulweg', 'Arbeits- oder Schulwege')}, ` +
      `${n(p.heimwege, 'Heimweg', 'Heimwege')}, ${n(p.terminwege, 'Weg zu Terminen', 'Wege zu Terminen')}.`;
    if (p.nahverkehr_gestoert) t += ' Der Fahrplandienst für Bus und Bahn ist gerade nicht erreichbar, deshalb fehlen Wege.';
    else if (p.fehler) t += ` An ${n(p.fehler, 'Tag', 'Tagen')} ging es schief.`;
    return t;
  }

  $effect(() => {
    if (form && 'gespeichert' in form && form.gespeichert) leeren();
  });
</script>

<svelte:head><title>Orte · Kalender</title></svelte:head>

<section class="mx-auto max-w-2xl space-y-6">
  <header class="space-y-2">
    <a href="/" class="inline-flex items-center gap-1 text-sm text-muted hover:text-text">
      <Icon name="chevron-left" size={14} /> Kalender
    </a>
    <h1 class="font-display text-4xl leading-tight">Orte</h1>
    <p class="text-sm text-muted">
      Aus Zuhause und Arbeit (oder Schule) rechnet der Kalender den Weg zur Arbeit, den Heimweg nach dem
      letzten Termin und die Wege zu Terminen mit Ort. Ein Einkaufsort macht den Einkaufs-Vorschlag auf dem
      Heimweg genauer. Ändert sich ein Ort, werden alle Wege neu gerechnet.
    </p>
  </header>

  {#if data.fehler}
    <p class="text-sm text-kupfer">Orte konnten nicht geladen werden: {data.fehler}</p>
  {/if}

  <ul class="divide-y divide-border rounded-xl border border-border bg-surface-2/40">
    {#each data.orte as o (o.id)}
      <li class="flex flex-wrap items-center gap-3 px-4 py-3">
        <span
          class="w-20 shrink-0 rounded-md border border-border-stark px-2 py-0.5 text-center text-xs text-muted"
          >{ART[o.kind] ?? o.kind}</span
        >
        <span class="min-w-0 flex-1">
          <span class="block font-medium">{o.name}</span>
          {#if o.lat === null || o.lon === null}
            <span class="block text-xs text-kupfer"
              >{o.address ? `${o.address}, ohne Lage` : 'ohne Adresse'}: zählt nicht für Wege</span
            >
          {:else}
            <span class="block break-words text-xs text-muted">{o.address ?? `${o.lat}, ${o.lon}`}</span>
          {/if}
        </span>
        <button
          type="button"
          onclick={() => aendern(o)}
          class="min-h-11 rounded-lg border border-border-stark px-3 text-sm text-muted hover:text-text"
          >Ändern</button
        >
        <form
          method="POST"
          action="?/loeschen"
          use:enhance={({ cancel }) => {
            if (!confirm(`„${o.name}“ löschen?`)) cancel();
          }}
        >
          <input type="hidden" name="id" value={o.id} />
          <button
            type="submit"
            class="min-h-11 rounded-lg border border-border-stark px-3 text-sm text-muted hover:text-kupfer"
            >Löschen</button
          >
        </form>
      </li>
    {:else}
      <li class="px-4 py-3 text-sm italic text-muted">Noch kein Ort. Fang mit Zuhause an.</li>
    {/each}
  </ul>

  <form
    method="POST"
    action="?/speichern"
    autocomplete="off"
    use:enhance={({ cancel }) => {
      if (
        ohneLage &&
        !confirm(
          'Die Adresse wurde nicht aus den Vorschlägen gewählt und hat keine Lage. Für Wege zählt der Ort dann nicht. Trotzdem speichern?',
        )
      ) {
        cancel();
        return;
      }
      busy = true;
      return async ({ update }) => {
        await update({ reset: false });
        busy = false;
      };
    }}
    class="space-y-3 rounded-xl border border-border bg-surface-2/60 p-4"
  >
    <h2 class="font-medium">{id ? `„${name}“ ändern` : 'Ort hinzufügen'}</h2>
    <input type="hidden" name="id" value={id} />
    <input type="hidden" name="lat" value={lat ?? ''} />
    <input type="hidden" name="lon" value={lon ?? ''} />
    <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Art</span>
        <select
          name="kind"
          bind:value={kind}
          onchange={artGewechselt}
          class="min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text"
        >
          {#each Object.entries(ART) as [wert, text] (wert)}
            <option value={wert}>{text}</option>
          {/each}
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Name</span>
        <input
          id="ort-name"
          name="name"
          bind:value={name}
          required
          maxlength="200"
          class="min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text outline-none focus:border-accent-400"
        />
      </label>
    </div>
    <label class="flex flex-col gap-1 text-sm">
      <span class="text-muted">Adresse</span>
      <input
        name="address"
        bind:value={address}
        oninput={adresseGetippt}
        maxlength="300"
        placeholder="Straße Hausnummer, Ort"
        class="min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text outline-none focus:border-accent-400"
      />
      <!-- Gemessen 2026-11-01: ohne Komma raet die Suche keinen Ort und findet
           „Hauptstraße Musterstadt" gar nicht, mit Komma schon. -->
      <span class="text-xs text-muted">Mit Komma vor dem Ort, z. B. „Hauptstraße 5, Musterstadt“, dann einen Vorschlag antippen.</span>
    </label>
    {#if treffer.length}
      <ul class="overflow-hidden rounded-lg border border-border-stark bg-surface">
        {#each treffer as t (t.text)}
          <li>
            <button
              type="button"
              onclick={() => waehlen(t)}
              class="flex min-h-11 w-full items-center gap-2 border-b border-border px-3 text-left text-sm last:border-b-0 hover:bg-surface-2"
            >
              {t.text}
              {#if GENAU[t.genauigkeit]}<span class="text-xs text-muted">{GENAU[t.genauigkeit]}</span>{/if}
            </button>
          </li>
        {/each}
      </ul>
    {:else if keinTreffer}
      <p class="text-xs text-muted">Keine Adresse gefunden.</p>
    {/if}
    {#if genau}<p class="text-xs text-kupfer">Achtung: {genau}.</p>{/if}

    <div class="flex flex-wrap items-center justify-end gap-2">
      {#if id}
        <button type="button" onclick={leeren} class="min-h-11 px-3 text-sm text-muted hover:text-text"
          >Neu statt ändern</button
        >
      {/if}
      <button
        type="submit"
        disabled={busy}
        class="min-h-11 rounded-lg bg-accent-500 px-4 text-sm font-medium text-accent-ink hover:bg-accent-400 disabled:opacity-50"
        >{busy ? 'Speichere…' : 'Speichern'}</button
      >
    </div>
    {#if form && 'fehler' in form && form.fehler}
      <p class="text-sm text-kupfer">{form.fehler}</p>
    {/if}
  </form>

  {#if form && 'plan' in form}
    <p class="text-sm text-muted" role="status">
      {#if form.plan}{planText(form.plan)}{:else}Gespeichert. Die Wege konnten nicht neu geplant werden.{/if}
    </p>
  {/if}
</section>
