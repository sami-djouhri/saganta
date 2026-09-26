<script lang="ts">
  import { Icon } from '@saganta/ui';
  import type { KalenderEvent } from '$lib/kalender-bff';
  import {
    type CalMeta,
    DAYTYPE_LABEL,
    DAYTYPE_TINT,
    DAYTYPE_DOT,
    byStart,
    dayKeyOf,
    dayTypeKeyOf,
    eventColor,
    fmtTime,
    inclusiveEndKey,
    isHolidayEvent,
    isBirthdayEvent,
    monthGridDays,
    shiftDay,
  } from '$lib/cal';

  interface Props {
    month: string; // YYYY-MM
    today: string; // YYYY-MM-DD (Berlin)
    events: KalenderEvent[];
    calMeta: Map<string, CalMeta>;
    selectedDay: string | null;
    onSelectDay: (day: string) => void;
    onSelectEvent: (ev: KalenderEvent) => void;
  }
  let { month, today, events, calMeta, selectedDay, onSelectDay, onSelectEvent }: Props = $props();

  const gridDays = $derived(monthGridDays(month));

  // Ein Event kann sich über mehrere Tage ziehen, es soll in jeder betroffenen
  // Zelle auftauchen. Für getimte Events reicht der Starttag; ganztägige/mehrtägige
  // (z. B. Urlaub, Geburtstag) über ihre volle Spanne eintragen.
  const eventsByDay = $derived.by(() => {
    const m = new Map<string, KalenderEvent[]>();
    const push = (k: string, ev: KalenderEvent) => {
      const b = m.get(k) ?? [];
      b.push(ev);
      m.set(k, b);
    };
    for (const ev of events) {
      if (dayTypeKeyOf(ev)) continue; // Tagestyp-Kontext → Tönung, nicht als Chip
      const start = dayKeyOf(ev);
      if (!start) continue;
      const end = inclusiveEndKey(ev);
      if (ev.all_day && end > start) {
        // Ganztägige Spanne über alle Tage verteilen (Schleifen-Guard gegen
        // kaputte Daten via i-Deckel).
        let d = start;
        for (let i = 0; i < 60 && d <= end; i++) {
          push(d, ev);
          d = shiftDay(d, 1);
        }
      } else {
        push(start, ev);
      }
    }
    for (const evs of m.values()) evs.sort(byStart);
    return m;
  });

  // Tagestyp je Kalendertag (aus den Kontext-Events abgeleitet) → Tönung + Punkt.
  const dayTypeByDay = $derived.by(() => {
    const map = new Map<string, string>();
    for (const ev of events) {
      const key = dayTypeKeyOf(ev);
      if (!key) continue;
      const start = dayKeyOf(ev);
      const end = inclusiveEndKey(ev);
      let d = start;
      for (let i = 0; i < 60 && d && d <= end; i++) {
        if (!map.has(d)) map.set(d, key);
        d = shiftDay(d, 1);
      }
    }
    return map;
  });

  const isCurrentMonth = (dayKey: string): boolean => dayKey.slice(0, 7) === month;
  const isWeekend = (dayKey: string): boolean => {
    const dow = new Date(dayKey + 'T12:00:00Z').getUTCDay();
    return dow === 0 || dow === 6;
  };
  function holidayTitle(day: string): string | null {
    const evs = eventsByDay.get(day) ?? [];
    const h = evs.find(isHolidayEvent);
    return h ? h.title : null;
  }
  const WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];
</script>

<div class="overflow-hidden rounded-xl border border-border bg-surface-2/40">
  <div class="grid grid-cols-7 border-b border-border">
    {#each WEEKDAYS as wd, i (wd)}
      <div
        class="px-2 py-2 text-center font-mono text-xs uppercase tracking-wider {i >= 5
          ? 'text-muted/60'
          : 'text-muted'}"
      >
        {wd}
      </div>
    {/each}
  </div>
  <div class="grid grid-cols-7">
    {#each gridDays as day, idx (day)}
      {@const evs = eventsByDay.get(day) ?? []}
      {@const dt = dayTypeByDay.get(day)}
      {@const holiday = holidayTitle(day)}
      {@const chipEvs = evs.filter((e) => !isHolidayEvent(e))}
      {@const maxChips = holiday ? 2 : 3}
      {@const inMonth = isCurrentMonth(day)}
      {@const isToday = day === today}
      {@const isSel = day === selectedDay}
      {@const weekend = isWeekend(day)}
      <button
        type="button"
        onclick={() => onSelectDay(day)}
        style={dt && DAYTYPE_TINT[dt] ? `background-color:${DAYTYPE_TINT[dt]}` : ''}
        class="group relative flex min-h-[6.5rem] flex-col gap-1 border-b border-r border-border/70 p-1.5 text-left transition-colors hover:bg-accent-500/[0.06] focus:outline-none focus-visible:ring-1 focus-visible:ring-accent-500
          {idx % 7 === 6 ? 'border-r-0' : ''}
          {idx >= 35 ? 'border-b-0' : ''}
          {!inMonth ? 'opacity-45' : ''}
          {weekend && !dt ? 'bg-black/10' : ''}
          {isSel ? 'ring-1 ring-inset ring-accent-500' : ''}"
      >
        <div class="flex items-center justify-between">
          <span
            class="grid h-6 min-w-6 place-items-center rounded-full px-1 font-mono text-xs
              {isToday
              ? 'bg-accent-500 font-semibold text-accent-ink'
              : weekend
                ? 'text-muted'
                : 'text-text'}"
          >
            {Number(day.slice(8, 10))}
          </span>
          {#if dt}
            <span
              class="hidden items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-muted sm:inline-flex"
            >
              <span class="h-1.5 w-1.5 rounded-full" style="background-color:{DAYTYPE_DOT[dt]}"
              ></span>
              {DAYTYPE_LABEL[dt]}
            </span>
          {/if}
        </div>

        {#if holiday}
          <div class="truncate rounded bg-accent-500/15 px-1 py-0.5 text-[10px] text-accent-200" title={holiday}>
            {holiday}
          </div>
        {/if}

        <div class="flex flex-1 flex-col gap-0.5 overflow-hidden">
          {#each chipEvs.slice(0, maxChips) as ev (ev.id + day)}
            {@const c = eventColor(ev, calMeta)}
            <button
              type="button"
              onclick={(e) => {
                e.stopPropagation();
                onSelectEvent(ev);
              }}
              class="flex items-center gap-1 rounded px-1 py-0.5 text-left text-[10px] leading-tight hover:bg-white/5"
              title={ev.title}
            >
              {#if ev.all_day || isBirthdayEvent(ev)}
                <span class="h-1.5 w-1.5 shrink-0 rounded-[2px]" style="background-color:{c}"></span>
                {#if isBirthdayEvent(ev)}<Icon name="cake" size={10} />{/if}<span class="truncate">{ev.title}</span>
              {:else}
                <span class="h-1.5 w-1.5 shrink-0 rounded-full" style="background-color:{c}"></span>
                <span class="truncate"><span class="text-muted">{fmtTime(ev.start_at ?? ev.start ?? '')}</span> {ev.title}</span>
              {/if}
            </button>
          {/each}
          {#if chipEvs.length > maxChips}
            <span class="px-1 text-[10px] text-muted">+{chipEvs.length - maxChips} mehr</span>
          {/if}
        </div>
      </button>
    {/each}
  </div>
</div>
