<script lang="ts">
  import { Icon, Spinner } from '@saganta/ui';

  interface Treffer {
    id: number;
    titel: string;
    ausschnitt: string;
    archiviert: boolean;
  }

  let {
    offen = false,
    ohne = [],
    schliessen,
    uebernehmen,
  }: {
    offen?: boolean;
    /** Kennungen, die nicht angeboten werden: die Notiz selbst und schon verbundene. */
    ohne?: number[];
    schliessen: () => void;
    uebernehmen: (id: number) => void;
  } = $props();

  let suche = $state('');
  let treffer = $state<Treffer[]>([]);
  let laedt = $state(false);
  let fehler = $state('');
  let sichtbar = $derived(treffer.filter((t) => !ohne.includes(t.id)));

  // Wie im Verknüpfen-Dialog: nur die Antwort der jüngsten Anfrage zählt.
  let lauf = 0;
  async function abrufen() {
    const meiner = ++lauf;
    laedt = true;
    fehler = '';
    try {
      const frage = new URLSearchParams({ q: suche, ohne: String(ohne[0] ?? '') });
      const res = await fetch(`/notizwahl?${frage}`);
      if (!res.ok) throw new Error(`${res.status}`);
      const daten = (await res.json()) as Treffer[];
      if (meiner !== lauf) return;
      treffer = daten;
    } catch {
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
      aria-label="Mit Notiz verbinden"
    >
      <div class="flex items-center gap-2 border-b border-border p-3">
        <span class="text-muted"><Icon name="search" size={16} /></span>
        <!-- svelte-ignore a11y_autofocus -->
        <input
          bind:value={suche}
          oninput={tippen}
          autofocus
          placeholder="Notiz suchen…"
          class="min-w-0 flex-1 bg-transparent text-sm outline-none"
        />
        {#if laedt}<Spinner size={16} />{/if}
        <button type="button" onclick={schliessen} class="grid size-11 place-items-center text-muted hover:text-text md:size-8" aria-label="Schließen">
          <Icon name="x" size={16} />
        </button>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto p-2">
        {#if fehler}
          <p class="px-3 py-6 text-center text-sm text-muted">{fehler}</p>
        {:else if sichtbar.length === 0 && !laedt}
          <p class="px-3 py-6 text-center text-sm text-muted">
            {suche ? 'Nichts gefunden.' : 'Keine weitere Notiz zum Verbinden.'}
          </p>
        {:else}
          <ul class="flex flex-col">
            {#each sichtbar as t (t.id)}
              <li>
                <button
                  type="button"
                  onclick={() => uebernehmen(t.id)}
                  class="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left hover:bg-surface-2 max-md:min-h-11"
                >
                  <span class="text-muted"><Icon name="link" size={16} /></span>
                  <span class="min-w-0 flex-1">
                    <span class="block truncate text-sm">{t.titel || 'Ohne Titel'}</span>
                    <span class="block truncate text-xs text-muted">
                      {t.archiviert ? 'Archiv · ' : ''}{t.ausschnitt}
                    </span>
                  </span>
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    </div>
  </div>
{/if}
