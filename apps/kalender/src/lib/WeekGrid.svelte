<script lang="ts">
  import { Icon } from '@saganta/ui';
  import type { KalenderEvent } from '$lib/kalender-bff';
  import {
    type CalMeta,
    DAYTYPE_DOT,
    DAYTYPE_LABEL,
    DAYTYPE_TINT,
    byStart,
    dayKeyOf,
    dayTypeKeyOf,
    eventColor,
    fmtTime,
    inclusiveEndKey,
    isMultiDay,
    localYmd,
    minutesOfDay,
  } from '$lib/cal';

  interface Props {
    days: string[]; // 7 Keys Mo–So
    today: string;
    events: KalenderEvent[];
    calMeta: Map<string, CalMeta>;
    nowMs: number | null;
    onSelectEvent: (ev: KalenderEvent) => void;
    onCreateAt: (dayKey: string, hour: number) => void;
    /** Ziehen: Tage und Minuten (Raster 15), seit 2026-11-07. Ohne: kein Ziehen. */
    onMoveEvent?: (ev: KalenderEvent, tage: number, minuten: number) => void;
  }
  let { days, today, events, calMeta, nowMs, onSelectEvent, onCreateAt, onMoveEvent }: Props = $props();

  // Ziehen mit Zeiger-Ereignissen statt HTML5-Drag: das gibt es auf dem
  // Telefon nicht. Maus: ab 6 px Bewegung. Finger: erst nach 400 ms Halten,
  // sonst kaeme jeder Wischer zum Scrollen als Verschieben an.
  let zug = $state<{ id: string; dx: number; dy: number } | null>(null);
  let start: { x: number; y: number; t: number; breite: number; aktiv: boolean; finger: boolean } | null = null;
  let warte: ReturnType<typeof setTimeout> | undefined;
  let klickSperre = false;

  function ziehbar(ev: KalenderEvent): boolean {
    return !!onMoveEvent && !ev.recurrence_rule && !ev.is_recurring_instance && !String(ev.id).includes('::');
  }

  function runter(e: PointerEvent, ev: KalenderEvent) {
    if (!ziehbar(ev) || e.button !== 0) return;
    const spalte = (e.currentTarget as HTMLElement).parentElement;
    start = { x: e.clientX, y: e.clientY, t: Date.now(), breite: spalte?.clientWidth ?? 100, aktiv: false, finger: e.pointerType === 'touch' };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    if (start.finger) {
      warte = setTimeout(() => {
        if (start) { start.aktiv = true; zug = { id: ev.id, dx: 0, dy: 0 }; }
      }, 400);
    }
  }

  function bewegen(e: PointerEvent, ev: KalenderEvent) {
    if (!start) return;
    const dx = e.clientX - start.x;
    const dy = e.clientY - start.y;
    if (!start.aktiv) {
      if (start.finger) {
        // Vor dem Halten bewegt: das ist Scrollen, nicht Ziehen.
        if (Math.hypot(dx, dy) > 8) { clearTimeout(warte); start = null; }
        return;
      }
      if (Math.hypot(dx, dy) < 6) return;
      start.aktiv = true;
    }
    e.preventDefault();
    zug = { id: ev.id, dx, dy };
  }

  function hoch(ev: KalenderEvent) {
    clearTimeout(warte);
    const s = start;
    start = null;
    if (!s?.aktiv || !zug) { zug = null; return; }
    const tage = Math.round(zug.dx / s.breite);
    const minuten = Math.round((zug.dy / HOUR_H) * 4) * 15;
    zug = null;
    klickSperre = true;
    setTimeout(() => (klickSperre = false), 0);
    if (tage !== 0 || minuten !== 0) onMoveEvent?.(ev, tage, minuten);
  }

  const HOUR_H = 46; // px pro Stunde

  interface Block {
    ev: KalenderEvent;
    top: number;
    height: number;
    lane: number;
    lanes: number;
  }

  // Greedy-Lane-Packing: überlappende Termine nebeneinander. Sortiert nach Start,
  // jeder Termin in die erste Spur, deren letzter Endzeitpunkt <= Start liegt.
  function packLanes(items: { ev: KalenderEvent; s: number; e: number }[]): Block[] {
    const sorted = [...items].sort((a, b) => a.s - b.s || a.e - b.e);
    const laneEnds: number[] = [];
    const withLane = sorted.map((it) => {
      let lane = laneEnds.findIndex((end) => end <= it.s);
      if (lane === -1) {
        lane = laneEnds.length;
        laneEnds.push(it.e);
      } else {
        laneEnds[lane] = it.e;
      }
      return { ...it, lane };
    });
    // Spuren-Gesamtzahl je Überlappungs-Cluster bestimmen.
    return withLane.map((it) => {
      const overlapping = withLane.filter((o) => o.s < it.e && o.e > it.s);
      const lanes = Math.max(...overlapping.map((o) => o.lane)) + 1;
      return { ev: it.ev, top: it.s, height: it.e - it.s, lane: it.lane, lanes };
    });
  }

  const layout = $derived.by(() => {
    const set = new Set(days);
    const allDay = new Map<string, KalenderEvent[]>();
    const bandsRaw = new Map<string, { ev: KalenderEvent; s: number; e: number }[]>();
    const timedRaw = new Map<string, { ev: KalenderEvent; s: number; e: number }[]>();
    let startMin = 7 * 60;
    let endMin = 21 * 60;

    for (const ev of events) {
      const dtype = dayTypeKeyOf(ev);
      const dk = dayKeyOf(ev);
      if (!dk || !set.has(dk)) {
        // Mehrtägige Ganztages-Events (Urlaub) können vor der Woche beginnen,
        // trotzdem in jedem betroffenen Wochentag zeigen.
        if (!ev.all_day) continue;
      }

      // Ganztägig / mehrtägig → obere „ganztägig"-Zeile (in jeden betroffenen Tag).
      if (ev.all_day || isMultiDay(ev)) {
        const start = dayKeyOf(ev);
        const end = inclusiveEndKey(ev);
        for (const d of days) {
          if (d >= start && d <= end) {
            const b = allDay.get(d) ?? [];
            b.push(ev);
            allDay.set(d, b);
          }
        }
        continue;
      }

      if (!set.has(dk)) continue;
      const s = minutesOfDay(ev.start_at ?? ev.start ?? '');
      const e = Math.max(s + 15, minutesOfDay(ev.end_at ?? ev.end ?? ''));

      if (dtype) {
        // Arbeit/Schule → schattiertes Hintergrund-Band.
        const b = bandsRaw.get(dk) ?? [];
        b.push({ ev, s, e });
        bandsRaw.set(dk, b);
      } else {
        const b = timedRaw.get(dk) ?? [];
        b.push({ ev, s, e });
        timedRaw.set(dk, b);
      }
      startMin = Math.min(startMin, Math.floor(s / 60) * 60);
      endMin = Math.max(endMin, Math.ceil(e / 60) * 60);
    }

    startMin = Math.max(0, startMin);
    endMin = Math.min(24 * 60, Math.max(endMin, startMin + 60));
    const startHour = Math.floor(startMin / 60);
    const endHour = Math.ceil(endMin / 60);
    const hours: number[] = [];
    for (let h = startHour; h < endHour; h++) hours.push(h);

    const toPx = (min: number) => ((min - startHour * 60) / 60) * HOUR_H;
    const byDay = new Map<
      string,
      { allDay: KalenderEvent[]; bands: Block[]; timed: Block[] }
    >();
    for (const d of days) {
      const bands = packLanes(bandsRaw.get(d) ?? []).map((b) => ({
        ...b,
        top: toPx(b.top),
        height: (b.height / 60) * HOUR_H,
        lanes: 1,
        lane: 0,
      }));
      const timed = packLanes(timedRaw.get(d) ?? []).map((b) => ({
        ...b,
        top: toPx(b.top),
        height: Math.max(18, (b.height / 60) * HOUR_H),
      }));
      byDay.set(d, {
        allDay: (allDay.get(d) ?? []).sort(byStart),
        bands,
        timed,
      });
    }
    return { hours, startHour, endHour, height: (endHour - startHour) * HOUR_H, byDay };
  });

  const nowInWeek = $derived(nowMs !== null && days.includes(localYmd(new Date(nowMs))));
  const nowTop = $derived.by(() => {
    if (nowMs === null) return 0;
    const min = minutesOfDay(new Date(nowMs).toISOString());
    return ((min - layout.startHour * 60) / 60) * HOUR_H;
  });
  const nowCol = $derived(nowMs !== null ? days.indexOf(localYmd(new Date(nowMs))) : -1);

  function dayHead(d: string): { wd: string; dom: string } {
    const dt = new Date(d + 'T12:00:00Z');
    return {
      wd: dt.toLocaleDateString('de-DE', { weekday: 'short', timeZone: 'UTC' }),
      dom: String(dt.getUTCDate()),
    };
  }
  const isWeekendCol = (d: string): boolean => {
    const dow = new Date(d + 'T12:00:00Z').getUTCDay();
    return dow === 0 || dow === 6;
  };
</script>

<div class="overflow-hidden rounded-xl border border-border bg-surface-2/40">
  <!-- Kopf: Wochentage -->
  <div class="grid border-b border-border" style="grid-template-columns: 3rem repeat(7, 1fr)">
    <div class="border-r border-border"></div>
    {#each days as d (d)}
      {@const h = dayHead(d)}
      <div
        class="flex items-center justify-center gap-1.5 border-r border-border/70 py-2 text-center last:border-r-0 {isWeekendCol(
          d,
        )
          ? 'bg-black/10'
          : ''}"
      >
        <span class="text-xs uppercase tracking-wide text-muted">{h.wd}</span>
        <span
          class="grid h-6 min-w-6 place-items-center rounded-full px-1 text-sm {d === today
            ? 'bg-accent-500 font-semibold text-accent-ink'
            : 'text-text'}">{h.dom}</span
        >
      </div>
    {/each}
  </div>

  <!-- Ganztägig-Zeile -->
  <div
    class="grid border-b border-border bg-surface/40"
    style="grid-template-columns: 3rem repeat(7, 1fr)"
  >
    <!-- Sinnbild statt „GANZTG": in 12 px passte das Wort nicht mehr in die
         3-rem-Spalte und lief in die erste Stundenzahl. -->
    <div class="flex items-center justify-end border-r border-border px-1.5 text-muted/70" title="Ganztägig">
      <Icon name="sun" size={14} />
      <span class="sr-only">Ganztägig</span>
    </div>
    {#each days as d (d)}
      {@const cell = layout.byDay.get(d)}
      <div class="min-h-[1.75rem] space-y-0.5 border-r border-border/70 p-1 last:border-r-0">
        {#each cell?.allDay ?? [] as ev (ev.id + d)}
          {@const dtype = dayTypeKeyOf(ev)}
          <button
            type="button"
            onclick={() => onSelectEvent(ev)}
            style={dtype && DAYTYPE_TINT[dtype]
              ? `background-color:${DAYTYPE_TINT[dtype]}`
              : `background-color:${eventColor(ev, calMeta)}22`}
            class="flex w-full items-center gap-1 truncate rounded px-1 py-0.5 text-left text-xs hover:brightness-125"
            title={ev.title}
          >
            <span
              class="h-1.5 w-1.5 shrink-0 rounded-[2px]"
              style="background-color:{dtype ? DAYTYPE_DOT[dtype] : eventColor(ev, calMeta)}"
            ></span>
            <span class="truncate">{dtype ? DAYTYPE_LABEL[dtype] : ev.title}</span>
          </button>
        {/each}
      </div>
    {/each}
  </div>

  <!-- Stunden-Grid -->
  <div class="grid" style="grid-template-columns: 3rem repeat(7, 1fr)">
    <!-- Zeit-Gutter -->
    <div class="relative border-r border-border" style="height:{layout.height}px">
      {#each layout.hours as h (h)}
        <div
          class="absolute right-1 font-mono text-xs text-muted {h === layout.startHour
            ? 'translate-y-0.5'
            : '-translate-y-1/2'}"
          style="top:{(h - layout.startHour) * HOUR_H}px"
        >
          {String(h).padStart(2, '0')}
        </div>
      {/each}
    </div>

    {#each days as d, col (d)}
      {@const cell = layout.byDay.get(d)}
      <div
        class="relative border-r border-border/70 last:border-r-0 {isWeekendCol(d) ? 'bg-black/[0.07]' : ''}"
        style="height:{layout.height}px"
      >
        <!-- Stunden-Linien + Klick-Flächen zum Anlegen -->
        {#each layout.hours as h (h)}
          <button
            type="button"
            onclick={() => onCreateAt(d, h)}
            aria-label="Termin um {h}:00 anlegen"
            class="absolute inset-x-0 border-t border-border/40 hover:bg-accent-500/[0.05]"
            style="top:{(h - layout.startHour) * HOUR_H}px; height:{HOUR_H}px"
          ></button>
        {/each}

        <!-- Arbeit/Schule-Bänder (Hintergrund) -->
        {#each cell?.bands ?? [] as b (b.ev.id + d)}
          {@const dtype = dayTypeKeyOf(b.ev)}
          <div
            class="pointer-events-none absolute inset-x-0.5 rounded-sm border-l-2"
            style="top:{b.top}px; height:{b.height}px; background-color:{dtype
              ? DAYTYPE_TINT[dtype]
              : 'rgba(255,255,255,0.04)'}; border-color:{dtype ? DAYTYPE_DOT[dtype] : '#8a8aa0'}"
          >
            <span class="px-1 text-xs uppercase tracking-wide text-muted">{dtype ? DAYTYPE_LABEL[dtype] : ''}</span>
          </div>
        {/each}

        <!-- Getimte Termine -->
        {#each cell?.timed ?? [] as b (b.ev.id + d)}
          {@const c = eventColor(b.ev, calMeta)}
          <button
            type="button"
            onclick={(e) => {
              e.stopPropagation();
              if (klickSperre) return;
              onSelectEvent(b.ev);
            }}
            onpointerdown={(e) => runter(e, b.ev)}
            onpointermove={(e) => bewegen(e, b.ev)}
            onpointerup={() => hoch(b.ev)}
            onpointercancel={() => { clearTimeout(warte); start = null; zug = null; }}
            class="absolute overflow-hidden rounded-md border-l-2 px-1 py-0.5 text-left text-xs leading-tight shadow-sm hover:brightness-125"
            style="top:{b.top}px; height:{b.height}px; left:calc({(b.lane / b.lanes) *
              100}% + 2px); width:calc({100 / b.lanes}% - 4px); background-color:{c}26; border-color:{c};{zug?.id === b.ev.id
              ? ` transform:translate(${zug.dx}px, ${zug.dy}px); z-index:20; touch-action:none; cursor:grabbing;`
              : ziehbar(b.ev) ? ' cursor:grab;' : ''}"
            title="{fmtTime(b.ev.start_at ?? b.ev.start ?? '')} {b.ev.title}"
          >
            <div class="truncate font-medium text-text">{b.ev.title}</div>
            {#if b.height > 28}
              <div class="truncate text-muted">{fmtTime(b.ev.start_at ?? b.ev.start ?? '')}</div>
            {/if}
          </button>
        {/each}

        <!-- Jetzt-Linie -->
        {#if nowInWeek && col === nowCol && nowTop >= 0 && nowTop <= layout.height}
          <div class="pointer-events-none absolute inset-x-0 z-10" style="top:{nowTop}px">
            <div class="h-px bg-fehler"></div>
            <div class="absolute -left-1 -top-1 h-2 w-2 rounded-full bg-fehler"></div>
          </div>
        {/if}
      </div>
    {/each}
  </div>
</div>
