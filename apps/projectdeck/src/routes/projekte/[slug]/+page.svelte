<script lang="ts">
  import { enhance } from '$app/forms';
  import { page } from '$app/stores';
  import { Button, Icon, NotizenBlock, appUrlById, aufgabeUrl, kalenderCaptureUrl } from '@saganta/ui';
  import {
    DEADLINE_TYPE,
    PROJECT_STATUS,
    PROJECT_TYPES,
    READINESS_LABELS,
    SCHEDULING_MODE,
    SHUTDOWN_LABELS,
    VISIBILITY,
    AUSGEBLENDET,
    PRIO_RANG,
    fmtMinutes,
  } from '$lib/meta';
  import type { AkteAufgabe, Aufgabe, Zeitpunkt } from '$lib/types';
  import { eingerueckt, verboteneEltern } from '$lib/gliederung';
  import type { PageData, ActionData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();

  // Dedup gegen Svelte-5 `each_key_duplicate`: dynamische Backend-Daten können
  // denselben id-Key doppelt liefern (z. B. Message-IDs über mehrere IMAP-Konten)
  // → Client-Hydration-Crash legt die Seite lahm. Eindeutige Keys erzwingen. (2026-06-28)
  function uniqueBy<T>(arr: readonly T[], key: (x: T) => unknown): T[] {
    const seen = new Set<unknown>();
    return arr.filter((x) => {
      const k = key(x);
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }
  let p = $derived(data.project);
  const host = $derived($page.url.host);

  // Zeit fuer das Projekt einplanen heisst: einen Termin im Saganta Kalender
  // anlegen. Die Schnelleingabe dort schlaegt bei Dauer ohne Uhrzeit bis zu
  // drei freie Zeiten vor; die Dauer aendert man vor dem Uebernehmen.
  const einplanenUrl = $derived(kalenderCaptureUrl(`1h ${p.name}`, undefined, host));
  // Eingeplant ist, was einen Tag oder eine Uhrzeit traegt.
  const eingeplant = $derived(
    data.aufgaben
      .filter((a) => !a.erledigt && (a.tag || a.start))
      .sort((a, b) => (a.start ?? a.tag ?? '').localeCompare(b.start ?? b.tag ?? '')),
  );

  const notizenBasis = $derived(appUrlById('notizen', $page.url.host));
  // Getrennt vom uebrigen Formularfehler: sonst erscheint „Bitte einen Titel
  // eingeben" aus dem Notiz-Block oben am Projekt-Formular, wo niemand etwas
  // eingegeben hat.
  const notizFehler = $derived(
    form && typeof form === 'object' && 'notizFehler' in form ? String(form.notizFehler) : null,
  );

  // Heute als ISO-Tag, um Meilenstein-Zieldaten als Text zu vergleichen. Beide
  // Seiten sind `YYYY-MM-DD`, der Vergleich ist damit lexikografisch korrekt
  // und braucht kein Date-Parsing mit Zeitzone.
  const heute = new Date().toISOString().slice(0, 10);

  // Kennung und Anzeigetext sind GETRENNT, und das ist der Grund, diese
  // Zeilen zu lesen. Bis zum 2026-10-24 war der englische Anzeigetext zugleich
  // der Zustandswert: 'Public Readiness' stand im Array UND in
  // `tab === 'Public Readiness'`. Damit waren die zehn Reiter dieser Ansicht
  // englisch, mitten in einer sonst durchgehend deutschen Oberflaeche, und das
  // ist die am haeufigsten geoeffnete Seite der App.
  //
  // Getrennt, weil es sonst beim naechsten Mal wieder passiert: eine
  // Eindeutschung musste vorher eine Kennung aendern und elf Vergleiche
  // mittreffen. Ein uebersehener Vergleich laesst den Reiter still LEER, denn
  // die `{:else if}`-Kette faellt dann einfach durch. Kein Fehler, kein
  // Inhalt, und anklickbar bleibt er trotzdem.
  //
  // Seit 08.11. oeffnet ein Projekt auf den Aufgaben (Entscheid), und
  // Reiter in `AUSGEBLENDET` (meta.ts) fehlen; ihr Inhalt bleibt im Code.
  const TABS = [
    { id: 'tasks', label: 'Aufgaben' },
    { id: 'zeitleiste', label: 'Zeitleiste' },
    { id: 'kontakte', label: 'Kontakte' },
    { id: 'budget', label: 'Budget' },
    { id: 'notizen', label: 'Notizen' },
    { id: 'overview', label: 'Einstellungen' },
    { id: 'milestones', label: 'Meilensteine' },
    { id: 'deadlines', label: 'Fristen' },
    { id: 'calendar', label: 'Kalender' },
    { id: 'assets', label: 'Verweise' },
    { id: 'reviews', label: 'Durchsichten' },
    { id: 'readiness', label: 'Veröffentlichung' },
    { id: 'client', label: 'Kunde' },
    { id: 'shutdown', label: 'Abschalten' },
  ].filter((t) => !AUSGEBLENDET.has(t.id));
  // Ein Anker waehlt den Reiter (`/projekte/x#zeitleiste`), sonst die Aufgaben.
  const anker = $page.url.hash.slice(1);
  let tab = $state(TABS.some((t) => t.id === anker) ? anker : 'tasks');

  // Offene nach Prioritaet, Wartende ans Ende; erledigte eingeklappt darunter.
  const alleAufgaben = $derived(uniqueBy(data.aufgaben, (x) => x.id));
  const offene = $derived(
    alleAufgaben
      .filter((a) => !a.erledigt)
      .sort(
        (x, y) =>
          Number(x.wartet) - Number(y.wartet) ||
          (PRIO_RANG[x.prioritaet] ?? 1) - (PRIO_RANG[y.prioritaet] ?? 1),
      ),
  );
  const erledigte = $derived(alleAufgaben.filter((a) => a.erledigt));
  let showAdvanced = $state(false);

  // ── Projektakte (15.11.) ────────────────────────────────────────────────
  const akte = $derived(data.akte);
  // Namen aus dem Teilbaum, sonst aus allen Projekten (angeheftete liegen oft daneben).
  const projektName = (slug: string) =>
    akte?.projekte[slug]?.name ?? data.alleProjekte?.find((q) => q.slug === slug)?.name ?? slug;
  const kurzDatum = (d: string) => `${d.slice(8, 10)}.${d.slice(5, 7)}.`;
  const mitUnterprojekten = $derived((akte?.kinder.length ?? 0) > 0);
  // Offene Aufgaben: aus der Akte (ganzer Teilbaum), sonst aus dem Einzelaufruf.
  const offeneAkte = $derived(
    akte && !akte.aufgaben_fehlen
      ? [...akte.aufgaben].sort(
          (x, y) =>
            Number(x.wartet) - Number(y.wartet) ||
            (PRIO_RANG[x.prioritaet] ?? 1) - (PRIO_RANG[y.prioritaet] ?? 1),
        )
      : null,
  );
  // Gruppen: zuerst das Projekt selbst („allgemein"), dann je Unterprojekt.
  const gruppen = $derived.by(() => {
    const liste = offeneAkte ?? (offene as AkteAufgabe[]);
    const je = new Map<string, AkteAufgabe[]>();
    for (const a of liste) {
      const s = a.projekt ?? p.slug;
      je.set(s, [...(je.get(s) ?? []), a as AkteAufgabe]);
    }
    return [...je.entries()].sort(([a], [b]) =>
      a === p.slug ? -1 : b === p.slug ? 1 : projektName(a).localeCompare(projektName(b), 'de'),
    );
  });
  const anzahlOffen = $derived(gruppen.reduce((s, [, l]) => s + l.length, 0));

  const ART_LABEL: Record<Zeitpunkt['art'], string> = {
    termin: 'Termin',
    frist: 'Frist',
    meilenstein: 'Meilenstein',
    projektfrist: 'Projekt',
    durchsicht: 'Durchsicht',
    geplant: 'Eingeplant',
  };
  const zeitleisteNachMonat = $derived.by(() => {
    const monate = new Map<string, Zeitpunkt[]>();
    for (const z of akte?.zeitleiste ?? []) {
      const m = z.datum.slice(0, 7);
      monate.set(m, [...(monate.get(m) ?? []), z]);
    }
    return [...monate.entries()];
  });
  const monatsName = (ym: string) =>
    new Date(`${ym}-01T12:00:00`).toLocaleDateString('de-DE', { month: 'long', year: 'numeric' });
  const tagKurz = (d: string) =>
    new Date(`${d}T12:00:00`).toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit' });
  const euro = (cent: number | null | undefined) =>
    cent == null ? '–' : (cent / 100).toLocaleString('de-DE', { style: 'currency', currency: 'EUR' });

  // Gliederung bearbeiten: als Oberprojekt kommt nicht in Frage, was schon darunter haengt.
  let zeigeGliederung = $state(false);
  // Jedes Projekt einmal: zwei Haken fuer dasselbe Projekt widerspraechen sich.
  const elternAuswahl = $derived(uniqueBy(eingerueckt(data.alleProjekte ?? []), (x) => x.projekt.id));
  const zielAuswahl = $derived(
    akte ? Object.entries(akte.projekte).map(([slug, v]) => ({ slug, ...v })) : [],
  );
  const verboten = $derived(verboteneEltern(data.alleProjekte ?? [], p.id));
  const istEltern = (id: number) => (p.eltern_ids ?? []).includes(id);
  let aiResult = $derived(form && 'ai' in form ? form.ai : undefined);
</script>

<div class="flex flex-wrap items-start justify-between gap-3">
  <div>
    <nav class="flex flex-wrap items-center gap-1 text-sm text-muted" aria-label="Pfad">
      <a href="/projekte" class="hover:text-text">Projekte</a>
      {#each akte?.pfad ?? [] as stufe (stufe.id)}
        <span aria-hidden="true">/</span>
        <a href={`/projekte/${stufe.slug}`} class="hover:text-text">{stufe.name}</a>
      {/each}
    </nav>
    <h1 class="font-display text-2xl">{p.name}</h1>
    {#if (akte?.eltern.length ?? 0) > 1}
      <p class="mt-0.5 text-xs text-muted">
        steht auch unter
        {#each akte!.eltern.slice(1) as e, i (e.id)}{i ? ', ' : ' '}<a href={`/projekte/${e.slug}`} class="text-akzent hover:text-akzent-stark">{e.name}</a>{/each}
      </p>
    {/if}
    <div class="mt-1 flex flex-wrap gap-1 text-xs text-muted">
      <span class="rounded bg-surface-2 px-1.5 py-0.5">{PROJECT_TYPES[p.type] ?? p.type}</span>
      <span class="rounded bg-surface-2 px-1.5 py-0.5">{PROJECT_STATUS[p.status] ?? p.status}</span>
      {#if p.visibility !== 'private' || p.type !== 'private'}
        <span class="rounded bg-surface-2 px-1.5 py-0.5">{VISIBILITY[p.visibility] ?? p.visibility}</span>
      {/if}
      <span class="rounded bg-surface-2 px-1.5 py-0.5">Prio {p.priority}</span>
      <span class="rounded bg-surface-2 px-1.5 py-0.5 font-mono">{p.slug}</span>
    </div>
    {#if p.next_action}
      <p class="mt-2 max-w-2xl text-sm text-muted">→ {p.next_action}</p>
    {/if}
  </div>
  <div class="flex flex-wrap items-center gap-2">
  <button
    type="button"
    onclick={() => (zeigeGliederung = !zeigeGliederung)}
    class="inline-flex items-center gap-1.5 rounded-md border border-border-stark px-3 py-1.5 text-sm text-muted transition-colors duration-fast ease-saganta hover:text-text"
    aria-expanded={zeigeGliederung}
  >
    Gliederung
  </button>
  <a
    href={einplanenUrl}
    class="inline-flex items-center gap-1.5 rounded-md bg-accent-500 px-3 py-1.5 text-sm text-accent-ink transition-colors duration-fast ease-saganta hover:bg-accent-400"
  >
    <Icon name="clock" size={15} /> Zeit einplanen
  </a>
  </div>
</div>

{#if zeigeGliederung}
  <section class="mt-4 rounded-lg border border-border bg-surface-2/40 p-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="text-sm font-medium">Oberprojekte</h2>
        <p class="text-xs text-muted">
          Ein Projekt kann unter mehreren stehen und bleibt dabei dasselbe. Nichts gewählt heißt: steht oben.
        </p>
      </div>
      <a
        href={`/projekte?oben=${p.id}`}
        class="inline-flex items-center gap-1 rounded-md bg-accent-500 px-3 py-1.5 text-sm text-accent-ink hover:bg-accent-400"
        ><Icon name="plus" size={14} /> Unterprojekt anlegen</a
      >
    </div>
    <form method="POST" action="?/setEltern" use:enhance class="mt-3">
      <div class="grid max-h-72 gap-x-4 overflow-y-auto rounded-md border border-border bg-surface p-2 sm:grid-cols-2">
        {#each elternAuswahl as { projekt: q, tiefe }, i (`${q.id}-${i}`)}
          {#if !verboten.has(q.id)}
            <label class="flex items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-surface-2" style:padding-left={`${tiefe * 1.1 + 0.25}rem`}>
              <input type="checkbox" name="eltern_id" value={q.id} checked={istEltern(q.id)} />
              <span class="truncate">{q.name}</span>
            </label>
          {/if}
        {/each}
      </div>
      <div class="mt-3"><Button type="submit" variant="primary" size="sm">Gliederung speichern</Button></div>
    </form>
  </section>
{/if}

{#if form && 'error' in form && form.error}
  <p class="mt-3 rounded border border-fehler/40 bg-fehler/10 px-3 py-2 text-sm text-fehler">
    {form.error}
  </p>
{/if}

<nav class="mt-5 flex flex-wrap gap-1 border-b border-border">
  {#each TABS as t (t.id)}
    <button
      onclick={() => (tab = t.id)}
      class="rounded-t-md px-3 py-2 text-sm {tab === t.id
        ? 'border-b-2 border-accent-500 text-text'
        : 'text-muted hover:text-text'}">{t.label}</button
    >
  {/each}
</nav>

<div class="mt-5">
  {#if tab === 'overview'}
    <form
      method="POST"
      action="?/updateProject"
      use:enhance
      class="grid gap-3 sm:grid-cols-2"
    >
      <label class="flex flex-col gap-1 text-sm sm:col-span-2">
        <span class="text-muted">Name</span>
        <input name="name" value={p.name} class="rounded-md border border-border-stark bg-surface px-3 py-2" />
      </label>
      <label class="flex flex-col gap-1 text-sm sm:col-span-2">
        <span class="text-muted">Beschreibung</span>
        <textarea name="description" rows="2" class="rounded-md border border-border-stark bg-surface px-3 py-2"
          >{p.description ?? ''}</textarea
        >
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Status</span>
        <select name="status" class="rounded-md border border-border-stark bg-surface px-3 py-2">
          {#each Object.entries(PROJECT_STATUS) as [v, l]}<option value={v} selected={p.status === v}>{l}</option>{/each}
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Typ</span>
        <select name="type" class="rounded-md border border-border-stark bg-surface px-3 py-2">
          {#each Object.entries(PROJECT_TYPES) as [v, l]}<option value={v} selected={p.type === v}>{l}</option>{/each}
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Sichtbarkeit</span>
        <select name="visibility" class="rounded-md border border-border-stark bg-surface px-3 py-2">
          {#each Object.entries(VISIBILITY) as [v, l]}<option value={v} selected={p.visibility === v}>{l}</option>{/each}
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Priorität (1=höchste)</span>
        <input name="priority" type="number" min="1" max="5" value={p.priority} class="rounded-md border border-border-stark bg-surface px-3 py-2" />
      </label>
      <label class="flex flex-col gap-1 text-sm sm:col-span-2">
        <span class="text-muted">Nächste Aktion</span>
        <!-- textarea statt input: das Feld fasst 500 Zeichen, und in einer
             Zeile sieht man davon rund sechzig. Wer hier mehr als ein Stichwort
             notiert, konnte seinen eigenen Satz nicht mehr lesen. -->
        <textarea
          name="next_action"
          rows="2"
          class="rounded-md border border-border-stark bg-surface px-3 py-2">{p.next_action ?? ''}</textarea
        >
      </label>

      <button
        type="button"
        onclick={() => (showAdvanced = !showAdvanced)}
        class="sm:col-span-2 text-left text-sm text-akzent hover:text-akzent-stark"
        >{showAdvanced ? '▾' : '▸'} Erweitert</button
      >
      {#if showAdvanced}
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Ziel: Sichtbarkeit</span>
          <select name="target_visibility" class="rounded-md border border-border-stark bg-surface px-3 py-2">
            <option value="">–</option>
            {#each Object.entries(VISIBILITY) as [v, l]}<option value={v} selected={p.target_visibility === v}>{l}</option>{/each}
          </select>
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Planungsart</span>
          <select name="scheduling_mode" class="rounded-md border border-border-stark bg-surface px-3 py-2">
            {#each Object.entries(SCHEDULING_MODE) as [v, l]}<option value={v} selected={p.scheduling_mode === v}>{l}</option>{/each}
          </select>
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Wochenbudget (Min.)</span>
          <input name="weekly_time_budget_minutes" type="number" min="0" value={p.weekly_time_budget_minutes} class="rounded-md border border-border-stark bg-surface px-3 py-2" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Durchsicht alle (Tage)</span>
          <input name="review_interval_days" type="number" min="1" value={p.review_interval_days ?? ''} class="rounded-md border border-border-stark bg-surface px-3 py-2" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Abschalt-Datum</span>
          <input name="sunset_date" type="date" value={p.sunset_date ?? ''} class="rounded-md border border-border-stark bg-surface px-3 py-2" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Geplante Veröffentlichung</span>
          <input name="public_target_date" type="date" value={p.public_target_date ?? ''} class="rounded-md border border-border-stark bg-surface px-3 py-2" />
        </label>
        <label class="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="hidden" name="_has_auto_schedule" value="1" />
          <input name="can_auto_schedule" type="checkbox" checked={p.can_auto_schedule} />
          <span>Automatisch im Kalender planbar</span>
        </label>
      {/if}
      <div class="sm:col-span-2">
        <Button type="submit" variant="primary">Speichern</Button>
      </div>
    </form>

  {:else if tab === 'tasks'}
    <!-- Die Aufgaben liegen seit dem Umzug (Nov. 2026) im Aufgaben-Dienst.
         Hier wird angelegt, abgehakt und geloescht; geoeffnet wird eine
         Aufgabe in Saganta Aufgaben (Entscheid 05.11.), dort liegen
         Listen, Bedingungen und Umhaengen. -->
    {#if mitUnterprojekten}
      <div class="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {#each akte!.kinder as k (k.id)}
          <a
            href={`/projekte/${k.slug}`}
            class="group flex flex-col gap-1 rounded-lg border border-border bg-surface-2/40 px-3 py-2.5 transition-colors duration-fast ease-saganta hover:border-accent-500/60"
          >
            <span class="flex items-center justify-between gap-2">
              <span class="truncate text-sm font-medium">{k.name}</span>
              <span class="shrink-0 text-xs tabular-nums text-muted">{k.offen} offen</span>
            </span>
            <span class="flex flex-wrap gap-x-2 text-xs text-muted">
              {#if k.ueberfaellig}<span class="text-fehler">{k.ueberfaellig} überfällig</span>{/if}
              {#if k.hoch}<span class="text-akzent">{k.hoch} hoch</span>{/if}
              {#if k.naechstes_datum}<span>nächstes {k.naechstes_datum.slice(8, 10)}.{k.naechstes_datum.slice(5, 7)}.</span>{/if}
              {#if k.unterprojekte}<span>{k.unterprojekte} darunter</span>{/if}
            </span>
          </a>
        {/each}
      </div>
    {/if}
    <form method="POST" action="?/addTask" use:enhance class="mb-4 flex flex-wrap items-end gap-2 rounded-lg border border-border bg-surface-2/40 p-3">
      <label class="flex flex-1 flex-col gap-1 text-sm">
        <span class="text-muted">Neue Aufgabe</span>
        <input name="titel" required placeholder="Titel" class="rounded-md border border-border-stark bg-surface px-3 py-2" />
      </label>
      {#if mitUnterprojekten}
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">in</span>
          <select name="projekt_id" class="rounded-md border border-border-stark bg-surface px-3 py-2">
            {#each zielAuswahl as z (z.slug)}
              <option value={z.id} selected={z.id === p.id}>{z.id === p.id ? `${z.name} (allgemein)` : z.name}</option>
            {/each}
          </select>
        </label>
      {/if}
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Dauer (Min.)</span>
        <input name="dauer_min" type="number" min="1" max="1440" class="w-28 rounded-md border border-border-stark bg-surface px-3 py-2" />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Priorität</span>
        <select name="prioritaet" class="rounded-md border border-border-stark bg-surface px-3 py-2">
          <option value="hoch">hoch</option>
          <option value="mittel" selected>mittel</option>
          <option value="niedrig">niedrig</option>
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Fällig</span>
        <input name="faellig" type="date" class="rounded-md border border-border-stark bg-surface px-3 py-2" />
      </label>
      <Button type="submit" variant="primary" aria-label="Hinzufügen"><Icon name="plus" size={16} /></Button>
    </form>
    {#if data.aufgabenFehlen}
      <p class="rounded border border-warnung/40 bg-warnung/10 px-3 py-2 text-sm text-warnung">
        Der Aufgaben-Dienst antwortet gerade nicht. Die Aufgaben dieses Projekts sind nicht verloren, nur nicht abrufbar.
      </p>
    {:else if anzahlOffen === 0 && erledigte.length === 0}
      <p class="text-sm text-muted">Keine Aufgaben.</p>
    {:else}
      {#if anzahlOffen === 0}
        <p class="text-sm text-muted">Nichts offen.</p>
      {:else}
        <p class="mb-2 text-xs text-muted">{anzahlOffen} offen{mitUnterprojekten ? ' hier und in den Unterprojekten' : ''}</p>
        {#each gruppen as [slug, liste] (slug)}
          {#if mitUnterprojekten}
            <h3 class="mt-4 mb-1.5 flex items-baseline gap-2 text-sm font-medium first:mt-0">
              {#if slug === p.slug}
                {p.name} <span class="text-xs font-normal text-muted">allgemein</span>
              {:else}
                <a href={`/projekte/${slug}`} class="hover:text-akzent">{projektName(slug)}</a>
              {/if}
              <span class="text-xs font-normal tabular-nums text-muted">{liste.length}</span>
            </h3>
          {/if}
          <ul class="divide-y divide-border rounded-lg border border-border">
            {#each uniqueBy(liste, (x) => x.id) as t (t.id)}
              {@render aufgabenZeile(t)}
            {/each}
          </ul>
        {/each}
      {/if}
      {#if erledigte.length}
        <details class="mt-4">
          <summary class="cursor-pointer text-sm text-muted hover:text-text">Erledigt ({erledigte.length})</summary>
          <ul class="mt-2 divide-y divide-border rounded-lg border border-border">
            {#each erledigte as t (t.id)}
              {@render aufgabenZeile(t)}
            {/each}
          </ul>
        </details>
      {/if}
    {/if}

  {:else if tab === 'zeitleiste'}
    <p class="mb-3 text-sm text-muted">
      Termine, Fristen, Meilensteine und eingeplante Arbeit{mitUnterprojekten ? ' dieses Projekts und aller Unterprojekte' : ''}. Termine vom letzten Monat bis ein Jahr voraus; offene Fristen und Eingeplantes auch, wenn sie älter sind.
      Einen Termin bekommt das Projekt im Kalender über das Feld „Projekt“.
    </p>
    {#if !akte}
      <p class="rounded border border-warnung/40 bg-warnung/10 px-3 py-2 text-sm text-warnung">Die Projektakte ist gerade nicht abrufbar.</p>
    {:else}
      {#if akte.termine_fehlen}
        <p class="mb-3 rounded border border-warnung/40 bg-warnung/10 px-3 py-2 text-sm text-warnung">Der Kalender antwortet gerade nicht; Termine fehlen unten, Fristen sind da.</p>
      {/if}
      {#if zeitleisteNachMonat.length === 0}
        <p class="text-sm text-muted">Keine Termine und Fristen.</p>
      {/if}
      {#each zeitleisteNachMonat as [monat, eintraege] (monat)}
        <h3 class="mt-5 mb-2 text-xs font-medium uppercase tracking-wide text-muted first:mt-0">{monatsName(monat)}</h3>
        <ol class="relative ml-2 border-l border-border-stark">
          {#each eintraege as z, i (`${z.art}-${z.ref ?? z.titel}-${z.datum}-${i}`)}
            {@const vorbei = z.datum < heute}
            {@const offenVorbei = vorbei && z.art !== 'termin' && z.art !== 'geplant'}
            <!-- Die Akte liest nur offene Aufgaben: Eingeplantes in der Vergangenheit ist verpasst, nicht erledigt. -->
            {@const verpasst = vorbei && z.art === 'geplant'}
            <li class="relative py-1.5 pl-5 {vorbei && !offenVorbei && !verpasst ? 'opacity-55' : ''}">
              <span
                class="absolute top-[0.7rem] -left-[5px] h-2.5 w-2.5 rounded-full {z.art === 'termin'
                  ? 'bg-akzent'
                  : z.art === 'geplant'
                    ? verpasst
                      ? 'border-2 border-warnung bg-surface'
                      : 'border-2 border-muted bg-surface'
                    : offenVorbei
                      ? 'bg-fehler'
                      : 'bg-kupfer'}"
                aria-hidden="true"
              ></span>
              <div class="flex flex-wrap items-baseline gap-x-2 text-sm">
                <span class="w-full shrink-0 whitespace-nowrap tabular-nums text-muted sm:w-28">{tagKurz(z.datum)}{z.uhrzeit ? ` · ${z.uhrzeit}` : ''}</span>
                {#if z.art === 'frist' || z.art === 'geplant'}
                  <a href={aufgabeUrl(z.ref ?? '', host)} class="min-w-0 hover:underline">{z.titel}</a>
                {:else}
                  <span class="min-w-0">{z.titel}</span>
                {/if}
                <span class="text-xs {offenVorbei ? 'text-fehler' : verpasst ? 'text-warnung' : 'text-muted'}">{ART_LABEL[z.art]}{offenVorbei ? ', überfällig' : ''}{verpasst ? ', verpasst' : ''}{z.ende ? ` bis ${z.ende}` : ''}{z.ort ? ` · ${z.ort}` : ''}</span>
                {#if mitUnterprojekten && z.projekt !== p.slug}
                  <a href={`/projekte/${z.projekt}`} class="ml-auto rounded bg-surface-2 px-1.5 py-0.5 text-xs text-muted hover:text-text">{projektName(z.projekt)}</a>
                {/if}
              </div>
            </li>
          {/each}
        </ol>
      {/each}
    {/if}

  {:else if tab === 'kontakte'}
    {#if !akte}
      <p class="rounded border border-warnung/40 bg-warnung/10 px-3 py-2 text-sm text-warnung">Die Projektakte ist gerade nicht abrufbar.</p>
    {:else}
      <form method="POST" action="?/kontaktAnheften" use:enhance class="mb-4 flex flex-wrap items-end gap-2 rounded-lg border border-border bg-surface-2/40 p-3">
        <label class="flex min-w-48 flex-1 flex-col gap-1 text-sm">
          <span class="text-muted">Kontakt anheften</span>
          {#if data.kontaktAuswahl}
            <select name="kontakt_id" required class="rounded-md border border-border-stark bg-surface px-3 py-2">
              <option value="">wählen …</option>
              {#each data.kontaktAuswahl as k (k.id)}
                <option value={k.id}>{k.name}{k.gruppe ? ` (${k.gruppe})` : ''}</option>
              {/each}
            </select>
          {:else}
            <span class="text-warnung">Saganta Kontakte antwortet gerade nicht.</span>
          {/if}
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Rolle</span>
          <input name="rolle" maxlength="80" placeholder="z. B. Kunde, Lieferant" class="rounded-md border border-border-stark bg-surface px-3 py-2" />
        </label>
        <Button type="submit" variant="primary" aria-label="Anheften"><Icon name="plus" size={16} /></Button>
      </form>
      {#if akte.kontakte.length === 0}
        <p class="text-sm text-muted">Noch keine Kontakte am Projekt.</p>
      {:else}
        <ul class="grid gap-2 sm:grid-cols-2">
          {#each akte.kontakte as k (k.verweis_id)}
            <li class="flex flex-col gap-1 rounded-lg border border-border bg-surface-2/40 px-3 py-2.5 text-sm">
              <div class="flex items-start justify-between gap-2">
                <span class="font-medium">
                  {#if k.fehlt}<span class="text-muted">Kontakt gelöscht</span>{:else if k.unbekannt}<span class="text-muted">nicht abrufbar</span>{:else}{k.name}{/if}
                </span>
                {#if k.projekt === p.slug}
                  <form method="POST" action="?/kontaktLoesen" use:enhance>
                    <input type="hidden" name="verweis_id" value={k.verweis_id} />
                    <button class="text-muted transition-colors duration-fast ease-saganta hover:text-fehler" title="Vom Projekt lösen" aria-label="Vom Projekt lösen"><Icon name="x" size={14} /></button>
                  </form>
                {:else}
                  <a href={`/projekte/${k.projekt}`} class="rounded bg-surface px-1.5 py-0.5 text-xs text-muted hover:text-text">{k.projekt_name}</a>
                {/if}
              </div>
              {#if k.projekt === p.slug}
                <form method="POST" action="?/kontaktRolle" use:enhance class="flex items-center gap-1">
                  <input type="hidden" name="verweis_id" value={k.verweis_id} />
                  <input name="rolle" value={k.rolle ?? ''} maxlength="80" placeholder="Rolle" aria-label="Rolle" class="w-full rounded border border-transparent bg-transparent px-1 py-0.5 text-xs text-muted hover:border-border-stark focus:border-border-stark focus:text-text" />
                </form>
              {:else if k.rolle}
                <span class="text-xs text-muted">{k.rolle}</span>
              {/if}
              <span class="flex flex-wrap gap-x-3 text-xs">
                {#if k.telefon}<a href={`tel:${k.telefon}`} class="text-akzent hover:text-akzent-stark">{k.telefon}</a>{/if}
                {#if k.email}<a href={`mailto:${k.email}`} class="truncate text-akzent hover:text-akzent-stark">{k.email}</a>{/if}
              </span>
            </li>
          {/each}
        </ul>
      {/if}
    {/if}

  {:else if tab === 'budget'}
    {#if !akte || !akte.budget.verfuegbar}
      <p class="rounded border border-border bg-surface-2/40 px-3 py-2 text-sm text-muted">
        Das Budget kommt aus Saganta Finanzen und ist hier gerade nicht verfügbar
        (Lesezugang nicht eingerichtet oder Finanzen antwortet nicht).
      </p>
    {:else if !akte.budget.gesamt || (akte.budget.gesamt.budget_cent == null && akte.budget.gesamt.anzahl_buchungen === 0)}
      <p class="text-sm text-muted">
        Noch kein Budget und keine Buchungen. In Finanzen eine Buchung dem Projekt „{p.slug}“ zuordnen oder ein Projektbudget anlegen.
      </p>
    {:else}
      {@const g = akte.budget.gesamt}
      {@const anteil = g.budget_cent ? Math.min(1, g.ausgaben_cent / g.budget_cent) : null}
      <div class="rounded-lg border border-border bg-surface-2/40 p-4">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div><p class="text-xs text-muted">Budget</p><p class="text-lg tabular-nums">{euro(g.budget_cent)}</p></div>
          <div><p class="text-xs text-muted">Ausgegeben</p><p class="text-lg tabular-nums">{euro(g.ausgaben_cent)}</p></div>
          <div><p class="text-xs text-muted">Rest</p><p class="text-lg tabular-nums {g.rest_cent != null && g.rest_cent < 0 ? 'text-fehler' : ''}">{euro(g.rest_cent)}</p></div>
          <div><p class="text-xs text-muted">Einnahmen</p><p class="text-lg tabular-nums">{euro(g.einnahmen_cent)}</p></div>
        </div>
        {#if anteil != null}
          <div class="mt-3 h-2 overflow-hidden rounded-full bg-surface" role="img" aria-label={`${Math.round(anteil * 100)} % des Budgets ausgegeben`}>
            <div class="h-full rounded-full {g.rest_cent != null && g.rest_cent < 0 ? 'bg-fehler' : anteil > 0.85 ? 'bg-warnung' : 'bg-kupfer'}" style:width={`${anteil * 100}%`}></div>
          </div>
        {/if}
      </div>
      {#if mitUnterprojekten && Object.keys(akte.budget.je).length > 1}
        <h3 class="mt-5 mb-2 text-sm font-medium">Je Projekt</h3>
        <ul class="divide-y divide-border rounded-lg border border-border text-sm">
          {#each Object.entries(akte.budget.je) as [slug, b] (slug)}
            <li class="flex items-center justify-between gap-3 px-3 py-2">
              <a href={`/projekte/${slug}`} class="hover:underline">{projektName(slug)}</a>
              <span class="text-xs tabular-nums text-muted">{euro(b.ausgaben_cent)} von {euro(b.budget_cent)}</span>
            </li>
          {/each}
        </ul>
      {/if}
      {#if akte.budget.letzte.length}
        <h3 class="mt-5 mb-2 text-sm font-medium">Letzte Buchungen{mitUnterprojekten ? ` (${p.name} allgemein)` : ''}</h3>
        <ul class="divide-y divide-border rounded-lg border border-border text-sm">
          {#each akte.budget.letzte as b, i (`${b.datum}-${i}`)}
            <li class="flex items-center justify-between gap-3 px-3 py-2">
              <span class="min-w-0 truncate">{b.text || b.kategorie || 'Buchung'}</span>
              <span class="shrink-0 text-xs tabular-nums {b.betrag_cent < 0 ? 'text-muted' : 'text-erfolg'}">{b.datum.slice(8, 10)}.{b.datum.slice(5, 7)}. · {euro(b.betrag_cent)}</span>
            </li>
          {/each}
        </ul>
      {/if}
    {/if}

  {:else if tab === 'notizen'}
    <!-- ⚠️ NACH dem Formular, nicht darin: der Block bringt sein eigenes
         `<form>` mit, und ein Formular im Formular ist in HTML nicht erlaubt.
         Der Browser bricht das verschachtelte stillschweigend auf, womit die
         Felder am falschen Formular landen.

         `ref` ist der **Slug**, nicht die Zeilennummer: so loest die
         Notizen-App Projekte auf (`quellen.ts`). Mit der `id` entstuende eine
         Verknuepfung, die von der anderen Seite nie gefunden wird, und zwar
         ohne jede Fehlermeldung. -->
    <div class="mt-6">
      <NotizenBlock
        typ="projekt"
        ref={p.slug}
        label={p.name}
        notizen={data.notizen}
        {notizenBasis}
        fehler={notizFehler}
        {enhance}
      />
    </div>

    {#if akte && mitUnterprojekten}
      {@const unten = akte.notizen.filter((n) => n.projekt !== p.slug)}
      {#if unten.length}
        <h3 class="mt-6 mb-2 text-sm font-medium">Aus den Unterprojekten</h3>
        <ul class="divide-y divide-border rounded-lg border border-border text-sm">
          {#each unten as n (`${n.projekt}-${n.id}`)}
            <li class="flex items-center justify-between gap-3 px-3 py-2">
              <a href={`${notizenBasis}/notiz/${n.id}`} class="min-w-0 truncate hover:underline">{n.titel}</a>
              <a href={`/projekte/${n.projekt}`} class="shrink-0 rounded bg-surface-2 px-1.5 py-0.5 text-xs text-muted hover:text-text">{projektName(n.projekt ?? '')}</a>
            </li>
          {/each}
        </ul>
      {/if}
    {/if}

  {:else if tab === 'milestones'}
    <form method="POST" action="?/addMilestone" use:enhance class="mb-4 flex flex-wrap items-end gap-2 rounded-lg border border-border bg-surface-2/40 p-3">
      <input name="title" required placeholder="Milestone" class="flex-1 rounded-md border border-border-stark bg-surface px-3 py-2 text-sm" />
      <input name="target_date" type="date" class="rounded-md border border-border-stark bg-surface px-3 py-2 text-sm" />
      <Button type="submit" variant="primary" aria-label="Hinzufügen"><Icon name="plus" size={16} /></Button>
    </form>
    <ul class="divide-y divide-border rounded-lg border border-border">
      {#each uniqueBy(data.milestones, (x) => x.id) as m (m.id)}
        {@const erreicht = ['done', 'erreicht', 'abgeschlossen', 'erledigt'].includes(
          (m.status ?? 'open').toLowerCase()
        )}
        {@const ueberfaellig = !erreicht && !!m.target_date && m.target_date < heute}
        <li class="flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
          <!-- Erreicht-Markieren und Löschen fehlten bis zum 2026-10-16 ganz:
               der Status blieb für immer `open`, DELETE gab es nur im Backend. -->
          <form method="POST" action="?/toggleMilestone" use:enhance class="flex">
            <input type="hidden" name="id" value={m.id} />
            <input type="hidden" name="status" value={erreicht ? 'open' : 'erreicht'} />
            <button
              class="text-muted transition-colors duration-fast ease-saganta hover:text-akzent"
              title={erreicht ? 'Wieder offen' : 'Als erreicht markieren'}
              aria-label={erreicht ? 'Wieder offen' : 'Als erreicht markieren'}
            >
              <Icon name={erreicht ? 'circle-check' : 'square-check'} size={16} />
            </button>
          </form>
          <span class={erreicht ? 'text-muted line-through' : ''}>{m.title}</span>
          <span class={`ml-auto text-xs ${ueberfaellig ? 'text-warnung' : 'text-muted'}`}>
            {m.target_date ?? ''}{ueberfaellig ? ' · überfällig' : ''}
          </span>
          <form method="POST" action="?/deleteMilestone" use:enhance class="flex">
            <input type="hidden" name="id" value={m.id} />
            <button class="text-muted transition-colors duration-fast ease-saganta hover:text-fehler" title="Löschen" aria-label="Löschen"><Icon name="x" size={14} /></button>
          </form>
        </li>
      {:else}
        <li class="px-3 py-2 text-sm text-muted">Keine Meilensteine.</li>
      {/each}
    </ul>

  {:else if tab === 'deadlines'}
    <form method="POST" action="?/updateProject" use:enhance class="grid gap-3 sm:grid-cols-2">
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Frist</span>
        <input name="deadline_date" type="date" value={p.deadline_date ?? ''} class="rounded-md border border-border-stark bg-surface px-3 py-2" />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Art der Frist</span>
        <select name="deadline_type" class="rounded-md border border-border-stark bg-surface px-3 py-2">
          <option value="">–</option>
          {#each Object.entries(DEADLINE_TYPE) as [v, l]}<option value={v} selected={p.deadline_type === v}>{l}</option>{/each}
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Datum der Durchsicht</span>
        <input name="review_date" type="date" value={p.review_date ?? ''} class="rounded-md border border-border-stark bg-surface px-3 py-2" />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Abschalt-Datum</span>
        <input name="sunset_date" type="date" value={p.sunset_date ?? ''} class="rounded-md border border-border-stark bg-surface px-3 py-2" />
      </label>
      <div class="sm:col-span-2"><Button type="submit" variant="primary">Speichern</Button></div>
    </form>
    <form method="POST" action="?/ai" use:enhance class="mt-4">
      <input type="hidden" name="kind" value="deadline" />
      <Button variant="ghost" size="sm">KI: Fristen-Einschätzung</Button>
    </form>

  {:else if tab === 'calendar'}
    <p class="mb-3 text-sm text-muted">
      Aufgaben dieses Projekts mit Tag oder Uhrzeit. Eingeplant wird in Saganta Aufgaben („Tag planen") oder über „Zeit einplanen" oben.
    </p>
    {#if data.aufgabenFehlen}
      <p class="text-sm text-warnung">Der Aufgaben-Dienst antwortet gerade nicht.</p>
    {:else if eingeplant.length === 0}
      <p class="text-sm text-muted">Nichts eingeplant.</p>
    {:else}
      <ul class="divide-y divide-border rounded-lg border border-border text-sm">
        {#each eingeplant as a (a.id)}
          <li class="flex items-center justify-between gap-3 px-3 py-2">
            <a href={aufgabeUrl(a.id, host)} class="min-w-0 truncate hover:underline">{a.titel}</a>
            <span class="shrink-0 text-xs text-muted">
              {a.start ? a.start.slice(0, 16).replace('T', ' ') : a.tag}{a.ende ? `–${a.ende.slice(11, 16)}` : ''}{a.dauer_min && !a.ende ? ` · ${fmtMinutes(a.dauer_min)}` : ''}
            </span>
          </li>
        {/each}
      </ul>
    {/if}

  {:else if tab === 'assets'}
    <form method="POST" action="?/addAsset" use:enhance class="mb-4 flex flex-wrap items-end gap-2 rounded-lg border border-border bg-surface-2/40 p-3">
      <select name="type" class="rounded-md border border-border-stark bg-surface px-3 py-2 text-sm">
        <option value="domain">Domain</option><option value="repo">Repo</option>
        <option value="deployment">Deployment</option><option value="link">Link</option><option value="doc">Doku</option>
      </select>
      <input name="label" placeholder="Label" class="rounded-md border border-border-stark bg-surface px-3 py-2 text-sm" />
      <input name="value" required placeholder="Wert (z. B. djouhri.de)" class="flex-1 rounded-md border border-border-stark bg-surface px-3 py-2 text-sm" />
      <input name="url" placeholder="URL (optional)" class="rounded-md border border-border-stark bg-surface px-3 py-2 text-sm" />
      <Button type="submit" variant="primary" aria-label="Hinzufügen"><Icon name="plus" size={16} /></Button>
    </form>
    <ul class="divide-y divide-border rounded-lg border border-border text-sm">
      {#each uniqueBy(data.assets, (x) => x.id) as a (a.id)}
        <li class="flex items-center gap-3 px-3 py-2">
          <span class="rounded bg-surface-2 px-1.5 py-0.5 text-xs uppercase text-muted">{a.type}</span>
          <span class="font-medium">{a.label}</span>
          {#if a.url}<a href={a.url} class="text-akzent hover:text-akzent-stark" target="_blank" rel="noreferrer">{a.value}</a>{:else}<span class="text-muted">{a.value}</span>{/if}
          <form method="POST" action="?/deleteAsset" use:enhance class="ml-auto">
            <input type="hidden" name="id" value={a.id} /><button class="text-muted transition-colors duration-fast ease-saganta hover:text-fehler" aria-label="Löschen"><Icon name="x" size={14} /></button>
          </form>
        </li>
      {:else}
        <li class="px-3 py-2 text-muted">Keine Verweise.</li>
      {/each}
    </ul>

  {:else if tab === 'reviews'}
    <form method="POST" action="?/addReview" use:enhance class="mb-4 grid gap-3 rounded-lg border border-border bg-surface-2/40 p-3 sm:grid-cols-2">
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Entscheidung</span>
        <select name="decision" class="rounded-md border border-border-stark bg-surface px-3 py-2">
          <option value="keep_active">Aktiv lassen</option>
          <option value="pause">Pausieren</option>
          <option value="prepare_public">Veröffentlichung vorbereiten</option>
          <option value="shutdown">Abschalten</option>
          <option value="archive">Archivieren</option>
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Neuer Status (optional)</span>
        <select name="new_status" class="rounded-md border border-border-stark bg-surface px-3 py-2">
          <option value="">– nicht ändern –</option>
          {#each Object.entries(PROJECT_STATUS) as [v, l]}<option value={v}>{l}</option>{/each}
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm sm:col-span-2">
        <span class="text-muted">Notizen</span>
        <textarea name="notes" rows="2" class="rounded-md border border-border-stark bg-surface px-3 py-2"></textarea>
      </label>
      <div class="sm:col-span-2"><Button type="submit" variant="primary">Durchsicht speichern</Button></div>
    </form>
    <form method="POST" action="?/ai" use:enhance class="mb-4">
      <input type="hidden" name="kind" value="review" />
      <Button variant="ghost" size="sm">KI: Zusammenfassung der Durchsicht</Button>
    </form>
    <ul class="divide-y divide-border rounded-lg border border-border text-sm">
      {#each uniqueBy(data.reviews, (x) => x.id) as r (r.id)}
        <li class="px-3 py-2">
          <div class="flex justify-between"><span class="font-medium">{r.decision}</span><span class="text-muted">{r.review_date}</span></div>
          {#if r.notes}<p class="text-muted">{r.notes}</p>{/if}
        </li>
      {:else}
        <li class="px-3 py-2 text-muted">Noch keine Durchsichten.</li>
      {/each}
    </ul>

  {:else if tab === 'readiness'}
    <form method="POST" action="?/saveReadiness" use:enhance class="rounded-lg border border-border">
      <p class="border-b border-border px-4 py-2 text-sm text-muted">
        {data.readiness.completed}/{data.readiness.total} erfüllt
      </p>
      <ul class="divide-y divide-border">
        {#each Object.keys(READINESS_LABELS) as key}
          <li class="flex items-center gap-3 px-4 py-2 text-sm">
            <input type="hidden" name="item_key" value={key} />
            <input type="checkbox" name={`done_${key}`} checked={data.readiness.items[key]?.done ?? false} />
            <span>{READINESS_LABELS[key]}</span>
          </li>
        {/each}
      </ul>
      <div class="px-4 py-3"><Button type="submit" variant="primary">Speichern</Button></div>
    </form>

  {:else if tab === 'client'}
    <form method="POST" action="?/updateProject" use:enhance class="grid gap-3 sm:grid-cols-2">
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Kunden-Kennung</span>
        <input name="client_id" value={p.client_id ?? ''} class="rounded-md border border-border-stark bg-surface px-3 py-2" />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Stand der Übergabe</span>
        <input name="handover_status" value={p.handover_status ?? ''} class="rounded-md border border-border-stark bg-surface px-3 py-2" />
      </label>
      <label class="flex flex-col gap-1 text-sm sm:col-span-2">
        <span class="text-muted">Versprochener Umfang</span>
        <textarea name="promised_scope" rows="2" class="rounded-md border border-border-stark bg-surface px-3 py-2">{p.promised_scope ?? ''}</textarea>
      </label>
      <label class="flex flex-col gap-1 text-sm sm:col-span-2">
        <span class="text-muted">Kommunikations-Notizen</span>
        <textarea name="communication_notes" rows="2" class="rounded-md border border-border-stark bg-surface px-3 py-2">{p.communication_notes ?? ''}</textarea>
      </label>
      <div class="sm:col-span-2"><Button type="submit" variant="primary">Speichern</Button></div>
    </form>

  {:else if tab === 'shutdown'}
    <form method="POST" action="?/ai" use:enhance class="mb-4">
      <input type="hidden" name="kind" value="shutdown" />
      <Button variant="ghost" size="sm">KI: Abschalt-Empfehlung</Button>
    </form>
    <form method="POST" action="?/saveShutdown" use:enhance class="rounded-lg border border-border">
      <p class="border-b border-border px-4 py-2 text-sm text-muted">
        Checkliste vor dem Abschalten: {data.shutdown.completed}/{data.shutdown.total} erledigt
      </p>
      <ul class="divide-y divide-border">
        {#each Object.keys(SHUTDOWN_LABELS) as key}
          <li class="flex items-center gap-3 px-4 py-2 text-sm">
            <input type="hidden" name="item_key" value={key} />
            <input type="checkbox" name={`done_${key}`} checked={data.shutdown.items[key]?.done ?? false} />
            <span>{SHUTDOWN_LABELS[key]}</span>
          </li>
        {/each}
      </ul>
      <div class="px-4 py-3"><Button type="submit" variant="primary">Speichern</Button></div>
    </form>
  {/if}

  {#if aiResult}
    <div class="mt-4 rounded-lg border border-accent-500/40 bg-accent-500/5 p-4">
      <p class="text-sm font-medium">KI ({aiResult.source}): {aiResult.summary}</p>
      <ul class="mt-2 list-disc pl-5 text-xs text-muted">
        {#each aiResult.reasoning as r}<li>{r}</li>{/each}
      </ul>
    </div>
  {/if}
</div>

{#snippet aufgabenZeile(t: Aufgabe)}
  <li class="flex items-start gap-3 px-3 py-2 text-sm {t.wartet && !t.erledigt ? 'opacity-60' : ''}">
    <form method="POST" action="?/taskStatus" use:enhance>
      <input type="hidden" name="id" value={t.id} />
      <input type="hidden" name="erledigt" value={t.erledigt ? 'nein' : 'ja'} />
      <button class="transition-colors duration-fast ease-saganta {t.erledigt ? 'text-erfolg' : 'text-muted hover:text-text'}" title="Abhaken umschalten" aria-label="Abhaken umschalten"><Icon name={t.erledigt ? 'square-check' : 'square'} size={18} /></button>
    </form>
    <div class="min-w-0 flex-1">
      <a
        href={aufgabeUrl(t.id, host)}
        class="hover:underline {t.erledigt ? 'text-muted line-through' : ''}"
        title="In Saganta Aufgaben öffnen">{t.titel}</a
      >
      {#if t.notiz}
        <p class="mt-0.5 whitespace-pre-line text-xs text-muted">{t.notiz}</p>
      {/if}
      {#if t.wartet && !t.erledigt}
        <p class="mt-0.5 text-xs text-muted">wartet{t.wartet_bis ? ` bis ${t.wartet_bis}` : ''}{t.wartet_grund ? `: ${t.wartet_grund}` : ''}</p>
      {/if}
      {#if ('notizen' in t && (t as AkteAufgabe).notizen?.length) || t.weitere_projekte?.length}
        <p class="mt-1 flex flex-wrap gap-1 text-xs text-muted">
          {#each ('notizen' in t ? (t as AkteAufgabe).notizen : []) as n (n.id)}
            <a href={`${notizenBasis}/notiz/${n.id}`} class="rounded bg-surface-2 px-1.5 py-0.5 hover:text-text" title="Notiz zur Aufgabe">✎ {n.titel}</a>
          {/each}
          {#each t.weitere_projekte ?? [] as s (s)}
            <a href={`/projekte/${s}`} class="rounded border border-border px-1.5 py-0.5 hover:text-text" title="Auch in diesem Projekt">auch: {projektName(s)}</a>
          {/each}
        </p>
      {/if}
    </div>
    {#if t.faellig && !t.erledigt}<span class="text-xs {t.faellig < heute ? 'text-fehler' : 'text-muted'}">{t.faellig < heute ? 'überfällig seit' : 'fällig'} {kurzDatum(t.faellig)}</span>{/if}
    {#if t.dauer_min}<span class="text-xs text-muted">{fmtMinutes(t.dauer_min)}</span>{/if}
    {#if t.prioritaet === 'hoch' && !t.erledigt}<span class="text-xs text-akzent">hoch</span>{/if}
    <form method="POST" action="?/deleteTask" use:enhance>
      <input type="hidden" name="id" value={t.id} />
      <button class="text-muted transition-colors duration-fast ease-saganta hover:text-fehler" title="Löschen" aria-label="Löschen"><Icon name="x" size={14} /></button>
    </form>
  </li>
{/snippet}
