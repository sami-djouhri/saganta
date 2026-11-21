<script lang="ts">
  import NetzKarte from '$lib/components/NetzKarte.svelte';
  import VerweisVorschlaege from '$lib/components/VerweisVorschlaege.svelte';
  import type { GesamtNetz } from '$lib/types';

  // Erfundenes Netz: zwei Gruppen, ein paar Einzelne, Text- und Handkanten.
  const namen = [
    'Projekt Lichtorgel', 'Bauteile Lichtorgel', 'Schaltplan v2', 'Lötstation', 'Einkauf Elektronik',
    'Reise Nordsee', 'Packliste', 'Fähre buchen', 'Unterkunft Sylt', 'Wetter prüfen',
    'Leseliste', 'Rezept Linsensuppe', 'Idee Vogelhaus', 'Steuer 2026', 'Fahrrad Wartung',
  ];
  const knoten: GesamtNetz['knoten'] = namen.map((titel, i) => ({
    id: i + 1, titel, notizbuch_id: i < 5 ? 1 : i < 10 ? 2 : null, archiviert: i === 14,
    angeheftet: i === 0, grad: 0, offene_verweise: i === 2 ? 1 : 0,
  }));
  const kanten: GesamtNetz['kanten'] = [
    { a: 1, b: 2, art: 'verbunden' }, { a: 1, b: 3, art: 'text' }, { a: 2, b: 5, art: 'text' },
    { a: 3, b: 4, art: 'verbunden' }, { a: 2, b: 3, art: 'verbunden' }, { a: 6, b: 7, art: 'verbunden' },
    { a: 6, b: 8, art: 'text' }, { a: 6, b: 9, art: 'text' }, { a: 9, b: 10, art: 'verbunden' },
    { a: 7, b: 10, art: 'text' }, { a: 5, b: 15, art: 'text' },
  ];
  for (const k of kanten) {
    knoten[k.a - 1]!.grad++;
    knoten[k.b - 1]!.grad++;
  }
  const farben = new Map([[1, '#0891B2'], [2, '#D97706']]);
  const fokus = Number(new URLSearchParams(location.search).get('fokus')) || null;

  let auswahl = $state<number | null>(null);
  let suche = $state(new URLSearchParams(location.search).get('suche') ?? '');
  let text = $state('Für den Herbst: siehe [[Gar');
  let feld = $state<HTMLTextAreaElement | null>(null);
</script>

<div class="mx-auto flex max-w-6xl flex-col gap-4 p-4">
  <div class="netz-flaeche h-[60vh] overflow-hidden rounded-lg border border-border-stark" data-probe="netz">
    <NetzKarte {knoten} {kanten} {farben} {suche} {fokus} bind:auswahl />
  </div>
  <p data-probe="auswahl">Auswahl: {auswahl ?? '-'}</p>
  <div class="relative max-w-3xl" data-probe="editor">
    <textarea bind:this={feld} bind:value={text} rows="8" class="min-h-48 w-full rounded-md border border-border bg-surface px-4 py-3 text-base leading-7"></textarea>
    <VerweisVorschlaege {feld} bind:wert={text} ohne={99} />
  </div>
  <pre data-probe="text">{text}</pre>
</div>

<style>
  .netz-flaeche {
    background:
      radial-gradient(circle at 50% 45%, color-mix(in srgb, var(--color-akzent) 7%, transparent), transparent 65%),
      color-mix(in srgb, var(--color-surface) 70%, black);
  }
</style>
