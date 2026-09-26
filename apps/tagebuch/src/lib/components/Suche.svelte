<script lang="ts">
  /**
   * Suchen, ohne dass der Server mitliest.
   *
   * Der Ablauf ist ungewöhnlich und das ist der Punkt: die Chiffrate eines
   * Jahres werden geholt, hier entschlüsselt und hier durchsucht. Der Server
   * bekommt den Suchbegriff nie zu sehen und könnte mit ihm auch nichts
   * anfangen.
   *
   * Der Preis ist Zeit und Speicher beim ersten Suchen eines Jahres. Deshalb
   * wird je Jahr genau einmal geladen und das Ergebnis behalten, solange die
   * Seite offen ist.
   */
  import { eintragEntschluesseln } from '$lib/krypto';
  import { tresor } from '$lib/tresor.svelte';
  import { langformat } from '$lib/datum';
  import type { EintragAus } from '$lib/tagebuch-api';

  let { jahr }: { jahr: number } = $props();

  interface Fund {
    datum: string;
    ausschnitt: string;
  }

  let begriff = $state('');
  let laedt = $state(false);
  let geladenesJahr = $state<number | null>(null);
  let entschluesselt = $state<{ datum: string; text: string }[]>([]);
  let fehler = $state('');

  let treffer = $derived.by<Fund[]>(() => {
    const gesucht = begriff.trim().toLowerCase();
    if (gesucht.length < 2) return [];
    const funde: Fund[] = [];
    for (const eintrag of entschluesselt) {
      const stelle = eintrag.text.toLowerCase().indexOf(gesucht);
      if (stelle < 0) continue;
      const von = Math.max(0, stelle - 40);
      funde.push({
        datum: eintrag.datum,
        ausschnitt:
          (von > 0 ? '… ' : '') +
          eintrag.text.slice(von, stelle + gesucht.length + 60).replace(/\s+/g, ' ') +
          ' …',
      });
    }
    return funde.reverse();
  });

  async function jahrLaden() {
    const dek = tresor.dek;
    if (!dek || laedt || geladenesJahr === jahr) return;
    laedt = true;
    fehler = '';
    try {
      const antwort = await fetch(`/api/eintraege?von=${jahr}-01-01&bis=${jahr}-12-31`);
      if (!antwort.ok) {
        fehler = `Die Einträge liessen sich nicht laden (${antwort.status}).`;
        return;
      }
      const roh = (await antwort.json()) as EintragAus[];
      const offen: { datum: string; text: string }[] = [];
      for (const eintrag of roh) {
        try {
          const inhalt = await eintragEntschluesseln(eintrag, dek);
          offen.push({ datum: eintrag.datum, text: inhalt.text });
        } catch {
          // Ein einzelner Eintrag, der nicht aufgeht, darf die Suche nicht
          // beenden. Er fehlt dann in den Ergebnissen, der Rest bleibt nutzbar.
        }
      }
      entschluesselt = offen;
      geladenesJahr = jahr;
    } finally {
      laedt = false;
    }
  }
</script>

<section class="mt-8" aria-label="Suche">
  <input
    type="search"
    bind:value={begriff}
    onfocus={jahrLaden}
    placeholder="Im Jahr {jahr} suchen"
    class="w-full rounded-md border border-border bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent-500"
  />

  {#if laedt}
    <p class="mt-2 text-xs text-muted">
      Die Einträge werden geholt und hier im Browser geöffnet …
    </p>
  {:else if fehler}
    <p class="mt-2 text-xs text-fehler">{fehler}</p>
  {:else if begriff.trim().length >= 2}
    <p class="mt-2 text-xs text-muted">
      {treffer.length}
      {treffer.length === 1 ? 'Treffer' : 'Treffer'} in {entschluesselt.length} Einträgen
    </p>
    <ul class="mt-2 flex flex-col gap-2">
      {#each treffer.slice(0, 40) as fund}
        <li>
          <a
            href="/?tag={fund.datum}"
            class="block rounded-md border border-border px-3 py-2 hover:border-accent-500"
          >
            <span class="text-xs text-muted">{langformat(fund.datum)}</span>
            <p class="mt-1 text-sm">{fund.ausschnitt}</p>
          </a>
        </li>
      {/each}
    </ul>
  {/if}
</section>
