<script lang="ts">
  /**
   * Die Aufgabe im Detail: bearbeiten, verschieben, verknuepfen, loeschen.
   *
   * Alles Seltene liegt hier, damit die Liste ruhig bleibt. Der Dialog ist ein
   * gewoehnliches Formular und traegt ohne JavaScript, weil `use:enhance` nur
   * eine Verbesserung ist und keine Voraussetzung.
   */
  import { enhance } from '$app/forms';
  import { Button, Icon, Spinner } from '@saganta/ui';
  import type { Aufgabe, Projekt } from '$lib/aufgaben-bff';
  import type { NotizKurz } from '$lib/server/notizen';
  import { ENERGIEN, ENERGIE_STIL, PRIORITAETEN, PRIO_STIL, tagePlus } from '$lib/ordnen';

  interface Props {
    offen: boolean;
    aufgabe: Aufgabe | null;
    projekte: Projekt[];
    notizen: NotizKurz[];
    /** Basis-Adresse der Notizen-App im aktuellen Raum. */
    notizenBasis: string;
    heute: string;
    fehler?: string | null;
    schliessen: () => void;
  }
  let {
    offen,
    aufgabe,
    projekte,
    notizen,
    notizenBasis,
    heute,
    fehler = null,
    schliessen,
  }: Props = $props();

  let notizSuche = $state('');
  let notizTreffer = $state<NotizKurz[]>([]);
  let notizLaedt = $state(false);

  let lauf = 0;
  async function notizenSuchen() {
    // Nur die Antwort des juengsten Aufrufs zaehlt: beim Tippen ueberholt sich
    // das sonst und die Treffer springen zurueck.
    const meiner = ++lauf;
    notizLaedt = true;
    try {
      const res = await fetch(`/notizen-suche?q=${encodeURIComponent(notizSuche)}`);
      const daten = (await res.json()) as { treffer: NotizKurz[] };
      if (meiner === lauf) notizTreffer = daten.treffer ?? [];
    } catch {
      if (meiner === lauf) notizTreffer = [];
    } finally {
      if (meiner === lauf) notizLaedt = false;
    }
  }

  let entprellung: ReturnType<typeof setTimeout> | undefined;
  function tippen() {
    clearTimeout(entprellung);
    entprellung = setTimeout(notizenSuchen, 250);
  }

  // Die drei Griffe, die im Alltag zaehlen. „Verschieben" laeuft ueber den
  // defer-Weg der Engine, der mitzaehlt, wie oft etwas geschoben wurde.
  const VERSCHIEBEN = [
    { tage: 1, label: 'Morgen' },
    { tage: 7, label: 'Nächste Woche' },
  ];
</script>

{#if offen && aufgabe}
  <div
    class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 pt-10"
    role="presentation"
    onclick={(e) => e.target === e.currentTarget && schliessen()}
  >
    <div
      class="w-full max-w-lg rounded-xl border border-border bg-surface shadow-xl"
      role="dialog"
      aria-modal="true"
      aria-label="Aufgabe bearbeiten"
    >
      <header class="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <h2 class="font-display text-lg">Aufgabe</h2>
        <button
          type="button"
          onclick={schliessen}
          class="text-muted hover:text-text"
          aria-label="Schließen"><Icon name="x" size={18} /></button
        >
      </header>

      {#if fehler}
        <p class="mx-4 mt-4 rounded-md border border-fehler/40 bg-fehler/10 px-3 py-2 text-sm">
          {fehler}
        </p>
      {/if}

      <form method="POST" action="?/speichern" use:enhance class="space-y-4 px-4 py-4">
        <input type="hidden" name="id" value={aufgabe.id} />

        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Titel</span>
          <input
            name="titel"
            value={aufgabe.title}
            required
            class="w-full rounded-md border border-border bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
          />
        </label>

        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Notiz zur Aufgabe</span>
          <textarea
            name="beschreibung"
            rows="3"
            class="w-full resize-y rounded-md border border-border bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
            >{aufgabe.description ?? ''}</textarea
          >
        </label>

        <div class="grid gap-3 sm:grid-cols-2">
          <label class="block space-y-1">
            <span class="text-xs uppercase tracking-wider text-muted">Fällig am</span>
            <input
              type="date"
              name="faellig"
              value={aufgabe.due_date ?? ''}
              class="w-full rounded-md border border-border bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
            />
          </label>
          <label class="block space-y-1">
            <span class="text-xs uppercase tracking-wider text-muted">Priorität</span>
            <select
              name="prioritaet"
              class="w-full rounded-md border border-border bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
            >
              {#each PRIORITAETEN as p (p)}
                <option value={p} selected={aufgabe.priority === p}>{PRIO_STIL[p]?.label}</option>
              {/each}
            </select>
          </label>
          <label class="block space-y-1">
            <span class="text-xs uppercase tracking-wider text-muted">Dauer (Minuten)</span>
            <input
              type="number"
              name="dauer"
              min="5"
              max="600"
              step="5"
              value={aufgabe.estimated_minutes ?? ''}
              placeholder="z. B. 30"
              class="w-full rounded-md border border-border bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
            />
            <span class="block text-[11px] text-muted"
              >Ohne Angabe kann die Tagesplanung sie nicht einplanen.</span
            >
          </label>
          <label class="block space-y-1">
            <span class="text-xs uppercase tracking-wider text-muted">Braucht Energie</span>
            <select
              name="energie"
              class="w-full rounded-md border border-border bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
            >
              <option value="">egal</option>
              {#each ENERGIEN as e (e)}
                <option value={e} selected={aufgabe.energy_required === e}
                  >{ENERGIE_STIL[e]?.label}</option
                >
              {/each}
            </select>
          </label>
        </div>

        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Projekt</span>
          <select
            name="projekt"
            class="w-full rounded-md border border-border bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
          >
            <option value="">ohne Projekt</option>
            {#each projekte as p (p.id)}
              <option value={p.id} selected={aufgabe.project_id === p.id}>{p.name}</option>
            {/each}
          </select>
        </label>

        <div class="flex flex-wrap items-center gap-2 pt-1">
          <Button type="submit" variant="primary">Speichern</Button>
          <span class="flex-1"></span>
        </div>
      </form>

      <!-- Verschieben und Löschen stehen außerhalb des Bearbeiten-Formulars:
           sie sind eigene Absichten, kein Sonderfall von „Speichern". -->
      <div class="flex flex-wrap items-center gap-2 border-t border-border px-4 py-3">
        {#each VERSCHIEBEN as v (v.tage)}
          <form method="POST" action="?/verschieben" use:enhance>
            <input type="hidden" name="id" value={aufgabe.id} />
            <input type="hidden" name="datum" value={tagePlus(aufgabe.due_date ?? heute, v.tage)} />
            <Button type="submit" variant="ghost" size="sm">
              <Icon name="chevrons-right" size={14} />
              {v.label}
            </Button>
          </form>
        {/each}
        <span class="flex-1"></span>
        <form
          method="POST"
          action="?/loeschen"
          use:enhance={({ cancel }) => {
            if (!confirm(`„${aufgabe?.title}" wirklich löschen?`)) cancel();
            return async ({ update }) => {
              await update();
              schliessen();
            };
          }}
        >
          <input type="hidden" name="id" value={aufgabe.id} />
          <Button type="submit" variant="ghost" size="sm">
            <Icon name="trash-2" size={14} /> Löschen
          </Button>
        </form>
      </div>

      <!-- Notizen. Der Bestand liegt in der Notizen-App; hier wird nur
           verknuepft und verlinkt. -->
      <section class="space-y-3 border-t border-border px-4 py-4">
        <h3 class="flex items-center gap-2 text-xs uppercase tracking-wider text-muted">
          <Icon name="link" size={14} /> Notizen
        </h3>

        {#if notizen.length > 0}
          <ul class="space-y-1">
            {#each notizen as n (n.id)}
              <li>
                <a
                  href="{notizenBasis}/notiz/{n.id}"
                  class="flex items-center gap-2 rounded-md border border-border bg-surface-2/60 px-3 py-2 text-sm hover:border-accent-500/50"
                >
                  <Icon name="file-text" size={14} />
                  <span class="min-w-0 flex-1 truncate">{n.titel || 'Ohne Titel'}</span>
                  <Icon name="arrow-right" size={14} />
                </a>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="text-sm text-muted">Noch keine Notiz verknüpft.</p>
        {/if}

        <div class="space-y-2">
          <div
            class="flex items-center gap-2 rounded-md border border-border bg-surface-2 px-3 py-2"
          >
            <Icon name="search" size={14} />
            <input
              bind:value={notizSuche}
              oninput={tippen}
              onfocus={notizenSuchen}
              placeholder="Notiz suchen und anhängen…"
              class="min-w-0 flex-1 bg-transparent text-sm outline-none"
            />
            {#if notizLaedt}<Spinner size={14} />{/if}
          </div>

          {#if notizTreffer.length > 0}
            <ul class="max-h-40 space-y-1 overflow-y-auto">
              {#each notizTreffer as t (t.id)}
                <li>
                  <form method="POST" action="?/notizAnhaengen" use:enhance class="flex">
                    <input type="hidden" name="id" value={aufgabe.id} />
                    <input type="hidden" name="titel" value={aufgabe.title} />
                    <input type="hidden" name="notiz" value={t.id} />
                    <button
                      type="submit"
                      class="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left text-sm hover:bg-surface-2"
                    >
                      <Icon name="plus" size={13} />
                      <span class="min-w-0 flex-1 truncate">{t.titel || 'Ohne Titel'}</span>
                    </button>
                  </form>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      </section>
    </div>
  </div>
{/if}
