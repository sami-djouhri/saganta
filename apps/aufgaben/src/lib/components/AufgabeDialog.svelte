<script lang="ts">
  /**
   * Die Aufgabe im Detail: bearbeiten, verschieben, verknuepfen, loeschen.
   *
   * Alles Seltene liegt hier, damit die Liste ruhig bleibt. Der Dialog ist ein
   * gewoehnliches Formular und traegt ohne JavaScript, weil `use:enhance` nur
   * eine Verbesserung ist und keine Voraussetzung.
   */
  import { enhance } from '$app/forms';
  import { Button, Icon, NotizenBlock, Spinner } from '@saganta/ui';
  import type { NotizKurz } from '@saganta/notizen-anschluss';
  import type { Aufgabe, Liste, Projekt } from '$lib/aufgaben-bff';
  import { ENERGIEN, ENERGIE_STIL, PRIORITAETEN, PRIO_STIL, tagePlus } from '$lib/ordnen';
  import { zuordnungVon } from '$lib/zuordnung';
  import ZuordnungAuswahl from './ZuordnungAuswahl.svelte';
  import ProjektOptionen from './ProjektOptionen.svelte';

  interface Props {
    offen: boolean;
    aufgabe: Aufgabe | null;
    projekte: Projekt[];
    listen?: Liste[];
    notizen: NotizKurz[];
    /** Basis-Adresse der Notizen-App im aktuellen Raum. */
    notizenBasis: string;
    heute: string;
    fehler?: string | null;
    /** Fehler des letzten Notiz-Versuchs, getrennt vom Aufgaben-Fehler. */
    notizFehler?: string | null;
    schliessen: () => void;
  }
  let {
    offen,
    aufgabe,
    projekte,
    listen = [],
    notizen,
    notizenBasis,
    heute,
    fehler = null,
    notizFehler = null,
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

  const TAGESZEITEN = [
    { wert: 'morgens', label: 'morgens (5 bis 11 Uhr)' },
    { wert: 'mittags', label: 'mittags (11 bis 14 Uhr)' },
    { wert: 'nachmittags', label: 'nachmittags (14 bis 18 Uhr)' },
    { wert: 'abends', label: 'abends (18 bis 23 Uhr)' },
  ];
  const WOCHENTAGE = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

  // „Auch in Projekten" (seit 2026-11-15): weitere Projekte neben dem Zuhause.
  // Der Stand lebt im Dialog und geht als versteckte Felder mit „Speichern";
  // ohne JavaScript bleiben die Felder unveraendert und damit auch die Liste.
  const HOECHSTENS_WEITERE = 10;
  let weitere = $state<string[]>([]);
  let gezeigteId = '';
  $effect.pre(() => {
    if (aufgabe && aufgabe.id !== gezeigteId) {
      gezeigteId = aufgabe.id;
      weitere = [...(aufgabe.weitere_projekte ?? [])];
    }
  });
  const projektName = $derived(new Map(projekte.map((p) => [p.slug ?? p.id, p.name])));
  function anheften(e: Event) {
    const feld = e.currentTarget as HTMLSelectElement;
    const slug = feld.value;
    feld.value = '';
    if (!slug || weitere.includes(slug) || slug === aufgabe?.project_id) return;
    if (weitere.length >= HOECHSTENS_WEITERE) return;
    weitere = [...weitere, slug];
  }
  const fenster = $derived(aufgabe?.zeitfenster?.[0] ?? null);

  // Die drei Griffe, die im Alltag zaehlen. „Verschieben" laeuft ueber den
  // defer-Weg der Engine, der mitzaehlt, wie oft etwas geschoben wurde.
  // Gerechnet ab heute, nicht ab der Frist: verschoben wird der Plantag, und
  // bei einer ueberfaelligen Aufgabe landete „Morgen“ sonst in der Vergangenheit.
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
            class="w-full rounded-md border border-border-stark bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
          />
        </label>

        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Notiz zur Aufgabe</span>
          <textarea
            name="beschreibung"
            rows="3"
            class="w-full resize-y rounded-md border border-border-stark bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
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
              class="w-full rounded-md border border-border-stark bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
            />
          </label>
          <label class="block space-y-1">
            <span class="text-xs uppercase tracking-wider text-muted">Priorität</span>
            <select
              name="prioritaet"
              class="w-full rounded-md border border-border-stark bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
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
              class="w-full rounded-md border border-border-stark bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
            />
            <span class="block text-xs text-muted"
              >Ohne Angabe kann die Tagesplanung sie nicht einplanen.</span
            >
          </label>
          <label class="block space-y-1">
            <span class="text-xs uppercase tracking-wider text-muted">Braucht Energie</span>
            <select
              name="energie"
              class="w-full rounded-md border border-border-stark bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
            >
              <option value="">egal</option>
              {#each ENERGIEN as e (e)}
                <option value={e} selected={aufgabe.energy_required === e}
                  >{ENERGIE_STIL[e]?.label}</option
                >
              {/each}
            </select>
          </label>
          <label class="block space-y-1 sm:col-span-2">
            <span class="text-xs uppercase tracking-wider text-muted">Wiederholen (Tage nach dem Abhaken)</span>
            <input
              type="number"
              name="turnus"
              min="1"
              max="730"
              step="1"
              list="turnus-vorschlaege"
              value={aufgabe.turnus_tage ?? ''}
              placeholder="nie"
              class="w-full rounded-md border border-border-stark bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
            />
            <datalist id="turnus-vorschlaege">
              <option value="7">jede Woche</option>
              <option value="14">alle zwei Wochen</option>
              <option value="30">jeden Monat</option>
              <option value="90">alle drei Monate</option>
              <option value="365">jedes Jahr</option>
            </datalist>
            <span class="block text-xs text-muted"
              >Beim Abhaken entsteht die nächste Runde, fällig so viele Tage später.</span
            >
          </label>
        </div>

        <!-- Wann: Plantag, Tageszeit, Zeitfenster (seit 2026-11-11). Der
             Planer legt die Aufgabe nur in diese Zeiten. -->
        <fieldset class="space-y-3 rounded-md border border-border px-3 py-3">
          <legend class="px-1 text-xs uppercase tracking-wider text-muted">Wann</legend>
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="block space-y-1">
              <span class="text-xs uppercase tracking-wider text-muted">Geplant für</span>
              <input type="hidden" name="tag_alt" value={aufgabe.planned_date ?? ''} />
              <input
                type="date"
                name="tag"
                value={aufgabe.planned_date ?? ''}
                class="w-full rounded-md border border-border-stark bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
              />
            </label>
            <label class="block space-y-1">
              <span class="text-xs uppercase tracking-wider text-muted">Tageszeit</span>
              <select
                name="tageszeit"
                class="w-full rounded-md border border-border-stark bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
              >
                <option value="">egal</option>
                {#each TAGESZEITEN as t (t.wert)}
                  <option value={t.wert} selected={aufgabe.tageszeit === t.wert}>{t.label}</option>
                {/each}
              </select>
            </label>
          </div>
          {#if (aufgabe.zeitfenster?.length ?? 0) > 1}
            <input type="hidden" name="fenster_mehrere" value="1" />
            <p class="text-xs text-muted">
              Diese Aufgabe hat {aufgabe.zeitfenster?.length} Zeitfenster; sie bleiben, wie sie sind.
            </p>
          {:else}
            <div class="space-y-2">
              <span class="block text-xs uppercase tracking-wider text-muted">Nur an diesen Tagen und Zeiten</span>
              <div class="flex flex-wrap gap-1">
                {#each WOCHENTAGE as w, i (w)}
                  <label class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-sm">
                    <input type="checkbox" name="fenster_tag" value={i} checked={fenster?.tage.includes(i) ?? false} />
                    {w}
                  </label>
                {/each}
              </div>
              <div class="flex flex-wrap items-center gap-2 text-sm">
                <span>von</span>
                <input
                  type="time"
                  name="fenster_von"
                  value={fenster?.von ?? ''}
                  class="rounded-md border border-border-stark bg-surface-2 px-2 py-1 text-sm outline-none focus:border-accent-500"
                />
                <span>bis</span>
                <input
                  type="time"
                  name="fenster_bis"
                  value={fenster?.bis ?? ''}
                  class="rounded-md border border-border-stark bg-surface-2 px-2 py-1 text-sm outline-none focus:border-accent-500"
                />
              </div>
              <span class="block text-xs text-muted"
                >Leer heißt jederzeit. Tage ohne Uhrzeit: ganztags. Uhrzeit ohne Tage: jeden Tag.</span
              >
            </div>
          {/if}
        </fieldset>

        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Bereich oder Projekt</span>
          <input type="hidden" name="zuordnung_alt" value={zuordnungVon(aufgabe)} />
          <ZuordnungAuswahl
            {listen}
            {projekte}
            wert={zuordnungVon(aufgabe)}
            klasse="w-full rounded-md border border-border-stark bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
          />
        </label>

        <fieldset class="space-y-2">
          <legend class="text-xs uppercase tracking-wider text-muted">Auch in Projekten</legend>
          <input type="hidden" name="weitere_alt" value={(aufgabe.weitere_projekte ?? []).join(',')} />
          {#each weitere as slug (slug)}
            <input type="hidden" name="weitere_projekt" value={slug} />
          {/each}
          {#if weitere.length > 0}
            <ul class="flex flex-wrap gap-1.5">
              {#each weitere as slug (slug)}
                <li
                  class="inline-flex min-h-9 items-center gap-1 rounded-full border border-border-stark bg-surface-2 py-0.5 pl-3 pr-1 text-sm"
                >
                  <Icon name="folder" size={13} />
                  <span>{projektName.get(slug) ?? slug}</span>
                  <button
                    type="button"
                    onclick={() => (weitere = weitere.filter((s) => s !== slug))}
                    class="grid size-7 place-items-center rounded-full text-muted hover:bg-surface hover:text-text"
                    aria-label="Von {projektName.get(slug) ?? slug} lösen"><Icon name="x" size={13} /></button
                  >
                </li>
              {/each}
            </ul>
          {/if}
          {#if weitere.length < HOECHSTENS_WEITERE && projekte.length > 0}
            <select
              onchange={anheften}
              aria-label="Weiteres Projekt anheften"
              class="w-full rounded-md border border-border-stark bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
            >
              <option value="">Weiteres Projekt anheften …</option>
              <ProjektOptionen {projekte} ohne={[...weitere, ...(aufgabe.project_id ? [aufgabe.project_id] : [])]} />
            </select>
          {/if}
          <span class="block text-xs text-muted"
            >Die Aufgabe bleibt in ihrem Projekt und erscheint zusätzlich bei diesen.</span
          >
        </fieldset>

        <div class="flex flex-wrap items-center gap-2 pt-1">
          <Button type="submit" variant="primary">Speichern</Button>
          <span class="flex-1"></span>
        </div>
      </form>

      <!-- Unteraufgaben, eine Ebene (Owner 2026-11-06). Jeder Griff ist ein
           eigenes kleines Formular auf `?/unteraufgabe`, damit ein Haken sofort
           wirkt und ohne JavaScript traegt; der Dienst haelt die ganze Liste. -->
      <section class="space-y-2 border-t border-border px-4 py-4">
        <p class="text-xs uppercase tracking-wider text-muted">
          Unteraufgaben{#if aufgabe.unteraufgaben?.length}
            · {aufgabe.unteraufgaben.filter((u) => u.erledigt).length}/{aufgabe.unteraufgaben.length}{/if}
        </p>
        {#if aufgabe.unteraufgaben?.length}
          <ul class="space-y-1">
            {#each aufgabe.unteraufgaben as u, i (i)}
              <li class="flex items-center gap-2 text-sm">
                <form method="POST" action="?/unteraufgabe" use:enhance class="flex">
                  <input type="hidden" name="id" value={aufgabe.id} />
                  <input type="hidden" name="art" value="umschalten" />
                  <input type="hidden" name="index" value={i} />
                  <button
                    type="submit"
                    class="relative grid size-4 shrink-0 place-items-center rounded border border-border-stark text-transparent before:absolute before:-inset-2 before:content-[''] hover:border-accent-500 {u.erledigt
                      ? 'border-accent-500 bg-accent-500 text-accent-ink'
                      : ''}"
                    aria-label={u.erledigt ? `${u.text} wieder öffnen` : `${u.text} abhaken`}
                  >
                    <Icon name="check" size={11} />
                  </button>
                </form>
                <span class="min-w-0 flex-1 truncate {u.erledigt ? 'text-muted line-through' : ''}">{u.text}</span>
                <form method="POST" action="?/unteraufgabe" use:enhance class="flex">
                  <input type="hidden" name="id" value={aufgabe.id} />
                  <input type="hidden" name="art" value="entfernen" />
                  <input type="hidden" name="index" value={i} />
                  <button type="submit" class="text-muted hover:text-text" aria-label="Unteraufgabe entfernen">
                    <Icon name="x" size={14} />
                  </button>
                </form>
              </li>
            {/each}
          </ul>
        {/if}
        <form method="POST" action="?/unteraufgabe" use:enhance class="flex items-center gap-2">
          <input type="hidden" name="id" value={aufgabe.id} />
          <input type="hidden" name="art" value="anlegen" />
          <input
            name="text"
            maxlength="300"
            placeholder="Neue Unteraufgabe"
            aria-label="Neue Unteraufgabe"
            class="min-w-0 flex-1 rounded-md border border-border-stark bg-surface-2 px-3 py-1.5 text-sm outline-none focus:border-accent-500"
          />
          <Button type="submit" variant="ghost" size="sm"><Icon name="plus" size={14} /> Dazu</Button>
        </form>
      </section>

      <!-- Verschieben und Löschen stehen außerhalb des Bearbeiten-Formulars:
           sie sind eigene Absichten, kein Sonderfall von „Speichern". -->
      <div class="flex flex-wrap items-center gap-2 border-t border-border px-4 py-3">
        {#each VERSCHIEBEN as v (v.tage)}
          <form method="POST" action="?/verschieben" use:enhance>
            <input type="hidden" name="id" value={aufgabe.id} />
            <input type="hidden" name="datum" value={tagePlus(heute, v.tage)} />
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

      <!-- Notizen. Der Bestand liegt in der Notizen-App; hier entsteht eine
           neue und hier wird eine vorhandene angehaengt.

           Der Knopf „Notiz dazu" ist seit dem 2026-10-24 die Hauptsache und
           die Suche darunter der Nebenfall: man sitzt an der Aufgabe und will
           etwas notieren, nicht in den Notizen und eine Aufgabe suchen. Beides
           laeuft in dieselbe Aktion (`?/notizDazu`), damit es nicht zwei Wege
           mit zwei Fehlerbildern werden. -->
      <section class="space-y-3 border-t border-border px-4 py-4">
        <NotizenBlock
          typ="aufgabe"
          ref={aufgabe.id}
          label={aufgabe.title}
          {notizen}
          {notizenBasis}
          fehler={notizFehler}
          {enhance}
          schlicht
        />

        <div class="space-y-2">
          <p class="text-xs uppercase tracking-wider text-muted">
            oder eine vorhandene Notiz anhängen
          </p>
          <div
            class="flex items-center gap-2 rounded-md border border-border-stark bg-surface-2 px-3 py-2 focus-within:border-accent-500"
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
                  <!-- Dieselbe Aktion wie der Knopf oben. `label` ist die
                       Beschriftung der AUFGABE (sie wird als Kopie
                       mitgespeichert), `titel` die der Notiz. -->
                  <form method="POST" action="?/notizDazu" use:enhance class="flex">
                    <input type="hidden" name="typ" value="aufgabe" />
                    <input type="hidden" name="ref" value={aufgabe.id} />
                    <input type="hidden" name="label" value={aufgabe.title} />
                    <input type="hidden" name="notiz" value={t.id} />
                    <input type="hidden" name="titel" value={t.titel} />
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
