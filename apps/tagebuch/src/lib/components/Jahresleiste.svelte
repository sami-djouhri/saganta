<script lang="ts">
  /**
   * Das Jahr auf einen Blick: welche Tage etwas enthalten.
   *
   * Der Server liefert dafür nur Datum und Länge des Chiffrats, nie den Inhalt.
   *
   * ★ Die erste Fassung stufte die Deckkraft nach Länge ab (0,25 bis 1,0), damit
   * ein langer Tag dunkler wirkt als eine Randnotiz. Nachgerechnet war das
   * unbrauchbar: ein kurzer Tag kam auf **1,4:1** gegen ein leeres Feld, ein
   * voller im hellen Theme auf 2,94:1, beides unter dem Richtwert 3:1 für
   * flächige Bedienelemente (WCAG 1.4.11). Ein Verlauf, den man nicht
   * unterscheiden kann, ist keine Information, sondern nur ein schlechter
   * Kontrast. Jetzt gibt es zwei Zustände, gefüllt oder leer, mit 5,9:1 (hell)
   * und 6,3:1 (dunkel). Die Länge steht dort, wo sie nicht stört: im Tooltip.
   *
   * ★★ **Künftige Tage sind seit 2026-09-13 kein Link mehr.** Vorher verlinkte
   * diese Leiste jeden Tag des Jahres, auch den 31. Dezember, während die
   * Pfeil-Navigation die Zukunft ausdrücklich sperrt (`vorwaertsMoeglich`). Zwei
   * Wege, zwei Regeln: wer in der Leiste auf einen künftigen Tag klickte, landete
   * dort und fand den Vorwärts-Knopf ausgegraut vor, weil es von dort aus kein
   * Weiter mehr gibt. Das sah aus, als sei die Navigation kaputt, und war in
   * Wahrheit ein Widerspruch zwischen zwei Bedienwegen auf dieselbe Sache.
   *
   * ★ Die Felder sind ausserdem von 12 auf 16 Pixel gewachsen und haben Abstand
   * bekommen. 12 Pixel lagen unter dem Mindestmass fuer ein Klickziel (WCAG
   * 2.5.8 nennt 24), und auf dem Handy traf man regelmaessig den Nachbartag.
   */
  import { MONATSNAMEN, tageImMonat } from '$lib/datum';
  import type { TagAus } from '$lib/tagebuch-api';

  interface Props {
    jahr: number;
    tage: TagAus[];
    aktuell: string;
    heute: string;
  }
  let { jahr, tage, aktuell, heute }: Props = $props();

  let nachDatum = $derived(new Map(tage.map((t) => [t.datum, t.zeichen])));

  function feld(jahr: number, monat: number, tag: number): string {
    return `${jahr}-${String(monat).padStart(2, '0')}-${String(tag).padStart(2, '0')}`;
  }

  /** Grobe Angabe der Länge. Aus Base64 wird geschätzt, nicht gerechnet: der
   * Server kennt den Klartext nicht, und ein genauer Wert wäre eine Genauigkeit,
   * die es nicht gibt. */
  function laenge(zeichen: number | undefined): string {
    if (!zeichen) return 'kein Eintrag';
    const woerter = Math.round((zeichen * 0.75) / 6 / 10) * 10;
    return woerter < 20 ? 'kurzer Eintrag' : `Eintrag, etwa ${woerter} Wörter`;
  }
</script>

<section aria-label="Übersicht {jahr}" class="mt-10">
  <h2 class="text-sm text-muted">{jahr}</h2>
  <div class="mt-2 flex flex-col gap-1.5">
    {#each MONATSNAMEN as name, index}
      {@const monat = index + 1}
      <div class="flex items-center gap-2">
        <span class="w-8 shrink-0 text-[11px] text-muted">{name.slice(0, 3)}</span>
        <div class="flex flex-wrap gap-1">
          {#each Array(tageImMonat(jahr, monat)) as _, i}
            {@const datum = feld(jahr, monat, i + 1)}
            {@const zeichen = nachDatum.get(datum)}
            {@const kuenftig = datum > heute}
            {#if kuenftig}
              <!-- Kein Link, aber weiterhin sichtbar: das Jahr soll nicht in der
                   Mitte abbrechen. Als `<span>` statt `<a>`, damit es weder im
                   Tastaturweg noch unter dem Zeiger als Ziel erscheint. -->
              <span
                title="{datum}: noch nicht"
                class="size-4 rounded-[3px] border border-border/40 bg-transparent"
              ></span>
            {:else}
              <a
                href="/?tag={datum}"
                data-sveltekit-noscroll
                title="{datum}: {laenge(zeichen)}"
                aria-label="{datum}, {laenge(zeichen)}"
                aria-current={datum === aktuell ? 'date' : undefined}
                class="size-4 rounded-[3px] border transition-colors duration-fast ease-saganta hover:border-accent-500 {datum ===
                aktuell
                  ? 'border-accent-500 ring-1 ring-accent-500'
                  : datum === heute
                    ? 'border-text'
                    : 'border-border'} {zeichen ? 'bg-muted' : 'bg-surface-2'}"
              ></a>
            {/if}
          {/each}
        </div>
      </div>
    {/each}
  </div>
  <p class="mt-2 text-[11px] text-muted">
    Gefüllte Felder sind Tage mit Eintrag, blasse liegen noch vor dir. Der Server kennt davon nur
    das Datum und die Länge.
  </p>
</section>
