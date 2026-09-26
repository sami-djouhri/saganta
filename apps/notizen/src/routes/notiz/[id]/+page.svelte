<script lang="ts">
  import { untrack } from 'svelte';
  import { deserialize, enhance } from '$app/forms';
  import { beforeNavigate, invalidateAll } from '$app/navigation';
  import { Button, Icon } from '@saganta/ui';
  import AnhangBild from '$lib/components/AnhangBild.svelte';
  import MarkdownAnsicht from '$lib/components/MarkdownAnsicht.svelte';
  import TeilenDialog from '$lib/components/TeilenDialog.svelte';
  import VerknuepfenDialog from '$lib/components/VerknuepfenDialog.svelte';
  import { page } from '$app/stores';
  import { TYP_BESCHRIFTUNG, TYP_SYMBOL, zielAdresse } from '$lib/verknuepfungen';
  import type { Fundstueck } from '$lib/types';
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
  function freigabeAdresse(merkmal: string): string {
    return `${data.freigabeBasis}/${merkmal}`;
  }

  let verknuepfenForm = $state<HTMLFormElement | null>(null);
  let neueVerknuepfung = $state<Fundstueck | null>(null);
  function verknuepfungUebernehmen(fund: Fundstueck) {
    neueVerknuepfung = fund;
    verknuepfenOffen = false;
    // Im nächsten Zyklus abschicken, wenn die versteckten Felder gefüllt sind.
    queueMicrotask(() => verknuepfenForm?.requestSubmit());
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
          <span class={data.notiz.angeheftet ? 'text-accent-400' : ''}>
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
          if (!confirm('Diese Notiz endgültig löschen?')) e.preventDefault();
          else verlassenErlaubt = true;
        }}
      >
        <Button type="submit" variant="ghost" size="sm" title="Löschen">
          <Icon name="x" size={16} />
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
    <input
      name="titel"
      bind:value={titel}
      placeholder="Titel"
      class="w-full rounded-md border border-border bg-surface px-3 py-2 font-display text-xl"
    />

    <div class="flex flex-wrap items-center gap-2 text-sm">
      <div class="inline-flex overflow-hidden rounded-md border border-border">
        <button
          type="button"
          onclick={() => (ansicht = 'schreiben')}
          class="px-3 py-1.5 {ansicht === 'schreiben' ? 'bg-surface-2 text-text' : 'text-muted'}"
          >Schreiben</button
        >
        <button
          type="button"
          onclick={() => (ansicht = 'lesen')}
          class="px-3 py-1.5 {ansicht === 'lesen' ? 'bg-surface-2 text-text' : 'text-muted'}"
          >Vorschau</button
        >
      </div>

      <select
        name="notizbuch_id"
        bind:value={notizbuchId}
        class="rounded-md border border-border bg-surface px-2 py-1.5"
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
        class="min-w-40 flex-1 rounded-md border border-border bg-surface px-3 py-1.5"
      />

      <Button type="submit" size="sm" disabled={!geaendert}>
        {geaendert ? 'Speichern' : 'Gespeichert'}
      </Button>
      {#if gespeichertUm && !geaendert}
        <span class="text-xs text-muted">um {gespeichertUm}</span>
      {/if}
    </div>

    {#if ansicht === 'schreiben'}
      <textarea
        name="inhalt"
        bind:value={inhalt}
        rows="18"
        spellcheck="true"
        onpaste={bildEingefuegt}
        placeholder="Markdown: # Überschrift, **fett**, - Liste, [Link](https://…), ```Code```"
        class="w-full rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm leading-relaxed"
      ></textarea>
    {:else}
      <input type="hidden" name="inhalt" value={inhalt} />
      <div class="min-h-64 rounded-md border border-border bg-surface px-4 py-3">
        <MarkdownAnsicht quelle={inhalt} />
      </div>
    {/if}
  </form>

  <div class="grid gap-5 lg:grid-cols-2">
    <!-- Verknüpfungen -->
    <section class="rounded-lg border border-border p-4">
      <div class="flex items-center justify-between">
        <h2 class="text-sm font-semibold">Verknüpft mit</h2>
        <Button type="button" variant="ghost" size="sm" onclick={() => (verknuepfenOffen = true)}>
          <Icon name="plus" size={14} /> Verknüpfen
        </Button>
      </div>

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
                  <a href={ziel} class="block truncate text-sm hover:underline">{v.label || v.ref}</a>
                {:else}
                  <span class="block truncate text-sm">{v.label || v.ref}</span>
                {/if}
                <span class="text-xs text-muted">{TYP_BESCHRIFTUNG[v.typ]}</span>
              </span>
              <form method="POST" action="?/entknuepfen" use:enhance class="opacity-0 group-hover:opacity-100">
                <input type="hidden" name="id" value={v.id} />
                <button type="submit" class="text-muted hover:text-text" aria-label="Verknüpfung lösen">
                  <Icon name="x" size={14} />
                </button>
              </form>
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
          class="min-w-0 flex-1 text-sm file:mr-2 file:rounded-md file:border file:border-border file:bg-surface-2 file:px-2 file:py-1 file:text-sm file:text-text"
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
                class="min-w-0 flex-1 truncate text-sm hover:underline">{a.dateiname}</a
              >
              <span class="shrink-0 text-xs text-muted">{groesse(a.groesse)}</span>
              <form method="POST" action="?/anhangLoeschen" use:enhance class="opacity-0 group-hover:opacity-100">
                <input type="hidden" name="id" value={a.id} />
                <button type="submit" class="text-muted hover:text-text" aria-label="Anhang löschen">
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
            <code class="min-w-0 flex-1 truncate text-xs">{freigabeAdresse(f.merkmal)}</code>
            <span class="text-xs {f.zustand === 'aktiv' ? 'text-muted' : 'text-accent-400'}">
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
                <button type="submit" class="text-xs text-muted underline hover:text-text">
                  zurückziehen
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
  schliessen={() => (teilenOffen = false)}
  fertig={() => invalidateAll()}
/>
