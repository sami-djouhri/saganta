<script lang="ts">
  import { enhance } from '$app/forms';
  import type { ActionData, PageData } from './$types';
  import type { Gewohnheit } from './+page.server';

  interface Props {
    data: PageData;
    form: ActionData;
  }
  let { data, form }: Props = $props();

  const ARTEN: Record<string, string> = {
    lernen: 'Lernen',
    lesen: 'Lesen',
    sport: 'Sport',
    hobby: 'Hobby',
    sonstige: 'Sonstiges',
  };

  // Vorgaben wie im Dienst (HabitCreate), damit eine hier angelegte Gewohnheit
  // genauso arbeitet wie eine aus der App.
  const NEU: Omit<Gewohnheit, 'id'> = {
    name: '',
    color: '#4a9eff',
    category: 'sonstige',
    target_hours_per_week: 6,
    session_duration_minutes: 90,
    weekday_start: '17:00',
    weekday_end: '20:00',
    weekend_start: '10:00',
    weekend_end: '18:00',
    active: true,
    learning_mode: false,
    focus_block_minutes: 25,
    break_minutes: 5,
  };

  let lernmodus = $state<Record<string, boolean>>({});
  const lern = (id: string, g: Omit<Gewohnheit, 'id'>) => lernmodus[id] ?? g.learning_mode;

  function zahl(x: number): string {
    return String(Math.round(x * 10) / 10).replace('.', ',');
  }

  const feld = 'min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text';
  const knopf = 'min-h-11 rounded-lg border border-border-stark px-4 text-sm text-muted hover:text-text';
</script>

<svelte:head><title>Gewohnheiten · Kalender</title></svelte:head>

{#snippet formular(id: string, g: Omit<Gewohnheit, 'id'>, aktion: string)}
  <form method="POST" action="?/{aktion}" use:enhance class="grid gap-3 sm:grid-cols-2">
    {#if id !== 'neu'}<input type="hidden" name="id" value={id} />{/if}
    <label class="flex flex-col gap-1 text-sm sm:col-span-2">
      <span class="text-muted">Name</span>
      <input name="name" required maxlength="200" value={g.name} class={feld} />
    </label>
    <label class="flex flex-col gap-1 text-sm">
      <span class="text-muted">Art</span>
      <select name="category" class={feld}>
        {#each Object.entries(ARTEN) as [wert, text] (wert)}
          <option value={wert} selected={g.category === wert}>{text}</option>
        {/each}
      </select>
    </label>
    <label class="flex flex-col gap-1 text-sm">
      <span class="text-muted">Farbe</span>
      <input type="color" name="color" value={g.color} class="{feld} w-20 py-1" />
    </label>
    <label class="flex flex-col gap-1 text-sm">
      <span class="text-muted">Ziel je Woche (Stunden)</span>
      <input name="target_hours_per_week" inputmode="decimal" required value={zahl(g.target_hours_per_week)} class={feld} />
    </label>
    <label class="flex flex-col gap-1 text-sm">
      <span class="text-muted">Länge einer Sitzung (Minuten)</span>
      <input name="session_duration_minutes" type="number" min="15" max="480" step="5" required value={g.session_duration_minutes} class={feld} />
    </label>
    <fieldset class="flex flex-wrap items-end gap-2 text-sm">
      <legend class="mb-1 text-muted">Mo bis Fr zwischen</legend>
      <input type="time" name="weekday_start" required value={g.weekday_start} class={feld} />
      <span class="pb-3 text-muted">und</span>
      <input type="time" name="weekday_end" required value={g.weekday_end} class={feld} />
    </fieldset>
    <fieldset class="flex flex-wrap items-end gap-2 text-sm">
      <legend class="mb-1 text-muted">Sa und So zwischen</legend>
      <input type="time" name="weekend_start" required value={g.weekend_start} class={feld} />
      <span class="pb-3 text-muted">und</span>
      <input type="time" name="weekend_end" required value={g.weekend_end} class={feld} />
    </fieldset>
    <label class="flex min-h-11 items-center gap-2 text-sm text-muted sm:col-span-2">
      <input
        type="checkbox"
        name="learning_mode"
        checked={lern(id, g)}
        onchange={(e) => (lernmodus[id] = e.currentTarget.checked)}
      />
      Lernmodus (Fokusblöcke mit Pausen)
    </label>
    {#if lern(id, g)}
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Fokusblock (Minuten)</span>
        <input name="focus_block_minutes" type="number" min="5" max="120" value={g.focus_block_minutes} class={feld} />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-muted">Pause (Minuten)</span>
        <input name="break_minutes" type="number" min="1" max="30" value={g.break_minutes} class={feld} />
      </label>
    {/if}
    {#if form?.fehler && form.id === id}
      <p class="text-sm text-kupfer sm:col-span-2">{form.fehler}</p>
    {/if}
    <div class="sm:col-span-2">
      <button type="submit" class="min-h-11 rounded-lg bg-accent-500 px-4 text-sm font-medium text-accent-ink hover:bg-accent-400">
        {id === 'neu' ? 'Anlegen' : 'Speichern'}
      </button>
    </div>
  </form>
{/snippet}

<section class="mx-auto max-w-2xl space-y-6 px-4 py-6">
  <header class="flex items-center justify-between gap-3">
    <div>
      <p class="font-mono text-xs uppercase tracking-widest text-muted">Saganta · Kalender</p>
      <h1 class="font-display text-3xl">Gewohnheiten</h1>
    </div>
    <a href="/" class="rounded-lg border border-border-stark px-4 py-2 text-sm text-muted hover:text-text">Zurück</a>
  </header>

  <p class="text-sm text-muted">
    Der Kalender legt die Sitzungen selbst in freie Zeit innerhalb der Fenster und meldet sie per Push.
    Jede Änderung plant die nächsten Wochen neu.
  </p>

  {#if data.fehler}
    <p class="text-sm text-kupfer">{data.fehler}</p>
  {/if}
  {#if form?.gespeichert}
    <p class="text-sm text-erfolg">{form.gespeichert}: gespeichert.</p>
  {/if}

  {#each data.gewohnheiten as g (g.id)}
    <details class="rounded-xl border border-border bg-surface-2/60 p-4" open={form?.id === g.id}>
      <summary class="flex cursor-pointer list-none items-center justify-between gap-3">
        <span class="flex min-w-0 items-center gap-2">
          <span class="h-3 w-3 shrink-0 rounded-full" style:background-color={g.color}></span>
          <span class="truncate font-medium {g.active ? '' : 'text-muted'}">{g.name}</span>
          {#if !g.active}<span class="text-xs text-muted">pausiert</span>{/if}
        </span>
        <span class="shrink-0 font-mono text-xs tabular-nums text-muted">
          {ARTEN[g.category] ?? g.category} · {zahl(g.target_hours_per_week)} h/Woche · {g.session_duration_minutes} min
        </span>
      </summary>
      <div class="mt-4 space-y-4 border-t border-border pt-4">
        {@render formular(g.id, g, 'aendern')}
        <div class="flex flex-wrap gap-2 border-t border-border pt-3">
          <form method="POST" action="?/pausieren" use:enhance>
            <input type="hidden" name="id" value={g.id} />
            <input type="hidden" name="aktiv" value={g.active ? '0' : '1'} />
            <button type="submit" class={knopf}>{g.active ? 'Pausieren' : 'Fortsetzen'}</button>
          </form>
          <form
            method="POST"
            action="?/loeschen"
            use:enhance={({ cancel }) => {
              if (!confirm(`„${g.name}" löschen? Auch die erledigten Sitzungen verschwinden aus der Statistik. Pausieren behält sie.`)) cancel();
            }}
          >
            <input type="hidden" name="id" value={g.id} />
            <button type="submit" class="{knopf} hover:text-kupfer">Löschen</button>
          </form>
        </div>
      </div>
    </details>
  {:else}
    {#if !data.fehler}
      <p class="text-sm text-muted">Noch keine Gewohnheiten.</p>
    {/if}
  {/each}

  <details class="rounded-xl border border-border bg-surface-2/60 p-4" open={form?.id === 'neu' || data.gewohnheiten.length === 0}>
    <summary class="cursor-pointer list-none font-medium">+ Neue Gewohnheit</summary>
    <div class="mt-4 border-t border-border pt-4">
      {@render formular('neu', NEU, 'anlegen')}
    </div>
  </details>
</section>
