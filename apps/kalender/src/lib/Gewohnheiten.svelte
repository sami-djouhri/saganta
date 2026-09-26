<script lang="ts">
  /**
   * Gewohnheiten: Wochenfortschritt + Sitzungen des Habit-Schedulers.
   *
   * ★ Die drei Antwortknöpfe sind der eigentliche Zweck dieser Komponente. Sie
   * sind kein CRUD, sondern der Eingriff in den Automatismus: „Annehmen"
   * bestätigt eine vorgeschlagene Sitzung, „Verwerfen" gibt den Slot frei,
   * worauf der native Scheduler in derselben Woche selbständig einen Ersatz
   * sucht.
   *
   * Bis 2026-08-25 kam in dieser Oberfläche kein einziger Habit-Aufruf vor
   * (`grep -ric habit src/` = 0), obwohl der BFF die Routen seit dem 20.08.
   * kann. Wer die ntfy-Nachricht „Lernen 17:00–18:30" bekam und am Rechner
   * saß, konnte nichts damit anfangen: der Vorschlag lief stumm in `dismissed`,
   * sobald seine Zeit verstrich.
   */
  import { enhance } from '$app/forms';
  import { fmtDate, fmtTime } from '$lib/cal';
  import type { HabitProgress, HabitSession } from '$lib/kalender-bff';

  interface Props {
    fortschritt?: HabitProgress[];
    sitzungen?: HabitSession[];
  }
  let { fortschritt = [], sitzungen = [] }: Props = $props();

  // ★ Zeitformatierung über cal.ts, nicht selbst gebaut. Ein erster Entwurf
  // hängte naiven Zeiten ein festes `+02:00` an, im Winter wäre jede Sitzung
  // eine Stunde falsch angezeigt worden. Der Kalender hat für diese Frage
  // bereits eine Konvention; eine zweite daneben wäre eine zweite Wahrheit.
  function spanne(s: string, e: string): string {
    if (!s) return '';
    return e ? `${fmtTime(s)}–${fmtTime(e)}` : fmtTime(s);
  }

  const soll = (g: HabitProgress) => Number(g.target_hours ?? g.target_hours_per_week ?? 0);
  const ist = (g: HabitProgress) => Number(g.completed_hours ?? g.done_hours ?? 0);
  // Auf 100 begrenzen: mehr als das Wochenziel ist erlaubt und steht in der
  // Zahl daneben, ein Balken über den Rahmen hinaus sagt nichts zusätzlich.
  const anteil = (g: HabitProgress) => {
    const z = soll(g);
    return z > 0 ? Math.min(100, Math.round((ist(g) / z) * 100)) : 0;
  };

  const ZUSTAND: Record<string, string> = {
    pending: 'vorgeschlagen',
    accepted: 'angenommen',
    completed: 'erledigt',
    dismissed: 'verworfen',
    cancelled: 'abgesagt',
  };

  let offen = $derived(sitzungen.filter((s) => s.status === 'pending'));
  let geplant = $derived(sitzungen.filter((s) => s.status !== 'pending'));
</script>

<section class="space-y-4 rounded-xl border border-border bg-surface-2/40 p-4">
  <div class="flex items-baseline justify-between gap-3">
    <h3 class="font-mono text-xs uppercase tracking-wider text-muted">Gewohnheiten</h3>
    {#if offen.length > 0}
      <span class="text-[11px] font-semibold text-warnung">
        {offen.length} wartet auf Antwort
      </span>
    {/if}
  </div>

  {#if fortschritt.length === 0 && sitzungen.length === 0}
    <p class="text-sm leading-relaxed text-muted">
      Keine Gewohnheiten angelegt. Gewohnheiten sind wiederkehrende Vorhaben mit
      Wochenziel, der Kalender plant die Sitzungen selbst in freie Fenster und
      meldet sie per Push.
    </p>
  {/if}

  {#if fortschritt.length > 0}
    <ul class="space-y-3">
      {#each fortschritt as g (g.habit_id)}
        <li>
          <div class="flex items-baseline justify-between gap-3">
            <span
              class="border-l-2 pl-2 text-sm font-medium"
              style:border-color={g.color || '#4a9eff'}>{g.name}</span
            >
            <span class="shrink-0 font-mono text-[11px] tabular-nums text-muted">
              {ist(g).toFixed(1)} / {soll(g).toFixed(1)} h
            </span>
          </div>
          <div
            class="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface"
            role="progressbar"
            aria-valuenow={anteil(g)}
            aria-valuemin="0"
            aria-valuemax="100"
            aria-label="{g.name}: {ist(g).toFixed(1)} von {soll(g).toFixed(1)} Stunden"
          >
            <div
              class="h-full rounded-full transition-all duration-300"
              class:bg-erfolg={anteil(g) >= 95}
              class:bg-warnung={anteil(g) >= 50 && anteil(g) < 95}
              class:bg-fehler={anteil(g) < 50}
              style:width="{anteil(g)}%"
            ></div>
          </div>
        </li>
      {/each}
    </ul>
  {/if}

  {#if offen.length > 0}
    <div class="space-y-2">
      <h4 class="font-mono text-[11px] uppercase tracking-wider text-warnung">
        Wartet auf Antwort
      </h4>
      {#each offen as s (s.id)}
        <article
          class="space-y-2 rounded-lg border border-border bg-surface/60 p-3 border-l-2"
          style:border-left-color={s.habit_color || '#4a9eff'}
        >
          <div class="flex items-baseline justify-between gap-3">
            <strong class="text-sm font-medium">{s.habit_name ?? 'Gewohnheit'}</strong>
            <span class="shrink-0 font-mono text-[11px] tabular-nums text-muted">
              {fmtDate(s.start)} · {spanne(s.start, s.end)}
            </span>
          </div>
          <div class="flex flex-wrap gap-2">
            <form method="POST" action="?/sitzungAktion" use:enhance>
              <input type="hidden" name="id" value={s.id} />
              <input type="hidden" name="aktion" value="accepted" />
              <button
                type="submit"
                class="rounded-lg border border-accent-500/60 bg-accent-500/10 px-3 py-1 text-xs font-semibold text-accent-200 hover:bg-accent-500/20"
                >Annehmen</button
              >
            </form>
            <form method="POST" action="?/sitzungAktion" use:enhance>
              <input type="hidden" name="id" value={s.id} />
              <input type="hidden" name="aktion" value="dismissed" />
              <button
                type="submit"
                class="rounded-lg border border-border px-3 py-1 text-xs hover:bg-surface-2"
                >Verwerfen</button
              >
            </form>
            <form method="POST" action="?/sitzungAktion" use:enhance>
              <input type="hidden" name="id" value={s.id} />
              <input type="hidden" name="aktion" value="start_early" />
              <button
                type="submit"
                class="rounded-lg border border-border px-3 py-1 text-xs hover:bg-surface-2"
                >Jetzt starten</button
              >
            </form>
          </div>
          <p class="text-[11px] leading-snug text-muted">
            Verwerfen lässt den Scheduler in derselben Woche einen Ersatztermin suchen.
          </p>
        </article>
      {/each}
    </div>
  {/if}

  {#if geplant.length > 0}
    <div class="space-y-1.5">
      <h4 class="font-mono text-[11px] uppercase tracking-wider text-muted">Geplant</h4>
      {#each geplant as s (s.id)}
        <article
          class="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-border border-l-2 bg-surface/40 px-3 py-2"
          style:border-left-color={s.habit_color || '#4a9eff'}
        >
          <div class="min-w-0">
            <span class="text-sm">{s.habit_name ?? 'Gewohnheit'}</span>
            <span
              class="ml-2 text-[11px]"
              class:text-erfolg={s.status === 'accepted'}
              class:text-muted={s.status !== 'accepted'}>{ZUSTAND[s.status] ?? s.status}</span
            >
          </div>
          <div class="flex items-baseline gap-2">
            <span class="font-mono text-[11px] tabular-nums text-muted">
              {fmtDate(s.start)} · {spanne(s.start, s.end)}
            </span>
            {#if s.status === 'accepted'}
              <form method="POST" action="?/sitzungAktion" use:enhance>
                <input type="hidden" name="id" value={s.id} />
                <input type="hidden" name="aktion" value="cancelled" />
                <button
                  type="submit"
                  class="rounded border border-border px-2 py-0.5 text-[11px] text-muted hover:bg-surface-2"
                  >absagen</button
                >
              </form>
            {/if}
          </div>
        </article>
      {/each}
    </div>
  {/if}
</section>
