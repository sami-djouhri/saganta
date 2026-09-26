<script lang="ts">
  import { enhance } from '$app/forms';
  import { Icon } from '@saganta/ui';
  import type { KalenderEvent } from '$lib/kalender-bff';
  import {
    type CalMeta,
    byStart,
    dayKeyOf,
    dayLabel,
    dayTypeKeyOf,
    DAYTYPE_LABEL,
    endNote,
    eventColor,
    isPast,
    timeCol,
    uniqueBy,
  } from '$lib/cal';

  interface Props {
    items: KalenderEvent[];
    selectedCalendar: string;
    calMeta: Map<string, CalMeta>;
    nowMs: number | null;
    onEdit: (ev: KalenderEvent) => void;
  }
  let { items, selectedCalendar, calMeta, nowMs, onEdit }: Props = $props();

  const grouped = $derived.by(() => {
    const filtered = items.filter(
      (ev) =>
        !dayTypeKeyOf(ev) && // Tagestyp-Kontext gehört nicht in die Terminliste
        (!selectedCalendar || ev.calendar_id === selectedCalendar),
    );
    const map = new Map<string, KalenderEvent[]>();
    for (const ev of filtered) {
      const k = dayKeyOf(ev);
      if (!k) continue;
      const bucket = map.get(k) ?? [];
      bucket.push(ev);
      map.set(k, bucket);
    }
    for (const evs of map.values()) evs.sort(byStart);
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  });

  // Tagestyp je Kalendertag (aus Kontext-Events) → Badge in der Tages-Überschrift.
  const dayTypeByDay = $derived.by(() => {
    const map = new Map<string, string>();
    for (const ev of items) {
      const key = dayTypeKeyOf(ev);
      if (!key) continue;
      const k = dayKeyOf(ev);
      if (k && !map.has(k)) map.set(k, DAYTYPE_LABEL[key] ?? key);
    }
    return map;
  });

  /** Generierte Kalender bleiben tabu: Tagestypen und Geburtstage werden erzeugt. */
  function istVerwaltet(ev: KalenderEvent): boolean {
    const cid = ev.calendar_id ?? '';
    return /^daytype-/.test(cid) || /^system-geburtstage/.test(cid);
  }

  function isEditable(ev: KalenderEvent): boolean {
    // Bearbeiten wirkt bei einer Serie auf die ganze Reihe, bis das im Editor
    // deutlich gesagt wird, bleibt es bei Instanzen aus.
    return !istVerwaltet(ev) && !ev.is_recurring_instance;
  }

  /**
   * Löschen ist auch bei Serien-Instanzen erlaubt, seit es dafür die feinen
   * Wege gibt.
   *
   * ★ Vorher waren bei einem Serientermin **alle** Knöpfe ausgeblendet: in der
   * Weboberfläche liess sich ein einzelner wiederkehrender Termin weder ändern
   * noch absagen. Das war richtig, solange der einzige verfügbare Weg „ganze
   * Reihe löschen" hiess, seit den zwei BFF-Routen (EXDATE/UNTIL) ist es nur
   * noch eine unnötige Sackgasse.
   */
  function istLoeschbar(ev: KalenderEvent): boolean {
    return !istVerwaltet(ev);
  }

  function istSerie(ev: KalenderEvent): boolean {
    return Boolean(ev.is_recurring_instance || ev.recurrence_rule);
  }

  /** Der Tag, um den es geht: aus der Instanz-ID, sonst aus dem Start. */
  function vorkommenTag(ev: KalenderEvent): string {
    const id = String(ev.id ?? '');
    if (id.includes('::')) return id.split('::')[1]!.slice(0, 10);
    return dayKeyOf(ev);
  }
</script>

{#if grouped.length === 0}
  <p class="rounded-xl border border-border bg-surface-2/40 px-4 py-10 text-center text-muted">
    {selectedCalendar ? 'Keine Termine in diesem Kalender.' : 'Keine Termine in diesem Zeitraum.'}
  </p>
{:else}
  <ol class="space-y-5">
    {#each grouped as [day, evs] (day)}
      <li class="grid gap-3 sm:grid-cols-[8rem_1fr]">
        <h3 class="flex items-start gap-2 pt-1 font-mono text-sm uppercase tracking-wider text-muted sm:flex-col sm:gap-1">
          <span class="text-text">{dayLabel(day, nowMs)}</span>
          {#if dayTypeByDay.get(day)}
            <span class="w-fit rounded-full border border-border px-2 py-0.5 text-[10px] normal-case tracking-normal text-muted">
              {dayTypeByDay.get(day)}
            </span>
          {/if}
        </h3>
        <ul class="space-y-1.5">
          {#each uniqueBy(evs, (e) => e.id) as ev (ev.id)}
            {@const color = eventColor(ev, calMeta)}
            <li
              class="group flex items-start gap-3 rounded-lg border border-border bg-surface-2/60 px-3 py-2.5 transition-colors hover:border-border/80 {isPast(
                ev,
                nowMs,
              )
                ? 'opacity-50'
                : ''}"
            >
              <span
                class="mt-0.5 w-[4.5rem] shrink-0 font-mono text-xs text-muted"
              >{timeCol(ev)}</span>
              <span class="mt-1 h-2 w-2 shrink-0 rounded-full" style="background-color:{color}"></span>
              <div class="min-w-0 flex-1">
                <div class="truncate font-medium">{ev.title}</div>
                {#if ev.location}
                  <div class="truncate text-xs text-muted">📍 {ev.location}</div>
                {/if}
                {#if endNote(ev)}
                  <div class="truncate text-xs text-muted">{endNote(ev)}</div>
                {/if}
              </div>
              {#if isEditable(ev) || istLoeschbar(ev)}
                <div class="flex shrink-0 items-center gap-2 text-sm opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                  {#if isEditable(ev)}
                    <button
                      type="button"
                      onclick={() => onEdit(ev)}
                      class="text-muted hover:text-accent-300"
                      title="Bearbeiten"
                      aria-label="Termin bearbeiten"><Icon name="pen" size={16} /></button
                    >
                  {/if}
                  {#if istLoeschbar(ev) && !istSerie(ev)}
                    <form method="POST" action="?/eventDelete" use:enhance>
                      <input type="hidden" name="id" value={ev.id} />
                      <button
                        type="submit"
                        class="text-muted hover:text-warm-500"
                        title="Löschen"
                        aria-label="Termin löschen"><Icon name="x" size={16} /></button
                      >
                    </form>
                  {:else if istLoeschbar(ev)}
                    <!-- Serie: nie stillschweigend die ganze Reihe. Die Auswahl
                         steht als kleines Aufklappmenü direkt am Termin, damit
                         der Unterschied beim Klicken sichtbar ist und nicht erst
                         hinterher auffällt. -->
                    <details class="relative">
                      <summary
                        class="cursor-pointer list-none text-muted hover:text-warm-500"
                        title="Serientermin absagen"
                        aria-label="Serientermin absagen"><Icon name="x" size={16} /></summary
                      >
                      <div
                        class="absolute right-0 z-20 mt-1 w-56 space-y-1 rounded-lg border border-border bg-surface-2 p-1.5 shadow-lg"
                      >
                        <p class="px-2 pb-1 pt-0.5 text-[11px] text-muted">
                          Wiederkehrend, was soll entfallen?
                        </p>
                        <form method="POST" action="?/eventDelete" use:enhance>
                          <input type="hidden" name="id" value={ev.id} />
                          <input type="hidden" name="modus" value="vorkommen" />
                          <input type="hidden" name="tag" value={vorkommenTag(ev)} />
                          <button
                            type="submit"
                            class="w-full rounded px-2 py-1 text-left text-xs hover:bg-surface"
                            >Nur dieser Termin</button
                          >
                        </form>
                        <form method="POST" action="?/eventDelete" use:enhance>
                          <input type="hidden" name="id" value={ev.id} />
                          <input type="hidden" name="modus" value="ab_hier" />
                          <input type="hidden" name="tag" value={vorkommenTag(ev)} />
                          <button
                            type="submit"
                            class="w-full rounded px-2 py-1 text-left text-xs hover:bg-surface"
                            >Dieser und alle folgenden</button
                          >
                        </form>
                        <form method="POST" action="?/eventDelete" use:enhance>
                          <input type="hidden" name="id" value={ev.id} />
                          <input type="hidden" name="modus" value="serie" />
                          <button
                            type="submit"
                            class="w-full rounded px-2 py-1 text-left text-xs text-warm-500 hover:bg-surface"
                            >Ganze Serie löschen</button
                          >
                        </form>
                      </div>
                    </details>
                  {/if}
                </div>
              {/if}
            </li>
          {/each}
        </ul>
      </li>
    {/each}
  </ol>
{/if}
