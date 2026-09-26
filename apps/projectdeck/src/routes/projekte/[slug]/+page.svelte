<script lang="ts">
  import { enhance } from '$app/forms';
  import { Button, Icon } from '@saganta/ui';
  import {
    DEADLINE_TYPE,
    PROJECT_STATUS,
    PROJECT_TYPES,
    READINESS_LABELS,
    SCHEDULING_MODE,
    SHUTDOWN_LABELS,
    VISIBILITY,
    fmtMinutes,
  } from '$lib/meta';
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

  const TABS = [
    'Overview',
    'Tasks',
    'Milestones',
    'Deadlines',
    'Calendar',
    'Assets',
    'Reviews',
    'Public Readiness',
    'Client',
    'Shutdown',
  ];
  let tab = $state('Overview');
  let showAdvanced = $state(false);
  let aiResult = $derived(form && 'ai' in form ? form.ai : undefined);
</script>

<div class="flex flex-wrap items-start justify-between gap-3">
  <div>
    <a href="/projekte" class="text-sm text-muted hover:text-text">← Projekte</a>
    <h1 class="font-display text-2xl">{p.name}</h1>
    <div class="mt-1 flex flex-wrap gap-1 text-[11px] text-muted">
      <span class="rounded bg-surface-2 px-1.5 py-0.5">{PROJECT_TYPES[p.type] ?? p.type}</span>
      <span class="rounded bg-surface-2 px-1.5 py-0.5">{PROJECT_STATUS[p.status] ?? p.status}</span>
      <span class="rounded bg-surface-2 px-1.5 py-0.5">{VISIBILITY[p.visibility] ?? p.visibility}</span>
      <span class="rounded bg-surface-2 px-1.5 py-0.5">P{p.priority}</span>
      <span class="rounded bg-surface-2 px-1.5 py-0.5 font-mono">{p.slug}</span>
    </div>
  </div>
  <form method="POST" action="?/plan" use:enhance>
    <Button type="submit" variant="primary" size="sm">
      <Icon name="refresh-cw" size={15} /> Im Kalender planen
    </Button>
  </form>
</div>

{#if form && 'error' in form && form.error}
  <p class="mt-3 rounded border border-fehler/40 bg-fehler/10 px-3 py-2 text-sm text-fehler">
    {form.error}
  </p>
{/if}
{#if form && 'planResult' in form && form.planResult}
  {#if 'planScheduled' in form && form.planScheduled > 0}
    <p class="mt-3 rounded border border-erfolg/40 bg-erfolg/10 px-3 py-2 text-sm text-erfolg">
      {form.planResult}
    </p>
  {:else}
    <p class="mt-3 rounded border border-warnung/40 bg-warnung/10 px-3 py-2 text-sm text-warnung">
      {form.planResult}
    </p>
  {/if}
{/if}

<nav class="mt-5 flex flex-wrap gap-1 border-b border-border">
  {#each TABS as t}
    <button
      onclick={() => (tab = t)}
      class="rounded-t-md px-3 py-2 text-sm {tab === t
        ? 'border-b-2 border-accent-500 text-text'
        : 'text-muted hover:text-text'}">{t}</button
    >
  {/each}
</nav>

<div class="mt-5">
  {#if tab === 'Overview'}
    <form
      method="POST"
      action="?/updateProject"
      use:enhance
      class="grid gap-3 sm:grid-cols-2"
    >
      <label class="flex flex-col gap-1 text-sm sm:col-span-2">
        <span class="text-muted">Name</span>
        <input name="name" value={p.name} class="rounded-md border border-border bg-surface px-3 py-2" />
      </label>
      <label class="flex flex-col gap-1 text-sm sm:col-span-2">
        <span class="text-muted">Beschreibung</span>
        <textarea name="description" rows="2" class="rounded-md border border-border bg-surface px-3 py-2"
          >{p.description ?? ''}</textarea
        >
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Status</span>
        <select name="status" class="rounded-md border border-border bg-surface px-3 py-2">
          {#each Object.entries(PROJECT_STATUS) as [v, l]}<option value={v} selected={p.status === v}>{l}</option>{/each}
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Typ</span>
        <select name="type" class="rounded-md border border-border bg-surface px-3 py-2">
          {#each Object.entries(PROJECT_TYPES) as [v, l]}<option value={v} selected={p.type === v}>{l}</option>{/each}
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Sichtbarkeit</span>
        <select name="visibility" class="rounded-md border border-border bg-surface px-3 py-2">
          {#each Object.entries(VISIBILITY) as [v, l]}<option value={v} selected={p.visibility === v}>{l}</option>{/each}
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Priorität (1=höchste)</span>
        <input name="priority" type="number" min="1" max="5" value={p.priority} class="rounded-md border border-border bg-surface px-3 py-2" />
      </label>
      <label class="flex flex-col gap-1 text-sm sm:col-span-2">
        <span class="text-muted">Nächste Aktion</span>
        <!-- textarea statt input: das Feld fasst 500 Zeichen, und in einer
             Zeile sieht man davon rund sechzig. Wer hier mehr als ein Stichwort
             notiert, konnte seinen eigenen Satz nicht mehr lesen. -->
        <textarea
          name="next_action"
          rows="2"
          class="rounded-md border border-border bg-surface px-3 py-2">{p.next_action ?? ''}</textarea
        >
      </label>

      <button
        type="button"
        onclick={() => (showAdvanced = !showAdvanced)}
        class="sm:col-span-2 text-left text-sm text-accent-300 hover:text-accent-200"
        >{showAdvanced ? '▾' : '▸'} Erweitert</button
      >
      {#if showAdvanced}
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Target Visibility</span>
          <select name="target_visibility" class="rounded-md border border-border bg-surface px-3 py-2">
            <option value="">–</option>
            {#each Object.entries(VISIBILITY) as [v, l]}<option value={v} selected={p.target_visibility === v}>{l}</option>{/each}
          </select>
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Scheduling Mode</span>
          <select name="scheduling_mode" class="rounded-md border border-border bg-surface px-3 py-2">
            {#each Object.entries(SCHEDULING_MODE) as [v, l]}<option value={v} selected={p.scheduling_mode === v}>{l}</option>{/each}
          </select>
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Wochenbudget (Min.)</span>
          <input name="weekly_time_budget_minutes" type="number" min="0" value={p.weekly_time_budget_minutes} class="rounded-md border border-border bg-surface px-3 py-2" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Review-Intervall (Tage)</span>
          <input name="review_interval_days" type="number" min="1" value={p.review_interval_days ?? ''} class="rounded-md border border-border bg-surface px-3 py-2" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Sunset-Date</span>
          <input name="sunset_date" type="date" value={p.sunset_date ?? ''} class="rounded-md border border-border bg-surface px-3 py-2" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Public Target Date</span>
          <input name="public_target_date" type="date" value={p.public_target_date ?? ''} class="rounded-md border border-border bg-surface px-3 py-2" />
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

  {:else if tab === 'Tasks'}
    <form method="POST" action="?/addTask" use:enhance class="mb-4 flex flex-wrap items-end gap-2 rounded-lg border border-border bg-surface-2/40 p-3">
      <label class="flex flex-1 flex-col gap-1 text-sm">
        <span class="text-muted">Neuer Task</span>
        <input name="title" required placeholder="Titel" class="rounded-md border border-border bg-surface px-3 py-2" />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Schätzung (Min.)</span>
        <input name="estimated_minutes" type="number" min="0" class="w-28 rounded-md border border-border bg-surface px-3 py-2" />
      </label>
      <label class="flex items-center gap-2 text-sm"><input name="can_schedule" type="checkbox" checked /> planbar</label>
      <Button type="submit" variant="primary" aria-label="Hinzufügen"><Icon name="plus" size={16} /></Button>
    </form>
    {#if data.tasks.length === 0}
      <p class="text-sm text-muted">Keine Tasks.</p>
    {:else}
      <ul class="divide-y divide-border rounded-lg border border-border">
        {#each uniqueBy(data.tasks, (x) => x.id) as t (t.id)}
          <li class="flex items-center gap-3 px-3 py-2 text-sm">
            <form method="POST" action="?/taskStatus" use:enhance>
              <input type="hidden" name="id" value={t.id} />
              <input type="hidden" name="status" value={t.status === 'done' ? 'open' : 'done'} />
              <button class="transition-colors duration-fast ease-saganta {t.status === 'done' ? 'text-erfolg' : 'text-muted hover:text-text'}" title="Status umschalten" aria-label="Status umschalten"><Icon name={t.status === 'done' ? 'square-check' : 'square'} size={18} /></button>
            </form>
            <span class="flex-1 {t.status === 'done' ? 'text-muted line-through' : ''}">{t.title}</span>
            <span class="text-xs text-muted">{fmtMinutes(t.remaining_minutes ?? t.estimated_minutes)}</span>
            {#if t.can_schedule}<span class="text-xs text-accent-300">planbar</span>{/if}
            {#if t.scheduled_event_id}<span class="text-erfolg" title="im Kalender"><Icon name="clock" size={13} label="im Kalender" /></span>{/if}
            <form method="POST" action="?/deleteTask" use:enhance>
              <input type="hidden" name="id" value={t.id} />
              <button class="text-muted transition-colors duration-fast ease-saganta hover:text-fehler" title="Löschen" aria-label="Löschen"><Icon name="x" size={14} /></button>
            </form>
          </li>
        {/each}
      </ul>
    {/if}

  {:else if tab === 'Milestones'}
    <form method="POST" action="?/addMilestone" use:enhance class="mb-4 flex flex-wrap items-end gap-2 rounded-lg border border-border bg-surface-2/40 p-3">
      <input name="title" required placeholder="Milestone" class="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm" />
      <input name="target_date" type="date" class="rounded-md border border-border bg-surface px-3 py-2 text-sm" />
      <Button type="submit" variant="primary" aria-label="Hinzufügen"><Icon name="plus" size={16} /></Button>
    </form>
    <ul class="divide-y divide-border rounded-lg border border-border">
      {#each uniqueBy(data.milestones, (x) => x.id) as m (m.id)}
        <li class="flex justify-between px-3 py-2 text-sm"><span>{m.title}</span><span class="text-muted">{m.target_date ?? ''}</span></li>
      {:else}
        <li class="px-3 py-2 text-sm text-muted">Keine Milestones.</li>
      {/each}
    </ul>

  {:else if tab === 'Deadlines'}
    <form method="POST" action="?/updateProject" use:enhance class="grid gap-3 sm:grid-cols-2">
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Deadline-Datum</span>
        <input name="deadline_date" type="date" value={p.deadline_date ?? ''} class="rounded-md border border-border bg-surface px-3 py-2" />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Deadline-Typ</span>
        <select name="deadline_type" class="rounded-md border border-border bg-surface px-3 py-2">
          <option value="">–</option>
          {#each Object.entries(DEADLINE_TYPE) as [v, l]}<option value={v} selected={p.deadline_type === v}>{l}</option>{/each}
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Review-Date</span>
        <input name="review_date" type="date" value={p.review_date ?? ''} class="rounded-md border border-border bg-surface px-3 py-2" />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Sunset-Date</span>
        <input name="sunset_date" type="date" value={p.sunset_date ?? ''} class="rounded-md border border-border bg-surface px-3 py-2" />
      </label>
      <div class="sm:col-span-2"><Button type="submit" variant="primary">Speichern</Button></div>
    </form>
    <form method="POST" action="?/ai" use:enhance class="mt-4">
      <input type="hidden" name="kind" value="deadline" />
      <Button variant="ghost" size="sm">KI: Deadline-Einschätzung</Button>
    </form>

  {:else if tab === 'Calendar'}
    <p class="mb-3 text-sm text-muted">Aus dem Kalender zurückgemeldete geplante Arbeitsblöcke.</p>
    {#if data.timeBlocks.length === 0}
      <p class="text-sm text-muted">Noch nichts geplant. Nutze „Im Kalender planen" oben.</p>
    {:else}
      <ul class="divide-y divide-border rounded-lg border border-border text-sm">
        {#each uniqueBy(data.timeBlocks, (x) => x.id) as b (b.id)}
          <li class="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
            <div class="min-w-0">
              <span
                >{b.planned_start ? b.planned_start.slice(0, 16).replace('T', ' ') : '–'} → {b.planned_end
                  ? b.planned_end.slice(11, 16)
                  : '–'}</span
              >
              <span class="ml-2 text-muted"
                >{b.status}{b.actual_minutes ? ` · ${fmtMinutes(b.actual_minutes)}` : ''}</span
              >
            </div>
            {#if b.status !== 'done'}
              <form method="POST" action="?/worklog" use:enhance class="flex items-center gap-2">
                <input type="hidden" name="calendar_event_id" value={b.calendar_event_id ?? ''} />
                <input type="hidden" name="task_id" value={b.task_id ?? ''} />
                <input
                  name="actual_minutes"
                  type="number"
                  min="0"
                  step="5"
                  placeholder="Min."
                  required
                  class="w-20 rounded-md border border-border bg-surface px-2 py-1 text-sm"
                />
                <label class="flex items-center gap-1 text-xs text-muted">
                  <input type="checkbox" name="completed" /> fertig
                </label>
                <Button type="submit" variant="ghost">Buchen</Button>
              </form>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}

  {:else if tab === 'Assets'}
    <form method="POST" action="?/addAsset" use:enhance class="mb-4 flex flex-wrap items-end gap-2 rounded-lg border border-border bg-surface-2/40 p-3">
      <select name="type" class="rounded-md border border-border bg-surface px-3 py-2 text-sm">
        <option value="domain">Domain</option><option value="repo">Repo</option>
        <option value="deployment">Deployment</option><option value="link">Link</option><option value="doc">Doku</option>
      </select>
      <input name="label" placeholder="Label" class="rounded-md border border-border bg-surface px-3 py-2 text-sm" />
      <input name="value" required placeholder="Wert (z. B. djouhri.de)" class="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm" />
      <input name="url" placeholder="URL (optional)" class="rounded-md border border-border bg-surface px-3 py-2 text-sm" />
      <Button type="submit" variant="primary" aria-label="Hinzufügen"><Icon name="plus" size={16} /></Button>
    </form>
    <ul class="divide-y divide-border rounded-lg border border-border text-sm">
      {#each uniqueBy(data.assets, (x) => x.id) as a (a.id)}
        <li class="flex items-center gap-3 px-3 py-2">
          <span class="rounded bg-surface-2 px-1.5 py-0.5 text-[11px] uppercase text-muted">{a.type}</span>
          <span class="font-medium">{a.label}</span>
          {#if a.url}<a href={a.url} class="text-accent-300 hover:text-accent-200" target="_blank" rel="noreferrer">{a.value}</a>{:else}<span class="text-muted">{a.value}</span>{/if}
          <form method="POST" action="?/deleteAsset" use:enhance class="ml-auto">
            <input type="hidden" name="id" value={a.id} /><button class="text-muted transition-colors duration-fast ease-saganta hover:text-fehler" aria-label="Löschen"><Icon name="x" size={14} /></button>
          </form>
        </li>
      {:else}
        <li class="px-3 py-2 text-muted">Keine Assets.</li>
      {/each}
    </ul>

  {:else if tab === 'Reviews'}
    <form method="POST" action="?/addReview" use:enhance class="mb-4 grid gap-3 rounded-lg border border-border bg-surface-2/40 p-3 sm:grid-cols-2">
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Entscheidung</span>
        <select name="decision" class="rounded-md border border-border bg-surface px-3 py-2">
          <option value="keep_active">Aktiv lassen</option>
          <option value="pause">Pausieren</option>
          <option value="prepare_public">Public vorbereiten</option>
          <option value="shutdown">Abschalten</option>
          <option value="archive">Archivieren</option>
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Neuer Status (optional)</span>
        <select name="new_status" class="rounded-md border border-border bg-surface px-3 py-2">
          <option value="">– nicht ändern –</option>
          {#each Object.entries(PROJECT_STATUS) as [v, l]}<option value={v}>{l}</option>{/each}
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm sm:col-span-2">
        <span class="text-muted">Notizen</span>
        <textarea name="notes" rows="2" class="rounded-md border border-border bg-surface px-3 py-2"></textarea>
      </label>
      <div class="sm:col-span-2"><Button type="submit" variant="primary">Review speichern</Button></div>
    </form>
    <form method="POST" action="?/ai" use:enhance class="mb-4">
      <input type="hidden" name="kind" value="review" />
      <Button variant="ghost" size="sm">KI: Review-Zusammenfassung</Button>
    </form>
    <ul class="divide-y divide-border rounded-lg border border-border text-sm">
      {#each uniqueBy(data.reviews, (x) => x.id) as r (r.id)}
        <li class="px-3 py-2">
          <div class="flex justify-between"><span class="font-medium">{r.decision}</span><span class="text-muted">{r.review_date}</span></div>
          {#if r.notes}<p class="text-muted">{r.notes}</p>{/if}
        </li>
      {:else}
        <li class="px-3 py-2 text-muted">Noch keine Reviews.</li>
      {/each}
    </ul>

  {:else if tab === 'Public Readiness'}
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

  {:else if tab === 'Client'}
    <form method="POST" action="?/updateProject" use:enhance class="grid gap-3 sm:grid-cols-2">
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Client-ID</span>
        <input name="client_id" value={p.client_id ?? ''} class="rounded-md border border-border bg-surface px-3 py-2" />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Handover-Status</span>
        <input name="handover_status" value={p.handover_status ?? ''} class="rounded-md border border-border bg-surface px-3 py-2" />
      </label>
      <label class="flex flex-col gap-1 text-sm sm:col-span-2">
        <span class="text-muted">Versprochener Scope</span>
        <textarea name="promised_scope" rows="2" class="rounded-md border border-border bg-surface px-3 py-2">{p.promised_scope ?? ''}</textarea>
      </label>
      <label class="flex flex-col gap-1 text-sm sm:col-span-2">
        <span class="text-muted">Kommunikations-Notizen</span>
        <textarea name="communication_notes" rows="2" class="rounded-md border border-border bg-surface px-3 py-2">{p.communication_notes ?? ''}</textarea>
      </label>
      <div class="sm:col-span-2"><Button type="submit" variant="primary">Speichern</Button></div>
    </form>

  {:else if tab === 'Shutdown'}
    <form method="POST" action="?/ai" use:enhance class="mb-4">
      <input type="hidden" name="kind" value="shutdown" />
      <Button variant="ghost" size="sm">KI: Shutdown-Empfehlung</Button>
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
