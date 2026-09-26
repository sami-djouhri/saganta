<script lang="ts">
  import { Button, Icon, Spinner } from '@saganta/ui';
  import {
    KDF_ITERATIONEN,
    neuerSchluessel,
    neuesSalz,
    paketSchnueren,
    schluesselAusPasswort,
    schluesselExportieren,
    verschluesseln,
  } from '$lib/krypto';
  import { freigabeBasis } from '$lib/meta';
  import type { Freigabe } from '$lib/types';

  let {
    offen = false,
    notizId,
    titel,
    inhalt,
    hatAnhaenge = false,
    schliessen,
    fertig,
  }: {
    offen?: boolean;
    notizId: number;
    titel: string;
    inhalt: string;
    hatAnhaenge?: boolean;
    schliessen: () => void;
    fertig: () => void;
  } = $props();

  let modus = $state<'offen' | 'chiffriert'>('chiffriert');
  let ablaufTage = $state<number | null>(7);
  let einmalig = $state(false);
  let passwort = $state('');
  let mitAnhaengen = $state(true);

  let laeuft = $state(false);
  let fehler = $state('');
  let ergebnis = $state<{ adresse: string; freigabe: Freigabe } | null>(null);
  let kopiert = $state(false);

  function zuruecksetzen() {
    ergebnis = null;
    fehler = '';
    kopiert = false;
    passwort = '';
  }

  async function anlegen() {
    laeuft = true;
    fehler = '';
    try {
      const wunsch: Record<string, unknown> = {
        modus,
        ablauf_tage: ablaufTage,
        max_abrufe: einmalig ? 1 : null,
      };
      let fragment = '';

      if (modus === 'chiffriert') {
        // Titel und Text wandern gemeinsam ins Chiffrat, sonst stünde der
        // Titel im Klartext auf dem Server, und der sagt oft schon alles.
        const paket = paketSchnueren(titel, inhalt);
        if (passwort) {
          const salz = neuesSalz();
          const key = await schluesselAusPasswort(passwort, salz, KDF_ITERATIONEN);
          const { chiffrat, iv } = await verschluesseln(paket, key);
          Object.assign(wunsch, {
            chiffrat,
            iv,
            kdf_salz: salz,
            kdf_iterationen: KDF_ITERATIONEN,
            algo: 'AES-GCM-256',
            schluessel_quelle: 'passwort',
          });
        } else {
          const key = await neuerSchluessel();
          const { chiffrat, iv } = await verschluesseln(paket, key);
          fragment = await schluesselExportieren(key);
          Object.assign(wunsch, {
            chiffrat,
            iv,
            algo: 'AES-GCM-256',
            schluessel_quelle: 'fragment',
          });
        }
      } else {
        wunsch.mit_anhaengen = mitAnhaengen;
        if (passwort) wunsch.passwort = passwort;
      }

      const res = await fetch(`/notiz/${notizId}/freigabe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(wunsch),
      });
      const daten = (await res.json()) as Freigabe & { fehler?: string };
      if (!res.ok) throw new Error(daten.fehler || `Fehler ${res.status}`);

      const basis = freigabeBasis(location.origin);
      ergebnis = {
        freigabe: daten,
        adresse: `${basis}/${daten.merkmal}${fragment ? `#${fragment}` : ''}`,
      };
      fertig();
    } catch (e) {
      fehler = e instanceof Error ? e.message : 'Freigabe fehlgeschlagen';
    } finally {
      laeuft = false;
    }
  }

  async function kopieren() {
    if (!ergebnis) return;
    try {
      await navigator.clipboard.writeText(ergebnis.adresse);
      kopiert = true;
      setTimeout(() => (kopiert = false), 2000);
    } catch {
      // Ohne Zwischenablage-Recht bleibt das Feld zum Markieren stehen.
      fehler = 'Kopieren war nicht erlaubt: Adresse von Hand markieren.';
    }
  }
</script>

{#if offen}
  <div
    class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 pt-16"
    role="presentation"
    onclick={(e) => e.target === e.currentTarget && schliessen()}
  >
    <div
      class="w-full max-w-lg rounded-lg border border-border bg-surface shadow-xl"
      role="dialog"
      aria-modal="true"
      aria-label="Notiz teilen"
    >
      <div class="flex items-center justify-between border-b border-border p-4">
        <h2 class="font-display text-lg">Notiz teilen</h2>
        <button type="button" onclick={schliessen} class="text-muted hover:text-text" aria-label="Schließen">
          <Icon name="x" size={16} />
        </button>
      </div>

      {#if ergebnis}
        <div class="flex flex-col gap-4 p-4">
          <div>
            <p class="text-sm text-muted">Adresse zum Weitergeben:</p>
            <div class="mt-1 flex gap-2">
              <input
                readonly
                value={ergebnis.adresse}
                class="min-w-0 flex-1 rounded-md border border-border bg-surface-2 px-3 py-2 font-mono text-xs"
                onfocus={(e) => e.currentTarget.select()}
              />
              <Button type="button" size="sm" onclick={kopieren}>
                {kopiert ? 'Kopiert' : 'Kopieren'}
              </Button>
            </div>
          </div>

          {#if ergebnis.freigabe.modus === 'chiffriert'}
            <div class="rounded-md border border-accent-700/50 bg-accent-500/5 p-3 text-sm">
              {#if ergebnis.freigabe.passwortgeschuetzt}
                <p class="flex items-start gap-2">
                  <span class="mt-0.5 shrink-0 text-accent-400"><Icon name="shield" size={14} /></span>
                  <span>
                    Der Text ist verschlüsselt. Der Empfänger braucht das Passwort: sag es ihm
                    <strong>auf einem anderen Weg</strong> als den Link. Beides im selben Chat
                    verschickt bringt nichts.
                  </span>
                </p>
              {:else}
                <p class="flex items-start gap-2">
                  <span class="mt-0.5 shrink-0 text-accent-400"><Icon name="shield" size={14} /></span>
                  <span>
                    Der Schlüssel steht hinter dem <code>#</code> und erreicht unseren Server nie.
                    <strong>Diese Adresse gibt es nur einmal</strong>, ohne den Teil hinter dem
                    <code>#</code> lässt sich die Notiz nicht mehr öffnen, auch von uns nicht.
                  </span>
                </p>
              {/if}
            </div>
          {/if}

          {#if ergebnis.freigabe.max_abrufe === 1}
            <p class="text-sm text-muted">
              Der Link lässt sich <strong>einmal</strong> öffnen. Danach ist der Inhalt weg.
            </p>
          {/if}

          <div class="flex justify-between gap-2">
            <Button type="button" variant="ghost" size="sm" onclick={zuruecksetzen}>
              Weiteren Link anlegen
            </Button>
            <Button type="button" size="sm" onclick={schliessen}>Fertig</Button>
          </div>
        </div>
      {:else}
        <div class="flex flex-col gap-4 p-4">
          <fieldset>
            <legend class="text-xs font-semibold uppercase tracking-wide text-muted">
              Wer soll mitlesen können?
            </legend>
            <div class="mt-2 flex flex-col gap-2">
              <label class="flex cursor-pointer items-start gap-2 rounded-md border p-3 {modus === 'chiffriert' ? 'border-accent-600 bg-accent-500/5' : 'border-border'}">
                <input type="radio" bind:group={modus} value="chiffriert" class="mt-1" />
                <span class="text-sm">
                  <span class="font-medium">Verschlüsselt</span>
                  <span class="block text-muted">
                    Der Text wird in deinem Browser verschlüsselt. Unser Server speichert nur
                    Buchstabensalat und kann den Inhalt nicht lesen, auch später nicht. Dafür zeigt
                    der Link den Stand von jetzt und wächst nicht mit.
                  </span>
                </span>
              </label>
              <label class="flex cursor-pointer items-start gap-2 rounded-md border p-3 {modus === 'offen' ? 'border-accent-600 bg-accent-500/5' : 'border-border'}">
                <input type="radio" bind:group={modus} value="offen" class="mt-1" />
                <span class="text-sm">
                  <span class="font-medium">Offen</span>
                  <span class="block text-muted">
                    Der Link zeigt die Notiz so, wie sie gerade ist: Änderungen erscheinen beim
                    Empfänger. Anhänge können mit. Der Server kann mitlesen.
                  </span>
                </span>
              </label>
            </div>
          </fieldset>

          <div class="grid gap-3 sm:grid-cols-2">
            <label class="text-sm">
              <span class="text-muted">Gültig für</span>
              <select
                bind:value={ablaufTage}
                class="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
              >
                <option value={1}>1 Tag</option>
                <option value={7}>7 Tage</option>
                <option value={30}>30 Tage</option>
                <option value={365}>1 Jahr</option>
                <option value={null}>Ohne Ablauf</option>
              </select>
            </label>

            <label class="text-sm">
              <span class="text-muted">Passwort (optional)</span>
              <input
                type="password"
                bind:value={passwort}
                autocomplete="new-password"
                placeholder="leer = keines"
                class="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
              />
            </label>
          </div>

          <label class="flex items-start gap-2 text-sm">
            <input type="checkbox" bind:checked={einmalig} class="mt-1" />
            <span>
              Nur einmal lesbar
              <span class="block text-muted">
                Nach dem ersten Öffnen wird der Inhalt gelöscht. Vorsicht bei Messengern, die Links
                automatisch vorladen, wir geben den Text deshalb erst nach einem Klick heraus, aber
                sicher ist sicher.
              </span>
            </span>
          </label>

          {#if modus === 'offen' && hatAnhaenge}
            <label class="flex items-center gap-2 text-sm">
              <input type="checkbox" bind:checked={mitAnhaengen} />
              <span>Anhänge mitgeben</span>
            </label>
          {:else if modus === 'chiffriert' && hatAnhaenge}
            <p class="rounded-md border border-border px-3 py-2 text-xs text-muted">
              Anhänge gehen bei verschlüsselten Links nicht mit: sie liegen unverschlüsselt bei uns,
              das würde die Zusage aushöhlen. Für Dateien den offenen Modus wählen.
            </p>
          {/if}

          {#if fehler}
            <p class="rounded-md border border-fehler/60 bg-fehler/10 px-3 py-2 text-sm text-fehler">
              {fehler}
            </p>
          {/if}

          <div class="flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onclick={schliessen}>Abbrechen</Button>
            <Button type="button" size="sm" onclick={anlegen} disabled={laeuft}>
              {#if laeuft}<Spinner size={14} />{/if} Link erzeugen
            </Button>
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}
