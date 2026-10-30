<script lang="ts">
  /**
   * Die verknüpften Notizen eines Gegenstücks, und der Knopf, eine neue
   * anzulegen.
   *
   * **Der Knopf ist der eigentliche Zweck.** Am 2026-10-24 war gemessen:
   * sechs Verknüpfungstypen gebaut, im BFF auflösbar, und null benutzt. Nicht
   * weil etwas fehlte, sondern weil die Richtung falsch war: man sitzt nicht in
   * den Notizen und sucht einen Termin, man sitzt am Termin und will etwas
   * notieren. Deshalb entsteht die Notiz **hier**, in der App, in der man
   * gerade arbeitet, und nicht nach einem Sprung in ein leeres Formular
   * woanders.
   *
   * Die Komponente ist absichtlich ein gewöhnliches Formular: sie trägt ohne
   * JavaScript, `use:enhance` ist eine Verbesserung und keine Voraussetzung.
   * Weil `packages/ui` kein SvelteKit kennt (und nicht kennen soll), kommt die
   * `enhance`-Action als Eigenschaft von der App herein.
   */
  import Icon from './Icon.svelte';
  import Button from './Button.svelte';
  import { TYP_NAME, TITEL_MAX, type NotizKurz, type VerknuepfungsTyp } from '@saganta/notizen-anschluss/typen';

  type EnhanceAction = (element: HTMLFormElement) => { destroy?: () => void } | void;

  interface Props {
    /** Art des Gegenstücks. */
    typ: VerknuepfungsTyp;
    /** Kennung des Gegenstücks. */
    ref: string;
    /** Beschriftung des Gegenstücks, wird als Kopie mitgespeichert. */
    label: string;
    /** Die Notizen, die schon daran hängen. */
    notizen?: NotizKurz[];
    /**
     * Basis-Adresse der Notizen-App im aktuellen Raum, für die Links.
     * Fehlt sie, werden die Notizen genannt, aber nicht verlinkt: ein Link auf
     * eine erratene Adresse ist schlimmer als keiner.
     */
    notizenBasis?: string;
    /**
     * Die Notizen-App antwortet gerade nicht. Dann wird das gesagt, statt
     * „keine Notiz" zu behaupten, was eine Aussage über einen Bestand wäre,
     * den man nicht gelesen hat.
     */
    stumm?: boolean;
    /** Form-Action der App. */
    aktion?: string;
    /** Fehlermeldung des letzten Versuchs. */
    fehler?: string | null;
    /** `enhance` aus `$app/forms`, falls die App es verdrahtet. */
    enhance?: EnhanceAction;
    /** Vorbelegung des Titels. Vorgabe ist die Beschriftung des Gegenstücks. */
    titelVorschlag?: string;
    /** Ohne Überschrift und Rahmen, für enge Stellen wie einen Dialog. */
    schlicht?: boolean;
  }

  let {
    typ,
    ref,
    label,
    notizen = [],
    notizenBasis = '',
    stumm = false,
    aktion = '?/notizDazu',
    fehler = null,
    enhance,
    titelVorschlag,
    schlicht = false,
  }: Props = $props();

  // Nach einem fehlgeschlagenen Versuch steht der Dialog schon beim ersten
  // Rendern offen, nicht erst wenn JavaScript geladen hat: sonst zeigt die
  // Seite eine Fehlermeldung zu einem Formular, das nicht zu sehen ist.
  //
  // Hier ist ausdruecklich nur der **Anfangswert** gemeint, und nicht eine
  // Bindung an `fehler`: der Dialog muss sich zuklappen lassen, auch wenn die
  // Meldung noch steht. Die spaeteren Aenderungen traegt der `$effect` unten.
  // svelte-ignore state_referenced_locally
  let offen = $state(Boolean(fehler));
  let titel = $state('');
  let inhalt = $state('');
  let feld: HTMLInputElement | undefined = $state();

  /**
   * `use:enhance` der App durchreichen.
   *
   * ⚠️ Nicht `use:enhance={...}` schreiben: das würde die Action `enhance`
   * aufrufen und den Wert als ihren **Parameter** übergeben. Gebraucht ist das
   * Gegenteil, nämlich die hereingegebene Action selbst. Ohne sie bleibt das
   * Formular ein gewöhnliches Post, was trägt, aber die Seite neu lädt.
   */
  function einbinden(element: HTMLFormElement) {
    return enhance?.(element);
  }

  // Der Titel wird vorbelegt, damit der häufigste Fall ein Klick ist: „Notiz
  // zum Elterngespräch" trifft fast immer, und wer etwas anderes will, tippt
  // darüber. Ein leeres Feld wäre eine Aufgabe, keine Hilfe.
  const vorschlag = $derived((titelVorschlag ?? label).slice(0, TITEL_MAX));

  function oeffnen(): void {
    titel = vorschlag;
    inhalt = '';
    offen = true;
    // Nach dem Rendern in das Textfeld springen, damit man sofort tippen kann.
    queueMicrotask(() => feld?.focus());
  }

  function abbrechen(): void {
    offen = false;
    inhalt = '';
  }

  // Und er geht wieder auf, wenn ein Versuch über `enhance` scheitert (dann
  // lädt die Seite nicht neu, der Zustand oben greift also nicht).
  $effect(() => {
    if (fehler) offen = true;
  });
</script>

<section class={schlicht ? 'space-y-3' : 'space-y-3 rounded-lg border border-border p-4'}>
  {#if !schlicht}
    <h3 class="flex items-center gap-2 text-xs uppercase tracking-wider text-muted">
      <Icon name="file-text" size={14} /> Notizen
    </h3>
  {/if}

  {#if notizen.length > 0}
    <ul class="space-y-1">
      {#each notizen as n (n.id)}
        <li>
          {#if notizenBasis}
            <a
              href="{notizenBasis}/notiz/{n.id}"
              class="flex items-center gap-2 rounded-md border border-border bg-surface-2/60 px-3 py-2 text-sm hover:border-accent-500/50"
            >
              <Icon name="file-text" size={14} />
              <span class="min-w-0 flex-1 truncate">{n.titel || 'Ohne Titel'}</span>
              <Icon name="arrow-right" size={14} />
            </a>
          {:else}
            <span
              class="flex items-center gap-2 rounded-md border border-border bg-surface-2/60 px-3 py-2 text-sm"
            >
              <Icon name="file-text" size={14} />
              <span class="min-w-0 flex-1 truncate">{n.titel || 'Ohne Titel'}</span>
            </span>
          {/if}
        </li>
      {/each}
    </ul>
  {:else if stumm}
    <p class="text-sm text-muted">
      Die Notizen-App antwortet gerade nicht. Verknüpfte Notizen werden deshalb nicht angezeigt.
    </p>
  {:else}
    <p class="text-sm text-muted">Noch keine Notiz dazu.</p>
  {/if}

  {#if fehler}
    <p class="rounded-md border border-fehler/40 bg-fehler/10 px-3 py-2 text-sm">{fehler}</p>
  {/if}

  {#if offen}
    <form
      method="POST"
      action={aktion}
      use:einbinden
      class="space-y-2 rounded-md border border-border-stark bg-surface-2 p-3"
    >
      <input type="hidden" name="typ" value={typ} />
      <input type="hidden" name="ref" value={ref} />
      <input type="hidden" name="label" value={label} />

      <label class="block space-y-1">
        <span class="text-xs uppercase tracking-wider text-muted">Titel</span>
        <input
          bind:this={feld}
          bind:value={titel}
          name="titel"
          maxlength={TITEL_MAX}
          class="w-full rounded-md border border-border-stark bg-surface px-3 py-2 text-sm outline-none focus:border-accent-500"
        />
      </label>

      <label class="block space-y-1">
        <span class="text-xs uppercase tracking-wider text-muted">Text</span>
        <textarea
          bind:value={inhalt}
          name="inhalt"
          rows="4"
          placeholder="Was soll festgehalten werden?"
          class="w-full resize-y rounded-md border border-border-stark bg-surface px-3 py-2 text-sm outline-none focus:border-accent-500"
        ></textarea>
      </label>

      <div class="flex flex-wrap items-center gap-2">
        <Button type="submit" variant="primary" size="sm">Notiz anlegen</Button>
        <button
          type="button"
          onclick={abbrechen}
          class="rounded-md px-3 py-1.5 text-sm text-muted hover:text-text">Abbrechen</button
        >
        <span class="flex-1"></span>
        <span class="text-[11px] text-muted">hängt am {TYP_NAME[typ]}</span>
      </div>
    </form>
  {:else}
    <Button type="button" variant="ghost" size="sm" onclick={oeffnen}>
      <Icon name="plus" size={14} /> Notiz dazu
    </Button>
  {/if}
</section>
