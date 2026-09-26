<script lang="ts">
  /**
   * Die Seitenhuelle jeder App: zentrierter Inhalt mit einheitlichen Abstaenden.
   *
   * Sie rendert das `<main>` selbst und traegt damit auch das Sprungziel des
   * Skip-Links aus der TopBar. Vorher schrieb jede App ihr eigenes `<main>`, und
   * das ist auf zwei Arten auseinandergelaufen:
   *
   *   1. Nur die shell hatte ueberhaupt ein `id="main"`. In den anderen sieben
   *      Apps ging der Sprung ins Leere, es gab ihn dort schlicht nicht.
   *   2. Der Innenabstand war siebenmal `px-6` und einmal `px-4 sm:px-6`. Nur
   *      der Kalender war damit auf schmalen Geraeten richtig: bei 360 px
   *      Geraetebreite kostet `px-6` 48 px, also gut ein Achtel des Schirms,
   *      allein fuer Rand.
   *
   * Die Breite bleibt Sache der App, weil sie inhaltlich begruendet ist: ein
   * Monatsgitter braucht mehr als eine Nachrichtenliste. Die Werte entsprechen
   * dem, was die Apps vorher schon hatten, damit diese Umstellung das Aussehen
   * nicht nebenbei mitveraendert.
   */
  interface Props {
    /** lesen = Fliesstext und Listen, standard = Uebersichten, breit = Gitter und Boards. */
    breite?: 'lesen' | 'standard' | 'breit';
    /** Zusaetzliche Klassen, etwa fuer abweichende vertikale Abstaende. */
    class?: string;
    children: import('svelte').Snippet;
  }
  let { breite = 'standard', class: extra = '', children }: Props = $props();

  const maxW = $derived({ lesen: 'max-w-3xl', standard: 'max-w-5xl', breit: 'max-w-6xl' }[breite]);
</script>

<main
  id="main"
  tabindex="-1"
  class="mx-auto w-full {maxW} px-4 py-8 outline-none sm:px-6 sm:py-10 {extra}"
>
  {@render children()}
</main>
