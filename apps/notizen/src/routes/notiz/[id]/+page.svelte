<script lang="ts">
  import { untrack } from 'svelte';
  import { deserialize, enhance } from '$app/forms';
  import { beforeNavigate, invalidateAll } from '$app/navigation';
  import { Button, Icon } from '@saganta/ui';
  import AnhangBild from '$lib/components/AnhangBild.svelte';
  import MarkdownAnsicht from '$lib/components/MarkdownAnsicht.svelte';
  import NotizWahl from '$lib/components/NotizWahl.svelte';
  import TeilenDialog from '$lib/components/TeilenDialog.svelte';
  import VerknuepfenDialog from '$lib/components/VerknuepfenDialog.svelte';
  import VerweisVorschlaege from '$lib/components/VerweisVorschlaege.svelte';
  import { page } from '$app/stores';
  import { verweisSchluessel } from '$lib/markdown';
  import { TYP_BESCHRIFTUNG, TYP_SYMBOL, zielAdresse } from '$lib/verknuepfungen';
  import type { Fundstueck, Verknuepfung } from '$lib/types';
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();

  // `untrack` sagt hier genau das Gemeinte: den Wert EINMAL übernehmen und die
  // Felder danach dem Nutzer überlassen. Ohne das wären es abgeleitete Werte,
  // die jede Hintergrund-Aktualisierung mitten ins Tippen schreiben würde.
  let titel = $state(untrack(() => data.notiz.titel));
  let inhalt = $state(untrack(() => data.notiz.inhalt));
  let tags = $state(untrack(() => data.notiz.tags.join(', ')));
  let notizbuchId = $state(
    untrack(() => (data.notiz.notizbuch_id ? String(data.notiz.notizbuch_id) : '')),
  );
  let ansicht = $state<'schreiben' | 'lesen'>('schreiben');
  let teilenOffen = $state(false);
  let verknuepfenOffen = $state(false);
  // Die Aufgabe, deren X gerade gefragt hat (Verknüpfung lösen oder Aufgabe löschen).
  let loesenFrage = $state<Verknuepfung | null>(null);
  let gespeichertUm = $state('');

  // Nach dem Neuladen der Seitendaten (z. B. nach einem Anhang-Upload) die
  // Felder nachziehen, aber nur, wenn nichts Ungespeichertes im Weg steht.
  let letzteId = $state(untrack(() => data.notiz.id));
  $effect(() => {
    if (data.notiz.id !== letzteId) {
      letzteId = data.notiz.id;
      titel = data.notiz.titel;
      inhalt = data.notiz.inhalt;
      tags = data.notiz.tags.join(', ');
      notizbuchId = data.notiz.notizbuch_id ? String(data.notiz.notizbuch_id) : '';
    }
  });

  let geaendert = $derived(
    titel !== data.notiz.titel ||
      inhalt !== data.notiz.inhalt ||
      tags !== data.notiz.tags.join(', ') ||
      notizbuchId !== (data.notiz.notizbuch_id ? String(data.notiz.notizbuch_id) : ''),
  );

  let speichernForm = $state<HTMLFormElement | null>(null);
  function tastatur(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      speichernForm?.requestSubmit();
    }
  }

  // Ungespeichertes schützen: interne Navigation fragt nach, beim Schließen
  // des Tabs übernimmt der Browser-Dialog (ein abgebrochenes `leave` löst ihn
  // aus). Nach dem bestätigten Löschen wäre die Frage sinnlos.
  let verlassenErlaubt = false;
  beforeNavigate((nav) => {
    if (!geaendert || verlassenErlaubt) return;
    if (nav.type === 'leave') {
      nav.cancel();
      return;
    }
    if (!confirm('Ungespeicherte Änderungen gehen verloren. Trotzdem verlassen?')) nav.cancel();
  });

  let bildAnhaenge = $derived(data.notiz.anhaenge.filter((a) => a.mime.startsWith('image/')));

  // Bilder aus der Zwischenablage landen direkt als Anhang: derselbe Weg wie
  // das Formular, nur von Hand abgeschickt, weil ein Paste kein Submit ist.
  let anhangFehler = $state('');
  let anhangLaedt = $state(false);
  async function bildEingefuegt(e: ClipboardEvent) {
    const bilder = Array.from(e.clipboardData?.files ?? []).filter((f) =>
      f.type.startsWith('image/'),
    );
    if (!bilder.length) return;
    e.preventDefault();
    anhangLaedt = true;
    anhangFehler = '';
    try {
      for (const bild of bilder) {
        const daten = new FormData();
        daten.append('datei', bild, bild.name || 'zwischenablage.png');
        const res = await fetch('?/anhangHochladen', {
          method: 'POST',
          body: daten,
          headers: { 'x-sveltekit-action': 'true' },
        });
        const ergebnis = deserialize(await res.text());
        if (ergebnis.type === 'failure') {
          const feld = (ergebnis.data as { fehler?: string } | undefined)?.fehler;
          anhangFehler = feld || 'Hochladen fehlgeschlagen.';
        } else if (ergebnis.type === 'error') {
          anhangFehler = 'Hochladen fehlgeschlagen.';
        }
      }
      await invalidateAll();
    } finally {
      anhangLaedt = false;
    }
  }

  function datum(roh: string | null): string {
    if (!roh) return '';
    const d = new Date(roh);
    return Number.isNaN(d.getTime()) ? '' : d.toLocaleString('de-DE', { dateStyle: 'medium' });
  }

  /** Datum und Uhrzeit eines Stands; der Dienst liefert naives UTC ohne Zone. */
  function standZeit(roh: string): string {
    const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(roh) ? roh : `${roh}Z`);
    return Number.isNaN(d.getTime())
      ? ''
      : d.toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short' });
  }

  function zeichenText(n: number): string {
    return n === 1 ? '1 Zeichen' : `${n.toLocaleString('de-DE')} Zeichen`;
  }

  // Nach dem Zurückholen sind die Seitendaten neu, die Felder aber bewusst
  // gelöst (untrack oben). Ohne Nachziehen stünde der alte Text im Editor,
  // die Seite meldete „ungespeichert", und Speichern überschriebe das eben
  // Zurückgeholte wieder.
  function felderNachziehen() {
    titel = data.notiz.titel;
    inhalt = data.notiz.inhalt;
    tags = data.notiz.tags.join(', ');
  }

  function groesse(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  const ZUSTAND_TEXT: Record<string, string> = {
    aktiv: 'aktiv',
    widerrufen: 'zurückgezogen',
    abgelaufen: 'abgelaufen',
    verbraucht: 'aufgebraucht',
    gesperrt: 'gesperrt',
    quelle_weg: 'ohne Notiz',
  };

  // Für die Weitergabe zeigen wir nur die Adresse ohne Schlüssel: der steht
  // bei verschlüsselten Freigaben ausschließlich in dem Link, der beim Anlegen
  // einmal angezeigt wurde. Hier ihn zu erwarten, wäre eine Fehlanzeige.
  //
  // Das `#…` ist deshalb keine Verzierung, sondern der Unterschied zwischen
  // einer vollständigen und einer halben Adresse. Ohne es sah beides gleich aus,
  // und wer von hier kopierte, gab einen Link weiter, der beim Empfänger nicht
  // aufgeht.
  function freigabeAdresse(f: { merkmal: string; schluessel_quelle: string | null }): string {
    const rest = f.schluessel_quelle === 'fragment' ? '#…' : '';
    return `${data.freigabeBasis}/${f.merkmal}${rest}`;
  }

  let verknuepfenForm = $state<HTMLFormElement | null>(null);
  let neueVerknuepfung = $state<Fundstueck | null>(null);
  function verknuepfungUebernehmen(fund: Fundstueck) {
    neueVerknuepfung = fund;
    verknuepfenOffen = false;
    // Im nächsten Zyklus abschicken, wenn die versteckten Felder gefüllt sind.
    queueMicrotask(() => verknuepfenForm?.requestSubmit());
  }

  // --- Verweise zwischen Notizen (seit 2026-11-20) ---------------------
  let wahlOffen = $state(false);
  let verbindenForm = $state<HTMLFormElement | null>(null);
  let verbindenMit = $state('');
  function verbindungUebernehmen(id: number) {
    verbindenMit = String(id);
    wahlOffen = false;
    queueMicrotask(() => verbindenForm?.requestSubmit());
  }

  // `[[Titel]]` → Kennung, aus dem gespeicherten Stand. Ein eben getippter,
  // noch nicht gespeicherter Verweis gilt bis zum Speichern als fehlend.
  let verweisZiele = $derived(
    new Map((data.netz?.verweist_auf ?? []).map((v) => [verweisSchluessel(v.text), v.id])),
  );
  const aufloesen = (titel: string) => verweisZiele.get(verweisSchluessel(titel)) ?? null;

  let inhaltFeld = $state<HTMLTextAreaElement | null>(null);

  let anlegenForm = $state<HTMLFormElement | null>(null);
  let anlegenTitel = $state('');
  function verweisAnlegen(t: string) {
    anlegenTitel = t;
    queueMicrotask(() => anlegenForm?.requestSubmit());
  }
</script>

<svelte:window on:keydown={tastatur} />

<div class="flex flex-col gap-5">
  <div class="flex flex-wrap items-center justify-between gap-2">
    <a href="/" class="flex items-center gap-1 text-sm text-muted hover:text-text">
      <Icon name="arrow-left" size={14} /> Alle Notizen
    </a>
    <div class="flex flex-wrap items-center gap-2">
      <form method="POST" action="?/umschalten" use:enhance>
        <input type="hidden" name="feld" value="angeheftet" />
        <input type="hidden" name="wert" value={String(!data.notiz.angeheftet)} />
        <Button
          type="submit"
          variant="ghost"
          size="sm"
          title={data.notiz.angeheftet ? 'Nicht mehr anheften' : 'Anheften'}
        >
          <Icon name="bookmark" size={16} />
          <span class={data.notiz.angeheftet ? 'text-akzent' : ''}>
            {data.notiz.angeheftet ? 'Angeheftet' : 'Anheften'}
          </span>
        </Button>
      </form>
      <form method="POST" action="?/umschalten" use:enhance>
        <input type="hidden" name="feld" value="archiviert" />
        <input type="hidden" name="wert" value={String(!data.notiz.archiviert)} />
        <Button type="submit" variant="ghost" size="sm">
          <Icon name="archive" size={16} />
          {data.notiz.archiviert ? 'Aus dem Archiv' : 'Archivieren'}
        </Button>
      </form>
      <Button
        type="button"
        size="sm"
        onclick={() => (teilenOffen = true)}
        disabled={geaendert}
        title={geaendert ? 'Erst speichern, sonst teilt der Link einen anderen Stand' : 'Teilen'}
      >
        <Icon name="globe" size={16} /> Teilen
      </Button>
      <form
        method="POST"
        action="?/loeschen"
        use:enhance
        onsubmit={(e) => {
          if (!confirm('Diese Notiz in den Papierkorb legen? Dort bleibt sie 30 Tage.')) e.preventDefault();
          else verlassenErlaubt = true;
        }}
      >
        <!-- Papierkorb statt nacktem x: neben "Teilen" las sich das x wie
             "Schliessen", nicht wie "in den Papierkorb". -->
        <Button type="submit" variant="ghost" size="sm" class="max-sm:min-w-11" title="In den Papierkorb" aria-label="In den Papierkorb">
          <Icon name="trash" size={16} /><span class="max-sm:hidden">Löschen</span>
        </Button>
      </form>
    </div>
  </div>

  <!-- `'fehler' in form` statt `form?.fehler`: die Aktionen dieser Seite geben
       je nach Ausgang verschiedene Formen zurück, und nur so ist für den
       Übersetzer (und den Leser) klar, welche gerade vorliegt. -->
  {#if form && 'fehler' in form}
    <p class="rounded-md border border-fehler/60 bg-fehler/10 px-3 py-2 text-sm text-fehler">
      {form.fehler}
    </p>
  {/if}

  <!-- Editor -->
  <form
    method="POST"
    action="?/speichern"
    bind:this={speichernForm}
    use:enhance={() =>
      ({ update, result }) => {
        // Nur ein gelungenes Speichern bekommt einen Zeitstempel; nach einem
        // 409 stünde da sonst „gespeichert", obwohl nichts übernommen wurde.
        if (result.type === 'success') {
          gespeichertUm = new Date().toLocaleTimeString('de-DE', {
            hour: '2-digit',
            minute: '2-digit',
          });
        }
        return update({ reset: false });
      }}
    class="flex flex-col gap-3"
  >
    <!-- Der Stand, von dem diese Änderung ausgeht. Kommt beim Speichern ein
         anderer Stand im Bestand an, antwortet die API mit 409 statt still zu
         überschreiben; nach jedem Neuladen der Daten zieht der Wert nach. -->
    <input type="hidden" name="basis" value={data.notiz.geaendert_am} />
    <!-- Titel als Ueberschrift, randlos und mitwachsend: das einzeilige Feld
         schnitt lange Titel am Handy ab. Enter schreibt keinen Zeilenumbruch. -->
    <textarea
      name="titel"
      bind:value={titel}
      rows="1"
      placeholder="Titel"
      aria-label="Titel"
      onkeydown={(e) => {
        if (e.key === 'Enter') e.preventDefault();
      }}
      class="w-full resize-none rounded-md border border-transparent bg-transparent px-1 py-1 font-display text-2xl leading-tight [field-sizing:content] hover:border-border focus:border-border-stark focus:outline-none"
    ></textarea>

    <div class="flex flex-wrap items-center gap-2 text-sm">
      <div class="inline-flex overflow-hidden rounded-md border border-border-stark">
        <button
          type="button"
          aria-pressed={ansicht === 'schreiben'}
          onclick={() => (ansicht = 'schreiben')}
          class="px-3 py-1.5 max-md:min-h-11 {ansicht === 'schreiben' ? 'bg-surface-2 text-text' : 'text-muted'}"
          >Schreiben</button
        >
        <button
          type="button"
          aria-pressed={ansicht === 'lesen'}
          onclick={() => (ansicht = 'lesen')}
          class="px-3 py-1.5 max-md:min-h-11 {ansicht === 'lesen' ? 'bg-surface-2 text-text' : 'text-muted'}"
          >Vorschau</button
        >
      </div>

      <select
        name="notizbuch_id"
        bind:value={notizbuchId}
        class="rounded-md border border-border-stark bg-surface px-2 py-1.5 max-md:min-h-11"
      >
        <option value="">Ohne Notizbuch</option>
        {#each data.notizbuecher as buch (buch.id)}
          <option value={String(buch.id)}>{buch.name}</option>
        {/each}
      </select>

      <input
        name="tags"
        bind:value={tags}
        placeholder="Tags, mit Komma getrennt"
        class="min-w-40 flex-1 rounded-md border border-border-stark bg-surface px-3 py-1.5 max-md:min-h-11"
      />

      <!-- Gespeichert ist ein Zustand, kein Knopf: vorher stand dauerhaft ein
           ausgegrauter Messing-Knopf "Gespeichert" da, Messing auf Messing. -->
      {#if geaendert}
        <Button type="submit" size="sm">Speichern</Button>
      {:else}
        <span class="inline-flex items-center gap-1 text-xs text-muted" role="status">
          <Icon name="check" size={12} /> Gespeichert{gespeichertUm ? ` um ${gespeichertUm}` : ''}
        </span>
      {/if}
    </div>

    {#if ansicht === 'schreiben'}
      <!-- relative: an diesem Rahmen richtet sich die Vorschlagsliste für [[ aus. -->
      <div class="relative max-w-3xl">
      <textarea
        name="inhalt"
        bind:this={inhaltFeld}
        bind:value={inhalt}
        rows="18"
        spellcheck="true"
        onpaste={bildEingefuegt}
        placeholder="Markdown: # Überschrift, **fett**, - Liste, [Link](https://…), [[andere Notiz]]"
        class="min-h-96 w-full max-w-3xl rounded-md border border-border bg-surface px-4 py-3 text-base leading-7 [field-sizing:content] focus:border-border-stark focus:outline-none"
      ></textarea>
      <VerweisVorschlaege feld={inhaltFeld} bind:wert={inhalt} ohne={data.notiz.id} />
      </div>
    {:else}
      <input type="hidden" name="inhalt" value={inhalt} />
      <div class="min-h-64 max-w-3xl rounded-md border border-border bg-surface px-4 py-3">
        <MarkdownAnsicht quelle={inhalt} verweise={aufloesen} anlegen={verweisAnlegen} />
      </div>
    {/if}
  </form>

  <!-- Verweise zwischen Notizen: von Hand verbunden, per [[Titel]] hin und zurück -->
  <section class="rounded-lg border border-border p-4" aria-labelledby="netz-kopf">
    <div class="flex items-center justify-between">
      <h2 id="netz-kopf" class="text-sm font-semibold">Verbundene Notizen</h2>
      <div class="flex items-center gap-1">
        <a href="/netz?fokus={data.notiz.id}" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-muted hover:bg-surface-2 hover:text-text max-md:min-h-11">
          <Icon name="share-2" size={14} /> Im Netz
        </a>
        <Button type="button" variant="ghost" size="sm" onclick={() => (wahlOffen = true)}>
          <Icon name="link" size={14} /> Verbinden
        </Button>
      </div>
    </div>

    <form method="POST" action="?/verbinden" bind:this={verbindenForm} use:enhance>
      <input type="hidden" name="mit" value={verbindenMit} />
    </form>
    <form method="POST" action="?/neuAusVerweis" bind:this={anlegenForm} use:enhance={({ cancel }) => {
      if (geaendert && !confirm('Ungespeicherte Änderungen gehen verloren. Trotzdem die neue Notiz öffnen?')) {
        cancel();
        return;
      }
      verlassenErlaubt = true;
    }}>
      <input type="hidden" name="titel" value={anlegenTitel} />
    </form>

    {#if !data.netz}
      <p class="mt-3 text-sm text-muted">Die Verweise ließen sich gerade nicht laden.</p>
    {:else}
      {@const netz = data.netz}
      {#if netz.verbunden.length === 0 && netz.erwaehnt_in.length === 0 && netz.verweist_auf.length === 0}
        <p class="mt-3 text-sm text-muted">
          Noch keine. Verbinde diese Notiz mit einer anderen, oder schreib <code>[[</code> in den
          Text, dann schlägt die Liste passende Titel vor und daraus wird ein Link. Mehrere auf einmal verbindest du in der Liste
          über „Auswählen“.
        </p>
      {/if}

      {#if netz.verbunden.length}
        <ul class="mt-3 flex flex-col gap-1">
          {#each netz.verbunden as n (n.id)}
            <li class="group flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-surface-2">
              <span class="shrink-0 text-muted"><Icon name="link" size={16} /></span>
              <a href="/notiz/{n.id}" class="min-w-0 flex-1 max-md:py-1.5">
                <span class="block truncate text-sm hover:underline">{n.titel || 'Ohne Titel'}</span>
                {#if n.ausschnitt}<span class="block truncate text-xs text-muted">{n.archiviert ? 'Archiv · ' : ''}{n.ausschnitt}</span>{/if}
              </a>
              <form method="POST" action="?/entbinden" use:enhance class="md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100">
                <input type="hidden" name="mit" value={n.id} />
                <button type="submit" class="grid size-11 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-text md:size-8" aria-label="Verbindung lösen">
                  <Icon name="x" size={14} />
                </button>
              </form>
            </li>
          {/each}
        </ul>
      {/if}

      {#if netz.verweist_auf.length}
        <h3 class="mt-4 text-xs font-semibold text-muted">Verweist im Text auf</h3>
        <ul class="mt-1 flex flex-wrap gap-2">
          {#each netz.verweist_auf as v (v.text)}
            <li>
              {#if v.id}
                <a href="/notiz/{v.id}" class="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1 text-sm hover:bg-surface-2 max-md:min-h-11">
                  <Icon name="file-text" size={12} />{v.text}
                </a>
              {:else}
                <button
                  type="button"
                  onclick={() => verweisAnlegen(v.text)}
                  title="Gibt es noch nicht: anlegen"
                  class="inline-flex items-center gap-1 rounded-full border border-dashed border-border-stark px-2.5 py-1 text-sm text-muted hover:text-text max-md:min-h-11"
                >
                  <Icon name="plus" size={12} />{v.text}
                </button>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}

      {#if netz.erwaehnt_in.length}
        <h3 class="mt-4 text-xs font-semibold text-muted">Erwähnt in</h3>
        <ul class="mt-1 flex flex-col gap-1">
          {#each netz.erwaehnt_in as n (n.id)}
            <li>
              <a href="/notiz/{n.id}" class="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-surface-2 max-md:min-h-11">
                <span class="shrink-0 text-muted"><Icon name="file-text" size={16} /></span>
                <span class="min-w-0 flex-1 truncate text-sm">{n.titel || 'Ohne Titel'}</span>
              </a>
            </li>
          {/each}
        </ul>
      {/if}
    {/if}
  </section>

  <div class="grid gap-5 lg:grid-cols-2">
    <!-- Verknüpfungen -->
    <section class="rounded-lg border border-border p-4">
      <div class="flex items-center justify-between">
        <h2 class="text-sm font-semibold">Verknüpft mit</h2>
        <div class="flex items-center gap-1">
          {#if data.kannAufgabe}
            <form method="POST" action="?/aufgabeDazu" use:enhance>
              <Button type="submit" variant="ghost" size="sm" title="Aufgabe mit dem Titel dieser Notiz anlegen und verbinden">
                <Icon name="check" size={14} /> Aufgabe dazu
              </Button>
            </form>
          {/if}
          <Button type="button" variant="ghost" size="sm" onclick={() => (verknuepfenOffen = true)}>
            <Icon name="plus" size={14} /> Verknüpfen
          </Button>
        </div>
      </div>
      {#if form && 'hinweis' in form}
        <p class="mt-2 text-xs text-muted" role="status">{form.hinweis}</p>
      {/if}

      <form method="POST" action="?/verknuepfen" bind:this={verknuepfenForm} use:enhance={() => {
        return async ({ update }) => {
          neueVerknuepfung = null;
          await update();
        };
      }}>
        <input type="hidden" name="typ" value={neueVerknuepfung?.typ ?? ''} />
        <input type="hidden" name="ref" value={neueVerknuepfung?.ref ?? ''} />
        <input type="hidden" name="label" value={neueVerknuepfung?.label ?? ''} />
      </form>

      {#if data.notiz.verknuepfungen.length === 0}
        <p class="mt-3 text-sm text-muted">
          Noch nichts. Eine Notiz lässt sich an einen Termin, eine Aufgabe, ein Ziel, ein Projekt,
          einen Kontakt oder einen Brief hängen.
        </p>
      {:else}
        <ul class="mt-3 flex flex-col gap-1">
          {#each data.notiz.verknuepfungen as v (v.id)}
            {@const ziel = zielAdresse(v.typ, v.ref, $page.url.host)}
            <li class="group flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-surface-2">
              <span class="shrink-0 text-muted"><Icon name={TYP_SYMBOL[v.typ]} size={16} /></span>
              <span class="min-w-0 flex-1">
                {#if ziel}
                  <a href={ziel} class="block truncate text-sm hover:underline max-md:py-1.5">{v.label || v.ref}</a>
                {:else}
                  <span class="block truncate text-sm">{v.label || v.ref}</span>
                {/if}
                <span class="text-xs text-muted">{TYP_BESCHRIFTUNG[v.typ]}</span>
              </span>
              <!-- Am PC erst beim Ueberfahren, am Handy immer sichtbar: dort gibt es
                   kein Hover, der Knopf war unsichtbar und blind antippbar. -->
              {#if v.typ === 'aufgabe' && data.kannAufgabe}
                <!-- Bei einer Aufgabe erst fragen: nur die Verknüpfung oder die Aufgabe selbst. -->
                <button type="button" onclick={() => (loesenFrage = v)} class="grid size-11 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-text md:size-8 md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100" aria-label="Verknüpfung lösen oder Aufgabe löschen">
                  <Icon name="x" size={14} />
                </button>
              {:else}
                <form method="POST" action="?/entknuepfen" use:enhance class="md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100">
                  <input type="hidden" name="id" value={v.id} />
                  <button type="submit" class="grid size-11 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-text md:size-8" aria-label="Verknüpfung lösen">
                    <Icon name="x" size={14} />
                  </button>
                </form>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <!-- Anhänge -->
    <section class="rounded-lg border border-border p-4">
      <h2 class="text-sm font-semibold">Anhänge</h2>
      <form
        method="POST"
        action="?/anhangHochladen"
        enctype="multipart/form-data"
        use:enhance={() =>
          async ({ update }) => {
            await update({ reset: true });
            await invalidateAll();
          }}
        class="mt-3 flex items-center gap-2"
      >
        <input
          type="file"
          name="datei"
          accept="image/jpeg,image/png,image/gif,image/webp,application/pdf,text/plain,text/markdown"
          class="min-w-0 flex-1 text-sm file:mr-2 file:rounded-md file:border file:border-border-stark file:bg-surface-2 file:px-2 file:py-1 file:text-sm file:text-text"
          onchange={(e) => e.currentTarget.form?.requestSubmit()}
        />
      </form>
      <p class="mt-1 text-xs text-muted">
        Bilder, PDF und Text bis 20 MB. Ein ins Textfeld eingefügtes Bild
        (Strg+V) landet direkt hier.
      </p>
      {#if anhangLaedt}
        <p class="mt-2 text-xs text-muted">Bild wird hochgeladen…</p>
      {/if}
      {#if anhangFehler}
        <p class="mt-2 rounded-md border border-fehler/60 bg-fehler/10 px-3 py-2 text-xs text-fehler">
          {anhangFehler}
        </p>
      {/if}

      {#if data.notiz.anhaenge.length}
        <ul class="mt-3 flex flex-col gap-1">
          {#each data.notiz.anhaenge as a (a.id)}
            <li class="group flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-surface-2">
              <span class="shrink-0 text-muted"><Icon name="download" size={16} /></span>
              <a
                href="/notiz/{data.notiz.id}/anhang/{a.id}"
                class="min-w-0 flex-1 truncate text-sm hover:underline max-md:py-3">{a.dateiname}</a
              >
              <span class="shrink-0 text-xs text-muted">{groesse(a.groesse)}</span>
              <!-- Am PC erst beim Ueberfahren, am Handy immer sichtbar: dort gibt es
                   kein Hover, der Knopf war unsichtbar und blind antippbar. -->
              <form method="POST" action="?/anhangLoeschen" use:enhance class="md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100">
                <input type="hidden" name="id" value={a.id} />
                <button type="submit" class="grid size-11 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-text md:size-8" aria-label="Anhang löschen">
                  <Icon name="x" size={14} />
                </button>
              </form>
            </li>
          {/each}
        </ul>
      {/if}

      {#if bildAnhaenge.length}
        <div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {#each bildAnhaenge as a (a.id)}
            <AnhangBild
              url="/notiz/{data.notiz.id}/anhang/{a.id}"
              beschriftung={a.dateiname}
            />
          {/each}
        </div>
      {/if}
    </section>
  </div>

  <!-- Frühere Stände (seit 2026-11-14) -->
  {#if data.stand}
    <section class="rounded-lg border border-akzent/60 p-4" aria-labelledby="stand-kopf">
      <div class="flex flex-wrap items-center gap-2">
        <h2 id="stand-kopf" class="flex-1 text-sm font-semibold">
          Stand vom {standZeit(data.stand.stand_vom)}
        </h2>
        <form
          method="POST"
          action="?/standWiederherstellen"
          use:enhance={() =>
            async ({ update }) => {
              await update();
              felderNachziehen();
            }}
        >
          <input type="hidden" name="id" value={data.stand.id} />
          <Button
            type="submit"
            size="sm"
            disabled={geaendert}
            title={geaendert ? 'Erst speichern oder verwerfen, sonst ginge Ungespeichertes verloren' : undefined}
          >
            Diesen Stand zurückholen
          </Button>
        </form>
        <a href="/notiz/{data.notiz.id}" class="text-xs text-muted underline hover:text-text">schließen</a>
      </div>
      <p class="mt-1 text-xs text-muted">
        Der jetzige Text wird dabei selbst als Stand abgelegt, das Zurückholen lässt sich also
        zurücknehmen.
      </p>
      {#if data.stand.titel}<p class="mt-3 font-semibold">{data.stand.titel}</p>{/if}
      <div class="mt-2 max-h-96 overflow-auto rounded-md bg-surface-2/40 p-3">
        <MarkdownAnsicht quelle={data.stand.inhalt} />
      </div>
      {#if data.stand.tags.length}
        <p class="mt-2 text-xs text-muted">Tags: {data.stand.tags.join(', ')}</p>
      {/if}
    </section>
  {/if}

  {#if data.staende?.length}
    <section class="rounded-lg border border-border p-4">
      <h2 class="text-sm font-semibold">Frühere Stände</h2>
      <ul class="mt-3 flex flex-col gap-1">
        {#each data.staende as s (s.id)}
          <li>
            <a
              href="?stand={s.id}"
              class="flex items-center gap-3 rounded-md px-2 py-1.5 text-sm hover:bg-surface-2 {data.stand?.id === s.id ? 'bg-surface-2' : ''}"
            >
              <span class="shrink-0 text-muted"><Icon name="clock" size={16} /></span>
              <span class="min-w-0 flex-1 truncate">{standZeit(s.stand_vom)}</span>
              <span class="shrink-0 text-xs text-muted">{zeichenText(s.zeichen)}</span>
            </a>
          </li>
        {/each}
      </ul>
      <p class="mt-2 text-xs text-muted">
        Die letzten fünf. Abgelegt wird der Stand vor jeder Sitzung, in der Titel, Text oder Tags
        sich ändern.
      </p>
    </section>
  {/if}

  <!-- Freigaben dieser Notiz -->
  {#if data.notiz.freigaben.length}
    <section class="rounded-lg border border-border p-4">
      <h2 class="text-sm font-semibold">Geteilte Links</h2>
      <ul class="mt-3 flex flex-col gap-2">
        {#each data.notiz.freigaben as f (f.id)}
          <li class="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md bg-surface-2/40 px-3 py-2">
            <span class="text-muted" title={f.modus === 'chiffriert' ? 'Verschlüsselt' : 'Offen'}>
              <Icon name={f.modus === 'chiffriert' ? 'shield' : 'globe'} size={16} />
            </span>
            <code
              class="min-w-0 flex-1 truncate text-xs"
              title={f.schluessel_quelle === 'fragment'
                ? 'Unvollständig: der Schlüssel hinter dem # steht nur in dem Link, der beim Anlegen zu sehen war'
                : undefined}>{freigabeAdresse(f)}</code
            >
            <span class="text-xs {f.zustand === 'aktiv' ? 'text-muted' : 'text-akzent'}">
              {ZUSTAND_TEXT[f.zustand] ?? f.zustand}
            </span>
            <span class="text-xs text-muted">
              {f.abrufe}{f.max_abrufe ? `/${f.max_abrufe}` : ''} geöffnet
              {#if f.ablauf_am}· bis {datum(f.ablauf_am)}{/if}
              {#if f.passwortgeschuetzt}· Passwort{/if}
            </span>
            {#if f.zustand === 'aktiv'}
              <form method="POST" action="?/freigabeWiderrufen" use:enhance>
                <input type="hidden" name="id" value={f.id} />
                <button type="submit" class="min-h-11 text-xs text-muted underline hover:text-text md:min-h-0">
                  zurückziehen
                </button>
              </form>
            {:else}
              <form method="POST" action="?/freigabeEntfernen" use:enhance>
                <input type="hidden" name="id" value={f.id} />
                <button type="submit" class="min-h-11 text-xs text-muted underline hover:text-text md:min-h-0">
                  entfernen
                </button>
              </form>
            {/if}
          </li>
        {/each}
      </ul>
      {#if data.notiz.freigaben.some((f) => f.modus === 'chiffriert')}
        <p class="mt-2 text-xs text-muted">
          Bei verschlüsselten Links fehlt hier der Schlüsselteil hinter dem <code>#</code>, den
          haben wir nie gespeichert. Ist er verloren, hilft nur ein neuer Link.
        </p>
      {/if}
    </section>
  {/if}
</div>

<NotizWahl
  offen={wahlOffen}
  ohne={[data.notiz.id, ...(data.netz?.verbunden.map((n) => n.id) ?? [])]}
  schliessen={() => (wahlOffen = false)}
  uebernehmen={verbindungUebernehmen}
/>

{#if loesenFrage}
  {@const frage = loesenFrage}
  <div
    class="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 pt-24"
    role="presentation"
    onclick={(e) => e.target === e.currentTarget && (loesenFrage = null)}
    onkeydown={(e) => e.key === 'Escape' && (loesenFrage = null)}
  >
    <div class="w-full max-w-md rounded-lg border border-border bg-surface p-4 shadow-xl" role="dialog" aria-modal="true" aria-labelledby="loesen-titel">
      <h2 id="loesen-titel" class="font-semibold">Aufgabe „{frage.label || frage.ref}“</h2>
      <p class="mt-1 text-sm text-muted">Nur die Verknüpfung zu dieser Notiz entfernen oder die Aufgabe ganz löschen?</p>
      <div class="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <form method="POST" action="?/entknuepfen" use:enhance={() => async ({ update }) => { loesenFrage = null; await update(); }}>
          <input type="hidden" name="id" value={frage.id} />
          <Button type="submit" size="sm">Nur Verknüpfung entfernen</Button>
        </form>
        <form method="POST" action="?/aufgabeLoeschen" use:enhance={() => async ({ update }) => { loesenFrage = null; await update(); }}>
          <input type="hidden" name="id" value={frage.id} />
          <input type="hidden" name="ref" value={frage.ref} />
          <Button type="submit" size="sm" variant="danger"><Icon name="trash" size={14} /> Aufgabe löschen</Button>
        </form>
        <Button type="button" size="sm" variant="ghost" onclick={() => (loesenFrage = null)}>Abbrechen</Button>
      </div>
    </div>
  </div>
{/if}

<VerknuepfenDialog
  offen={verknuepfenOffen}
  schliessen={() => (verknuepfenOffen = false)}
  uebernehmen={verknuepfungUebernehmen}
/>

<TeilenDialog
  offen={teilenOffen}
  notizId={data.notiz.id}
  titel={data.notiz.titel}
  inhalt={data.notiz.inhalt}
  hatAnhaenge={data.notiz.anhaenge.length > 0}
  basis={data.freigabeBasis}
  schliessen={() => (teilenOffen = false)}
  fertig={() => invalidateAll()}
/>
