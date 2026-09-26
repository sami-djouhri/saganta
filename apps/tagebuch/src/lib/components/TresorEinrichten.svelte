<script lang="ts">
  /**
   * Das Einrichten, einmal je Konto.
   *
   * ★ Reihenfolge mit Bedacht: erst wird der Tresor gespeichert, dann der
   * Wiederherstellungsschlüssel gezeigt. Andersherum könnte jemand einen
   * Schlüssel abschreiben, der nie irgendwo angekommen ist, und ihn Jahre
   * später vergeblich benutzen.
   */
  import { Button, Icon } from '@saganta/ui';
  import { KryptoFehler, tresorAnlegen, sichererKontext } from '$lib/krypto';
  import { oeffnen } from '$lib/tresor.svelte';

  let { fertig }: { fertig: () => void } = $props();

  const MINDESTLAENGE = 12;

  let passphrase = $state('');
  let wiederholung = $state('');
  let laeuft = $state(false);
  let fehler = $state('');
  let notfallschluessel = $state('');
  let notiert = $state(false);

  let kontextFehlt = $derived(!sichererKontext());
  let zuKurz = $derived(passphrase.length > 0 && passphrase.length < MINDESTLAENGE);
  let ungleich = $derived(wiederholung.length > 0 && passphrase !== wiederholung);
  let bereit = $derived(
    !kontextFehlt && passphrase.length >= MINDESTLAENGE && passphrase === wiederholung,
  );

  async function anlegen() {
    if (!bereit || laeuft) return;
    laeuft = true;
    fehler = '';
    try {
      const { pakete, wiederherstellungsschluessel, dek } = await tresorAnlegen(passphrase);

      const antwort = await fetch('/api/tresor', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(pakete),
      });
      if (!antwort.ok) {
        fehler =
          antwort.status === 409
            ? 'Es gibt bereits einen Tresor für dieses Konto. Bitte die Seite neu laden.'
            : `Der Tresor liess sich nicht speichern (${antwort.status}).`;
        return;
      }

      // Erst jetzt gilt der Schlüssel, denn erst jetzt gibt es etwas, das er öffnet.
      notfallschluessel = wiederherstellungsschluessel;
      oeffnen(dek, pakete);
      passphrase = '';
      wiederholung = '';
    } catch (e) {
      fehler = e instanceof KryptoFehler ? e.message : 'Das Einrichten ist fehlgeschlagen.';
    } finally {
      laeuft = false;
    }
  }

  async function kopieren() {
    try {
      await navigator.clipboard.writeText(notfallschluessel);
    } catch {
      /* Ohne Zwischenablage bleibt Abschreiben, und das ist der vorgesehene Weg. */
    }
  }
</script>

<section class="mx-auto max-w-lg py-10">
  {#if notfallschluessel}
    <h1 class="font-display text-2xl">Der Schlüssel für den Notfall</h1>
    <p class="mt-3 text-muted">
      Dies ist der einzige Weg zurück, wenn die Passphrase verloren geht. Er wird jetzt einmal
      angezeigt und danach nie wieder, auch nicht von diesem Server: der kennt ihn nicht.
    </p>

    <p
      class="mt-6 select-all rounded-md border border-border bg-surface-2 px-4 py-4 text-center font-mono text-lg tracking-widest"
    >
      {notfallschluessel}
    </p>

    <div class="mt-3 flex gap-2">
      <Button variant="ghost" size="sm" onclick={kopieren}>
        <Icon name="copy" size={16} /> Kopieren
      </Button>
      <Button variant="ghost" size="sm" onclick={() => window.print()}>
        <Icon name="printer" size={16} /> Drucken
      </Button>
    </div>

    <p class="mt-6 text-sm text-muted">
      Gut aufgehoben ist er im Passwortspeicher oder ausgedruckt an einem Ort, den man auch dann
      noch findet, wenn der Rechner kaputt ist. Wer Passphrase und diesen Schlüssel verliert,
      verliert die Einträge endgültig, auch aus jeder Sicherung. Das ist keine Panne des Verfahrens,
      sondern seine Bedingung: gäbe es einen dritten Weg hinein, hätte ihn auch jemand anderes.
    </p>

    <label class="mt-6 flex items-start gap-2 text-sm">
      <input type="checkbox" bind:checked={notiert} class="mt-1" />
      <span>Ich habe den Schlüssel notiert oder gespeichert.</span>
    </label>

    <Button class="mt-4 w-full" disabled={!notiert} onclick={fertig}>Weiter zum Tagebuch</Button>
  {:else}
    <h1 class="font-display text-2xl">Tagebuch einrichten</h1>
    <p class="mt-3 text-muted">
      Die Einträge werden in diesem Browser verschlüsselt und verlassen ihn nur verschlossen. Der
      Server verwahrt sie, ohne sie lesen zu können. Dafür wird eine Passphrase gebraucht, die
      nirgends gespeichert wird.
    </p>

    {#if kontextFehlt}
      <p class="mt-6 rounded-md border border-fehler/40 bg-fehler/10 px-4 py-3 text-sm">
        Dieser Browser gibt die Verschlüsselung nicht frei. Das Tagebuch braucht eine
        https-Adresse (<code>tagebuch.home.arpa</code>); über eine nackte IP-Adresse
        funktioniert es nicht.
      </p>
    {:else}
      <form
        class="mt-6 flex flex-col gap-3"
        onsubmit={(e) => {
          e.preventDefault();
          anlegen();
        }}
      >
        <label class="flex flex-col gap-1 text-sm">
          <span>Passphrase</span>
          <input
            type="password"
            bind:value={passphrase}
            autocomplete="new-password"
            class="rounded-md border border-border bg-surface-2 px-3 py-2"
          />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span>Noch einmal</span>
          <input
            type="password"
            bind:value={wiederholung}
            autocomplete="new-password"
            class="rounded-md border border-border bg-surface-2 px-3 py-2"
          />
        </label>

        <p class="text-xs text-muted">
          Mindestens {MINDESTLAENGE} Zeichen. Ein Satz, den nur du kennst, ist besser als ein kurzes
          Kunstwort: er ist länger und leichter zu behalten.
        </p>

        {#if zuKurz}
          <p class="text-sm text-warnung">Noch zu kurz.</p>
        {/if}
        {#if ungleich}
          <p class="text-sm text-warnung">Die beiden Eingaben sind nicht gleich.</p>
        {/if}
        {#if fehler}
          <p class="text-sm text-fehler">{fehler}</p>
        {/if}

        <Button type="submit" disabled={!bereit || laeuft}>
          {laeuft ? 'Wird eingerichtet …' : 'Einrichten'}
        </Button>
      </form>
    {/if}
  {/if}
</section>
