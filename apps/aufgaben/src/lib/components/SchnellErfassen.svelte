<script lang="ts">
  /**
   * Eine Zeile zum Aufschreiben, der Rest klappt auf.
   *
   * ★ Die Huerde einer Aufgabenliste ist nicht das Verwalten, sondern das
   * Erfassen: was nicht in drei Sekunden hineingeht, wird gar nicht erst
   * aufgeschrieben. Deshalb steht hier ein Feld und ein Knopf; Termin, Dauer und
   * Projekt liegen hinter „Mehr" und sind ohne Ausnahme freiwillig.
   *
   * Ohne Termin landet die Aufgabe im Vorrat, und genau von dort holt sie „Tag
   * planen" spaeter selbst. Man muss also nicht entscheiden, wann man etwas
   * macht, nur dass man es machen will.
   */
  import { enhance } from '$app/forms';
  import { Icon } from '@saganta/ui';
  import type { Projekt } from '$lib/aufgaben-bff';
  import { PRIORITAETEN, PRIO_STIL, tagePlus } from '$lib/ordnen';

  interface Props {
    projekte: Projekt[];
    heute: string;
  }
  let { projekte, heute }: Props = $props();

  let mehr = $state(false);
  let feld = $state<HTMLInputElement | undefined>();
</script>

<form
  method="POST"
  action="?/anlegen"
  use:enhance={() =>
    async ({ update }) => {
      await update();
      // Nach dem Anlegen bleibt der Fokus im Feld: mehrere Gedanken hintereinander
      // aufzuschreiben ist der Normalfall, nicht die Ausnahme.
      feld?.focus();
    }}
  class="rounded-xl border border-border bg-surface-2/40 p-3"
>
  <div class="flex items-center gap-2">
    <span class="text-muted"><Icon name="plus" size={16} /></span>
    <input
      bind:this={feld}
      name="titel"
      required
      placeholder="Was ist zu tun?"
      class="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted"
    />
    <button
      type="button"
      onclick={() => (mehr = !mehr)}
      aria-expanded={mehr}
      class="shrink-0 rounded-md px-2 py-1 text-xs text-muted hover:text-text"
      >{mehr ? 'Weniger' : 'Mehr'}</button
    >
    <button
      type="submit"
      class="shrink-0 rounded-md bg-accent-500 px-3 py-1.5 text-sm font-medium text-accent-ink hover:bg-accent-400"
      >Hinzufügen</button
    >
  </div>

  {#if mehr}
    <div class="mt-3 grid gap-2 border-t border-border pt-3 sm:grid-cols-2 lg:grid-cols-4">
      <label class="space-y-1">
        <span class="text-[11px] uppercase tracking-wider text-muted">Fällig</span>
        <input
          type="date"
          name="faellig"
          min={tagePlus(heute, -365)}
          class="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
        />
      </label>
      <label class="space-y-1">
        <span class="text-[11px] uppercase tracking-wider text-muted">Priorität</span>
        <select
          name="prioritaet"
          class="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
        >
          {#each PRIORITAETEN as p (p)}
            <option value={p} selected={p === 'mittel'}>{PRIO_STIL[p]?.label}</option>
          {/each}
        </select>
      </label>
      <label class="space-y-1">
        <span class="text-[11px] uppercase tracking-wider text-muted">Dauer (min)</span>
        <input
          type="number"
          name="dauer"
          min="5"
          max="600"
          step="5"
          placeholder="30"
          class="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
        />
      </label>
      <label class="space-y-1">
        <span class="text-[11px] uppercase tracking-wider text-muted">Projekt</span>
        <select
          name="projekt"
          class="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
        >
          <option value="">ohne</option>
          {#each projekte as p (p.id)}
            <option value={p.id}>{p.name}</option>
          {/each}
        </select>
      </label>
    </div>
  {/if}
</form>
