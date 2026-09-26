<script lang="ts">
  /**
   * Die Tagesdecke: der wache Tag als lückenlose Kette von Blöcken.
   *
   * Bedienung ist Ziehen und Fallenlassen, und zwar mit **Pointer-Events**, nicht
   * mit der HTML5-Drag-Schnittstelle. Der Unterschied ist nicht Geschmack: die
   * HTML5-Variante wird auf Touch-Geräten von keinem mobilen Browser zuverlässig
   * ausgelöst, und der Kalender soll ausdrücklich auch am Handy korrigierbar
   * sein. Pointer-Events decken Maus, Stift und Finger mit demselben Code ab.
   *
   * Zwei Zustände je Tag:
   * - **offen**: die Decke wird gerechnet, Blöcke haben keine Kennung. Korrigieren
   *   geht nicht, weil es nichts zu korrigieren gibt, was Bestand hätte.
   * - **festgeschrieben**: jeder Block ist eine Zeile. Erst hier ist Ziehen,
   *   Verwerfen und Umsortieren sinnvoll.
   */
  import { Icon } from '@saganta/ui';

  interface Block {
    id: string | null;
    start: string;
    ende: string;
    minuten: number;
    art: string;
    titel: string;
    begruendung: string | null;
    status: string;
    herkunft_typ: string | null;
  }

  interface Decke {
    datum: string;
    wach_von: string;
    wach_bis: string;
    wach_minuten: number;
    verplant_minuten: number;
    offen_minuten: number;
    summe_je_art: Record<string, number>;
    bloecke: Block[];
    festgeschrieben: boolean;
    capacity?: { level?: string; reason?: string } | null;
    hinweise?: string[];
  }

  interface Props {
    decke: Decke | null;
    /** Läuft gerade ein Server-Aufruf? Sperrt das Ziehen. */
    beschaeftigt?: boolean;
    onFestschreiben: () => void;
    onNeuOrdnen: (reihenfolge: string[]) => void;
    onVerwerfen: (blockId: string) => void;
    onTagWechsel: (datum: string) => void;
  }
  let {
    decke,
    beschaeftigt = false,
    onFestschreiben,
    onNeuOrdnen,
    onVerwerfen,
    onTagWechsel,
  }: Props = $props();

  const ART_ICON: Record<string, string> = {
    fix: 'calendar-clock',
    gewohnheit: 'refresh-cw',
    ziel: 'target',
    aufgabe: 'square-check',
    training: 'dumbbell',
    erholung: 'armchair',
    grundlast: 'utensils',
    puffer: 'circle',
    schlaf: 'moon',
  };
  // Farbton je Art als rgba, damit Tailwinds Purge sie nicht entfernt (gleiche
  // Begründung wie bei DAYTYPE_TINT in cal.ts).
  const ART_FARBE: Record<string, string> = {
    fix: 'rgba(93, 126, 255, 0.85)',
    gewohnheit: 'rgba(155, 109, 255, 0.85)',
    ziel: 'rgba(212, 183, 72, 0.85)',
    aufgabe: 'rgba(72, 183, 212, 0.85)',
    training: 'rgba(62, 201, 138, 0.85)',
    erholung: 'rgba(200, 136, 74, 0.85)',
    grundlast: 'rgba(224, 99, 154, 0.70)',
    puffer: 'rgba(140, 140, 140, 0.45)',
    schlaf: 'rgba(90, 100, 140, 0.60)',
  };

  /** "2027-03-09T18:30:00" → "18:30". Bewusst ohne Date: der Wert ist bereits
   *  Berliner Wanduhr, ein Parsen würde ihn in die Zone des Browsers ziehen. */
  function uhrzeit(iso: string): string {
    return iso.slice(11, 16);
  }

  function dauer(minuten: number): string {
    if (minuten < 60) return `${minuten} min`;
    const h = Math.floor(minuten / 60);
    const m = minuten % 60;
    return m === 0 ? `${h} h` : `${h} h ${m} min`;
  }

  function tagVerschieben(tage: number): string {
    if (!decke) return '';
    const [j, m, t] = decke.datum.split('-').map(Number);
    // UTC-Konstruktion: sonst kippt der Tag an der Zeitumstellung um eins.
    const d = new Date(Date.UTC(j ?? 1970, (m ?? 1) - 1, t ?? 1));
    d.setUTCDate(d.getUTCDate() + tage);
    return d.toISOString().slice(0, 10);
  }

  const heute = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Berlin' }).format(
    new Date(),
  );

  // --- Ziehen und Fallenlassen ----------------------------------------

  /** Arbeitskopie der Reihenfolge. Während des Ziehens wird hier umsortiert,
   *  damit die Ansicht sofort folgt; der Server bekommt erst beim Loslassen
   *  Bescheid. Bricht der Aufruf, lädt die Seite neu und der Server gewinnt. */
  let ordnung = $state<Block[]>([]);
  let ziehtIndex = $state<number | null>(null);
  let ueberEntfernen = $state(false);
  let zeigerY = $state(0);
  // ★ `$state`, nicht ein blankes Array: `bind:this` in einer `{#each}`-Schleife
  // schreibt sonst in eine nicht verfolgte Eigenschaft. Svelte meldet das zur
  // Laufzeit (`binding_property_non_reactive`, einmal je Block), `svelte-check`
  // sieht es nicht. Praktische Folge ist ein veralteter Eintrag, sobald die
  // Liste kürzer wird: die Zielposition beim Ziehen wird dann gegen ein
  // Element gemessen, das nicht mehr im Dokument hängt.
  let elemente = $state<HTMLElement[]>([]);
  let listeEl: HTMLElement | undefined = $state();
  /** Höhe der Entfernen-Zone am unteren Rand, in Pixeln (siehe unten). */
  const ENTFERNEN_HOEHE = 84;

  // Kommt eine neue Decke vom Server, wird die Arbeitskopie ersetzt.
  // ⚠️ Hier NICHT zusätzlich `elemente` stutzen: dieser Effect hängt an
  // `ordnung`, und ein Schreibzugriff auf verfolgten Zustand im selben Effect
  // lässt ihn sich selbst erneut auslösen. Das Aufräumen alter Knoten passiert
  // stattdessen beim Lesen in `bewegen()`.
  $effect(() => {
    ordnung = decke ? [...decke.bloecke] : [];
  });

  const korrigierbar = $derived(Boolean(decke?.festgeschrieben) && !beschaeftigt);

  function greifen(index: number, ereignis: PointerEvent) {
    if (!korrigierbar) return;
    const block = ordnung[index];
    if (!block?.id) return;
    ereignis.preventDefault();
    (ereignis.target as HTMLElement).setPointerCapture?.(ereignis.pointerId);
    ziehtIndex = index;
    zeigerY = ereignis.clientY;
  }

  function bewegen(ereignis: PointerEvent) {
    if (ziehtIndex === null) return;
    ereignis.preventDefault();
    zeigerY = ereignis.clientY;

    // ★★ Über der Entfernen-Zone? Gemessen wird gegen den **unteren Rand des
    // Fensters**, nicht gegen das Ende der Liste. Die erste Fassung tat
    // letzteres, und damit war Verwerfen am Handy unmöglich: eine volle
    // Tagesdecke ist dort rund 1040 px lang, der Bildschirm 844 px hoch. Die
    // Bedingung „Zeiger unterhalb des Listenendes" konnte kein Finger erfüllen,
    // denn `clientY` wird nie größer als die Fensterhöhe. Gemessen am
    // 2026-09-16 mit einem Arbeitstag aus zwölf Blöcken: die Zone lag 193 px
    // unter der Bildschirmkante. Scrollen half nicht, weil das Ziehen
    // `preventDefault()` ruft und die Liste `touch-none` trägt.
    ueberEntfernen = ereignis.clientY > window.innerHeight - ENTFERNEN_HOEHE;
    if (ueberEntfernen) return;

    // Zielposition aus den gemessenen Mitten der Nachbarn ableiten. Gemessen
    // statt gerechnet, weil die Blöcke unterschiedlich hoch sind (die Höhe
    // folgt der Dauer) und eine Rechnung über eine feste Zeilenhöhe hier
    // daneben läge.
    // ★ Nur bis zur aktuellen Listenlänge lesen. Wird ein Block verworfen, wird
    // die Liste kürzer, `elemente` aber nicht: die überzähligen Einträge zeigen
    // dann auf Knoten, die nicht mehr im Dokument hängen. Deren
    // `getBoundingClientRect()` liefert lauter Nullen, und die Zielposition
    // landet daneben, ohne dass irgendwo ein Fehler auftaucht.
    const ziel = elemente.slice(0, ordnung.length).findIndex((el) => {
      if (!el) return false;
      const r = el.getBoundingClientRect();
      return ereignis.clientY < r.top + r.height / 2;
    });
    const neuerIndex = ziel === -1 ? ordnung.length - 1 : ziel;
    if (neuerIndex !== ziehtIndex && neuerIndex >= 0) {
      const kopie = [...ordnung];
      const [gezogen] = kopie.splice(ziehtIndex, 1);
      if (gezogen) {
        kopie.splice(neuerIndex, 0, gezogen);
        ordnung = kopie;
        ziehtIndex = neuerIndex;
      }
    }
  }

  function loslassen() {
    if (ziehtIndex === null) return;
    const block = ordnung[ziehtIndex];
    const warUeberEntfernen = ueberEntfernen;
    ziehtIndex = null;
    ueberEntfernen = false;

    if (!block?.id) return;
    if (warUeberEntfernen) {
      onVerwerfen(block.id);
      return;
    }
    const neueReihenfolge = ordnung.map((b) => b.id).filter((id): id is string => Boolean(id));
    const alteReihenfolge = (decke?.bloecke ?? [])
      .map((b) => b.id)
      .filter((id): id is string => Boolean(id));
    // Nur senden, wenn sich wirklich etwas geändert hat: ein Antippen ohne
    // Bewegung soll keinen Schreibvorgang auslösen.
    if (neueReihenfolge.join() !== alteReihenfolge.join()) {
      onNeuOrdnen(neueReihenfolge);
    }
  }

  /** Minuten seit Mitternacht als "HH:MM". */
  function alsUhr(minuten: number): string {
    const m = ((minuten % 1440) + 1440) % 1440;
    return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
  }

  /**
   * Vorläufige Zeiten während des Ziehens.
   *
   * ★ Ohne sie behält jeder Block seine alte Uhrzeit, während er an einer neuen
   * Stelle liegt. Man zieht die Morgenroutine hinter einen Block, der um 06:10
   * beginnt, und liest danach 06:10 über 05:30: eine Liste, die zeitlich
   * rückwärts läuft. Bei einer Ansicht, deren Zusage „lückenlose Kette" ist,
   * sieht das nach einem Fehler aus, und der Nutzer lässt los, um ihn
   * loszuwerden.
   *
   * Gerechnet wird genau wie im Server (`tagesdecke.neu_ordnen`): ab dem Beginn
   * des wachen Fensters die Dauern aneinanderhängen. Gilt nur, solange gezogen
   * wird; danach antwortet der Server und gewinnt.
   */
  const vorlaeufigeZeiten = $derived.by(() => {
    if (ziehtIndex === null || !decke) return null;
    let cursor =
      Number(decke.wach_von.slice(11, 13)) * 60 + Number(decke.wach_von.slice(14, 16));
    return ordnung.map((block) => {
      const von = cursor;
      cursor += block.minuten;
      return { start: alsUhr(von), ende: alsUhr(cursor) };
    });
  });

  /**
   * Höhe eines Blocks.
   *
   * ★ Sie muss **monoton** sein: länger darf nie niedriger aussehen. Die erste
   * Fassung rechnete `min(120, max(44, minuten * 0.9))`, und weil der Inhalt
   * zweizeiliger Blöcke die Untergrenze ohnehin überstieg, kam dabei heraus:
   * zehn Minuten Puffer 57 px hoch, dreißig Minuten Aufgabe 51 px. Der kürzere
   * Block war der größere. Jetzt liegt die Basis über dem Inhalt, der Zuwachs
   * ist gedeckelt (neun Stunden Arbeit würden sonst 486 px belegen und die
   * Liste unbrauchbar machen). Die echte Proportion trägt der Balken oben.
   */
  function blockHoehe(minuten: number): number {
    return 58 + Math.min(62, minuten * 0.25);
  }

  const anteil = $derived.by(() => {
    if (!decke) return [] as { art: string; minuten: number; prozent: number }[];
    const gesamt = Math.max(1, decke.wach_minuten);
    return Object.entries(decke.summe_je_art)
      .map(([art, minuten]) => ({ art, minuten, prozent: (minuten / gesamt) * 100 }))
      .sort((a, b) => b.minuten - a.minuten);
  });
</script>

<section class="rounded-xl border border-border bg-surface/40">
  <header class="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3">
    <h2 class="flex items-center gap-2 text-sm font-semibold">
      <Icon name="clock" size={16} />
      Tagesdecke
    </h2>

    {#if decke}
      <div class="flex items-center gap-1 text-xs">
        <button
          type="button"
          class="rounded px-1.5 py-1 hover:bg-surface"
          onclick={() => onTagWechsel(tagVerschieben(-1))}
          aria-label="Vorheriger Tag"
        >
          <Icon name="chevron-left" size={14} />
        </button>
        <span class="tabular-nums text-muted">{decke.datum}</span>
        <button
          type="button"
          class="rounded px-1.5 py-1 hover:bg-surface"
          onclick={() => onTagWechsel(tagVerschieben(1))}
          aria-label="Nächster Tag"
        >
          <Icon name="chevron-right" size={14} />
        </button>
        {#if decke.datum !== heute}
          <button
            type="button"
            class="ml-1 rounded px-2 py-1 text-muted hover:bg-surface"
            onclick={() => onTagWechsel(heute)}
          >
            heute
          </button>
        {/if}
      </div>

      <p class="ml-auto text-xs text-muted tabular-nums">
        wach {uhrzeit(decke.wach_von)} bis {uhrzeit(decke.wach_bis)}
        <span class="mx-1 opacity-50">·</span>
        {dauer(decke.wach_minuten)}
      </p>
    {/if}
  </header>

  {#if !decke}
    <p class="px-4 py-6 text-sm text-muted">Die Decke konnte nicht geladen werden.</p>
  {:else}
    <!-- Verteilungsbalken: wofür der Tag draufgeht, auf einen Blick. -->
    <div class="px-4 pt-3">
      <div class="flex h-2 w-full overflow-hidden rounded-full bg-border/40">
        {#each anteil as teil (teil.art)}
          <div
            class="h-full"
            style="width: {teil.prozent}%; background: {ART_FARBE[teil.art] ?? ART_FARBE.puffer}"
            title="{teil.art}: {dauer(teil.minuten)}"
          ></div>
        {/each}
      </div>
      <p class="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted">
        {#each anteil as teil (teil.art)}
          <span class="inline-flex items-center gap-1">
            <span
              class="inline-block h-2 w-2 rounded-full"
              style="background: {ART_FARBE[teil.art] ?? ART_FARBE.puffer}"
            ></span>
            {teil.art} {dauer(teil.minuten)}
          </span>
        {/each}
      </p>
    </div>

    {#each decke.hinweise ?? [] as hinweis}
      <p class="mx-4 mt-3 rounded-lg border border-border bg-surface/60 px-3 py-2 text-xs text-muted">
        {hinweis}
      </p>
    {/each}

    {#if !decke.festgeschrieben}
      <div class="mx-4 mt-3 rounded-lg border border-border bg-surface/60 px-3 py-2.5">
        <p class="text-xs text-muted">
          Dieser Tag ist noch offen: die Decke wird laufend neu gerechnet und folgt
          deinen Terminen. Zum Korrigieren einmal festhalten, danach lässt sich
          verschieben und herausnehmen.
        </p>
        <button
          type="button"
          class="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs hover:bg-surface disabled:opacity-50"
          onclick={onFestschreiben}
          disabled={beschaeftigt}
        >
          <Icon name="pen" size={13} />
          Tag festhalten und korrigieren
        </button>
      </div>
    {/if}

    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <ul
      bind:this={listeEl}
      class="flex flex-col gap-1 px-4 py-3"
      onpointermove={bewegen}
      onpointerup={loslassen}
      onpointercancel={loslassen}
    >
      {#each ordnung as block, index (block.id ?? `${block.start}-${block.art}`)}
        {@const gezogen = ziehtIndex === index}
        {@const verworfen = block.status === 'verworfen'}
        <li
          bind:this={elemente[index]}
          class="flex items-stretch gap-2 rounded-lg border bg-surface/60 transition-shadow
                 {gezogen ? 'border-accent shadow-lg' : 'border-border'}
                 {verworfen ? 'opacity-45' : ''}"
          style="min-height: {blockHoehe(block.minuten)}px"
        >
          <span
            class="w-1 shrink-0 rounded-l-lg"
            style="background: {ART_FARBE[block.art] ?? ART_FARBE.puffer}"
          ></span>

          <span class="flex w-12 shrink-0 flex-col justify-center py-2 text-[11px] tabular-nums text-muted">
            <span>{vorlaeufigeZeiten?.[index]?.start ?? uhrzeit(block.start)}</span>
            <span class="opacity-60">
              {vorlaeufigeZeiten?.[index]?.ende ?? uhrzeit(block.ende)}
            </span>
          </span>

          <span class="flex min-w-0 flex-1 flex-col justify-center py-2 pr-2">
            <span class="flex items-center gap-1.5 text-sm">
              <Icon name={ART_ICON[block.art] ?? 'circle'} size={13} />
              <span class="truncate {verworfen ? 'line-through' : ''}">{block.titel}</span>
              <span class="shrink-0 text-[11px] text-muted tabular-nums">{dauer(block.minuten)}</span>
            </span>
            {#if verworfen}
              <span class="mt-0.5 text-[11px] text-muted">war geplant, fand nicht statt</span>
            {:else if block.begruendung}
              <span class="mt-0.5 truncate text-[11px] text-muted">{block.begruendung}</span>
            {/if}
          </span>

          {#if korrigierbar && block.id}
            <button
              type="button"
              class="flex w-9 shrink-0 cursor-grab touch-none items-center justify-center text-muted hover:text-fg active:cursor-grabbing"
              onpointerdown={(e) => greifen(index, e)}
              aria-label="{block.titel} verschieben"
            >
              <Icon name="chevrons-right" size={15} />
            </button>
          {/if}
        </li>
      {/each}
    </ul>

    {#if ziehtIndex !== null}
      <!-- Erscheint nur während des Ziehens: sonst lädt eine dauerhaft
           sichtbare Entfernen-Fläche zum versehentlichen Treffer ein.

           ★★ `fixed` am unteren Fensterrand, nicht unter der Liste. Eine
           Tagesdecke ist so lang wie der wache Tag, am Handy also länger als
           der Bildschirm; eine Zone am Listenende wäre dort nie erreichbar, und
           genau dafür sind die Pointer-Events da. Am Fensterrand ist sie in
           jeder Listenlänge und jeder Scrollposition an derselben Stelle. -->
      <div
        style="height: {ENTFERNEN_HOEHE}px"
        class="fixed inset-x-0 bottom-0 z-50 flex items-center justify-center gap-2 border-t-2 border-dashed px-3 text-sm backdrop-blur transition-colors
               {ueberEntfernen
          ? 'border-danger bg-danger/20 text-danger'
          : 'border-border bg-surface/90 text-muted'}"
      >
        <Icon name="x" size={15} />
        {ueberEntfernen ? 'Loslassen: hat nicht stattgefunden' : 'Hierher ziehen, was du nicht gemacht hast'}
      </div>
    {/if}
  {/if}
</section>
