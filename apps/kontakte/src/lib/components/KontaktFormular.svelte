<script lang="ts">
  import { untrack } from 'svelte';
  import { enhance } from '$app/forms';
  import { Button, Icon } from '@saganta/ui';
  import type { Jahrestag, Kontakt } from '$lib/typen';

  interface Props {
    kontakt?: Kontakt | null;
    gruppen: string[];
    aktion: string;
    knopf: string;
  }
  let { kontakt = null, gruppen, aktion, knopf }: Props = $props();

  // Nur der Anfangsstand: die Seite baut das Formular nach dem Speichern neu ({#key}).
  let jahrestage = $state<Jahrestag[]>(untrack(() => kontakt?.jahrestage.map((j) => ({ ...j })) ?? []));
  let sendet = $state(false);

  const feldKlasse =
    'w-full rounded-md border border-border-stark bg-surface-2 px-3 py-2 text-sm outline-none focus:border-akzent';
</script>

<form
  method="POST"
  action={aktion}
  class="space-y-4"
  use:enhance={() => {
    sendet = true;
    return async ({ update }) => {
      await update({ reset: false });
      sendet = false;
    };
  }}
>
  <label class="block space-y-1">
    <span class="text-sm text-muted">Name</span>
    <input name="name" required maxlength="200" value={kontakt?.name ?? ''} class={feldKlasse} autocomplete="off" />
  </label>

  <div class="grid gap-4 sm:grid-cols-2">
    <label class="block space-y-1">
      <span class="text-sm text-muted">Telefon</span>
      <input name="telefon" type="tel" maxlength="50" value={kontakt?.telefon ?? ''} class={feldKlasse} />
    </label>
    <label class="block space-y-1">
      <span class="text-sm text-muted">Mail</span>
      <input name="email" type="email" maxlength="300" value={kontakt?.email ?? ''} class={feldKlasse} />
    </label>
  </div>

  <label class="block space-y-1">
    <span class="text-sm text-muted">Adresse</span>
    <input name="adresse" maxlength="300" value={kontakt?.adresse ?? ''} class={feldKlasse} />
  </label>

  <div class="grid gap-4 sm:grid-cols-2">
    <label class="block space-y-1">
      <span class="text-sm text-muted">Geburtstag</span>
      <input name="geburtstag" type="date" value={kontakt?.geburtstag ?? ''} class={feldKlasse} />
    </label>
    <label class="block space-y-1">
      <span class="text-sm text-muted">Gruppe</span>
      <input name="gruppe" maxlength="60" list="gruppen-liste" value={kontakt?.gruppe ?? ''} class={feldKlasse} placeholder="z. B. Familie" />
      <datalist id="gruppen-liste">
        {#each gruppen as g (g)}<option value={g}></option>{/each}
      </datalist>
    </label>
  </div>

  <fieldset class="space-y-2">
    <legend class="text-sm text-muted">Jahrestage</legend>
    {#each jahrestage as j, i (i)}
      <div class="flex gap-2">
        <input name="jt_bezeichnung" bind:value={j.bezeichnung} maxlength="80" placeholder="z. B. Hochzeitstag" aria-label="Bezeichnung" class={feldKlasse} />
        <input name="jt_datum" type="date" bind:value={j.datum} aria-label="Datum" class="{feldKlasse} max-w-44" />
        <button
          type="button"
          class="rounded-md border border-border px-2 text-muted hover:text-text"
          aria-label="Jahrestag entfernen"
          onclick={() => (jahrestage = jahrestage.filter((_, k) => k !== i))}><Icon name="x" size={14} /></button
        >
      </div>
    {/each}
    <button
      type="button"
      class="inline-flex items-center gap-1.5 text-sm text-muted hover:text-text"
      onclick={() => (jahrestage = [...jahrestage, { bezeichnung: '', datum: '' }])}
    >
      <Icon name="plus" size={14} /> Jahrestag
    </button>
    <p class="text-xs text-muted">Geburtstage und Jahrestage stehen im Kalender. Erinnerung kommt am Tag und drei Tage vorher.</p>
  </fieldset>

  <label class="block space-y-1">
    <span class="text-sm text-muted">Notiz</span>
    <textarea name="notiz" rows="3" maxlength="10000" class={feldKlasse}>{kontakt?.notiz ?? ''}</textarea>
  </label>

  <Button type="submit" disabled={sendet}>{sendet ? 'Speichert…' : knopf}</Button>
</form>
