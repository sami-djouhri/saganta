/**
 * Schlanker Ersatz für den Sammel-Export von `@saganta/ui` in der Ansichtsprobe.
 *
 * Der Sammel-Export zieht `UpdateBanner` mit, und der greift auf `$app/stores`
 * zu. Diesen Alias gibt es nur unter SvelteKit; in der Probe scheitert der
 * Import mit 500, und zwar bevor irgendetwas gerendert wird. Sichtbar ist dann
 * eine leere Seite, die wie ein Fehler in der geprüften Komponente aussieht.
 *
 * ★ Das Icon selbst ist **nicht** nachgebaut, sondern dieselbe Datei wie in der
 * App. Ein Platzhalter-Icon würde genau das verstecken, wofür die Probe da ist:
 * Symbole, die fehlen oder die Zeilenhöhe verschieben.
 */
export { default as Icon } from '../../../packages/ui/src/components/Icon.svelte';
