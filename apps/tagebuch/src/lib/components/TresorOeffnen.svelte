<script lang="ts">
  /**
   * Aufschliessen, mit beiden Wegen.
   *
   * Der zweite Weg (Wiederherstellungsschlüssel) steht bewusst sichtbar
   * daneben und nicht hinter einem kleinen Link: wer die Passphrase gerade
   * vergessen hat, sucht nicht lange, sondern gibt auf.
   */
  import { Button } from '@saganta/ui';
  import {
    KryptoFehler,
    passphraseNeuVerpacken,
    sichererKontext,
    tresorOeffnen,
    tresorOeffnenMitWiederherstellung,
    type TresorPakete,
  } from '$lib/krypto';
  import { oeffnen, tresor } from '$lib/tresor.svelte';

  let { pakete }: { pakete: TresorPakete } = $props();

  let weg = $state<'passphrase' | 'wiederherstellung'>('passphrase');
  let eingabe = $state('');
  let neueP = $state('');
  let neueP2 = $state('');
  let laeuft = $state(false);
  let fehler = $state('');
  let neuSetzen = $state(false);

  let kontextFehlt = $derived(!sichererKontext());

  async function aufschliessen(e: Event) {
    e.preventDefault();
    if (laeuft || !eingabe) return;
    laeuft = true;
    fehler = '';
    try {
      const dek =
        weg === 'passphrase'
          ? await tresorOeffnen(pakete, eingabe)
          : await tresorOeffnenMitWiederherstellung(pakete, eingabe);

      if (weg === 'wiederherstellung') {
        // Wer über den Notfallweg hereinkommt, hat seine Passphrase nicht
        // mehr. Ihn jetzt ins Tagebuch zu lassen und nichts weiter zu tun,
        // hiesse: beim nächsten Laden steht er wieder vor derselben Tür.
        neuSetzen = true;
        oeffnen(dek, pakete);
        return;
      }
      oeffnen(dek, pakete);
    } catch (e) {
      fehler =
        e instanceof KryptoFehler
          ? e.message
          : 'Das Aufschliessen ist fehlgeschlagen. Bitte noch einmal versuchen.';
    } finally {
      laeuft = false;
    }
  }

  async function passphraseSetzen(e: Event) {
    e.preventDefault();
    if (neueP.length < 12 || neueP !== neueP2) return;
    const dek = tresor.dek;
    if (!dek) return;
    laeuft = true;
    fehler = '';
    try {
      const paket = await passphraseNeuVerpacken(dek, neueP);
      const antwort = await fetch('/api/tresor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(paket),
      });
      if (!antwort.ok) {
        fehler = `Die neue Passphrase liess sich nicht speichern (${antwort.status}).`;
        return;
      }
      neuSetzen = false;
    } finally {
      laeuft = false;
    }
  }
</script>

<section class="mx-auto max-w-md py-16">
  {#if kontextFehlt}
    <h1 class="font-display text-2xl">Verschlüsselung nicht verfügbar</h1>
    <p class="mt-3 text-muted">
      Dieser Browser gibt die Verschlüsselung nicht frei. Das Tagebuch braucht eine https-Adresse
      (<code>tagebuch.home.arpa</code>); über eine nackte IP-Adresse funktioniert es nicht.
    </p>
  {:else if neuSetzen}
    <h1 class="font-display text-2xl">Neue Passphrase setzen</h1>
    <p class="mt-3 text-muted">
      Das Tagebuch ist offen. Damit das beim nächsten Mal wieder mit einer Passphrase klappt, bitte
      jetzt eine neue vergeben. Der Notfallschlüssel bleibt derselbe und gilt weiter.
    </p>
    <form class="mt-6 flex flex-col gap-3" onsubmit={passphraseSetzen}>
      <input
        type="password"
        bind:value={neueP}
        placeholder="Neue Passphrase"
        autocomplete="new-password"
        class="rounded-md border border-border bg-surface-2 px-3 py-2"
      />
      <input
        type="password"
        bind:value={neueP2}
        placeholder="Noch einmal"
        autocomplete="new-password"
        class="rounded-md border border-border bg-surface-2 px-3 py-2"
      />
      {#if fehler}<p class="text-sm text-fehler">{fehler}</p>{/if}
      <Button type="submit" disabled={laeuft || neueP.length < 12 || neueP !== neueP2}>
        Passphrase setzen
      </Button>
      <button type="button" class="text-xs text-muted underline" onclick={() => (neuSetzen = false)}>
        Später, jetzt erst schreiben
      </button>
    </form>
  {:else}
    <h1 class="font-display text-2xl">Tagebuch aufschliessen</h1>

    <form class="mt-6 flex flex-col gap-3" onsubmit={aufschliessen}>
      {#if weg === 'passphrase'}
        <label class="flex flex-col gap-1 text-sm">
          <span>Passphrase</span>
          <!-- svelte-ignore a11y_autofocus -->
          <input
            type="password"
            bind:value={eingabe}
            autocomplete="current-password"
            autofocus
            class="rounded-md border border-border bg-surface-2 px-3 py-2"
          />
        </label>
      {:else}
        <label class="flex flex-col gap-1 text-sm">
          <span>Wiederherstellungsschlüssel</span>
          <input
            type="text"
            bind:value={eingabe}
            spellcheck="false"
            autocapitalize="characters"
            placeholder="XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX"
            class="rounded-md border border-border bg-surface-2 px-3 py-2 font-mono tracking-wider"
          />
          <span class="text-xs text-muted">
            Gross- und Kleinschreibung sind egal, Trennstriche auch. Die Zeichen 0 und O, 1 und I
            werden gleich behandelt.
          </span>
        </label>
      {/if}

      {#if fehler}<p class="text-sm text-fehler">{fehler}</p>{/if}

      <Button type="submit" disabled={laeuft || !eingabe}>
        {laeuft ? 'Wird geprüft …' : 'Aufschliessen'}
      </Button>
    </form>

    <button
      type="button"
      class="mt-4 text-sm text-muted underline"
      onclick={() => {
        weg = weg === 'passphrase' ? 'wiederherstellung' : 'passphrase';
        eingabe = '';
        fehler = '';
      }}
    >
      {weg === 'passphrase'
        ? 'Passphrase vergessen? Mit dem Notfallschlüssel öffnen'
        : 'Doch mit der Passphrase öffnen'}
    </button>

    <p class="mt-8 text-xs text-muted">
      Das Aufschliessen dauert einen Moment. Die Ableitung rechnet mit
      {pakete.kdf_iterationen.toLocaleString('de-DE')} Runden, und genau diese Langsamkeit ist es, die
      ein Durchprobieren aussichtslos macht.
    </p>
  {/if}
</section>
