<script lang="ts">
  import { onMount } from 'svelte';
  import { enhance } from '$app/forms';
  import { Icon, appUrlById } from '@saganta/ui';
  import { page } from '$app/stores';
  import type { ActionData, PageData } from './$types';
  import type { KalenderEvent } from '$lib/kalender-bff';
  import QuickCapture from '$lib/QuickCapture.svelte';
  import SekretaerHeute from '$lib/SekretaerHeute.svelte';
  import AktivitaetsInsights from '$lib/AktivitaetsInsights.svelte';
  import AktivitaetsFeedback from '$lib/AktivitaetsFeedback.svelte';
  import Gewohnheiten from '$lib/Gewohnheiten.svelte';
  import MonthGrid from '$lib/MonthGrid.svelte';
  import WeekGrid from '$lib/WeekGrid.svelte';
  import AgendaList from '$lib/AgendaList.svelte';
  import EventModal from '$lib/EventModal.svelte';
  import Tagesdecke from '$lib/Tagesdecke.svelte';
  import { invalidateAll, goto } from '$app/navigation';
  import {
    buildCalMeta,
    byStart,
    dayKeyOf,
    dayLabel,
    dayTypeKeyOf,
    DAYTYPE_LABEL,
    DAYTYPE_DOT,
    eventColor,
    fmtTime,
    isContextDaytypeCal,
    isHolidayEvent,
    isBirthdayEvent,
    monthLabel,
    shiftDay,
    shiftMonth,
    startOf,
    endOf,
    timeCol,
    uniqueBy,
    weekGridDays,
    weekLabel,
  } from '$lib/cal';

  let { data, form }: { data: PageData; form: ActionData } = $props();

  // `now` erst nach dem Mount → relative Labels + Jetzt-Linie laufen rein
  // client-seitig (verhindert SSR/Client-Hydration-Mismatch, da der SSR-Node
  // auf UTC läuft, der Browser auf Berlin).
  let nowMs = $state<number | null>(null);
  onMount(() => {
    nowMs = Date.now();
  });

  // --- Tagesdecke -------------------------------------------------------
  // Die Aktionen laufen über `fetch` auf die Server-Actions statt über ein
  // <form>: das Ziehen endet mit einem Pointer-Ereignis, nicht mit einem Klick
  // auf einen Absendeknopf, und ein verstecktes Formular je Block wäre ein
  // Dutzend toter Elemente pro Tag. Danach `invalidateAll()`, damit die neuen
  // Zeiten vom Server kommen und nicht aus der Annahme des Browsers.
  let deckeLaeuft = $state(false);
  let deckeFehler = $state<string | null>(null);

  async function deckeAktion(action: string, felder: Record<string, string>) {
    deckeLaeuft = true;
    deckeFehler = null;
    try {
      const daten = new FormData();
      for (const [schluessel, wert] of Object.entries(felder)) daten.set(schluessel, wert);
      const antwort = await fetch(`?/${action}`, { method: 'POST', body: daten });
      if (!antwort.ok) throw new Error(`Server antwortete ${antwort.status}`);
      const ergebnis = await antwort.json();
      // SvelteKit verpackt `fail()` als type 'failure'. Ohne diese Prüfung sähe
      // ein abgelehnter Aufruf wie ein erfolgreicher aus: der Statuscode der
      // Hülle ist 200, der Fehler steckt im Rumpf.
      if (ergebnis?.type === 'failure') throw new Error('Die Änderung wurde abgelehnt.');
      await invalidateAll();
    } catch (err) {
      deckeFehler = err instanceof Error ? err.message : String(err);
    } finally {
      deckeLaeuft = false;
    }
  }

  const deckeFestschreiben = () =>
    deckeAktion('deckeFestschreiben', { datum: data.deckeTag });
  const deckeNeuOrdnen = (reihenfolge: string[]) =>
    deckeAktion('deckeNeuOrdnen', { datum: data.deckeTag, reihenfolge: reihenfolge.join(',') });
  const deckeVerwerfen = (blockId: string) =>
    deckeAktion('deckeBlockVerwerfen', { block_id: blockId });

  function deckeTagWechsel(datum: string) {
    const ziel = new URL($page.url);
    ziel.searchParams.set('decke', datum);
    goto(ziel, { keepFocus: true, noScroll: true });
  }

  const calMeta = $derived(buildCalMeta(data.calendars));
  const items = $derived(data.upcoming?.items ?? []);
  const failure = $derived(data.failures?.bff);
  const capped = $derived((data.upcoming?.items.length ?? 0) >= 200);

  // ── Termin-Editor (Modal) ─────────────────────────────────────────────
  let modalOpen = $state(false);
  let editing = $state<KalenderEvent | null>(null);
  let prefillDate = $state('');
  let prefillStart = $state('');
  let prefillEnd = $state('');
  const editableCalendars = $derived(
    data.calendars.filter((c) => !/^daytype-/.test(c.id) && !/^system-geburtstage/.test(c.id)),
  );
  const formError = $derived(
    form && typeof form === 'object' && 'error' in form ? (form.error as string) : null,
  );

  // ── Feierabend heute ──
  interface FeierabendRes {
    date: string;
    cancelled: { title: string }[];
    planned: { title: string; day: string | null; start?: string }[];
  }
  let feierabendConfirm = $state(false);
  const feierabendResult: FeierabendRes | null = $derived(
    form && typeof form === 'object' && 'feierabend' in form
      ? (form as unknown as { feierabend: FeierabendRes }).feierabend
      : null,
  );

  function isEditable(ev: KalenderEvent): boolean {
    const cid = ev.calendar_id ?? '';
    if (/^daytype-/.test(cid) || /^system-geburtstage/.test(cid)) return false;
    return !ev.is_recurring_instance;
  }
  function openCreate(date = '', start = '', end = ''): void {
    editing = null;
    prefillDate = date;
    prefillStart = start;
    prefillEnd = end;
    modalOpen = true;
  }
  function openEdit(ev: KalenderEvent): void {
    editing = ev;
    modalOpen = true;
  }
  function closeModal(): void {
    modalOpen = false;
    editing = null;
    prefillDate = prefillStart = prefillEnd = '';
  }
  function onSelectEvent(ev: KalenderEvent): void {
    if (isEditable(ev)) openEdit(ev);
    else selectedDay = dayKeyOf(ev); // Feiertag/Geburtstag/Serie → Tages-Detail
  }
  function onCreateAt(dayKey: string, hour: number): void {
    const h = String(hour).padStart(2, '0');
    const h2 = String(Math.min(23, hour + 1)).padStart(2, '0');
    openCreate(dayKey, `${h}:00`, `${h2}:00`);
  }

  // ── Ausgewählter Tag (Tages-Detail) ───────────────────────────────────
  let selectedDay = $state<string | null>(null);
  function selectDay(day: string): void {
    selectedDay = selectedDay === day ? null : day;
  }
  const selectedDayEvents = $derived(
    selectedDay
      ? items
          .filter((e) => !dayTypeKeyOf(e) && dayKeyOf(e) === selectedDay)
          .slice()
          .sort(byStart)
      : [],
  );
  const selectedDayType = $derived.by(() => {
    if (!selectedDay) return null;
    for (const ev of items) {
      const k = dayTypeKeyOf(ev);
      if (k && dayKeyOf(ev) === selectedDay) return DAYTYPE_LABEL[k] ?? k;
    }
    return null;
  });

  // ── Agenda-Nav (Tages-Fenster + Kalenderfilter) ───────────────────────
  function agendaHref(params: { days?: number; calendar?: string }): string {
    const p = new URLSearchParams();
    p.set('view', 'list'); // Agenda ist nicht die Standard-Ansicht → immer setzen
    const days = params.days ?? data.days;
    const calendar = params.calendar ?? data.selectedCalendar;
    if (days !== 14) p.set('days', String(days));
    if (calendar) p.set('calendar', calendar);
    return `/?${p.toString()}`;
  }

  // ★★ Aufgaben und Ziele werden hier nur noch GEZAEHLT, nicht mehr verwaltet.
  // Sie sind am 2026-09-13 in die eigene App `aufgaben.saganta.*` gezogen, die
  // auf derselben Engine sitzt (`/api/todos`, `/api/goals` desselben BFF): es ist
  // derselbe Bestand, nicht eine Kopie. Was hier bleibt, ist der Tagesbezug, den
  // ein Kalender braucht: wie viel steht heute an, und wo geht es hin.
  const heuteFaellig = $derived(
    (data.todos ?? []).filter((t) => !t.completed && t.due_date && t.due_date <= data.today).length,
  );
  const offeneZiele = $derived((data.goals ?? []).filter((g) => g.status !== 'achieved').length);
  const aufgabenBasis = $derived(appUrlById('aufgaben', $page.url.host));

  const headerTitle = $derived(
    data.view === 'month'
      ? monthLabel(data.month)
      : data.view === 'week'
        ? weekLabel(data.week)
        : `Nächste ${data.days} Tage`,
  );
  const weekDays = $derived(weekGridDays(data.week));

  // Legende: echte Kalender (ohne Tagestyp-Kontext) mit aufgelöster Farbe.
  const legendCals = $derived(
    data.calendars
      .filter((c) => !isContextDaytypeCal(c.id))
      .map((c) => ({
        name: calMeta.get(c.id)?.name ?? c.id,
        color: /^daytype-feiertag-/.test(c.id)
          ? '#cf8524'
          : /^system-geburtstage/.test(c.id)
            ? '#e0639a'
            : (calMeta.get(c.id)?.color ?? '#8a8aa0'),
      })),
  );
  const daytypeLegend = [
    { label: 'Arbeit', color: DAYTYPE_DOT.arbeit },
    { label: 'Schule', color: DAYTYPE_DOT.schule },
    { label: 'Urlaub', color: DAYTYPE_DOT.urlaub },
    { label: 'Krank', color: DAYTYPE_DOT.krank },
  ];

  // Zeit-Statistik (v1): Summe der getimten Termine je Kalender im aktuell
  // geladenen Zeitraum (Tagestyp-Kontext + ganztägige ausgenommen). Zeigt, wofür
  // die verplante Zeit draufgeht: erste Ausbaustufe „Statistiken über meine Zeit".
  const timeStats = $derived.by(() => {
    const mins = new Map<string, number>();
    for (const ev of items) {
      if (dayTypeKeyOf(ev) || ev.all_day) continue;
      const s = Date.parse(startOf(ev));
      const e = Date.parse(endOf(ev));
      if (Number.isNaN(s) || Number.isNaN(e) || e <= s) continue;
      const cid = ev.calendar_id ?? '?';
      mins.set(cid, (mins.get(cid) ?? 0) + (e - s) / 60000);
    }
    const rows = [...mins.entries()]
      .map(([cid, m]) => ({
        name: calMeta.get(cid)?.name ?? 'Sonstige',
        color: calMeta.get(cid)?.color ?? '#8a8aa0',
        min: m,
      }))
      .sort((a, b) => b.min - a.min);
    const total = rows.reduce((n, r) => n + r.min, 0);
    const max = rows.length ? rows[0]!.min : 0;
    return { rows, total, max };
  });
  const fmtH = (min: number): string =>
    min >= 60 ? `${Math.round((min / 60) * 10) / 10} h` : `${Math.round(min)} min`;
  const rangeLabel = $derived(
    data.view === 'week' ? 'diese Woche' : data.view === 'month' ? 'dieser Monat' : 'sichtbar',
  );
</script>

<section class="space-y-6">
  <!-- Kopf -->
  <header class="space-y-3">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p class="font-mono text-xs uppercase tracking-widest text-muted">Saganta · Kalender</p>
        <h1 class="font-display text-4xl capitalize leading-tight">{headerTitle}</h1>
      </div>
      <button
        type="button"
        onclick={() => openCreate(data.today)}
        class="shrink-0 rounded-lg bg-accent-500 px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-400"
        >+ Termin</button
      >
    </div>

    <!-- Ansichts-Umschalter + Navigation -->
    <div class="flex flex-wrap items-center gap-2">
      <div class="inline-flex rounded-lg border border-border p-0.5">
        <a
          href="/?view=month&month={data.month}"
          class="rounded-md px-3 py-1 text-sm {data.view === 'month'
            ? 'bg-accent-500/15 text-accent-200'
            : 'text-muted hover:text-text'}">Monat</a
        >
        <a
          href="/?view=week&week={data.week}"
          class="rounded-md px-3 py-1 text-sm {data.view === 'week'
            ? 'bg-accent-500/15 text-accent-200'
            : 'text-muted hover:text-text'}">Woche</a
        >
        <a
          href="/?view=list"
          class="rounded-md px-3 py-1 text-sm {data.view === 'list'
            ? 'bg-accent-500/15 text-accent-200'
            : 'text-muted hover:text-text'}">Agenda</a
        >
      </div>

      {#if data.view === 'month'}
        <span class="mx-1 h-5 w-px bg-border"></span>
        <a
          href="/?view=month&month={shiftMonth(data.month, -1)}"
          class="grid size-8 place-items-center rounded-md border border-border text-muted hover:text-text"
          aria-label="Vorheriger Monat"><Icon name="chevron-left" size={18} /></a
        >
        <a
          href="/?view=month"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-muted hover:text-text">Heute</a
        >
        <a
          href="/?view=month&month={shiftMonth(data.month, 1)}"
          class="grid size-8 place-items-center rounded-md border border-border text-muted hover:text-text"
          aria-label="Nächster Monat"><Icon name="chevron-right" size={18} /></a
        >
      {:else if data.view === 'week'}
        <span class="mx-1 h-5 w-px bg-border"></span>
        <a
          href="/?view=week&week={shiftDay(data.week, -7)}"
          class="grid size-8 place-items-center rounded-md border border-border text-muted hover:text-text"
          aria-label="Vorherige Woche"><Icon name="chevron-left" size={18} /></a
        >
        <a
          href="/?view=week"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-muted hover:text-text">Heute</a
        >
        <a
          href="/?view=week&week={shiftDay(data.week, 7)}"
          class="grid size-8 place-items-center rounded-md border border-border text-muted hover:text-text"
          aria-label="Nächste Woche"><Icon name="chevron-right" size={18} /></a
        >
      {:else}
        <span class="mx-1 h-5 w-px bg-border"></span>
        {#each data.allowedDays as n (n)}
          <a
            href={agendaHref({ days: n })}
            class="rounded-md border px-3 py-1.5 text-sm {data.days === n
              ? 'border-accent-500 text-accent-200'
              : 'border-border text-muted hover:text-text'}">{n} Tage</a
          >
        {/each}
      {/if}
    </div>

    <!-- Kalenderfilter (nur Agenda) -->
    {#if data.view === 'list' && data.calendars.length > 0}
      <div class="flex flex-wrap items-center gap-1.5 text-sm">
        <a
          href={agendaHref({ calendar: '' })}
          class="rounded-full border px-3 py-1 {!data.selectedCalendar
            ? 'border-accent-500 text-accent-200'
            : 'border-border text-muted hover:text-text'}">Alle</a
        >
        {#each uniqueBy( data.calendars.filter((c) => !isContextDaytypeCal(c.id)), (c) => c.id ) as c (c.id)}
          {@const meta = calMeta.get(c.id)}
          <a
            href={agendaHref({ calendar: c.id })}
            class="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 {data.selectedCalendar ===
            c.id
              ? 'border-accent-500 text-accent-200'
              : 'border-border text-muted hover:text-text'}"
          >
            <span class="h-2 w-2 shrink-0 rounded-full" style="background-color:{meta?.color}"></span>
            {meta?.name}
          </a>
        {/each}
      </div>
    {/if}
  </header>

  {#if failure}
    <div class="rounded-lg border border-warm-500/40 bg-warm-500/10 p-3 text-sm">
      <div class="font-medium">Kalender-BFF nicht erreichbar.</div>
      <div class="mt-1 font-mono text-xs text-muted">{failure}</div>
    </div>
  {/if}

  <!-- Kalender (Hauptfläche) + Tages-Sidebar -->
  <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_19rem]">
    <div class="min-w-0 space-y-4">
      {#if data.view === 'month'}
        <MonthGrid
          month={data.month}
          today={data.today}
          events={items}
          {calMeta}
          {selectedDay}
          onSelectDay={selectDay}
          {onSelectEvent}
        />
      {:else if data.view === 'week'}
        <div class="overflow-x-auto">
          <div class="min-w-[44rem]">
            <WeekGrid
              days={weekDays}
              today={data.today}
              events={items}
              {calMeta}
              {nowMs}
              {onSelectEvent}
              {onCreateAt}
            />
          </div>
        </div>
      {:else}
        <AgendaList
          {items}
          selectedCalendar={data.selectedCalendar}
          {calMeta}
          {nowMs}
          onEdit={openEdit}
        />
        {#if capped && !failure}
          <p class="text-center text-xs text-muted">
            Auf die nächsten 200 Termine begrenzt, im Zeitraum könnten weitere liegen.
          </p>
        {/if}
      {/if}
    </div>

    <!-- Sidebar, nach Aufmerksamkeit sortiert: gewählter Tag → heutiger Anker →
         Erfassen → seltene Aktion → einklappbare Einblicke → einklappbare Referenz. -->
    <aside class="space-y-5">
      <!-- Tages-Detail: unmittelbare Reaktion auf einen Tages-Klick → ganz oben,
           damit die Auswahl nicht unter dem Anker-Block verschwindet. -->
      {#if selectedDay}
        <section class="rounded-xl border border-accent-500/30 bg-accent-500/[0.04] p-4">
          <div class="mb-2 flex items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <h2 class="font-display text-lg">{dayLabel(selectedDay, nowMs)}</h2>
              {#if selectedDayType}
                <span class="rounded-full border border-border px-2 py-0.5 text-[10px] text-muted"
                  >{selectedDayType}</span
                >
              {/if}
            </div>
            <button
              type="button"
              onclick={() => (selectedDay = null)}
              class="text-muted hover:text-text"
              aria-label="Schließen"><Icon name="x" size={16} /></button
            >
          </div>
          {#if selectedDayEvents.length === 0}
            <p class="text-sm text-muted">Keine Termine.</p>
          {:else}
            <ul class="space-y-1.5">
              {#each uniqueBy(selectedDayEvents, (e) => e.id) as ev (ev.id)}
                <li>
                  <button
                    type="button"
                    onclick={() => onSelectEvent(ev)}
                    class="flex w-full items-start gap-2 rounded-lg border border-border bg-surface-2/60 px-2.5 py-2 text-left hover:border-border/80"
                  >
                    <span
                      class="mt-1 h-2 w-2 shrink-0 rounded-full"
                      style="background-color:{eventColor(ev, calMeta)}"
                    ></span>
                    <span class="min-w-0 flex-1">
                      <span class="flex items-center gap-1.5 truncate text-sm font-medium">
                        {#if isBirthdayEvent(ev)}<Icon name="cake" size={13} />{/if}{ev.title}
                      </span>
                      <span class="block text-xs text-muted">{timeCol(ev)}</span>
                    </span>
                  </button>
                </li>
              {/each}
            </ul>
          {/if}
          <button
            type="button"
            onclick={() => openCreate(selectedDay ?? data.today)}
            class="mt-3 w-full rounded-lg border border-accent-500/60 px-3 py-1.5 text-sm text-accent-200 hover:bg-accent-500/10"
            >+ Termin an diesem Tag</button
          >
        </section>
      {/if}

      <!-- Dein Tag (adaptiver Sekretär), der tägliche Anker: Check-in +
           „Wie lief's?" sollen das Erste sein, was ins Auge fällt. -->
      <SekretaerHeute assistant={data.assistant} today={data.today} {aufgabenBasis} />

      <!-- Die Tagesdecke: der wache Tag lückenlos, Erholung eingeschlossen.
           Steht direkt unter „Dein Tag", weil sie dieselbe Frage beantwortet,
           nur vollständig: nicht „was steht an", sondern „wo geht der Tag hin". -->
      <Tagesdecke
        decke={data.tagesdecke}
        beschaeftigt={deckeLaeuft}
        onFestschreiben={deckeFestschreiben}
        onNeuOrdnen={deckeNeuOrdnen}
        onVerwerfen={deckeVerwerfen}
        onTagWechsel={deckeTagWechsel}
      />
      {#if deckeFehler}
        <p class="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
          {deckeFehler}
        </p>
      {/if}

      <!-- Gewohnheiten: Wochenfortschritt + die Sitzungen, die der Scheduler
           selbst geplant hat. Direkt unter „Dein Tag“, weil ein offener
           Vorschlag eine Antwort braucht, bevor seine Zeit verstreicht. -->
      <Gewohnheiten fortschritt={data.habitProgress} sitzungen={data.habitSessions} />

      <QuickCapture prefill={data.prefillCapture} prefillDate={data.prefillDate} {form} />

      <!-- Feierabend heute: seltene Tages-Aktion: im Ruhezustand nur ein Knopf
           (keine permanente Card), expandiert erst bei Bestätigung/Ergebnis. -->
      <section>
        {#if feierabendResult}
          <div class="space-y-2 rounded-xl border border-border bg-surface-2/40 p-4">
            <p class="flex items-center gap-2 text-sm">
              <Icon name="moon" size={15} /> Feierabend: {feierabendResult.cancelled.length}
              {feierabendResult.cancelled.length === 1 ? 'Termin' : 'Termine'} abgesagt.
            </p>
            {#if feierabendResult.planned.length > 0}
              <ul class="space-y-1 text-xs text-muted">
                {#each feierabendResult.planned as p (p.title + (p.day ?? ''))}
                  <li>
                    {p.title}
                    {#if p.day}
                      → {dayLabel(p.day, nowMs)}{#if p.start}, {fmtTime(p.start)}{/if}
                    {:else}
                      → kein freier Slot gefunden
                    {/if}
                  </li>
                {/each}
              </ul>
            {/if}
            <p class="text-xs text-muted">Genieß den Feierabend.</p>
          </div>
        {:else if feierabendConfirm}
          <div class="rounded-xl border border-border bg-surface-2/40 p-4">
            <p class="mb-3 text-sm text-muted">
              Heute Feierabend? Die noch offene Routine wird abgesagt und in die nächsten Tage verschoben.
            </p>
            <div class="flex gap-2">
              <form
                method="POST"
                action="?/feierabend"
                use:enhance={() =>
                  async ({ update }) => {
                    await update();
                    feierabendConfirm = false;
                  }}
              >
                <button
                  type="submit"
                  class="rounded-lg bg-accent-500 px-4 py-1.5 text-sm font-medium text-accent-ink hover:bg-accent-400"
                  >Ja, Feierabend</button
                >
              </form>
              <button
                type="button"
                onclick={() => (feierabendConfirm = false)}
                class="rounded-lg border border-border px-4 py-1.5 text-sm text-muted hover:text-text"
                >Abbrechen</button
              >
            </div>
          </div>
        {:else}
          <button
            type="button"
            onclick={() => (feierabendConfirm = true)}
            class="flex w-full items-center justify-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-muted hover:border-accent-500/60 hover:text-text"
            ><Icon name="moon" size={15} /> Feierabend heute</button
          >
        {/if}
      </section>

      <!-- Einblicke: Reflexion (was Saganta gelernt hat + Zeit-Verteilung) in
           einer Gruppe, einklappbar: sekundär, soll nicht permanent Reize ziehen. -->
      {#if (data.insights?.length ?? 0) > 0 || timeStats.rows.length > 0 || (data.reviewable?.length ?? 0) > 0}
        <details class="group rounded-xl border border-border bg-surface-2/40" open>
          <summary
            class="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3"
          >
            <h3 class="font-mono text-xs uppercase tracking-wider text-muted">Einblicke</h3>
            <Icon
              name="chevron-down"
              size={16}
              class="shrink-0 text-muted transition-transform duration-200 group-open:rotate-180"
            />
          </summary>
          <div class="space-y-5 border-t border-border px-4 py-4">
            <!-- ★ „Wie lief's?" lag bis 2026-09-13 mitten im Tagesblock und zog
                 dort Aufmerksamkeit fuer eine Frage, die den vergangenen Tag
                 betrifft. Hier steht sie neben dem, was daraus entsteht. -->
            {#if (data.reviewable?.length ?? 0) > 0}
              <div class="space-y-2">
                <h4 class="font-mono text-xs uppercase tracking-wider text-muted">
                  Wie lief's? ({data.reviewable.length})
                </h4>
                <ul class="space-y-2">
                  {#each data.reviewable.slice(0, 5) as a (a.instance_id)}
                    <AktivitaetsFeedback activity={a} />
                  {/each}
                </ul>
                {#if data.reviewable.length > 5}
                  <p class="text-[11px] text-muted">
                    +{data.reviewable.length - 5} ältere warten noch auf eine Rückmeldung.
                  </p>
                {/if}
              </div>
            {/if}

            <AktivitaetsInsights insights={data.insights} bare />

            {#if timeStats.rows.length > 0}
              <div>
                <div class="mb-3 flex items-baseline justify-between">
                  <h4 class="font-mono text-xs uppercase tracking-wider text-muted">Zeit-Verteilung</h4>
                  <span class="text-[10px] text-muted">{rangeLabel} · {fmtH(timeStats.total)}</span>
                </div>
                <div class="space-y-2">
                  {#each timeStats.rows as r (r.name)}
                    <div class="space-y-1">
                      <div class="flex items-center justify-between text-xs">
                        <span class="flex items-center gap-1.5 text-muted">
                          <span class="h-2 w-2 rounded-full" style="background-color:{r.color}"></span>
                          {r.name}
                        </span>
                        <span class="text-muted">{fmtH(r.min)}</span>
                      </div>
                      <div class="h-1.5 overflow-hidden rounded-full bg-white/10">
                        <div
                          class="h-full rounded-full"
                          style="width:{timeStats.max ? (r.min / timeStats.max) * 100 : 0}%; background-color:{r.color}"
                        ></div>
                      </div>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        </details>
      {/if}

      <!-- Legende: reine Referenz, einklappbar (im Ruhezustand zu). -->
      {#if legendCals.length > 0}
        <details class="group rounded-xl border border-border bg-surface-2/40">
          <summary
            class="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3"
          >
            <h3 class="font-mono text-xs uppercase tracking-wider text-muted">Legende</h3>
            <Icon
              name="chevron-down"
              size={16}
              class="shrink-0 text-muted transition-transform duration-200 group-open:rotate-180"
            />
          </summary>
          <div class="border-t border-border px-4 py-4">
            <div class="grid grid-cols-2 gap-x-3 gap-y-1.5">
              {#each legendCals as c (c.name)}
                <div class="flex items-center gap-2 text-xs">
                  <span class="h-2.5 w-2.5 shrink-0 rounded-full" style="background-color:{c.color}"></span>
                  <span class="truncate text-muted">{c.name}</span>
                </div>
              {/each}
            </div>
            <div class="mt-3 flex flex-wrap gap-x-3 gap-y-1 border-t border-border pt-2.5">
              {#each daytypeLegend as d (d.label)}
                <div class="flex items-center gap-1.5 text-[11px]">
                  <span class="h-2 w-2 shrink-0 rounded-[3px]" style="background-color:{d.color}"></span>
                  <span class="text-muted">{d.label}</span>
                </div>
              {/each}
            </div>
          </div>
        </details>
      {/if}
    </aside>
  </div>

  <!-- Aufgaben und Ziele: nur noch der Verweis.
       ★★ Hier standen bis 2026-09-13 zwei vollbreite Karten mit je einer Liste
       und einem Anlege-Formular (Prioritaet, Datum, Loeschen je Zeile). Sie
       waren der groesste Einzelblock der Seite und hatten mit dem Kalender
       nichts zu tun: es sind dieselben Daten, die jetzt die Aufgaben-App
       fuehrt, dort mit Filtern, Projektbezug, Notiz-Verknuepfung und
       Tagesplanung. Zwei Oberflaechen auf denselben Bestand hiesse, jede
       Aenderung zweimal zu bauen und irgendwann eine davon zu vergessen. -->
  <a
    href="{aufgabenBasis}/"
    class="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-border bg-surface-2/40 px-4 py-3 text-sm transition-colors duration-fast ease-saganta hover:border-accent-500/50"
  >
    <span class="flex items-center gap-2 font-medium">
      <span class="text-muted"><Icon name="list-todo" size={16} /></span> Aufgaben
    </span>
    <span class="text-muted">
      {#if heuteFaellig > 0}
        {heuteFaellig} heute fällig
      {:else}
        heute nichts fällig
      {/if}
      {#if offeneZiele > 0}
        · {offeneZiele} {offeneZiele === 1 ? 'Tagesziel' : 'Tagesziele'}
      {/if}
    </span>
    <span class="flex-1"></span>
    <span class="flex items-center gap-1 text-xs text-muted">
      Öffnen <Icon name="arrow-right" size={13} />
    </span>
  </a>

  <EventModal
    open={modalOpen}
    {editing}
    {editableCalendars}
    defaultDate={data.today}
    {prefillDate}
    {prefillStart}
    {prefillEnd}
    {formError}
    onClose={closeModal}
  />
</section>
