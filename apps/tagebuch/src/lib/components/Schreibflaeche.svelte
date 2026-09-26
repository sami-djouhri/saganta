<script lang="ts">
  /**
   * Die Seite, auf die geschrieben wird.
   *
   * Zwei Dinge sind hier bewusst gebaut und nicht selbstverständlich:
   *
   * 1. **Automatisches Speichern.** Bei einem Tagebuch ist verlorener Text der
   *    schlimmste Fehler, den die App machen kann, schlimmer als ein Absturz:
   *    was weg ist, kann niemand rekonstruieren. Gespeichert wird deshalb nach
   *    kurzer Ruhe von selbst, zusätzlich beim Tageswechsel und beim Verlassen.
   *
   * 2. **Der Vergleich mit dem geladenen Stand.** Ohne ihn löste jeder
   *    Tageswechsel ein Speichern aus, weil das Befüllen des Textfeldes wie
   *    eine Änderung aussieht. Das Ergebnis wäre ein Eintrag mit heutigem
   *    Änderungsdatum an jedem Tag, den man nur angesehen hat.
   */
  import { Button, Icon } from '@saganta/ui';
  import {
    eintragEntschluesseln,
    eintragVerschluesseln,
    KryptoFehler,
    type Eintragsinhalt,
  } from '$lib/krypto';
  import { tresor } from '$lib/tresor.svelte';
  import type { Tageskontext } from '$lib/kontext';
  import { langformat } from '$lib/datum';

  interface Props {
    tag: string;
    verschluesselt: { chiffrat: string; iv: string } | null;
    kontext: Tageskontext;
    heute: string;
    gespeichert?: () => void;
  }
  let { tag, verschluesselt, kontext, heute, gespeichert }: Props = $props();

  const STIMMUNGEN = [
    { wert: 'gut', label: 'gut' },
    { wert: 'neutral', label: 'neutral' },
    { wert: 'mies', label: 'mies' },
  ] as const;
  const ENERGIEN = [
    { wert: 'hoch', label: 'hoch' },
    { wert: 'mittel', label: 'mittel' },
    { wert: 'niedrig', label: 'niedrig' },
  ] as const;
  const SCHLAF = [
    { wert: 'gut', label: 'gut' },
    { wert: 'mittel', label: 'mittel' },
    { wert: 'schlecht', label: 'schlecht' },
  ] as const;

  const RUHE_MS = 2500;

  let inhalt = $state<Eintragsinhalt>({ text: '', stimmung: null, energie: null, schlaf: null });
  let geladenerStand = $state('');
  let zustand = $state<'leer' | 'laedt' | 'bereit' | 'speichert' | 'fehler'>('laedt');
  let meldung = $state('');
  let zuletzt = $state('');
  let uhr: ReturnType<typeof setTimeout> | undefined;

  let jetzigerStand = $derived(JSON.stringify(inhalt));
  let ungespeichert = $derived(zustand === 'bereit' && jetzigerStand !== geladenerStand);
  let leer = $derived(
    !inhalt.text.trim() && !inhalt.stimmung && !inhalt.energie && !inhalt.schlaf,
  );

  // Tageswechsel: entschlüsseln, was da ist, sonst ein leeres Blatt.
  $effect(() => {
    const dek = tresor.dek;
    const paket = verschluesselt;
    void tag;
    if (!dek) return;

    zustand = 'laedt';
    (async () => {
      if (!paket) {
        inhalt = { text: '', stimmung: null, energie: null, schlaf: null };
        geladenerStand = JSON.stringify(inhalt);
        zustand = 'bereit';
        return;
      }
      try {
        inhalt = await eintragEntschluesseln(paket, dek);
        geladenerStand = JSON.stringify(inhalt);
        zustand = 'bereit';
      } catch (e) {
        meldung =
          e instanceof KryptoFehler
            ? 'Dieser Eintrag lässt sich mit dem geöffneten Schlüssel nicht lesen.'
            : 'Der Eintrag konnte nicht geöffnet werden.';
        zustand = 'fehler';
      }
    })();
  });

  // Automatisches Speichern nach kurzer Ruhe.
  $effect(() => {
    void jetzigerStand;
    if (!ungespeichert) return;
    clearTimeout(uhr);
    uhr = setTimeout(() => void speichern(), RUHE_MS);
    return () => clearTimeout(uhr);
  });

  // Beim Verlassen der Seite noch schnell sichern. `visibilitychange` fängt
  // auch das Wegwischen auf dem Handy, wo `beforeunload` nicht zuverlässig ist.
  $effect(() => {
    function beiVerlassen(ereignis: BeforeUnloadEvent) {
      if (!ungespeichert) return;
      ereignis.preventDefault();
      ereignis.returnValue = '';
    }
    function beiWechsel() {
      if (document.visibilityState === 'hidden' && ungespeichert) void speichern();
    }
    window.addEventListener('beforeunload', beiVerlassen);
    document.addEventListener('visibilitychange', beiWechsel);
    return () => {
      window.removeEventListener('beforeunload', beiVerlassen);
      document.removeEventListener('visibilitychange', beiWechsel);
    };
  });

  export async function speichern(): Promise<void> {
    const dek = tresor.dek;
    if (!dek || zustand === 'speichert') return;
    const stand = jetzigerStand;

    // Ein leerer Tag wird nicht angelegt. Wer nur geblättert hat, soll keine
    // Spur hinterlassen.
    if (leer && !verschluesselt) {
      geladenerStand = stand;
      return;
    }

    clearTimeout(uhr);
    zustand = 'speichert';
    meldung = '';
    try {
      const paket = await eintragVerschluesseln(inhalt, dek);
      const antwort = await fetch(`/api/eintrag/${tag}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(paket),
      });
      if (!antwort.ok) {
        meldung = `Nicht gespeichert (${antwort.status}). Der Text steht noch hier.`;
        zustand = 'fehler';
        return;
      }
      geladenerStand = stand;
      zuletzt = new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
      zustand = 'bereit';
      gespeichert?.();

      // Die drei Skalen an den Kalender, getrennt und nachrangig. Scheitert es,
      // bleibt der Eintrag trotzdem gespeichert: der Kalender ist Empfänger,
      // nicht Wirt.
      void fetch('/api/checkin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          datum: tag,
          stimmung: inhalt.stimmung,
          energie: inhalt.energie,
          schlaf: inhalt.schlaf,
        }),
      }).catch(() => undefined);
    } catch {
      meldung = 'Das Verschlüsseln ist fehlgeschlagen. Der Text steht noch hier.';
      zustand = 'fehler';
    }
  }

  async function loeschen() {
    if (!confirm(`Den Eintrag vom ${langformat(tag)} wirklich löschen?`)) return;
    const antwort = await fetch(`/api/eintrag/${tag}`, { method: 'DELETE' });
    if (antwort.ok || antwort.status === 404) {
      inhalt = { text: '', stimmung: null, energie: null, schlaf: null };
      geladenerStand = JSON.stringify(inhalt);
      gespeichert?.();
    }
  }

  function tasten(ereignis: KeyboardEvent) {
    if ((ereignis.ctrlKey || ereignis.metaKey) && ereignis.key === 'Enter') {
      ereignis.preventDefault();
      void speichern();
    }
  }
</script>

<article>
  <header class="flex flex-wrap items-baseline justify-between gap-2">
    <h1 class="font-display text-xl">
      {langformat(tag)}{#if tag === heute}<span class="ml-2 text-sm text-muted">heute</span>{/if}
    </h1>
    <p class="text-xs text-muted" aria-live="polite">
      {#if zustand === 'speichert'}
        wird gespeichert …
      {:else if ungespeichert}
        ungespeicherte Änderungen
      {:else if zuletzt}
        gespeichert {zuletzt}
      {/if}
    </p>
  </header>

  {#if kontext.tagestyp || kontext.termine.length}
    <!-- Gedächtnisstütze aus dem Kalender. Sie wird nicht mitgespeichert:
         was im Eintrag steht, hat der Schreibende selbst getippt. -->
    <p class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
      {#if kontext.tagestyp}
        <span class="rounded-full bg-surface-2 px-2 py-0.5">{kontext.tagestyp}</span>
      {/if}
      {#each kontext.termine.slice(0, 6) as termin}
        <span>{termin.ganztags ? '' : `${termin.von} `}{termin.titel}</span>
      {/each}
      {#if kontext.termine.length > 6}
        <span>und {kontext.termine.length - 6} weitere</span>
      {/if}
    </p>
  {/if}

  {#if zustand === 'laedt'}
    <p class="mt-6 text-muted">wird geöffnet …</p>
  {:else}
    {#if meldung}
      <p class="mt-4 rounded-md border border-fehler/40 bg-fehler/10 px-3 py-2 text-sm">{meldung}</p>
    {/if}

    <textarea
      bind:value={inhalt.text}
      onkeydown={tasten}
      placeholder="Was war heute?"
      rows="18"
      class="mt-4 w-full resize-y rounded-md border border-border bg-surface-2 px-4 py-3 text-base leading-relaxed outline-none focus:border-accent-500"
    ></textarea>

    <div class="mt-4 flex flex-wrap gap-6">
      <!-- ★ Der aktive Wert ist gefüllt, nicht nur umrandet. Nachgerechnet:
           ein Rahmen in accent-500 kommt im hellen Theme auf 2,63:1 gegen die
           Fläche und liegt damit unter dem Richtwert 3:1 für flächige
           Bedienelemente. Gefüllt unterscheiden sich die Zustände in Fläche,
           Textfarbe und Schriftschnitt zugleich; es ist ausserdem dasselbe
           Muster wie beim primären Button der Suite. -->
      {#snippet skala(
        titel: string,
        werte: readonly { wert: string; label: string }[],
        aktuell: string | null | undefined,
        setzen: (w: string | null) => void,
      )}
        <fieldset class="flex items-center gap-2">
          <legend class="sr-only">{titel}</legend>
          <span class="text-xs text-muted">{titel}</span>
          {#each werte as eintrag}
            <button
              type="button"
              aria-pressed={aktuell === eintrag.wert}
              onclick={() => setzen(aktuell === eintrag.wert ? null : eintrag.wert)}
              class="rounded-full border px-3 py-1 text-xs transition-colors duration-fast {aktuell ===
              eintrag.wert
                ? 'border-accent-500 bg-accent-500 font-semibold text-accent-ink'
                : 'border-border text-muted hover:text-text'}"
            >
              {eintrag.label}
            </button>
          {/each}
        </fieldset>
      {/snippet}

      {@render skala('Stimmung', STIMMUNGEN, inhalt.stimmung, (w) => (inhalt.stimmung = w as never))}
      {@render skala('Energie', ENERGIEN, inhalt.energie, (w) => (inhalt.energie = w as never))}
      {@render skala('Schlaf', SCHLAF, inhalt.schlaf, (w) => (inhalt.schlaf = w as never))}
    </div>

    <p class="mt-2 text-xs text-muted">
      Die drei Angaben gehen zusätzlich an den Kalender und steuern dort die Tagesplanung. Der Text
      bleibt hier.
    </p>

    <div class="mt-5 flex items-center gap-2">
      <Button onclick={() => speichern()} disabled={zustand === 'speichert' || !ungespeichert}>
        Speichern
      </Button>
      <span class="text-xs text-muted">oder Strg+Enter</span>
      <span class="flex-1"></span>
      {#if verschluesselt}
        <Button variant="ghost" size="sm" onclick={loeschen}>
          <Icon name="trash-2" size={16} /> Löschen
        </Button>
      {/if}
    </div>
  {/if}
</article>
