<script lang="ts">
  import { enhance } from '$app/forms';
  import { Icon } from '@saganta/ui';
  import type { KalenderEvent } from '$lib/kalender-bff';
  import { startOf, endOf } from '$lib/cal';

  interface Props {
    open: boolean;
    editing: KalenderEvent | null;
    editableCalendars: { id: string; name?: string; title?: string }[];
    defaultDate: string; // YYYY-MM-DD (heute)
    prefillDate?: string;
    prefillStart?: string; // HH:MM
    prefillEnd?: string;
    formError?: string | null;
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
    onClose,
  }: Props = $props();

  // naive ISO "2026-07-18T15:00:00" → datetime-local "2026-07-18T15:00"
  const toLocalInput = (iso: string): string => (iso ?? '').slice(0, 16);
  const dateBase = $derived(prefillDate || defaultDate);
  const startValue = $derived(
    editing ? toLocalInput(startOf(editing)) : `${dateBase}T${prefillStart || '09:00'}`,
  );
  const endValue = $derived(
    editing ? toLocalInput(endOf(editing)) : `${dateBase}T${prefillEnd || '10:00'}`,
  );

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
    <form
      method="POST"
      action={editing ? '?/eventUpdate' : '?/eventCreate'}
      use:enhance={() =>
        async ({ result, update }) => {
          await update({ reset: false });
          if (result.type === 'success') onClose();
        }}
      class="w-full max-w-lg space-y-4 rounded-2xl border border-border bg-surface-2 p-6 shadow-2xl"
    >
      <div class="flex items-center justify-between">
        <h3 class="font-display text-2xl">{editing ? 'Termin bearbeiten' : 'Neuer Termin'}</h3>
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
          value={editing?.title ?? ''}
          class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent-400"
        />
      </label>

      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Kalender</span>
          <select
            name="calendar_id"
            class="w-full rounded-lg border border-border bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
          >
            {#each editableCalendars as c (c.id)}
              <option value={c.id} selected={editing?.calendar_id === c.id}
                >{c.name ?? c.title ?? c.id}</option
              >
            {/each}
          </select>
        </label>
        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Ort (optional)</span>
          <input
            name="location"
            value={editing?.location ?? ''}
            class="w-full rounded-lg border border-border bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
          />
        </label>
      </div>

      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Start</span>
          <input
            type="datetime-local"
            name="start"
            required
            value={startValue}
            class="w-full rounded-lg border border-border bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
          />
        </label>
        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Ende</span>
          <input
            type="datetime-local"
            name="end"
            value={endValue}
            class="w-full rounded-lg border border-border bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
          />
        </label>
      </div>

      <label class="flex items-center gap-2 text-sm text-muted">
        <input type="checkbox" name="all_day" checked={editing?.all_day ?? false} />
        Ganztägig (Uhrzeit wird ignoriert)
      </label>

      <label class="block space-y-1">
        <span class="text-xs uppercase tracking-wider text-muted">Aktivität (für Feedback & Planung)</span>
        <select
          name="activity_type"
          class="w-full rounded-lg border border-border bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
        >
          <option value="" selected={!editing?.activity_type}>kein (normaler Termin)</option>
          <option value="lernen" selected={editing?.activity_type === 'lernen'}>Lernen</option>
          <option value="sport" selected={editing?.activity_type === 'sport'}>Sport</option>
          <option value="lesen" selected={editing?.activity_type === 'lesen'}>Lesen</option>
          <option value="hobby" selected={editing?.activity_type === 'hobby'}>Hobby</option>
          <option value="sonstige" selected={editing?.activity_type === 'sonstige'}>Sonstige</option>
        </select>
        <span class="block text-[11px] text-muted">Markierte Aktivitäten kannst du danach kurz bewerten.</span>
      </label>

      {#if formError}
        <p class="rounded-lg border border-warm-500/40 bg-warm-500/10 px-3 py-2 text-sm text-warm-500">
          {formError}
        </p>
      {/if}

      <div class="flex justify-end gap-2 pt-1">
        <button
          type="button"
          onclick={onClose}
          class="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-text"
          >Abbrechen</button
        >
        <button
          type="submit"
          class="rounded-lg bg-accent-500 px-5 py-2 text-sm font-medium text-accent-ink hover:bg-accent-400"
          >{editing ? 'Speichern' : 'Anlegen'}</button
        >
      </div>
    </form>
  </div>
{/if}
