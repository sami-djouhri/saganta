<script lang="ts">
  import { enhance } from '$app/forms';
  import type { ActionData, PageData } from './$types';
  import type { Eintrag } from './+page.server';

  interface Props {
    data: PageData;
    form: ActionData;
  }
  let { data, form }: Props = $props();

  const TAGE = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];
  const ARTEN: Record<Eintrag['art'], string> = {
    arbeit: 'Gearbeitet',
    ausgleich: 'Freizeitausgleich',
    krank_frueher: 'Krank früher gegangen',
  };

  function zahl(x: number | null | undefined): string {
    return x == null ? '–' : String(Math.round(x * 10) / 10).replace('.', ',');
  }

  function stunden(min: number, vorzeichen = false): string {
    const b = Math.abs(min);
    const t = `${Math.floor(b / 60)}:${String(b % 60).padStart(2, '0')}`;
    if (min < 0) return '−' + t;
    return vorzeichen && min > 0 ? '+' + t : t;
  }

  function datum(iso: string): string {
    const [j, m, t] = iso.split('-');
    return `${Number(t)}.${Number(m)}.${j}`;
  }

  const heute = new Date().toISOString().slice(0, 10);
  let art = $state<Eintrag['art']>('arbeit');
  const b = $derived(data.bilanz);
  const k = $derived(data.konto);
  const sp = $derived(data.plan);
  const spTag = $derived(data.tag ?? heute);
  const spWochentag = $derived((new Date(spTag + 'T12:00:00').getDay() + 6) % 7);
  const spStunden = $derived(sp?.stunden[String(spWochentag)] ?? []);
  const spAusfall = $derived(new Set(sp?.ausfall[spTag] ?? []));
  function tagText(liste: { fach: string; von: string; bis: string }[]): string {
    return liste.map((s) => `${s.von}-${s.bis} ${s.fach}`).join('\n');
  }
</script>

<svelte:head><title>Urlaub & Zeitkonto · Kalender</title></svelte:head>

<section class="mx-auto max-w-2xl space-y-6 px-4 py-6">
  <header class="flex items-center justify-between gap-3">
    <div>
      <p class="font-mono text-xs uppercase tracking-widest text-muted">Saganta · Kalender</p>
      <h1 class="font-display text-3xl">Urlaub & Zeitkonto</h1>
    </div>
    <a href="/" class="rounded-lg border border-border-stark px-4 py-2 text-sm text-muted hover:text-text">Zurück</a>
  </header>

  {#if data.fehler}
    <p class="text-sm text-kupfer">{data.fehler}</p>
  {/if}

  {#if b}
    <div class="space-y-3 rounded-xl border border-border bg-surface-2/60 p-4">
      <div class="flex items-center justify-between gap-2">
        <h2 class="font-medium">Urlaub {data.jahr}</h2>
        <div class="flex gap-2 text-sm">
          <a href="?jahr={data.jahr - 1}" class="rounded-lg border border-border-stark px-3 py-1 text-muted hover:text-text">‹</a>
          <a href="?jahr={data.jahr + 1}" class="rounded-lg border border-border-stark px-3 py-1 text-muted hover:text-text">›</a>
        </div>
      </div>
      {#if b.rest_nach_plan != null}
        <p class="font-display text-4xl {b.rest_nach_plan < 0 ? 'text-kupfer' : ''}">
          {zahl(b.rest_nach_plan)} <span class="text-base text-muted">Tage übrig nach Plan</span>
        </p>
      {/if}
      <dl class="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <dt class="text-muted">Genommen</dt><dd class="text-right">{zahl(b.genommen ?? b.verbraucht)}</dd>
        <dt class="text-muted">Geplant</dt><dd class="text-right">{zahl(b.geplant)}</dd>
        <dt class="text-muted">Anspruch</dt><dd class="text-right">{zahl(b.anspruch)}</dd>
        {#if b.uebertrag && b.uebertrag.tage > 0}
          <dt class="text-muted">Rest aus dem Vorjahr</dt><dd class="text-right">{zahl(b.uebertrag.tage)}</dd>
          {#if b.uebertrag.offen > 0}
            <dt class="text-kupfer">offen bis {datum(b.uebertrag.verfall)}</dt><dd class="text-right text-kupfer">{zahl(b.uebertrag.offen)}</dd>
          {/if}
          {#if b.uebertrag.verfallen > 0}
            <dt class="text-muted">verfallen</dt><dd class="text-right">{zahl(b.uebertrag.verfallen)}</dd>
          {/if}
        {/if}
      </dl>
      <form method="POST" action="?/anspruch" use:enhance class="flex flex-wrap items-end gap-2">
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Anspruch im Jahr (Tage)</span>
          <input name="anspruch" inputmode="decimal" value={b.anspruch ?? ''} class="min-h-11 w-28 rounded-lg border border-border-stark bg-surface px-3 text-text" />
        </label>
        <button type="submit" class="min-h-11 rounded-lg border border-border-stark px-4 text-sm text-muted hover:text-text">Speichern</button>
      </form>
      <p class="text-xs text-muted">Nur Arbeitstage zählen, halbe Tage halb. Tage bis zum Stichtag nehmen zuerst den Rest aus dem Vorjahr.</p>
      <form method="POST" action="?/tagestyp" use:enhance class="flex flex-wrap items-end gap-2 border-t border-border pt-3">
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Von</span>
          <input type="date" name="von" required class="min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Bis (leer = ein Tag)</span>
          <input type="date" name="bis" class="min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Tagestyp</span>
          <select name="typ" class="min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text">
            <option value="urlaub">Urlaub</option>
            <option value="krank">Krank</option>
            <option value="arbeit">Arbeit</option>
            <option value="schule">Schule</option>
            <option value="frei">Frei (Eintrag entfernen)</option>
          </select>
        </label>
        <label class="flex min-h-11 items-center gap-2 text-sm text-muted">
          <input type="checkbox" name="halb" /> halber Tag
        </label>
        <label class="flex min-h-11 items-center gap-2 text-sm text-muted">
          <input type="checkbox" name="wochenende" /> auch Wochenenden
        </label>
        <button type="submit" class="min-h-11 rounded-lg border border-border-stark px-4 text-sm text-muted hover:text-text">Eintragen</button>
      </form>
    </div>
  {/if}

  {#if k}
    <div class="space-y-3 rounded-xl border border-border bg-surface-2/60 p-4">
      <h2 class="font-medium">Zeitkonto</h2>
      <p class="font-display text-4xl {k.saldo < 0 ? 'text-kupfer' : ''}">
        {stunden(k.saldo, true)} <span class="text-base text-muted">Stunden</span>
      </p>
      <p class="text-xs text-muted">Nur Tage mit Eintrag zählen. Ein Arbeitstag ohne Eintrag gilt als nach Plan gearbeitet; Schule, Urlaub und Krank gelten als Soll erfüllt.</p>

      <form method="POST" action="?/eintragen" use:enhance class="grid gap-3 sm:grid-cols-2">
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Tag</span>
          <input type="date" name="tag" value={heute} required class="min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Art</span>
          <select name="art" bind:value={art} class="min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text">
            {#each Object.entries(ARTEN) as [wert, text] (wert)}<option value={wert}>{text}</option>{/each}
          </select>
        </label>
        {#if art === 'arbeit'}
          <label class="flex flex-col gap-1 text-sm">
            <span class="text-muted">Beginn</span>
            <input type="time" name="von" value="07:00" step="300" class="min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text" />
          </label>
          <label class="flex flex-col gap-1 text-sm">
            <span class="text-muted">Ende (Pause wird abgezogen)</span>
            <input type="time" name="bis" value="16:00" step="300" class="min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text" />
          </label>
        {/if}
        <label class="flex flex-col gap-1 text-sm sm:col-span-2">
          <span class="text-muted">Notiz (optional)</span>
          <input name="notiz" maxlength="200" class="min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text" />
        </label>
        <div class="flex justify-end sm:col-span-2">
          <button type="submit" class="min-h-11 rounded-lg bg-accent-500 px-4 text-sm font-medium text-accent-ink hover:bg-accent-400">Eintragen</button>
        </div>
      </form>

      {#if k.eintraege.length}
        <ul class="divide-y divide-border overflow-hidden rounded-lg border border-border">
          {#each k.eintraege as e (e.datum)}
            <li class="flex items-center gap-3 px-3 py-2">
              <span class="min-w-0 flex-1">
                <span class="block font-medium">{datum(e.datum)}</span>
                <span class="block text-xs text-muted">
                  {e.art === 'arbeit' ? `${e.von && e.bis ? `${e.von} bis ${e.bis}, ` : ''}${stunden(e.ist)} h gearbeitet` : ARTEN[e.art]}{e.notiz ? ` · ${e.notiz}` : ''}
                </span>
              </span>
              <span class="font-medium {e.abweichung < 0 ? 'text-kupfer' : ''}">{stunden(e.abweichung, true)}</span>
              <form method="POST" action="?/loeschen" use:enhance>
                <input type="hidden" name="tag" value={e.datum} />
                <button type="submit" class="min-h-11 rounded-lg border border-border-stark px-3 text-sm text-muted hover:text-kupfer">Löschen</button>
              </form>
            </li>
          {/each}
        </ul>
      {/if}

      <form method="POST" action="?/plan" use:enhance class="space-y-2">
        <h3 class="text-sm font-medium">Wochenplan</h3>
        <div class="grid grid-cols-[3rem_1fr_1fr] items-center gap-2 text-sm">
          <span></span><span class="text-muted">Soll (h:mm)</span><span class="text-muted">Pause (min)</span>
          {#each TAGE as name, wt (name)}
            <span class="font-medium">{name}</span>
            <input name="soll-{wt}" value={stunden(k.plan[String(wt)]?.soll ?? 0)} class="min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text" aria-label="Soll {name}" />
            <input name="pause-{wt}" inputmode="numeric" value={k.plan[String(wt)]?.pause ?? 0} class="min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text" aria-label="Pause {name}" />
          {/each}
        </div>
        <div class="flex justify-end">
          <button type="submit" class="min-h-11 rounded-lg border border-border-stark px-4 text-sm text-muted hover:text-text">Plan speichern</button>
        </div>
      </form>
    </div>
  {/if}

  {#if sp}
    <div class="space-y-3 rounded-xl border border-border bg-surface-2/60 p-4">
      <h2 class="font-medium">Stundenplan</h2>
      <form method="GET" class="flex flex-wrap items-end gap-2">
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-muted">Tag</span>
          <input type="date" name="tag" value={spTag} class="min-h-11 rounded-lg border border-border-stark bg-surface px-3 text-text" />
        </label>
        <input type="hidden" name="jahr" value={data.jahr} />
        <button type="submit" class="min-h-11 rounded-lg border border-border-stark px-4 text-sm text-muted hover:text-text">Zeigen</button>
      </form>
      {#if spStunden.length}
        <ul class="divide-y divide-border overflow-hidden rounded-lg border border-border">
          {#each spStunden as s (s.von)}
            {@const aus = spAusfall.has(s.von)}
            <li class="flex items-center gap-3 px-3 py-2">
              <span class="min-w-0 flex-1 {aus ? 'text-muted line-through' : ''}">{s.von}–{s.bis} {s.fach}</span>
              <form method="POST" action="?/ausfall" use:enhance>
                <input type="hidden" name="datum" value={spTag} />
                <input type="hidden" name="von" value={s.von} />
                <input type="hidden" name="ausgefallen" value={aus ? 'false' : 'true'} />
                <button type="submit" class="min-h-11 rounded-lg border border-border-stark px-3 text-sm text-muted hover:text-text">{aus ? 'findet statt' : 'fällt aus'}</button>
              </form>
            </li>
          {/each}
        </ul>
        <p class="text-xs text-muted">An einem Schultag folgen Beginn und Ende des Tages den verbleibenden Stunden.</p>
      {:else}
        <p class="text-sm text-muted">An diesem Wochentag stehen keine Stunden im Plan.</p>
      {/if}
      {#if form && 'ausfallErgebnis' in form && form.ausfallErgebnis}
        <p class="text-sm text-muted" role="status">
          {#if form.ausfallErgebnis.alle_ausgefallen}Alle Stunden fallen aus. Der Tag bleibt Schultag; „frei“ setzt du im Kalender.
          {:else if form.ausfallErgebnis.zeiten}Schultag jetzt {form.ausfallErgebnis.zeiten.von} bis {form.ausfallErgebnis.zeiten.bis}.
          {:else}Vermerkt (kein Schultag eingetragen).{/if}
        </p>
      {/if}
      <form method="POST" action="?/stundenplan" use:enhance class="space-y-2">
        <h3 class="text-sm font-medium">Wochenraster, eine Zeile je Stunde: „08:00-09:30 Deutsch“</h3>
        {#each TAGE.slice(0, 6) as name, wt (name)}
          <label class="flex flex-col gap-1 text-sm">
            <span class="text-muted">{name}</span>
            <textarea name="tag-{wt}" rows="3" class="rounded-lg border border-border-stark bg-surface px-3 py-2 font-mono text-sm text-text" value={tagText(sp.stunden[String(wt)] ?? [])}></textarea>
          </label>
        {/each}
        <div class="flex justify-end">
          <button type="submit" class="min-h-11 rounded-lg border border-border-stark px-4 text-sm text-muted hover:text-text">Stundenplan speichern</button>
        </div>
      </form>
    </div>
  {/if}

  {#if form && 'fehler' in form && form.fehler}
    <p class="text-sm text-kupfer" role="alert">{form.fehler}</p>
  {:else if form && 'gespeichert' in form}
    <p class="text-sm text-muted" role="status">Gespeichert.</p>
  {/if}
</section>
