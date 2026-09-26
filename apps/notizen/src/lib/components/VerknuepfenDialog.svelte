<script lang="ts">
  import { Button, Icon, Spinner } from '@saganta/ui';
  import { TYP_BESCHRIFTUNG, TYP_SYMBOL } from '$lib/verknuepfungen';
  import type { Fundstueck, VerknuepfungsTyp } from '$lib/types';

  let {
    offen = false,
    schliessen,
    uebernehmen,
  }: {
    offen?: boolean;
    schliessen: () => void;
    uebernehmen: (fund: Fundstueck) => void;
  } = $props();

  const TYPEN: (VerknuepfungsTyp | 'alle')[] = [
    'alle',
    'termin',
    'aufgabe',
    'ziel',
    'projekt',
    'kontakt',
    'brief',
  ];

  let suche = $state('');
  let typ = $state<VerknuepfungsTyp | 'alle'>('alle');
  let treffer = $state<Fundstueck[]>([]);
  let stumm = $state<VerknuepfungsTyp[]>([]);
  let laedt = $state(false);
  let fehler = $state('');

  let lauf = 0;
  async function abrufen() {
    // Jeder Aufruf bekommt eine Nummer; nur die Antwort des jüngsten wird
    // übernommen. Ohne das überschreibt eine langsame frühere Anfrage die
    // schon angezeigten Treffer der späteren: beim Tippen der Normalfall.
    const meiner = ++lauf;
    laedt = true;
    fehler = '';
    try {
      const frage = new URLSearchParams({ q: suche });
      if (typ !== 'alle') frage.set('typ', typ);
      const res = await fetch(`/verknuepfbar?${frage}`);
      if (!res.ok) throw new Error(`${res.status}`);
      const daten = (await res.json()) as { treffer: Fundstueck[]; stumm: VerknuepfungsTyp[] };
      if (meiner !== lauf) return;
      treffer = daten.treffer;
      stumm = daten.stumm;
    } catch (e) {
      if (meiner !== lauf) return;
      fehler = 'Die Suche hat nicht geantwortet.';
      treffer = [];
    } finally {
      if (meiner === lauf) laedt = false;
    }
  }

  let entprellung: ReturnType<typeof setTimeout> | undefined;
  function tippen() {
    clearTimeout(entprellung);
    entprellung = setTimeout(abrufen, 250);
  }

  $effect(() => {
    if (offen) abrufen();
  });
</script>

{#if offen}
  <div
    class="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 pt-16"
    role="presentation"
    onclick={(e) => e.target === e.currentTarget && schliessen()}
  >
    <div
      class="flex max-h-[70vh] w-full max-w-xl flex-col rounded-lg border border-border bg-surface shadow-xl"
      role="dialog"
      aria-modal="true"
      aria-label="Notiz verknüpfen"
    >
      <div class="flex items-center gap-2 border-b border-border p-3">
        <span class="text-muted"><Icon name="search" size={16} /></span>
        <!-- svelte-ignore a11y_autofocus -->
        <input
          bind:value={suche}
          oninput={tippen}
          autofocus
          placeholder="Termin, Aufgabe, Projekt, Kontakt oder Brief suchen…"
          class="min-w-0 flex-1 bg-transparent text-sm outline-none"
        />
        {#if laedt}<Spinner size={16} />{/if}
        <button type="button" onclick={schliessen} class="text-muted hover:text-text" aria-label="Schließen">
          <Icon name="x" size={16} />
        </button>
      </div>

      <div class="flex flex-wrap gap-1 border-b border-border px-3 py-2">
        {#each TYPEN as t (t)}
          <button
            type="button"
            onclick={() => {
              typ = t;
              abrufen();
            }}
            class="rounded-full border px-2.5 py-0.5 text-xs {typ === t
              ? 'border-accent-500 bg-accent-500/10 text-accent-300'
              : 'border-border text-muted hover:text-text'}"
          >
            {t === 'alle' ? 'Alle' : TYP_BESCHRIFTUNG[t]}
          </button>
        {/each}
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto p-2">
        {#if fehler}
          <p class="px-3 py-6 text-center text-sm text-muted">{fehler}</p>
        {:else if treffer.length === 0 && !laedt}
          <p class="px-3 py-6 text-center text-sm text-muted">Nichts gefunden.</p>
        {:else}
          <ul class="flex flex-col">
            {#each treffer as fund (fund.typ + fund.ref)}
              <li>
                <button
                  type="button"
                  onclick={() => uebernehmen(fund)}
                  class="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left hover:bg-surface-2"
                >
                  <span class="text-muted"><Icon name={TYP_SYMBOL[fund.typ]} size={16} /></span>
                  <span class="min-w-0 flex-1">
                    <span class="block truncate text-sm">{fund.label}</span>
                    <span class="block truncate text-xs text-muted">
                      {TYP_BESCHRIFTUNG[fund.typ]}{fund.zusatz ? ` · ${fund.zusatz}` : ''}
                    </span>
                  </span>
                </button>
              </li>
            {/each}
          </ul>
        {/if}

        {#if stumm.length}
          <!-- Ehrlich benennen, was fehlt: sonst sieht ein ausgefallener Kalender
               aus wie „es gibt keine Termine". -->
          <p class="mt-2 border-t border-border px-3 pt-2 text-xs text-muted">
            Keine Antwort von: {stumm.map((s) => TYP_BESCHRIFTUNG[s]).join(', ')}. Diese Quellen
            fehlen in der Liste.
          </p>
        {/if}
      </div>
    </div>
  </div>
{/if}
