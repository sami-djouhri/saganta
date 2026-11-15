<script lang="ts">
  import { enhance } from '$app/forms';
  import { Icon, NotizenBlock } from '@saganta/ui';
  import type { NotizKurz } from '@saganta/notizen-anschluss';
  import type { KalenderEvent, Konflikt, KonfliktVorschlag, KonfliktWeg } from '$lib/kalender-bff';
  import { startOf, endOf, fmtTime } from '$lib/cal';

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
    onClose,
  }: Props = $props();

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
        <h3 class="font-display text-2xl">{istVorkommen ? 'Dieses Vorkommen' : editing ? 'Termin bearbeiten' : 'Neuer Termin'}</h3>
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
          disabled={istVorkommen}
          value={editing?.title ?? ''}
          class="w-full rounded-lg border border-border-stark bg-surface px-3 py-2 text-sm outline-none focus:border-accent-400"
        />
      </label>

      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Kalender</span>
          <select
            name="calendar_id"
            disabled={istVorkommen}
            class="w-full rounded-lg border border-border-stark bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
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
            disabled={istVorkommen}
            value={editing?.location ?? ''}
            class="w-full rounded-lg border border-border-stark bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
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
            class="w-full rounded-lg border border-border-stark bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
          />
        </label>
        <label class="block space-y-1">
          <span class="text-xs uppercase tracking-wider text-muted">Ende</span>
          <input
            type="datetime-local"
            name="end"
            value={endValue}
            class="w-full rounded-lg border border-border-stark bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
          />
        </label>
      </div>

      <label class="flex items-center gap-2 text-sm text-muted">
        <input type="checkbox" name="all_day" disabled={istVorkommen} checked={editing?.all_day ?? false} />
        Ganztägig (Uhrzeit wird ignoriert)
      </label>

      {#if istVorkommen}
        <p class="rounded-lg border border-border bg-surface px-3 py-2 text-xs text-muted">
          Wiederkehrender Termin. Die Zeit oben gilt nur für dieses Vorkommen, die Reihe bleibt
          unverändert. Titel und Wiederholung änderst du in der Agenda.
        </p>
      {/if}

      <label class="block space-y-1">
        <span class="text-xs uppercase tracking-wider text-muted">Aktivität (für Feedback & Planung)</span>
        <select
          name="activity_type"
          disabled={istVorkommen}
          class="w-full rounded-lg border border-border-stark bg-surface px-2 py-2 text-sm text-text outline-none focus:border-accent-400"
        >
          <option value="" selected={!editing?.activity_type}>kein (normaler Termin)</option>
          <option value="lernen" selected={editing?.activity_type === 'lernen'}>Lernen</option>
          <option value="sport" selected={editing?.activity_type === 'sport'}>Sport</option>
          <option value="lesen" selected={editing?.activity_type === 'lesen'}>Lesen</option>
          <option value="hobby" selected={editing?.activity_type === 'hobby'}>Hobby</option>
          <option value="sonstige" selected={editing?.activity_type === 'sonstige'}>Sonstige</option>
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
          class="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-text"
          >Abbrechen</button
        >
        <button
          type="submit"
          class="rounded-lg bg-accent-500 px-5 py-2 text-sm font-medium text-accent-ink hover:bg-accent-400"
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
                  class="rounded-lg border border-border px-3 py-1.5 text-xs text-text hover:bg-white/5"
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
              use:enhance={() => async ({ result, update }) => { await update(); if (result.type === 'success') onClose(); }}
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
