<script lang="ts">
  import { goto, invalidateAll } from '$app/navigation';
  import { Button, Icon } from '@saganta/ui';
  import TresorEinrichten from '$lib/components/TresorEinrichten.svelte';
  import TresorOeffnen from '$lib/components/TresorOeffnen.svelte';
  import Schreibflaeche from '$lib/components/Schreibflaeche.svelte';
  import Jahresleiste from '$lib/components/Jahresleiste.svelte';
  import Suche from '$lib/components/Suche.svelte';
  import { tresor, schliessen } from '$lib/tresor.svelte';
  import { sprungZiel, vorwaertsMoeglich as darfVor } from '$lib/navigation';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  let offen = $derived(tresor.dek !== null);

  // Kein Blättern in die Zukunft: dort gibt es nichts zu erinnern. Die Regel
  // liegt in `$lib/navigation` und gilt auch für die Jahresleiste; vorher stand
  // sie an zwei Stellen und nur eine hielt sich daran (siehe dort).
  let vorwaertsMoeglich = $derived(darfVor(data.tag, data.heute));
  let istHeute = $derived(data.tag === data.heute);

  /**
   * Wie weit ein Sprung reicht.
   *
   * ★ Bis 2026-09-13 gab es nur ±1 Tag. Wer einen Eintrag von vor drei Wochen
   * suchte, klickte einundzwanzig Mal oder musste das Datumsfeld auf dem Handy
   * bedienen. Eine Woche als zweite Stufe deckt den Alltagsfall („letzten
   * Montag") mit einem Klick ab; für alles Weitere bleiben Datumsfeld und
   * Jahresleiste.
   */
  const SCHRITTE = [
    { tage: 7, symbol: 'chevrons-right', beschriftung: 'Woche' },
    { tage: 1, symbol: 'chevron-right', beschriftung: 'Tag' },
  ] as const;

  async function zuTag(datum: string) {
    await goto(`/?tag=${datum}`, { noScroll: true, keepFocus: true });
  }

  /** Blättern um `tage`, gedeckelt auf heute (siehe `$lib/navigation`). */
  async function springen(tage: number) {
    await zuTag(sprungZiel(data.tag, tage, data.heute));
  }

  /**
   * Pfeiltasten blättern, solange nicht gerade geschrieben wird.
   *
   * Die Prüfung auf das Eingabeziel ist der Punkt: ohne sie würde der Cursor im
   * Textfeld den Tag wechseln, und der halb geschriebene Satz wäre weg.
   */
  function tasten(ereignis: KeyboardEvent) {
    if (!offen || ereignis.metaKey || ereignis.ctrlKey || ereignis.altKey) return;
    const ziel = ereignis.target as HTMLElement | null;
    if (ziel && /^(input|textarea|select)$/i.test(ziel.tagName)) return;
    if (ziel?.isContentEditable) return;

    if (ereignis.key === 'ArrowLeft') {
      ereignis.preventDefault();
      void springen(-1);
    } else if (ereignis.key === 'ArrowRight' && vorwaertsMoeglich) {
      ereignis.preventDefault();
      void springen(1);
    }
  }
</script>

<svelte:window onkeydown={tasten} />

<svelte:head>
  <title>Tagebuch</title>
</svelte:head>

{#if !data.tresorVorhanden}
  <TresorEinrichten fertig={() => invalidateAll()} />
{:else if !offen}
  <TresorOeffnen pakete={data.tresor!} />
{:else}
  <nav class="mb-4 flex flex-wrap items-center gap-1.5" aria-label="Tag wählen">
    <!-- Zurück: Woche, dann Tag. Die Reihenfolge spiegelt die Vorwärts-Seite,
         damit „weiter weg" außen liegt und „einen Schritt" innen. -->
    {#each SCHRITTE as schritt (schritt.tage)}
      <Button
        variant="ghost"
        size="sm"
        aria-label="{schritt.tage} {schritt.tage === 1 ? 'Tag' : 'Tage'} zurück"
        title="{schritt.beschriftung} zurück"
        onclick={() => springen(-schritt.tage)}
      >
        <Icon name={schritt.symbol === 'chevrons-right' ? 'chevrons-right' : 'chevron-right'} size={16} class="rotate-180" />
      </Button>
    {/each}

    <input
      type="date"
      value={data.tag}
      max={data.heute}
      aria-label="Datum wählen"
      onchange={(e) => zuTag((e.currentTarget as HTMLInputElement).value)}
      class="rounded-md border border-border bg-surface-2 px-2 py-1 text-sm"
    />

    <!-- Vorwärts: Tag, dann Woche. -->
    {#each [...SCHRITTE].reverse() as schritt (schritt.tage)}
      <Button
        variant="ghost"
        size="sm"
        aria-label="{schritt.tage} {schritt.tage === 1 ? 'Tag' : 'Tage'} vor"
        title={vorwaertsMoeglich ? `${schritt.beschriftung} vor` : 'Heute ist der letzte Tag'}
        disabled={!vorwaertsMoeglich}
        onclick={() => springen(schritt.tage)}
      >
        <Icon name={schritt.symbol} size={16} />
      </Button>
    {/each}

    <!-- ★ Der Heute-Knopf steht jetzt IMMER da, auf heute nur ausgegraut.
         Vorher erschien er erst, wenn man nicht auf heute war, und die ganze
         Leiste sprang beim Blättern um seine Breite. Ein Bedienelement, das
         seinen Platz wechselt, ist schwerer zu treffen als eines, das bleibt. -->
    <Button
      variant="ghost"
      size="sm"
      disabled={istHeute}
      title={istHeute ? 'Du bist auf heute' : 'Zurück zu heute'}
      onclick={() => zuTag(data.heute)}
    >
      Heute
    </Button>

    <span class="flex-1"></span>
    <Button variant="ghost" size="sm" onclick={schliessen} title="Tagebuch zuklappen">
      <Icon name="lock" size={16} /> Zuklappen
    </Button>
  </nav>

  <Schreibflaeche
    tag={data.tag}
    verschluesselt={data.eintrag}
    kontext={data.kontext}
    heute={data.heute}
    gespeichert={() => invalidateAll()}
  />

  <Suche jahr={data.jahr} />

  <Jahresleiste jahr={data.jahr} tage={data.tage} aktuell={data.tag} heute={data.heute} />
{/if}
