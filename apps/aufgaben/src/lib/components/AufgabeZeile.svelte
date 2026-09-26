<script lang="ts">
  /**
   * Eine Zeile der Aufgabenliste.
   *
   * ★ Die Zeile traegt **eine** unmittelbare Handlung, das Abhaken, und legt
   * alles Weitere hinter einen Klick auf die Zeile selbst. Die Vorgaengerin im
   * Kalender zeigte je Aufgabe vier Bedienelemente nebeneinander (Haken, Titel,
   * Datum, Prioritaet, Loeschen) und war damit bei zwanzig Aufgaben eine Wand
   * aus achtzig Zielen. Was selten gebraucht wird, gehoert nicht dauerhaft
   * sichtbar neben das, was staendig gebraucht wird.
   *
   * Zusatzangaben (Uhrzeit, Dauer, Projekt, Notizen) stehen als Symbol mit
   * Beschriftung nur dann, wenn sie belegt sind. Eine leere Spalte ist eine
   * Behauptung, dass es dort etwas zu sehen gaebe.
   */
  import { enhance } from '$app/forms';
  import { Icon } from '@saganta/ui';
  import type { Aufgabe, Projekt } from '$lib/aufgaben-bff';
  import type { NotizKurz } from '$lib/server/notizen';
  import { ENERGIE_STIL, PRIO_STIL, dauer, datumsEtikett, istUeberfaellig } from '$lib/ordnen';

  interface Props {
    aufgabe: Aufgabe;
    heute: string;
    projekt?: Projekt | null;
    notizen?: NotizKurz[];
    /** Zeigt das Faelligkeitsdatum. In der Tagesansicht ueberfluessig. */
    zeigeDatum?: boolean;
    oeffnen?: (a: Aufgabe) => void;
  }
  let { aufgabe, heute, projekt = null, notizen = [], zeigeDatum = true, oeffnen }: Props =
    $props();

  const prio = $derived(PRIO_STIL[aufgabe.priority] ?? PRIO_STIL.mittel!);
  const ueberfaellig = $derived(istUeberfaellig(aufgabe, heute));
  const energie = $derived(
    aufgabe.energy_required ? (ENERGIE_STIL[aufgabe.energy_required] ?? null) : null,
  );
  const zeit = $derived(
    aufgabe.scheduled_start && aufgabe.scheduled_start.slice(0, 10) === heute
      ? aufgabe.scheduled_start.slice(11, 16)
      : aufgabe.due_date === heute && aufgabe.due_time
        ? aufgabe.due_time
        : '',
  );
</script>

<li
  class="group flex items-start gap-3 rounded-lg border border-border bg-surface-2/50 px-3 py-2.5 transition-colors duration-fast ease-saganta hover:border-border/80 hover:bg-surface-2"
>
  <!-- Abhaken: das eine, was hier immer sofort gehen muss. Eigenes Formular,
       damit es ohne JavaScript traegt. -->
  <form method="POST" action="?/umschalten" use:enhance class="flex pt-0.5">
    <input type="hidden" name="id" value={aufgabe.id} />
    <input type="hidden" name="erledigt" value={String(aufgabe.completed)} />
    <button
      type="submit"
      class="grid size-5 shrink-0 place-items-center rounded border border-border text-transparent transition-colors duration-fast ease-saganta hover:border-accent-500 hover:text-accent-400 {aufgabe.completed
        ? 'border-accent-500 bg-accent-500 text-accent-ink'
        : ''}"
      aria-label={aufgabe.completed ? `${aufgabe.title} wieder öffnen` : `${aufgabe.title} abhaken`}
    >
      <Icon name="check" size={13} />
    </button>
  </form>

  <button
    type="button"
    onclick={() => oeffnen?.(aufgabe)}
    class="min-w-0 flex-1 text-left"
    aria-label="{aufgabe.title} bearbeiten"
  >
    <span
      class="block truncate text-sm {aufgabe.completed ? 'text-muted line-through' : 'text-text'}"
      >{aufgabe.title}</span
    >

    <!-- Die Beiwerk-Zeile. Jedes Stueck erscheint nur, wenn es einen Wert hat. -->
    {#if zeit || aufgabe.estimated_minutes || projekt || notizen.length || (zeigeDatum && aufgabe.due_date) || aufgabe.energy_required || (aufgabe.defer_count ?? 0) >= 3}
      <span class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        {#if zeit}
          <span class="inline-flex items-center gap-1 text-accent-300">
            <Icon name="clock" size={12} />{zeit}
          </span>
        {/if}
        {#if zeigeDatum && aufgabe.due_date}
          <span class="inline-flex items-center gap-1 {ueberfaellig ? 'text-fehler' : ''}">
            <Icon name={ueberfaellig ? 'alert-triangle' : 'flag'} size={12} />{datumsEtikett(
              aufgabe.due_date,
              heute,
            )}
          </span>
        {/if}
        {#if aufgabe.estimated_minutes}
          <span class="inline-flex items-center gap-1">
            <Icon name="timer" size={12} />{dauer(aufgabe.estimated_minutes)}
          </span>
        {/if}
        {#if energie}
          <span class="inline-flex items-center gap-1" title="Energiebedarf: {energie.label}">
            <Icon name={energie.symbol} size={12} />{energie.label}
          </span>
        {/if}
        {#if projekt}
          <span class="inline-flex items-center gap-1">
            <span
              class="size-2 shrink-0 rounded-full"
              style="background-color:{projekt.color ?? '#8a8aa0'}"
            ></span>{projekt.name}
          </span>
        {/if}
        {#if notizen.length}
          <span class="inline-flex items-center gap-1" title="Verknüpfte Notizen">
            <Icon name="file-text" size={12} />{notizen.length}
          </span>
        {/if}
        {#if (aufgabe.defer_count ?? 0) >= 3}
          <!-- Bleibt liegen. Nicht als Vorwurf, sondern damit die Entscheidung
               „machen oder streichen" ueberhaupt sichtbar wird. -->
          <span class="inline-flex items-center gap-1 text-warnung" title="Schon oft verschoben">
            <Icon name="chevrons-right" size={12} />{aufgabe.defer_count}× verschoben
          </span>
        {/if}
      </span>
    {/if}
  </button>

  <span
    class="mt-0.5 shrink-0 rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wide {prio.klasse}"
    >{prio.label}</span
  >
</li>
