<script lang="ts">
  import { enhance } from '$app/forms';
  import { page } from '$app/state';
  import { Button } from '@saganta/ui';
  import type { ActionData, PageData } from './$types';

  interface Props {
    data: PageData;
    form: ActionData;
  }
  let { data, form }: Props = $props();

  let pwGeaendert = $derived(page.url.searchParams.get('pwOk') === '1');
  let freischalten = $state(false);
  let aendern = $state(false);

  const tarifName: Record<string, string> = { free: 'Kostenlos', pro: 'Pro' };
</script>

<section class="mx-auto max-w-2xl space-y-8">
  <header class="space-y-1">
    <h1 class="font-display text-3xl">Konto</h1>
    <p class="text-muted">
      Anmeldedaten und Tarif. Gilt für alle Saganta-Apps, denn sie teilen sich eine Anmeldung.
    </p>
  </header>

  <!-- Wer bin ich: immer sichtbar, auch ohne Freigabe. Das ist keine
       schützenswerte Information, und ohne sie wirkt die Passwortabfrage wie
       eine zweite Anmeldung an einem fremden Ort. -->
  <div class="flex items-center gap-4 rounded-lg border border-border bg-surface-2 p-5">
    <div
      class="grid size-12 shrink-0 place-items-center rounded-full bg-accent-500/15 font-display text-xl text-accent-300"
      aria-hidden="true"
    >
      {(data.konto.name ?? data.konto.email).charAt(0).toUpperCase()}
    </div>
    <div class="min-w-0 flex-1">
      {#if data.konto.name}
        <div class="truncate font-medium text-text">{data.konto.name}</div>
      {/if}
      <div class="truncate text-sm text-muted">{data.konto.email}</div>
    </div>
    <span
      class="shrink-0 rounded-full border border-border px-3 py-1 text-xs text-muted"
      title="Tarif dieses Kontos"
    >
      {tarifName[data.konto.plan] ?? data.konto.plan}
    </span>
  </div>

  {#if pwGeaendert}
    <div class="rounded-md border border-erfolg/40 bg-erfolg/10 px-4 py-3 text-erfolg" role="status">
      <span class="font-medium">Passwort geändert.</span>
      Andere Geräte wurden abgemeldet und müssen sich neu anmelden.
    </div>
  {/if}

  {#if !data.freigegeben}
    <!-- ── Zweite Tür ────────────────────────────────────────────────────── -->
    <div class="space-y-5 rounded-lg border border-border bg-surface-2 p-6">
      <div class="space-y-1">
        <h2 class="font-display text-xl">Bitte Passwort bestätigen</h2>
        <p class="text-sm text-muted">
          Die Anmeldung in den Apps hält lange und gilt überall. Für Änderungen am Konto fragen
          wir deshalb noch einmal nach, auch wenn du angemeldet bist.
        </p>
      </div>

      {#if form?.fehler}
        <div class="rounded-md border border-fehler/40 bg-fehler/10 px-4 py-2 text-fehler" role="alert">
          {form.fehler}
        </div>
      {/if}

      <form
        method="POST"
        action="?/freischalten"
        class="space-y-4"
        use:enhance={() => {
          freischalten = true;
          return async ({ update }) => {
            await update();
            freischalten = false;
          };
        }}
      >
        <div class="space-y-2">
          <label for="passwort" class="block text-sm font-medium">Passwort</label>
          <input
            id="passwort"
            name="passwort"
            type="password"
            autocomplete="current-password"
            required
            class="w-full rounded-md border border-border bg-surface px-3 py-2 text-text"
          />
        </div>
        <div class="flex items-center justify-between gap-3">
          <a
            href="/"
            class="text-sm text-muted transition-colors duration-fast ease-saganta hover:text-text"
            >← Zurück</a
          >
          <Button type="submit" variant="primary" loading={freischalten}>
            {freischalten ? 'Prüfe…' : 'Weiter'}
          </Button>
        </div>
      </form>

      <p class="border-t border-border pt-4 text-sm text-muted">
        Passwort vergessen? <a
          href="/forgot"
          class="text-accent-300 underline-offset-2 hover:underline">Neues Passwort anfordern</a
        >
      </p>
    </div>
  {:else}
    <!-- ── Konto offen ───────────────────────────────────────────────────── -->
    <div class="flex items-center justify-between gap-3 rounded-md border border-erfolg/30 bg-erfolg/5 px-4 py-2">
      <p class="text-sm text-muted">
        Konto für die nächsten Minuten entsperrt.
      </p>
      <form method="POST" action="?/sperren">
        <button
          type="submit"
          class="text-sm text-muted underline-offset-2 transition-colors duration-fast ease-saganta hover:text-text hover:underline"
        >
          Wieder sperren
        </button>
      </form>
    </div>

    <div class="space-y-5 rounded-lg border border-border bg-surface-2 p-6">
      <div class="space-y-1">
        <h2 class="font-display text-xl">Passwort ändern</h2>
        <p class="text-sm text-muted">
          Mindestens 8 Zeichen. Alle anderen Geräte werden dabei abgemeldet.
        </p>
      </div>

      {#if form?.pwFehler}
        <div class="rounded-md border border-fehler/40 bg-fehler/10 px-4 py-2 text-fehler" role="alert">
          {form.pwFehler}
        </div>
      {/if}

      <form
        method="POST"
        action="?/passwortAendern"
        class="space-y-4"
        use:enhance={() => {
          aendern = true;
          return async ({ update }) => {
            await update();
            aendern = false;
          };
        }}
      >
        <div class="space-y-2">
          <label for="aktuellesPasswort" class="block text-sm font-medium">Aktuelles Passwort</label>
          <input
            id="aktuellesPasswort"
            name="aktuellesPasswort"
            type="password"
            autocomplete="current-password"
            required
            class="w-full rounded-md border border-border bg-surface px-3 py-2 text-text"
          />
        </div>
        <div class="space-y-2">
          <label for="neuesPasswort" class="block text-sm font-medium">Neues Passwort</label>
          <input
            id="neuesPasswort"
            name="neuesPasswort"
            type="password"
            autocomplete="new-password"
            minlength="8"
            required
            class="w-full rounded-md border border-border bg-surface px-3 py-2 text-text"
          />
        </div>
        <div class="space-y-2">
          <label for="bestaetigung" class="block text-sm font-medium">Neues Passwort wiederholen</label>
          <input
            id="bestaetigung"
            name="bestaetigung"
            type="password"
            autocomplete="new-password"
            minlength="8"
            required
            class="w-full rounded-md border border-border bg-surface px-3 py-2 text-text"
          />
        </div>
        <div class="flex justify-end pt-1">
          <Button type="submit" variant="primary" loading={aendern}>
            {aendern ? 'Ändere…' : 'Passwort ändern'}
          </Button>
        </div>
      </form>
    </div>

    <!-- Platzhalter für das, was hier laut Planung noch hinkommt. Bewusst als
         sichtbarer Hinweis und nicht als leerer Bereich: eine Kontoseite, auf
         der das Abo fehlt, lässt einen sonst suchen. -->
    <div class="rounded-lg border border-dashed border-border p-6">
      <h2 class="font-display text-xl">Abo</h2>
      <p class="mt-1 text-sm text-muted">
        Tarif dieses Kontos: <span class="text-text">{tarifName[data.konto.plan] ?? data.konto.plan}</span>.
        Buchen und Kündigen kommt an diese Stelle.
      </p>
    </div>
  {/if}

  <p class="text-sm text-muted">
    Aussehen und Sprache stehen unter <a
      href="/settings"
      class="text-accent-300 underline-offset-2 hover:underline">Einstellungen</a
    >.
  </p>
</section>
