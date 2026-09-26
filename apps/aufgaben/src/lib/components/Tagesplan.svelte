<script lang="ts">
  /**
   * „Tag planen": rechnen lassen, dann entscheiden.
   *
   * ★★ **Das ist der Unterschied zur Vorschlagsliste, die der Kalender vorher
   * zeigte.** Dort standen bis zu sechs Vorschlaege nebeneinander („Was jetzt?"),
   * jeder mit Titel, Dauer, Energiestufe und Begruendung. Sie sahen nach
   * Assistenz aus, waren aber nur Text: keiner liess sich annehmen. Wer etwas
   * davon wollte, musste es selbst als Termin anlegen. Ein Vorschlag, den man
   * abtippen muss, ist keine Planung, sondern eine Erinnerung daran, dass man
   * planen muesste.
   *
   * Hier gibt es einen Knopf, eine Vorschau und eine Frage. Die Engine sucht die
   * freien Fenster, haelt den Aufwand gegen die heutige Kapazitaet und schlaegt
   * eine Belegung vor; angenommen wird sie erst auf Bestaetigung. Nichts
   * passiert hinter dem Ruecken, und nichts bleibt liegen, weil man es haette
   * abschreiben muessen.
   *
   * Was die Engine **nicht** einplanen konnte, steht ausdruecklich mit Grund da.
   * Ohne diese Zeile sieht ein zu voller Tag genauso aus wie ein leerer Vorrat.
   */
  import { enhance } from '$app/forms';
  import { Button, Icon } from '@saganta/ui';
  import type { Planung } from '$lib/aufgaben-bff';
  import { dauer } from '$lib/ordnen';

  interface Props {
    plan: Planung | null;
    festgelegt: boolean;
    heute: string;
    poolGroesse: number;
  }
  let { plan, festgelegt, heute, poolGroesse }: Props = $props();

  const geplant = $derived(plan?.suggestions ?? []);
  const zurueckgestellt = $derived(plan?.deferred ?? []);

  /** Naive Berlin-ISO zu `HH:MM`. Kein Date-Objekt, kein Zonenwechsel. */
  function uhrzeit(iso?: string): string {
    return iso ? iso.slice(11, 16) : '';
  }
</script>

{#if festgelegt && plan}
  <section class="rounded-xl border border-erfolg/40 bg-erfolg/[0.07] p-4">
    <p class="flex items-center gap-2 text-sm font-medium text-erfolg">
      <Icon name="circle-check" size={16} />
      {#if geplant.length > 0}
        {geplant.length}
        {geplant.length === 1 ? 'Aufgabe' : 'Aufgaben'} in den Tag gelegt.
      {:else}
        Nichts einzuplanen.
      {/if}
    </p>
    {#if geplant.length > 0}
      <ul class="mt-2 space-y-1 text-sm">
        {#each geplant as s (s.todo_id)}
          <li class="flex items-baseline gap-2">
            <span class="font-mono text-xs text-muted">{uhrzeit(s.start)}</span>
            <span class="min-w-0 flex-1">{s.title}</span>
          </li>
        {/each}
      </ul>
    {/if}
  </section>
{:else if plan}
  <section class="rounded-xl border border-accent-500/40 bg-accent-500/[0.06] p-4">
    {#if geplant.length === 0}
      <p class="text-sm">Es liess sich nichts einplanen.</p>
      <p class="mt-1 text-xs text-muted">
        {#if poolGroesse === 0}
          Der Vorrat ist leer: es gibt keine Aufgabe ohne Termin, die in eine Lücke passen könnte.
        {:else}
          Entweder ist der Tag voll, oder den wartenden Aufgaben fehlt eine geschätzte Dauer.
        {/if}
      </p>
    {:else}
      <h2 class="flex items-center gap-2 text-sm font-medium">
        <Icon name="sparkles" size={16} /> Vorschlag für heute
      </h2>
      <ul class="mt-2 space-y-1.5">
        {#each geplant as s (s.todo_id)}
          <li class="text-sm">
            <span class="flex items-baseline gap-2">
              <span class="font-mono text-xs text-accent-300"
                >{uhrzeit(s.start)}{s.end ? `–${uhrzeit(s.end)}` : ''}</span
              >
              <span class="min-w-0 flex-1">{s.title}</span>
              {#if s.minutes}<span class="shrink-0 text-xs text-muted">{dauer(s.minutes)}</span>{/if}
            </span>
            {#if s.reason}
              <span class="ml-[3.6rem] block text-xs text-muted">{s.reason}</span>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}

    {#if zurueckgestellt.length > 0}
      <div class="mt-3 border-t border-accent-500/20 pt-2.5">
        <p class="text-xs font-medium text-muted">Nicht eingeplant</p>
        <ul class="mt-1 space-y-0.5 text-xs text-muted">
          {#each zurueckgestellt as d (d.todo_id)}
            <li>{d.title} · {d.reason}</li>
          {/each}
        </ul>
      </div>
    {/if}

    <div class="mt-3 flex flex-wrap gap-2">
      {#if geplant.length > 0}
        <form method="POST" action="?/planen" use:enhance>
          <input type="hidden" name="datum" value={heute} />
          <input type="hidden" name="festlegen" value="true" />
          <Button type="submit" variant="primary">So einplanen</Button>
        </form>
      {/if}
      <!-- Verwerfen ist ein gewoehnlicher Seitenaufruf, kein Zustand im Browser:
           damit verschwindet der Vorschlag auch ohne JavaScript. -->
      <a
        href="/"
        class="inline-flex items-center rounded-md border border-border px-4 py-1.5 text-sm text-muted hover:text-text"
        >Verwerfen</a
      >
    </div>
  </section>
{:else}
  <form method="POST" action="?/planen" use:enhance>
    <input type="hidden" name="datum" value={heute} />
    <input type="hidden" name="festlegen" value="false" />
    <button
      type="submit"
      class="flex w-full flex-wrap items-center justify-center gap-x-2 gap-y-0.5 rounded-xl border border-border bg-surface-2/40 px-4 py-3 text-sm text-muted transition-colors duration-fast ease-saganta hover:border-accent-500/60 hover:text-text"
    >
      <span class="inline-flex items-center gap-2"><Icon name="sparkles" size={16} /> Tag planen</span>
      <span class="text-xs">(Vorschlag ansehen, dann entscheiden)</span>
    </button>
  </form>
{/if}
