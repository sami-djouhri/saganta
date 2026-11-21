<script lang="ts">
  import { tick } from 'svelte';
  import { Icon } from '@saganta/ui';
  import { cursorPunkt, offenerVerweis, verweisEinsetzen, type OffenerVerweis } from '$lib/verweis-eingabe';
  import { verweisSchluessel } from '$lib/markdown';

  interface Treffer {
    id: number;
    titel: string;
    archiviert: boolean;
  }

  let {
    feld,
    wert = $bindable(''),
    ohne,
  }: {
    /** Das Textfeld, an dem die Liste hängt; ihr Elternteil muss `relative` sein. */
    feld: HTMLTextAreaElement | null;
    wert: string;
    /** Die eigene Notiz bietet sich nicht selbst an. */
    ohne: number;
  } = $props();

  let offen = $state<OffenerVerweis | null>(null);
  let treffer = $state<Treffer[]>([]);
  let markiert = $state(0);
  let lage = $state({ x: 0, y: 0 });

  // Was die Liste anbietet: die gefundenen Titel und, wenn keiner genau passt,
  // die Eingabe selbst als Verweis auf eine Notiz, die es noch nicht gibt.
  let angebot = $derived.by(() => {
    const liste: { titel: string; neu: boolean; archiviert: boolean }[] = treffer.map((t) => ({
      titel: t.titel,
      neu: false,
      archiviert: t.archiviert,
    }));
    const eingabe = offen?.anfrage.trim() ?? '';
    if (eingabe && !treffer.some((t) => verweisSchluessel(t.titel) === verweisSchluessel(eingabe))) {
      liste.push({ titel: eingabe, neu: true, archiviert: false });
    }
    return liste;
  });

  let lauf = 0;
  let entprellung: ReturnType<typeof setTimeout> | undefined;
  function abrufen(anfrage: string) {
    clearTimeout(entprellung);
    entprellung = setTimeout(async () => {
      const meiner = ++lauf;
      try {
        const res = await fetch(`/titelwahl?${new URLSearchParams({ q: anfrage, ohne: String(ohne) })}`);
        if (!res.ok) throw new Error(String(res.status));
        const daten = (await res.json()) as Treffer[];
        if (meiner === lauf) {
          treffer = daten;
          markiert = 0;
        }
      } catch {
        if (meiner === lauf) treffer = [];
      }
    }, 120);
  }

  function pruefen() {
    if (!feld || feld.selectionStart !== feld.selectionEnd) {
      schliessen();
      return;
    }
    const neu = offenerVerweis(feld.value, feld.selectionStart);
    if (!neu) {
      schliessen();
      return;
    }
    const geaendert = neu.anfrage !== offen?.anfrage || neu.start !== offen?.start;
    offen = neu;
    if (geaendert) {
      const p = cursorPunkt(feld, neu.start);
      lage = {
        x: Math.min(feld.offsetLeft + p.x, feld.offsetLeft + feld.clientWidth - 288),
        y: feld.offsetTop + p.y + 4,
      };
      abrufen(neu.anfrage);
    }
  }

  function schliessen() {
    offen = null;
    treffer = [];
    lauf++;
    clearTimeout(entprellung);
  }

  async function uebernehmen(titel: string) {
    if (!feld || !offen) return;
    const neu = verweisEinsetzen(feld.value, feld.selectionStart, offen, titel);
    wert = neu.text;
    schliessen();
    await tick();
    feld.focus();
    feld.setSelectionRange(neu.cursor, neu.cursor);
  }

  function taste(e: KeyboardEvent) {
    if (!offen || angebot.length === 0) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const n = angebot.length;
      markiert = (markiert + (e.key === 'ArrowDown' ? 1 : n - 1)) % n;
    } else if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault();
      uebernehmen(angebot[markiert]?.titel ?? '');
    } else if (e.key === 'Escape') {
      e.preventDefault();
      schliessen();
    }
  }

  $effect(() => {
    if (!feld) return;
    const ziel = feld;
    // Nach dem Tippen erst im nächsten Takt lesen, dann steht der Cursor fest.
    const nachher = () => queueMicrotask(pruefen);
    const weg = () => setTimeout(schliessen, 150);
    ziel.addEventListener('input', nachher);
    ziel.addEventListener('click', nachher);
    ziel.addEventListener('keydown', taste);
    const pfeil = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight' || e.key === 'Home' || e.key === 'End') nachher();
    };
    ziel.addEventListener('keyup', pfeil);
    ziel.addEventListener('blur', weg);
    return () => {
      ziel.removeEventListener('input', nachher);
      ziel.removeEventListener('click', nachher);
      ziel.removeEventListener('keydown', taste);
      ziel.removeEventListener('keyup', pfeil);
      ziel.removeEventListener('blur', weg);
    };
  });
</script>

{#if offen && angebot.length}
  <ul
    role="listbox"
    aria-label="Notiz verlinken"
    class="absolute z-20 w-72 max-w-[calc(100%-1rem)] overflow-hidden rounded-md border border-akzent/60 bg-surface py-1 text-sm shadow-[0_0_22px_-8px_var(--color-akzent)]"
    style="left: {Math.max(8, lage.x)}px; top: {lage.y}px"
  >
    {#each angebot as a, i (a.titel + a.neu)}
      <li role="option" aria-selected={i === markiert}>
        <!-- mousedown statt click: sonst verliert das Textfeld zuerst den Fokus
             und die Liste schließt sich, bevor der Klick ankommt. -->
        <button
          type="button"
          class="flex w-full items-center gap-2 px-3 py-2 text-left max-md:min-h-11 {i === markiert ? 'bg-surface-2 text-text' : 'text-muted'}"
          onmousedown={(e) => {
            e.preventDefault();
            uebernehmen(a.titel);
          }}
          onmouseenter={() => (markiert = i)}
        >
          <span class="shrink-0 {a.neu ? 'text-muted' : 'text-akzent'}"><Icon name={a.neu ? 'plus' : 'file-text'} size={14} /></span>
          <span class="min-w-0 flex-1 truncate">{a.titel}</span>
          {#if a.neu}<span class="shrink-0 text-xs text-muted">neu</span>{:else if a.archiviert}<span class="shrink-0 text-xs text-muted">Archiv</span>{/if}
        </button>
      </li>
    {/each}
  </ul>
{/if}
