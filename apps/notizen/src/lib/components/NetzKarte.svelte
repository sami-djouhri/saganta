<script lang="ts">
  import { untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    nachbarn,
    netzLayout,
    rahmen,
    type NetzKanteMitBuch,
    type NetzKnotenMitBuch,
    type Punkt,
  } from '$lib/netz-layout';
  import { verweisSchluessel } from '$lib/markdown';

  // Notizbücher kommen als Knoten mit `buch` und negativer Kennung mit (mitNotizbuechern).
  type Knoten = NetzKnotenMitBuch;
  type Kante = NetzKanteMitBuch;

  let {
    knoten,
    kanten,
    farben,
    suche = '',
    auswahl = $bindable<number | null>(null),
    fokus = null,
  }: {
    knoten: Knoten[];
    kanten: Kante[];
    /** Notizbuch → Farbe; ohne Eintrag leuchtet der Knoten im Akzent. */
    farben: Map<number, string>;
    suche?: string;
    auswahl?: number | null;
    /** Beim ersten Zeichnen auswählen und in die Mitte holen. */
    fokus?: number | null;
  } = $props();

  let breite = $state(800);
  let hoehe = $state(560);

  // Die Anordnung entsteht neu, sobald sich die gezeigten Knoten oder Kanten
  // ändern; gezogene Knoten bleiben bis dahin, wo man sie hingelegt hat.
  let lage = $state(new Map<number, Punkt>());
  let schluessel = '';
  $effect(() => {
    const neu = `${knoten.map((k) => k.id).join(',')}|${kanten.map((k) => `${k.a}-${k.b}`).join(',')}`;
    if (neu === schluessel) return;
    schluessel = neu;
    // Mit Notizbüchern längere Kanten, sonst drängen sich die Notizen eines
    // Buchs so eng um die Raute, dass sich die Beschriftungen überlagern.
    lage = netzLayout(knoten.map((k) => k.id), kanten, { laenge: knoten.some((k) => k.buch) ? 100 : 70 });
    angefasst = false;
    untrack(einpassen);
  });

  // Solange niemand verschoben oder gezoomt hat, folgt die Ansicht der Größe
  // der Fläche; die erste Messung kommt erst nach dem ersten Zeichnen.
  let angefasst = false;
  $effect(() => {
    void breite;
    void hoehe;
    if (!angefasst) untrack(einpassen);
  });

  // Ansicht: verschieben (tx, ty) und zoomen (k), in Bildschirmpixeln.
  let tx = $state(0);
  let ty = $state(0);
  let k = $state(1);

  function einpassen() {
    const r = rahmen(lage.values());
    const neuK = Math.min(2, Math.max(0.15, Math.min(breite / r.b, hoehe / r.h)));
    k = neuK;
    tx = breite / 2 - (r.x + r.b / 2) * neuK;
    ty = hoehe / 2 - (r.y + r.h / 2) * neuK;
  }

  export function zentrieren(id: number, zoom = Math.max(k, 1.1)) {
    const p = lage.get(id);
    if (!p) return;
    angefasst = true;
    k = zoom;
    tx = breite / 2 - p.x * zoom;
    ty = hoehe / 2 - p.y * zoom;
  }

  let fokusErledigt = false;
  $effect(() => {
    if (fokusErledigt || fokus === null || !lage.has(fokus) || breite < 10) return;
    fokusErledigt = true;
    auswahl = fokus;
    zentrieren(fokus, 1.3);
  });

  let nachbarschaft = $derived(nachbarn(kanten));
  let hover = $state<number | null>(null);
  let brennpunkt = $derived(hover ?? auswahl);
  let umfeld = $derived(
    brennpunkt === null ? null : new Set([brennpunkt, ...(nachbarschaft.get(brennpunkt) ?? [])]),
  );
  let treffer = $derived.by(() => {
    const s = verweisSchluessel(suche);
    if (!s) return null;
    return new Set(knoten.filter((n) => verweisSchluessel(n.titel).includes(s)).map((n) => n.id));
  });

  // Gezeichnet wird in Bildschirmpixeln, nicht in einer skalierten Gruppe:
  // Schrift, Linien und Punkte bleiben so beim Herauszoomen lesbar, statt mit
  // der Karte zu schrumpfen. Die Punkte wachsen nur gedämpft mit.
  const bild = (p: Punkt) => ({ x: p.x * k + tx, y: p.y * k + ty });
  let massstab = $derived(Math.min(1.5, Math.max(0.75, Math.sqrt(k))));
  const radius = (n: Knoten) =>
    n.buch ? (9 + 1.6 * Math.sqrt(n.grad)) * massstab : (5 + 2.6 * Math.sqrt(n.grad)) * massstab;
  const oeffnen = (n: Knoten) => goto(n.buch ? `/?buch=${n.notizbuch_id}` : `/notiz/${n.id}`);
  let nachId = $derived(new Map(knoten.map((n) => [n.id, n])));

  /** Linie von Rand zu Rand, damit die Pfeilspitze nicht im Kreis verschwindet. */
  function strecke(kante: Kante) {
    const wa = lage.get(kante.a);
    const wb = lage.get(kante.b);
    if (!wa || !wb) return null;
    const p = bild(wa);
    const q = bild(wb);
    const d = Math.hypot(q.x - p.x, q.y - p.y) || 1;
    const ra = radius(nachId.get(kante.a)!);
    const rb = radius(nachId.get(kante.b)!) + (kante.art === 'text' ? 3 : 0);
    return {
      x1: p.x + ((q.x - p.x) / d) * ra,
      y1: p.y + ((q.y - p.y) / d) * ra,
      x2: q.x - ((q.x - p.x) / d) * rb,
      y2: q.y - ((q.y - p.y) / d) * rb,
    };
  }

  // --- Zeiger: Knoten ziehen, Fläche verschieben, zwei Finger zoomen -------
  let svg = $state<SVGSVGElement | null>(null);
  const zeiger = new Map<number, { x: number; y: number }>();
  let ziehen: { id: number | null; startX: number; startY: number; bewegt: boolean } | null = null;
  let kneifen: { abstand: number; k: number } | null = null;

  function lokal(e: PointerEvent | WheelEvent) {
    const r = svg!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  function runter(e: PointerEvent, id: number | null) {
    e.stopPropagation();
    svg?.setPointerCapture(e.pointerId);
    zeiger.set(e.pointerId, lokal(e));
    const [a, b] = [...zeiger.values()];
    if (a && b) {
      kneifen = { abstand: Math.hypot(a.x - b.x, a.y - b.y) || 1, k };
      ziehen = null;
      return;
    }
    const p = lokal(e);
    ziehen = { id, startX: p.x, startY: p.y, bewegt: false };
  }

  function bewegen(e: PointerEvent) {
    if (!zeiger.has(e.pointerId)) return;
    const alt = zeiger.get(e.pointerId)!;
    const p = lokal(e);
    zeiger.set(e.pointerId, p);
    const [a, b] = [...zeiger.values()];
    if (kneifen && a && b) {
      const mitte = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      zoomenUm(mitte, (kneifen.k * Math.hypot(a.x - b.x, a.y - b.y)) / kneifen.abstand);
      return;
    }
    if (!ziehen) return;
    if (Math.hypot(p.x - ziehen.startX, p.y - ziehen.startY) > 4) ziehen.bewegt = true;
    if (!ziehen.bewegt) return;
    if (ziehen.id === null) {
      angefasst = true;
      tx += p.x - alt.x;
      ty += p.y - alt.y;
    } else {
      const punkt = lage.get(ziehen.id);
      if (punkt) {
        const neu = new Map(lage);
        neu.set(ziehen.id, { x: punkt.x + (p.x - alt.x) / k, y: punkt.y + (p.y - alt.y) / k });
        lage = neu;
      }
    }
  }

  function hoch(e: PointerEvent) {
    zeiger.delete(e.pointerId);
    if (zeiger.size < 2) kneifen = null;
    if (ziehen && !ziehen.bewegt) {
      // Ein Tipp: auf einen Knoten wählt ihn, auf die Fläche hebt die Wahl auf.
      auswahl = ziehen.id;
    }
    ziehen = null;
  }

  function zoomenUm(p: { x: number; y: number }, neuK: number) {
    angefasst = true;
    const grenze = Math.min(4, Math.max(0.1, neuK));
    tx = p.x - ((p.x - tx) * grenze) / k;
    ty = p.y - ((p.y - ty) * grenze) / k;
    k = grenze;
  }

  function rad(e: WheelEvent) {
    e.preventDefault();
    zoomenUm(lokal(e), k * Math.exp(-e.deltaY * 0.0015));
  }

  // Nicht als onwheel im Markup: Svelte haengt Rad-Ereignisse passiv an, dann
  // wirkt preventDefault nicht und die Seite scrollt beim Zoomen mit.
  $effect(() => {
    if (!svg) return;
    const ziel = svg;
    ziel.addEventListener('wheel', rad, { passive: false });
    return () => ziel.removeEventListener('wheel', rad);
  });

  function taste(e: KeyboardEvent, n: Knoten) {
    if (e.key === 'Enter') {
      if (auswahl === n.id) oeffnen(n);
      else auswahl = n.id;
    }
  }

  // Beschriftung: bei genug Zoom alle, sonst nur, was gerade zählt.
  function beschriften(n: Knoten): boolean {
    if (n.buch) return true;
    if (umfeld?.has(n.id) || treffer?.has(n.id)) return true;
    if (k >= 0.85 || (knoten.length <= 40 && k >= 0.4)) return true;
    return k >= 0.45 && n.grad >= 3;
  }
</script>

<div class="relative h-full w-full touch-none select-none" bind:clientWidth={breite} bind:clientHeight={hoehe}>
  <svg
    bind:this={svg}
    width={breite}
    height={hoehe}
    class="block cursor-grab active:cursor-grabbing"
    role="application"
    aria-label="Netz der Notizen. Ziehen verschiebt, Mausrad oder zwei Finger zoomen, Tippen auf einen Punkt wählt die Notiz."
    onpointerdown={(e) => runter(e, null)}
    onpointermove={bewegen}
    onpointerup={hoch}
    onpointercancel={hoch}
  >
    <defs>
      <filter id="netz-schein" x="-100%" y="-100%" width="300%" height="300%">
        <feGaussianBlur stdDeviation="4" result="weich" />
        <feMerge><feMergeNode in="weich" /><feMergeNode in="SourceGraphic" /></feMerge>
      </filter>
      <marker id="netz-pfeil" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" fill="currentColor" />
      </marker>
    </defs>

    <g>
      {#each kanten as kante (`${kante.a}-${kante.b}`)}
        {@const s = strecke(kante)}
        {#if s}
          {@const hell = umfeld?.has(kante.a) && umfeld?.has(kante.b) && (kante.a === brennpunkt || kante.b === brennpunkt)}
          <line
            {...s}
            class="netz-kante {kante.art} {hell ? 'hell' : umfeld ? 'blass' : ''}"
            stroke-width={kante.art === 'buch' ? 1 : 1.4}
            marker-end={kante.art === 'text' ? 'url(#netz-pfeil)' : undefined}
          />
        {/if}
      {/each}

      {#each knoten as n (n.id)}
        {@const welt = lage.get(n.id)}
        {#if welt}
          {@const p = bild(welt)}
          {@const r = radius(n)}
          {@const farbe = (n.notizbuch_id && farben.get(n.notizbuch_id)) || 'var(--color-akzent)'}
          {@const gewaehlt = auswahl === n.id}
          <!-- Die gewählte Notiz und ihre Nachbarn gewinnen gegen die Suche: sonst
               verblasste die eben angetippte Notiz, nur weil sie nicht passt. -->
          {@const blass = umfeld ? !umfeld.has(n.id) : treffer ? !treffer.has(n.id) : false}
          <g
            class="netz-knoten {blass ? 'blass' : ''}"
            transform="translate({p.x} {p.y})"
            role="button"
            tabindex="0"
            aria-label={n.buch
              ? `Notizbuch ${n.titel}, ${n.grad === 1 ? '1 Notiz' : `${n.grad} Notizen`}`
              : `${n.titel || 'Ohne Titel'}, ${n.grad === 1 ? '1 Verbindung' : `${n.grad} Verbindungen`}`}
            aria-pressed={gewaehlt}
            onpointerdown={(e) => runter(e, n.id)}
            onpointerenter={() => (hover = n.id)}
            onpointerleave={() => (hover = null)}
            ondblclick={() => oeffnen(n)}
            onkeydown={(e) => taste(e, n)}
            onfocus={() => (hover = n.id)}
            onblur={() => (hover = null)}
          >
            {#if n.buch}
              <!-- Notizbuch: Raute mit Ring, Name immer sichtbar und fett. -->
              {#if gewaehlt || treffer?.has(n.id)}
                <rect x={-r - 5} y={-r - 5} width={2 * r + 10} height={2 * r + 10} rx="3" transform="rotate(45)" fill="none" stroke={farbe} stroke-width="1.5" opacity="0.7" filter="url(#netz-schein)" />
              {/if}
              <rect x={-r} y={-r} width={2 * r} height={2 * r} rx="2.5" transform="rotate(45)" class="netz-buch" fill="var(--color-surface)" stroke={farbe} stroke-width="2" filter="url(#netz-schein)" />
              <text y={r * 1.45 + 14} text-anchor="middle" class="netz-titel buch {gewaehlt ? 'gewaehlt' : ''}">
                {n.titel.length > 32 ? `${n.titel.slice(0, 30)}…` : n.titel}
              </text>
            {:else}
            {#if gewaehlt || treffer?.has(n.id)}
              <circle r={r + 5} fill="none" stroke={farbe} stroke-width="1.5" opacity="0.7" filter="url(#netz-schein)" />
            {/if}
            <circle
              {r}
              fill={n.grad > 0 ? farbe : 'transparent'}
              stroke={farbe}
              stroke-width={n.grad > 0 ? 0 : 1.6}
              filter={n.grad >= 3 || gewaehlt || hover === n.id ? 'url(#netz-schein)' : undefined}
              opacity={n.archiviert ? 0.5 : 1}
            />
            {#if n.angeheftet}
              <circle r={r + 2.5} fill="none" stroke="var(--color-text)" stroke-width="0.8" opacity="0.5" />
            {/if}
            {#if beschriften(n)}
              <text y={r + 13} text-anchor="middle" class="netz-titel {gewaehlt ? 'gewaehlt' : ''}">
                {(n.titel || 'Ohne Titel').length > 32 ? `${(n.titel || '').slice(0, 30)}…` : n.titel || 'Ohne Titel'}
              </text>
            {/if}
            {/if}
          </g>
        {/if}
      {/each}
    </g>
  </svg>

  <div class="absolute right-2 bottom-2 flex flex-col gap-1">
    <button type="button" class="netz-knopf" aria-label="Näher" onclick={() => zoomenUm({ x: breite / 2, y: hoehe / 2 }, k * 1.3)}>+</button>
    <button type="button" class="netz-knopf" aria-label="Weiter weg" onclick={() => zoomenUm({ x: breite / 2, y: hoehe / 2 }, k / 1.3)}>−</button>
    <button type="button" class="netz-knopf text-xs" aria-label="Alles zeigen" title="Alles zeigen" onclick={einpassen}>⤢</button>
  </div>
</div>

<style>
  .netz-kante {
    stroke: var(--color-muted);
    opacity: 0.55;
    color: var(--color-muted);
    transition: opacity 120ms;
  }
  .netz-kante.text {
    stroke-dasharray: 5 4;
  }
  .netz-kante.buch {
    stroke-dasharray: 1 4;
    stroke-linecap: round;
    opacity: 0.4;
  }
  .netz-kante.hell {
    stroke: var(--color-akzent);
    color: var(--color-akzent);
    opacity: 1;
  }
  .netz-kante.blass {
    opacity: 0.12;
  }
  .netz-knoten {
    cursor: pointer;
    outline: none;
    transition: opacity 120ms;
  }
  .netz-knoten.blass {
    opacity: 0.22;
  }
  .netz-knoten:focus-visible circle:first-of-type {
    stroke: var(--color-text);
    stroke-width: 2;
  }
  .netz-titel {
    fill: var(--color-text);
    font-size: 11px;
    paint-order: stroke;
    stroke: var(--color-surface);
    stroke-width: 3px;
    stroke-linejoin: round;
    pointer-events: none;
  }
  .netz-titel.buch {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.02em;
  }
  .netz-titel.gewaehlt {
    fill: var(--color-akzent);
    font-weight: 600;
  }
  .netz-knopf {
    display: grid;
    place-items: center;
    width: 2.75rem;
    height: 2.75rem;
    border-radius: 0.375rem;
    border: 1px solid var(--color-border-stark);
    background: var(--color-surface);
    color: var(--color-text);
    font-size: 1.1rem;
  }
  .netz-knopf:hover {
    border-color: var(--color-akzent);
  }
</style>
