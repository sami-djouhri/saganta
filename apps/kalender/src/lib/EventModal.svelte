<script lang="ts">
  import { untrack } from 'svelte';
  import { enhance } from '$app/forms';
  import { Icon, NotizenBlock, eingerueckt, projektUrl, type BaumZeile } from '@saganta/ui';
  import { page } from '$app/stores';
  import type { NotizKurz } from '@saganta/notizen-anschluss';
  import type { KalenderEvent, Konflikt, KonfliktVorschlag, KonfliktWeg } from '$lib/kalender-bff';
  import { startOf, endOf, fmtTime } from '$lib/cal';
  import { DAUER_KNOEPFE, ERINNERUNGEN, dauerMinuten, dauerText, endeNachDauer, endeWandertMit } from '$lib/terminzeit';

  interface Props {
    open: boolean;
    editing: KalenderEvent | null;
    editableCalendars: { id: string; name?: string; title?: string }[];
    defaultDate: string; // YYYY-MM-DD (heute)
    prefillDate?: string;
    prefillStart?: string; // HH:MM
    prefillEnd?: string;
    formError?: string | null;
    /** Notizen, die an diesem Termin hängen. */
    notizen?: NotizKurz[];
    /** Basis-Adresse der Notizen-App im aktuellen Raum. */
    notizenBasis?: string;
    /** Die Notizen-App antwortet gerade nicht. */
    notizenStumm?: boolean;
    /** Fehler des letzten Notiz-Versuchs. */
    notizFehler?: string | null;
    /** Überschneidungen, an denen dieser Termin beteiligt ist (seit 2026-11-14). */
    konflikte?: Konflikt[];
    /** Wege für ein Paar beim Dienst erfragen. */
    onVorschlag?: (paar: Konflikt) => Promise<KonfliktVorschlag | null>;
    /** Einen Weg ausführen; schließt bei Erfolg den Dialog. */
    onWeg?: (weg: KonfliktWeg) => Promise<void>;
    /** Projekte eingerueckt nach der Gliederung (leer, wenn das ProjectDeck schweigt). */
    projektZeilen?: BaumZeile[];
    /** Namen je Slug, auch archivierte. */
    projektNamen?: Record<string, string>;
    /** „Duplizieren" an der Termin-Karte: neuer Termin mit den Feldern dieser Vorlage, ohne Wiederholung. */
    vorlage?: KalenderEvent | null;
    /** Nach dem Löschen eines Einzeltermins (für „Rückgängig"). */
    onGeloescht?: (ev: KalenderEvent) => void;
    onClose: () => void;
  }
  let {
    open,
    editing,
    editableCalendars,
    defaultDate,
    prefillDate = '',
    prefillStart = '',
    prefillEnd = '',
    formError = null,
    notizen = [],
    notizenBasis = '',
    notizenStumm = false,
    notizFehler = null,
    konflikte = [],
    onVorschlag,
    onWeg,
    projektZeilen = [],
    projektNamen = {},
    vorlage = null,
    onGeloescht,
    onClose,
  }: Props = $props();

  // Vorbelegung: der bearbeitete Termin, sonst die Vorlage zum Kopieren.
  const quelle = $derived(editing ?? vorlage);
  const projektJetzt = $derived(quelle?.projekt ?? '');
  // Ein Bezug, den die Auswahl nicht kennt (archiviert, Liste ausgefallen),
  // bleibt als eigene Zeile stehen, sonst zeigte das Feld „kein Projekt".
  const projektFremd = $derived(!!projektJetzt && !projektZeilen.some((z) => z.slug === projektJetzt));

  // Serien-Vorkommen (`basis::datum`): Titel und Reihe werden in der Agenda
  // gepflegt, hier gilt die Zeit nur fuer diesen Tag (EXDATE + Einzeltermin),
  // und das Verwerfen bietet die drei Stufen der Agenda an.
  const istVorkommen = $derived(!!editing && String(editing.id).includes('::'));
  const vorkommenTag = $derived(editing ? String(editing.id).split('::')[1]?.slice(0, 10) ?? '' : '');
  const formAction = $derived(istVorkommen ? '?/eventVerschieben' : editing ? '?/eventUpdate' : '?/eventCreate');

  // Überschneidungen: Wege je Paar erst auf Wunsch holen (ein Aufruf an den Dienst).
  let wegeNach = $state<Record<number, KonfliktVorschlag | null | 'laedt'>>({});
  let wegLaeuft = $state(false);
  function partner(k: Konflikt) {
    return editing && k.a.id === editing.id ? k.b : k.a;
  }
  async function wegeHolen(i: number, k: Konflikt) {
    if (!onVorschlag) return;
    wegeNach[i] = 'laedt';
    wegeNach[i] = await onVorschlag(k);
  }
  async function wegWaehlen(weg: KonfliktWeg) {
    if (!onWeg || wegLaeuft) return;
    if (weg.aktion === 'loeschen' && !confirm(`${weg.text}?`)) return;
    wegLaeuft = true;
    try {
      await onWeg(weg);
    } finally {
      wegLaeuft = false;
    }
  }
  $effect(() => {
    // Beim Wechsel des Termins die geholten Wege vergessen.
    void editing;
    wegeNach = {};
  });

  // naive ISO "2026-07-18T15:00:00" → datetime-local "2026-07-18T15:00"
  const toLocalInput = (iso: string): string => (iso ?? '').slice(0, 16);
  const dateBase = $derived(prefillDate || defaultDate);
  const startValue = $derived(
    quelle ? toLocalInput(startOf(quelle)) : `${dateBase}T${prefillStart || '09:00'}`,
  );
  const endValue = $derived(
    quelle ? toLocalInput(endOf(quelle)) : `${dateBase}T${prefillEnd || '10:00'}`,
  );

  // ── Felder als Zustand (seit 2026-11-21) ──
  // Vorher ungebunden mit `value=`; fuer „Ende wandert mit", die Dauer-Knoepfe
  // und die Titel-Vorschlaege muss der Dialog die Werte selbst halten. Neu
  // belegt wird bei jedem Oeffnen und jedem Wechsel des Termins.
  let titel = $state('');
  let ort = $state('');
  let kalender = $state('');
  let projekt = $state('');
  let erinnerung = $state('');
  let startW = $state('');
  let endeW = $state('');
  // Schluessel statt der Werte selbst: nach einem abgelehnten Speichern laedt die
  // Seite neu, und eine Abhaengigkeit an `editableCalendars` oder `quelle` haette
  // dabei alles Getippte ueberschrieben.
  const belegKey = $derived(
    open ? `${editing?.id ?? ''}|${vorlage?.id ?? ''}|${prefillDate}|${prefillStart}|${prefillEnd}` : '',
  );
  $effect(() => {
    if (!belegKey) return;
    untrack(belegen);
  });
  function belegen(): void {
    titel = quelle?.title ?? '';
    ort = quelle?.location ?? '';
    kalender = quelle?.calendar_id ?? editableCalendars[0]?.id ?? '';
    projekt = projektJetzt;
    erinnerung = quelle?.reminder_minutes == null ? '' : String(quelle.reminder_minutes);
    startW = startValue;
    endeW = endValue;
    titelTreffer = [];
  }
  const dauerJetzt = $derived(dauerMinuten(startW, endeW));
  // Eine Erinnerung, die keine der Vorgaben ist (z. B. 15 aus der App), bleibt waehlbar.
  const erinnerungFremd = $derived(
    erinnerung !== '' && !ERINNERUNGEN.some((e) => String(e.minuten ?? '') === erinnerung),
  );

  function startGeaendert(neu: string): void {
    if (neu && startW) endeW = endeWandertMit(startW, neu, endeW);
    startW = neu;
  }
  function dauerSetzen(minuten: number): void {
    const ende = endeNachDauer(startW, minuten);
    if (ende) endeW = ende;
  }

  // ── Vorschlaege aus frueheren Terminen (nur beim Anlegen) ──
  interface TitelTreffer {
    title: string;
    dauer_min: number | null;
    all_day: boolean;
    location: string | null;
    calendar_id: string;
    projekt: string | null;
    reminder_minutes: number | null;
  }
  let titelTreffer = $state<TitelTreffer[]>([]);
  let titelFokus = $state(false);
  let orteListe = $state<string[]>([]);
  let suchUhr: ReturnType<typeof setTimeout> | undefined;
  let ortUhr: ReturnType<typeof setTimeout> | undefined;
  async function vorschlaegeHolen<T>(art: 'titel' | 'ort', q: string): Promise<T[]> {
    try {
      const a = await fetch(`/vorschlaege?art=${art}&q=${encodeURIComponent(q)}`);
      if (!a.ok) return [];
      const d = await a.json();
      return (art === 'ort' ? d.orte : d.titel) ?? [];
    } catch {
      return [];
    }
  }
  function titelGetippt(q: string): void {
    titel = q;
    clearTimeout(suchUhr);
    if (editing || q.trim().length < 2) {
      titelTreffer = [];
      return;
    }
    suchUhr = setTimeout(async () => {
      const t = await vorschlaegeHolen<TitelTreffer>('titel', q.trim());
      // Nur zeigen, was nicht schon genau so dasteht.
      titelTreffer = t.filter((x) => x.title.toLowerCase() !== titel.trim().toLowerCase() || t.length > 1).slice(0, 6);
    }, 200);
  }
  function titelUebernehmen(t: TitelTreffer): void {
    titel = t.title;
    if (t.location) ort = t.location;
    if (editableCalendars.some((c) => c.id === t.calendar_id)) kalender = t.calendar_id;
    if (t.projekt) projekt = t.projekt;
    if (t.reminder_minutes != null) erinnerung = String(t.reminder_minutes);
    if (t.dauer_min && !t.all_day) dauerSetzen(t.dauer_min);
    titelTreffer = [];
  }
  function ortGetippt(q: string): void {
    ort = q;
    clearTimeout(ortUhr);
    ortUhr = setTimeout(async () => (orteListe = await vorschlaegeHolen<string>('ort', q.trim())), 200);
  }
  $effect(() => {
    // Beim Oeffnen die haeufigsten Orte holen, dann bietet das Feld sie sofort an.
    if (open && !istVorkommen) void vorschlaegeHolen<string>('ort', '').then((o) => (orteListe = o));
  });

  function onKey(e: KeyboardEvent): void {
    if (e.key === 'Escape') onClose();
  }
</script>

<svelte:window onkeydown={open ? onKey : undefined} />

{#if open}
  <!-- Backdrop -->
  <div
    class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 pt-[8vh] backdrop-blur-sm"
    role="presentation"
    onclick={(e) => {
      if (e.target === e.currentTarget) onClose();
    }}
  >
    <!-- ⚠️ Der Notizen-Block steht NEBEN diesem Formular, nicht darin: er bringt
         sein eigenes `<form>` mit, und ein Formular im Formular ist in HTML
         nicht erlaubt. Der Browser bricht das verschachtelte stillschweigend
         auf, womit die Felder am falschen Formular landen. Deshalb umschliesst
         beides ein gemeinsames `div`. -->
    <div class="w-full max-w-lg space-y-4">
      <form
        method="POST"
        action={formAction}
        use:enhance={() =>
          async ({ result, update }) => {
            await update({ reset: false });
            if (result.type === 'success') onClose();
          }}
        class="space-y-4 rounded-2xl border border-border bg-surface-2 p-6 shadow-2xl"
      >
      <div class="flex items-center justify-between">
        <h3 class="font-display text-2xl">{istVorkommen ? 'Dieses Vorkommen' : editing ? 'Termin bearbeiten' : vorlage ? 'Termin kopieren' : 'Neuer Termin'}</h3>
        <button
          type="button"
          onclick={onClose}
          class="grid size-8 place-items-center rounded-lg text-muted hover:bg-white/5 hover:text-text"
          aria-label="Schließen"><Icon name="x" size={18} /></button
        >
      </div>

      {#if editing}<input type="hidden" name="id" value={editing.id} />{/if}

      <label class="block space-y-1">
        <span class="text-xs uppercase tracking-wider text-muted">Titel</span>
        <input
          name="title"
          placeholder="Worum geht's?"
          required
          autocomplete="off"
          disabled={istVorkommen}
          value={titel}
          oninput={(e) => titelGetippt(e.currentTarget.value)}
          onfocus={() => (titelFokus = true)}
          onblur={() => setTimeout(() => (titelFokus = false), 150)}
          class="w-full rounded-lg border border-border-stark bg-surface px-3 py-2 text-sm outline-none focus:border-accent-400"
        />
      </label>
      {#if titelFokus && titelTreffer.length > 0}
        <!-- Fruehere Termine: ein Tipp uebernimmt Dauer, Ort, Kalender, Projekt und Erinnerung. -->
        <div class="-mt-2 overflow-hidden rounded-lg border border-border-stark bg-surface" role="listbox" aria-label="Frühere Termine">
          {#each titelTreffer as t (t.title)}
            <button
              type="button"
              role="option"
              aria-selected="false"
              onmousedown={(e) => e.preventDefault()}
              onclick={() => titelUebernehmen(t)}
              class="flex w-full items-baseline gap-2 px-3 py-2 text-left text-sm hover:bg-white/5"
            >
              <span class="truncate text-text">{t.title}</span>
              <span class="shrink-0 truncate text-xs text-muted"
                >{[t.all_day ? 'ganztägig' : t.dauer_min ? dauerText(t.dauer_min) : '', t.location ?? ''].filter(Boolean).join(' · ')}</span
              >
            </button>
          {/each}
        </div>
      {/if}

      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Kalender</span>
          <select
            name="calendar_id"
            disabled={istVorkommen}
            bind:value={kalender}
            class="w-full rounded-lg border border-border-stark bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
          >
            {#each editableCalendars as c (c.id)}
              <option value={c.id}>{c.name ?? c.title ?? c.id}</option>
            {/each}
          </select>
        </label>
        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Ort (optional)</span>
          <input
            name="location"
            list="termin-orte"
            autocomplete="off"
            disabled={istVorkommen}
            value={ort}
            oninput={(e) => ortGetippt(e.currentTarget.value)}
            class="w-full rounded-lg border border-border-stark bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
          />
          <datalist id="termin-orte">
            {#each orteListe as o (o)}<option value={o}></option>{/each}
          </datalist>
        </label>
      </div>

      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Start</span>
          <input
            type="datetime-local"
            name="start"
            required
            value={startW}
            onchange={(e) => startGeaendert(e.currentTarget.value)}
            class="w-full rounded-lg border border-border-stark bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
          />
        </label>
        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Ende</span>
          <input
            type="datetime-local"
            name="end"
            value={endeW}
            oninput={(e) => (endeW = e.currentTarget.value)}
            class="w-full rounded-lg border border-border-stark bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
          />
        </label>
      </div>

      <div class="flex flex-wrap items-center gap-1.5">
        <span class="mr-1 text-xs uppercase tracking-wider text-muted">Dauer</span>
        {#each DAUER_KNOEPFE as m (m)}
          <button
            type="button"
            onclick={() => dauerSetzen(m)}
            aria-pressed={dauerJetzt === m}
            class="min-h-9 rounded-lg border px-3 text-xs sm:min-h-8 {dauerJetzt === m
              ? 'border-accent-500 text-akzent'
              : 'border-border-stark text-muted hover:text-text'}">{dauerText(m)}</button
          >
        {/each}
        {#if dauerJetzt !== null && dauerJetzt > 0 && !(DAUER_KNOEPFE as readonly number[]).includes(dauerJetzt)}
          <span class="text-xs text-muted">jetzt {dauerText(dauerJetzt)}</span>
        {/if}
      </div>

      <label class="block space-y-1">
        <span class="text-xs uppercase tracking-wider text-muted">Erinnerung</span>
        <select
          name="reminder_minutes"
          disabled={istVorkommen}
          bind:value={erinnerung}
          class="w-full rounded-lg border border-border-stark bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
        >
          {#each ERINNERUNGEN as e (e.text)}
            <option value={e.minuten === null ? '' : String(e.minuten)}>{e.text}</option>
          {/each}
          {#if erinnerungFremd}<option value={erinnerung}>{erinnerung} min vorher</option>{/if}
        </select>
      </label>

      <label class="flex items-center gap-2 text-sm text-muted">
        <input type="checkbox" name="all_day" disabled={istVorkommen} checked={quelle?.all_day ?? false} />
        Ganztägig (Uhrzeit wird ignoriert)
      </label>

      {#if istVorkommen}
        <p class="rounded-lg border border-border bg-surface px-3 py-2 text-xs text-muted">
          Wiederkehrender Termin. Die Zeit oben gilt nur für dieses Vorkommen, die Reihe bleibt
          unverändert. Titel und Wiederholung änderst du in der Agenda.
        </p>
      {/if}

      <div class="space-y-1">
        <div class="flex items-center justify-between gap-2">
          <label for="termin-projekt" class="text-xs uppercase tracking-wider text-muted">Projekt</label>
          {#if projektJetzt}
            <a
              href={projektUrl(projektJetzt, $page.url.host)}
              class="inline-flex items-center gap-1 text-xs text-muted hover:text-akzent"
              >Im ProjectDeck <Icon name="arrow-right" size={12} /></a
            >
          {/if}
        </div>
        {#if editing}<input type="hidden" name="projekt_alt" value={projektJetzt} />{/if}
        <select
          id="termin-projekt"
          name="projekt"
          disabled={istVorkommen}
          bind:value={projekt}
          class="w-full rounded-lg border border-border-stark bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
        >
          <option value="">kein Projekt</option>
          {#if projektFremd}
            <option value={projektJetzt}>{projektNamen[projektJetzt] ?? projektJetzt}</option>
          {:else if projekt && !projektZeilen.some((z) => z.slug === projekt)}
            <!-- aus einem Titel-Vorschlag, das Projekt steht nicht (mehr) in der Liste -->
            <option value={projekt}>{projektNamen[projekt] ?? projekt}</option>
          {/if}
          {#each projektZeilen as z (z.schluessel)}
            <option value={z.slug}>{eingerueckt(z)}</option>
          {/each}
        </select>
        {#if projektZeilen.length === 0}
          <span class="block text-xs text-muted">Die Projektliste ist gerade nicht erreichbar.</span>
        {/if}
      </div>

      <label class="block space-y-1">
        <span class="text-xs uppercase tracking-wider text-muted">Aktivität (für Feedback & Planung)</span>
        <select
          name="activity_type"
          disabled={istVorkommen}
          class="w-full rounded-lg border border-border-stark bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
        >
          <option value="" selected={!quelle?.activity_type}>kein (normaler Termin)</option>
          <option value="lernen" selected={quelle?.activity_type === 'lernen'}>Lernen</option>
          <option value="sport" selected={quelle?.activity_type === 'sport'}>Sport</option>
          <option value="lesen" selected={quelle?.activity_type === 'lesen'}>Lesen</option>
          <option value="hobby" selected={quelle?.activity_type === 'hobby'}>Hobby</option>
          <option value="sonstige" selected={quelle?.activity_type === 'sonstige'}>Sonstige</option>
        </select>
        <span class="block text-xs text-muted">Markierte Aktivitäten kannst du danach kurz bewerten.</span>
      </label>

      {#if formError}
        <p class="rounded-lg border border-warm-500/40 bg-warm-500/10 px-3 py-2 text-sm text-kupfer">
          {formError}
        </p>
      {/if}

      <div class="flex justify-end gap-2 pt-1">
        <button
          type="button"
          onclick={onClose}
          class="min-h-11 rounded-lg border border-border-stark px-4 text-sm text-muted hover:text-text sm:min-h-9"
          >Abbrechen</button
        >
        <button
          type="submit"
          class="min-h-11 rounded-lg bg-accent-500 px-5 text-sm font-medium text-accent-ink hover:bg-accent-400 sm:min-h-9"
          >{istVorkommen ? 'Nur dieses Vorkommen verschieben' : editing ? 'Speichern' : 'Anlegen'}</button
        >
        </div>
      </form>

      {#if editing && konflikte.length > 0}
        <!-- Überschneidungen: der Dienst rechnet die Wege (später schieben,
             vorziehen, kürzen, aussetzen, löschen), hier stehen sie als Knöpfe.
             Nichts passiert ohne Klick. -->
        <div class="space-y-3 rounded-2xl border border-warm-500/40 bg-surface-2 p-6 shadow-2xl">
          <h4 class="flex items-center gap-2 text-sm font-medium text-kupfer">
            <Icon name="alert-triangle" size={16} />
            {konflikte.length === 1 ? 'Überschneidung' : `${konflikte.length} Überschneidungen`}
          </h4>
          {#each konflikte as k, i (k.a.id + k.b.id)}
            {@const p = partner(k)}
            {@const v = wegeNach[i]}
            <div class="space-y-2">
              <p class="text-sm text-text">
                Mit <span class="font-medium">„{p.titel}“</span>
                <span class="text-muted">{fmtTime(p.start)} bis {fmtTime(p.ende)}</span>
              </p>
              {#if v === undefined}
                <button
                  type="button"
                  onclick={() => wegeHolen(i, k)}
                  class="rounded-lg border border-border-stark px-3 py-1.5 text-xs text-text hover:bg-white/5"
                  >Wege zeigen</button
                >
              {:else if v === 'laedt'}
                <p class="text-xs text-muted">Wege werden gerechnet …</p>
              {:else if v === null}
                <p class="text-xs text-kupfer">Der Kalender hat nicht geantwortet.</p>
              {:else}
                {#if v.hinweis}<p class="text-xs text-muted">{v.hinweis}</p>{/if}
                <div class="flex flex-wrap gap-1.5">
                  {#each v.wege ?? [] as weg (weg.aktion + weg.ziel.id + (weg.start ?? '') + (weg.ende ?? ''))}
                    <button
                      type="button"
                      disabled={wegLaeuft}
                      onclick={() => wegWaehlen(weg)}
                      class="rounded-lg border px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50 {weg.aktion ===
                        'loeschen' || weg.aktion === 'aussetzen'
                        ? 'border-warm-500/40 text-kupfer'
                        : 'border-border text-text'}"
                      >{weg.text}</button
                    >
                  {/each}
                  {#if (v.wege ?? []).length === 0}
                    <p class="text-xs text-muted">Kein Weg berechnet.</p>
                  {/if}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}

      {#if editing}
        <!-- Verwerfen. Bis 2026-11-14 hatte dieser Dialog keinen Löschen-Knopf,
             ein Termin liess sich nur in der Agenda entfernen. Bei einer Reihe
             dieselben drei Stufen wie dort, nie stillschweigend die ganze Reihe. -->
        <div class="rounded-2xl border border-border bg-surface-2 p-6 shadow-2xl">
          <h4 class="mb-3 text-xs uppercase tracking-wider text-muted">Verwerfen</h4>
          {#if istVorkommen}
            <div class="flex flex-wrap gap-2">
              <form method="POST" action="?/eventDelete" use:enhance={() => async ({ result, update }) => { await update(); if (result.type === 'success') onClose(); }}>
                <input type="hidden" name="id" value={editing.id} />
                <input type="hidden" name="modus" value="vorkommen" />
                <input type="hidden" name="tag" value={vorkommenTag} />
                <button type="submit" class="rounded-lg border border-warm-500/40 px-3 py-1.5 text-xs text-kupfer hover:bg-white/5"
                  >Nur dieses Vorkommen</button
                >
              </form>
              <form method="POST" action="?/eventDelete" use:enhance={() => async ({ result, update }) => { await update(); if (result.type === 'success') onClose(); }}>
                <input type="hidden" name="id" value={editing.id} />
                <input type="hidden" name="modus" value="ab_hier" />
                <input type="hidden" name="tag" value={vorkommenTag} />
                <button type="submit" class="rounded-lg border border-border px-3 py-1.5 text-xs text-text hover:bg-white/5"
                  >Dieses und alle folgenden</button
                >
              </form>
              <form
                method="POST"
                action="?/eventDelete"
                onsubmit={(e) => { if (!confirm(`Ganze Reihe „${editing?.title}“ löschen?`)) e.preventDefault(); }}
                use:enhance={() => async ({ result, update }) => { await update(); if (result.type === 'success') onClose(); }}
              >
                <input type="hidden" name="id" value={editing.id} />
                <input type="hidden" name="modus" value="serie" />
                <button type="submit" class="rounded-lg border border-border px-3 py-1.5 text-xs text-muted hover:text-kupfer"
                  >Ganze Reihe löschen</button
                >
              </form>
            </div>
          {:else}
            <form
              method="POST"
              action="?/eventDelete"
              onsubmit={(e) => { if (!confirm(`Termin „${editing?.title}“ löschen?`)) e.preventDefault(); }}
              use:enhance={() => {
                const geloescht = editing;
                return async ({ result, update }) => {
                  await update();
                  if (result.type === 'success') {
                    onClose();
                    if (geloescht) onGeloescht?.(geloescht);
                  }
                };
              }}
            >
              <input type="hidden" name="id" value={editing.id} />
              <input type="hidden" name="modus" value="serie" />
              <button type="submit" class="rounded-lg border border-warm-500/40 px-3 py-1.5 text-xs text-kupfer hover:bg-white/5"
                >Termin löschen</button
              >
            </form>
          {/if}
        </div>
      {/if}

      {#if editing}
        <!-- Nur beim Bearbeiten. Ein noch nicht angelegter Termin hat keine
             Kennung, eine Notiz könnte also an nichts hängen. Den Knopf
             trotzdem zu zeigen hiesse, etwas anzubieten, das beim Klick
             scheitern muss. -->
        <div class="rounded-2xl border border-border bg-surface-2 p-6 shadow-2xl">
          <NotizenBlock
            typ="termin"
            ref={editing.id}
            label={editing.title}
            {notizen}
            {notizenBasis}
            stumm={notizenStumm}
            fehler={notizFehler}
            {enhance}
          />
        </div>
      {/if}
    </div>
  </div>
{/if}
