<script lang="ts">
  import { Button, Icon, Spinner } from '@saganta/ui';
  import AnhangBild from '$lib/components/AnhangBild.svelte';
  import MarkdownAnsicht from '$lib/components/MarkdownAnsicht.svelte';
  import {
    entschluesseln,
    paketOeffnen,
    schluesselAusPasswort,
    schluesselImportieren,
    KDF_ITERATIONEN,
  } from '$lib/krypto';
  import type { OeffentlicherInhalt } from '$lib/types';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  let passwort = $state('');
  let laeuft = $state(false);
  let fehler = $state('');
  let geoeffnet = $state<{
    titel: string;
    inhalt: string;
    anhaenge: OeffentlicherInhalt['anhaenge'];
    schein: string | null;
    einmalig: boolean;
  } | null>(null);

  let zustand = $derived(data.zustand);
  let brauchtPasswort = $derived(zustand.braucht_passwort);

  const ZUSTAND_MELDUNG: Record<string, { titel: string; text: string }> = {
    widerrufen: {
      titel: 'Zurückgezogen',
      text: 'Der Absender hat diesen Link zurückgezogen. Der Inhalt ist gelöscht.',
    },
    abgelaufen: {
      titel: 'Abgelaufen',
      text: 'Dieser Link war zeitlich begrenzt und ist nicht mehr gültig.',
    },
    verbraucht: {
      titel: 'Bereits gelesen',
      text: 'Diese Notiz war nur einmal abrufbar und wurde schon geöffnet. Der Inhalt wurde danach gelöscht, auch wir haben ihn nicht mehr.',
    },
    gesperrt: {
      titel: 'Gesperrt',
      text: 'Es wurde zu oft ein falsches Passwort eingegeben. Der Absender muss einen neuen Link anlegen.',
    },
    quelle_weg: {
      titel: 'Nicht mehr vorhanden',
      text: 'Die Notiz hinter diesem Link wurde gelöscht.',
    },
  };

  async function oeffnen() {
    laeuft = true;
    fehler = '';
    try {
      const res = await fetch(`/n/${data.merkmal}/oeffnen`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // Bei verschlüsselten Freigaben bleibt das Passwort hier: es geht in die
        // Schlüsselableitung, nicht an den Server.
        body: JSON.stringify({ passwort: zustand.modus === 'offen' ? passwort : null }),
      });
      const roh = (await res.json()) as OeffentlicherInhalt & { fehler?: string };
      if (!res.ok) throw new Error(roh.fehler || `Fehler ${res.status}`);

      if (roh.modus === 'chiffriert') {
        const key = await schluesselHolen(roh);
        const klar = await entschluesseln(roh.chiffrat ?? '', roh.iv ?? '', key);
        const paket = paketOeffnen(klar);
        geoeffnet = {
          titel: paket.titel,
          inhalt: paket.inhalt,
          anhaenge: [],
          schein: null,
          einmalig: roh.einmalig,
        };
      } else {
        geoeffnet = {
          titel: roh.titel,
          inhalt: roh.inhalt ?? '',
          anhaenge: roh.anhaenge,
          schein: roh.anhang_schein,
          einmalig: roh.einmalig,
        };
      }
    } catch (e) {
      fehler = deutlich(e);
    } finally {
      laeuft = false;
    }
  }

  async function schluesselHolen(roh: OeffentlicherInhalt): Promise<CryptoKey> {
    if (zustand.schluessel_quelle === 'passwort') {
      if (!passwort) throw new Error('Passwort fehlt.');
      return schluesselAusPasswort(
        passwort,
        zustand.kdf_salz ?? '',
        zustand.kdf_iterationen ?? KDF_ITERATIONEN,
      );
    }
    const fragment = location.hash.replace(/^#/, '');
    if (!fragment) {
      throw new Error(
        'Der Adresse fehlt der Schlüssel hinter dem #. Wahrscheinlich wurde beim Weiterleiten ' +
          'nur ein Teil kopiert: bitte den vollständigen Link anfordern.',
      );
    }
    return schluesselImportieren(fragment);
  }

  function deutlich(e: unknown): string {
    const text = e instanceof Error ? e.message : String(e);
    // Ein fehlgeschlagenes Entschlüsseln meldet der Browser nur mit einem
    // nichtssagenden „OperationError". Für den Leser ist die Ursache aber fast
    // immer dieselbe, und die soll er lesen können.
    if (/operation|decrypt/i.test(text)) {
      return zustand.schluessel_quelle === 'passwort'
        ? 'Das Passwort passt nicht zu dieser Notiz.'
        : 'Der Schlüssel in der Adresse passt nicht. Ist der Link vollständig?';
    }
    return text;
  }
</script>

<svelte:head>
  <title>Geteilte Notiz · Saganta</title>
  <meta name="robots" content="noindex, nofollow, noarchive" />
  <meta name="referrer" content="no-referrer" />
</svelte:head>

<div class="mx-auto flex min-h-dvh max-w-2xl flex-col px-4 py-10">
  <header class="mb-6 flex items-center gap-2 text-sm text-muted">
    <Icon name={zustand.modus === 'chiffriert' ? 'shield' : 'globe'} size={16} />
    <span>Geteilte Notiz</span>
  </header>

  {#if geoeffnet}
    <article class="rounded-lg border border-border bg-surface-2/30 p-6">
      {#if geoeffnet.titel}
        <h1 class="font-display text-2xl">{geoeffnet.titel}</h1>
      {/if}
      <MarkdownAnsicht quelle={geoeffnet.inhalt} klasse={geoeffnet.titel ? 'mt-4' : ''} />

      {#if geoeffnet.anhaenge.length}
        <div class="mt-6 border-t border-border pt-4">
          <h2 class="text-sm font-semibold">Anhänge</h2>
          <ul class="mt-2 flex flex-col gap-1">
            {#each geoeffnet.anhaenge as a (a.id)}
              <li>
                <a
                  href="/n/{data.merkmal}/anhang/{a.id}?schein={encodeURIComponent(
                    geoeffnet.schein ?? '',
                  )}"
                  class="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-surface-2"
                >
                  <Icon name="download" size={16} />
                  <span class="min-w-0 flex-1 truncate">{a.dateiname}</span>
                  <span class="text-xs text-muted">{Math.max(1, Math.round(a.groesse / 1024))} KB</span>
                </a>
              </li>
            {/each}
          </ul>

          {#if geoeffnet.anhaenge.some((a) => a.mime.startsWith('image/'))}
            <div class="mt-3 grid grid-cols-2 gap-3">
              {#each geoeffnet.anhaenge.filter((a) => a.mime.startsWith('image/')) as a (a.id)}
                <AnhangBild
                  url="/n/{data.merkmal}/anhang/{a.id}?schein={encodeURIComponent(
                    geoeffnet.schein ?? '',
                  )}"
                  beschriftung={a.dateiname}
                />
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </article>

    {#if geoeffnet.einmalig}
      <p class="mt-4 rounded-md border border-accent-700/50 bg-accent-500/5 px-4 py-3 text-sm">
        <strong>Diese Notiz war nur einmal abrufbar.</strong> Sie ist jetzt gelöscht. Solange
        dieses Fenster offen ist, kannst du sie noch lesen: danach ist sie fort. Wenn du sie
        behalten willst, kopiere sie jetzt.
      </p>
    {/if}
  {:else if zustand.zustand !== 'aktiv'}
    {@const meldung = ZUSTAND_MELDUNG[zustand.zustand]}
    <div class="rounded-lg border border-border p-8 text-center">
      <p class="text-muted"><Icon name="eye-off" size={28} /></p>
      <h1 class="mt-3 font-display text-xl">{meldung?.titel ?? 'Nicht abrufbar'}</h1>
      <p class="mt-2 text-sm text-muted">{meldung?.text ?? 'Dieser Link führt ins Leere.'}</p>
    </div>
  {:else}
    <div class="rounded-lg border border-border p-8">
      <h1 class="font-display text-xl">Es liegt eine Notiz für dich bereit.</h1>

      <ul class="mt-4 flex flex-col gap-2 text-sm text-muted">
        {#if zustand.modus === 'chiffriert'}
          <li class="flex items-start gap-2">
            <span class="mt-0.5 shrink-0 text-accent-400"><Icon name="shield" size={14} /></span>
            <span>
              Der Inhalt ist verschlüsselt. Entschlüsselt wird er erst hier in deinem Browser:
              auf dem Server liegt er unlesbar.
            </span>
          </li>
        {/if}
        {#if zustand.einmalig}
          <li class="flex items-start gap-2">
            <span class="mt-0.5 shrink-0 text-accent-400"><Icon name="eye" size={14} /></span>
            <span>
              <strong>Nur einmal lesbar.</strong> Mit dem Klick wird sie geöffnet und danach
              gelöscht. Ein zweiter Aufruf zeigt nichts mehr.
            </span>
          </li>
        {:else if zustand.verbleibende_abrufe !== null}
          <li>Noch {zustand.verbleibende_abrufe}× abrufbar.</li>
        {/if}
        {#if zustand.ablauf_am}
          <li class="flex items-start gap-2">
            <span class="mt-0.5 shrink-0"><Icon name="clock" size={14} /></span>
            <span>Gültig bis {new Date(zustand.ablauf_am).toLocaleString('de-DE', { dateStyle: 'long' })}.</span>
          </li>
        {/if}
      </ul>

      {#if brauchtPasswort}
        <label class="mt-5 block text-sm">
          <span class="text-muted">Passwort</span>
          <input
            type="password"
            bind:value={passwort}
            autocomplete="off"
            onkeydown={(e) => e.key === 'Enter' && oeffnen()}
            class="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2"
          />
        </label>
      {/if}

      {#if fehler}
        <p class="mt-4 rounded-md border border-fehler/60 bg-fehler/10 px-3 py-2 text-sm text-fehler">
          {fehler}
        </p>
      {/if}

      <Button
        type="button"
        onclick={oeffnen}
        disabled={laeuft || (brauchtPasswort && !passwort)}
        class="mt-5"
      >
        {#if laeuft}<Spinner size={14} />{/if} Notiz öffnen
      </Button>
    </div>
  {/if}

  <footer class="mt-auto pt-10 text-center text-xs text-muted">
    Geteilt über <a href="https://saganta.de" class="underline">Saganta</a>
  </footer>
</div>
