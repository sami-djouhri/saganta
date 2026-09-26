<script lang="ts">
  /**
   * Dezenter Hinweis auf die native Android-App der gerade geoeffneten Web-App.
   *
   * Warum es das gibt: wer Saganta ueber das Handy aufruft, landet im Browser und
   * erfaehrt nirgends, dass es die App gibt. Die Downloads-Seite hing bis 2026-08-29
   * ausschliesslich im Konto-Menue der Shell. In den Sub-Apps gab es gar keinen Weg
   * dorthin. Der Hinweis schliesst die Luecke an der Stelle, an der sie auffaellt.
   *
   * Die Regeln sind bewusst streng, damit er nicht zum Nag-Banner wird:
   *  - nur auf Android (fuer iOS gibt es keine App, Desktop kann eine APK nicht nutzen),
   *  - nur wenn im Downloads-Volume wirklich ein Release liegt (das Artefakt entscheidet,
   *    nicht eine zweite gepflegte Liste, dieselbe Regel wie auf /apps),
   *  - hoechstens einmal pro Browser-Sitzung und insgesamt {@link MAX_SITZUNGEN} mal,
   *  - Wegklicken schaltet ihn dauerhaft still.
   *
   * Erscheint nie in der nativen App selbst: kalender-android und projectdeck-android
   * sind Compose-Apps, keine WebView-Wrapper, sie rendern dieses Frontend nicht.
   */
  import { onMount } from 'svelte';
  import Icon from './Icon.svelte';
  import { SHELL_URL } from '../apps';

  interface Props {
    /**
     * Id des Release-Manifests unter /downloads/<app>.json, nicht die `currentAppId`
     * der TopBar. Die weichen auseinander: der Kalender heisst im App-Katalog
     * `calendar`, sein Manifest aber `kalender.json`.
     */
    app: string;
    /** Anzeigename der App im Hinweistext. */
    name: string;
    /** Nur fuer angemeldete Besucher zeigen: ausgeloggt steht die Anmeldung im Weg. */
    zeigen?: boolean;
  }
  let { app, name, zeigen = true }: Props = $props();

  /** Nach so vielen Browser-Sitzungen ohne Reaktion gibt der Hinweis von selbst Ruhe. */
  const MAX_SITZUNGEN = 3;

  interface Release {
    versionName: string;
    size: number;
    /** Versionierte URL aus dem Manifest (umgeht den Rand-Cache auf dem stabilen Namen). */
    apkUrl: string;
  }

  let release = $state<Release | null>(null);

  const merker = $derived(`saganta:app-hinweis:${app}`);

  /** localStorage/sessionStorage koennen im privaten Modus werfen, dann eben ohne Gedaechtnis. */
  function lies(store: Storage | undefined, key: string): string | null {
    try {
      return store?.getItem(key) ?? null;
    } catch {
      return null;
    }
  }
  function schreib(store: Storage | undefined, key: string, wert: string): void {
    try {
      store?.setItem(key, wert);
    } catch {
      // Kein Speicher = der Hinweis erscheint wieder. Unschoen, aber harmlos.
    }
  }

  function wegklicken() {
    release = null;
    schreib(window.localStorage, merker, 'aus');
  }

  onMount(() => {
    if (!zeigen) return;
    if (!/\bAndroid\b/i.test(navigator.userAgent)) return;

    const stand = lies(window.localStorage, merker);
    if (stand === 'aus') return;
    // Unlesbarer Stand zaehlt als "noch nie gezeigt". Ohne die Normalisierung waere
    // der Zaehler ab dem ersten kaputten Wert NaN, NaN >= 3 ist falsch, und der
    // Hinweis erschiene von da an bei jedem Aufruf. Genau das soll er nicht.
    const roh = Number(stand ?? '0');
    const gesehen = Number.isFinite(roh) ? roh : 0;
    if (gesehen >= MAX_SITZUNGEN) return;

    // Pro Sitzung hoechstens einmal hochzaehlen: sonst waere der Vorrat nach drei
    // Seitenwechseln aufgebraucht, ohne dass jemand den Hinweis wirklich gelesen hat.
    const dieseSitzung = lies(window.sessionStorage, merker) === 'gezaehlt';

    // Das ausgelieferte Artefakt ist die Wahrheit. Liegt keins da (oder ist die Shell
    // nicht erreichbar), bleibt der Hinweis einfach aus: lieber still als falsch.
    fetch(`${SHELL_URL}/downloads/${app}.json`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((m: Release | null) => {
        if (!m?.versionName || !m?.apkUrl) return;
        release = m;
        if (!dieseSitzung) {
          schreib(window.sessionStorage, merker, 'gezaehlt');
          schreib(window.localStorage, merker, String(gesehen + 1));
        }
      })
      .catch(() => {
        // Netzwerkfehler sind kein Grund, dem Nutzer etwas zu erzaehlen.
      });
  });

  const groesse = $derived(release ? `${(release.size / 1024 / 1024).toFixed(1)} MB` : '');
</script>

{#if release}
  <div
    class="border-b border-border bg-surface-2/60 backdrop-blur-sm"
    role="complementary"
    aria-label="Hinweis auf die Android-App"
  >
    <div class="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2.5">
      <span class="grid size-8 shrink-0 place-items-center rounded-lg bg-accent-500/12 text-accent-300">
        <Icon name="smartphone" size={16} />
      </span>
      <div class="min-w-0 flex-1">
        <!-- Kurz halten: bei 412 px (Pixel-Klasse) schnitt „{name} gibt es auch als
             Android-App" hinter „Android" ab und las sich wie ein abgebrochener Satz. -->
        <p class="truncate text-sm text-text">{name} als Android-App</p>
        <p class="truncate text-xs text-muted">Version {release.versionName} · {groesse}</p>
      </div>
      <a
        href={release.apkUrl}
        class="shrink-0 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium transition-colors duration-fast ease-saganta hover:border-accent-500/50 hover:text-accent-300"
      >
        Holen
      </a>
      <button
        type="button"
        onclick={wegklicken}
        class="shrink-0 rounded-md p-1.5 text-muted transition-colors duration-fast ease-saganta hover:text-text"
        aria-label="Hinweis nicht mehr anzeigen"
        title="Nicht mehr anzeigen"
      >
        <Icon name="x" size={16} />
      </button>
    </div>
  </div>
{/if}
