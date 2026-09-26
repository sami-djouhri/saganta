<script lang="ts">
  import { enhance } from '$app/forms';
  import { Icon, kalenderCaptureUrl } from '@saganta/ui';
  import type { BriefingItem } from '$lib/briefing-api';
  import { haKonfiguration } from '$lib/heimautomation';
  import type { PageData, ActionData } from './$types';

  interface Props {
    data: PageData;
    form: ActionData;
  }
  let { data, form }: Props = $props();

  const isPro = $derived(data.configured ? (data.plan?.is_pro ?? false) : false);
  const proBenefits = $derived(data.configured ? (data.plan?.pro_benefits ?? []) : []);
  // Stripe an => Self-Service-Checkout-Button; sonst mailto-Fallback (early sales).
  const stripeEnabled = $derived(data.configured ? (data.plan?.stripe_enabled ?? false) : false);
  const upgradeMailto =
    'mailto:sami@djouhri.de?subject=Saganta%20Briefing%20Pro&body=Ich%20m%C3%B6chte%20Briefing%20Pro%20freischalten.';

  // Aktuelle Interessen als Map (tag -> weight) für Vorauswahl.
  const currentInterests = $derived(
    new Map((data.configured ? (data.profile?.interests ?? []) : []).map((i) => [i.tag, i.weight])),
  );

  let showAdvanced = $state(false);
  let zeigeHa = $state(false);
  // Welcher Kopierknopf gerade „Kopiert!" zeigt. Ein gemeinsames Flag liess
  // beide zugleich umschlagen, was aussieht, als haette man das Falsche kopiert.
  let kopiert = $state<'' | 'feed' | 'json' | 'ha'>('');

  function kopieren(text: string, welcher: 'feed' | 'json' | 'ha') {
    navigator.clipboard?.writeText(text).then(() => {
      kopiert = welcher;
      setTimeout(() => (kopiert = ''), 2000);
    });
  }

  function fmtDate(iso: string | null): string {
    if (!iso) return '';
    return new Date(iso).toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Europe/Berlin',
    });
  }

  function stripHtml(s: string): string {
    const t = s.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    return t.length > 200 ? `${t.slice(0, 200)}…` : t;
  }

  /** HH:MM aus einem ISO-Start. Kalender-Zeiten liegen naiv als Berlin-Wanduhr vor:
   *  sie durch `new Date()` zu schicken würde sie als UTC deuten und um zwei Stunden
   *  verschieben. Deshalb wird die Zeichenkette gelesen, nicht geparst. */
  function hhmm(iso: string | undefined | null): string {
    if (!iso) return '';
    return iso.match(/T(\d{2}:\d{2})/)?.[1] ?? '';
  }

  function fmtTag(iso: string): string {
    return new Date(`${iso}T12:00:00`).toLocaleDateString('de-DE', {
      weekday: 'short',
      day: '2-digit',
      month: '2-digit',
    });
  }

  const DAYTYPE_LABEL: Record<string, string> = {
    arbeit: 'Arbeitstag',
    schule: 'Schultag',
    urlaub: 'Urlaub',
    feiertag: 'Feiertag',
    frei: 'Freier Tag',
    wochenende: 'Wochenende',
  };

  /** Gleichnamige Lern-/Habit-Blöcke zusammenfassen (Gegenstück zu `_session_groups`
   *  im Backend): der Scheduler legt denselben Block mehrfach am Tag an. */
  function sessionGroups(sessions: { title?: string; start?: string }[] = []) {
    const map = new Map<string, { title: string; count: number; start: string }>();
    for (const s of sessions) {
      if (!s.title) continue;
      const g = map.get(s.title);
      if (!g) map.set(s.title, { title: s.title, count: 1, start: s.start ?? '' });
      else {
        g.count += 1;
        if (s.start && (!g.start || s.start < g.start)) g.start = s.start;
      }
    }
    return [...map.values()].sort((a, b) => a.start.localeCompare(b.start));
  }
</script>

<!-- Aktionsreihe unter einem Artikel. Merken/Gelesen schreiben in denselben
     Zustand wie der News-Feed (`UserItemState`), Daumen hoch/runter in das
     Briefing-eigene Scoring, der Kalender-Knopf legt eine Notiz an. Ein Ort für
     alle drei, damit die Sektionen und das Top-Thema nicht auseinanderlaufen. -->
{#snippet aktionen(item: BriefingItem)}
  <div class="mt-2 flex flex-wrap gap-2">
    {#if item.id !== undefined}
      <form method="POST" action="?/itemState" use:enhance>
        <input type="hidden" name="item_id" value={item.id} />
        <input type="hidden" name="field" value="bookmarked" />
        <input type="hidden" name="value" value={(!item.bookmarked).toString()} />
        <button
          type="submit"
          class="inline-flex items-center gap-1.5 rounded border border-border px-2 py-1 text-xs {item.bookmarked
            ? 'text-warm-500'
            : 'text-muted hover:text-text'}"
          title={item.bookmarked ? 'Bookmark entfernen' : 'In News merken'}
        >
          <Icon name="bookmark" size={13} filled={item.bookmarked} />
          {item.bookmarked ? 'Gemerkt' : 'Merken'}
        </button>
      </form>
      <form method="POST" action="?/itemState" use:enhance>
        <input type="hidden" name="item_id" value={item.id} />
        <input type="hidden" name="field" value="read" />
        <input type="hidden" name="value" value={(!item.read).toString()} />
        <button
          type="submit"
          class="inline-flex items-center gap-1.5 rounded border border-border px-2 py-1 text-xs text-muted hover:text-text"
          title={item.read ? 'Als ungelesen markieren' : 'Als gelesen markieren'}
        >
          <Icon name={item.read ? 'rotate-ccw' : 'check'} size={13} />
          {item.read ? 'Ungelesen' : 'Gelesen'}
        </button>
      </form>
    {/if}
    <form method="POST" action="?/feedback" use:enhance>
      <input type="hidden" name="link" value={item.link} />
      <input type="hidden" name="signal" value="1" />
      <button type="submit" class="rounded border border-border px-2 py-1 text-xs text-muted hover:text-accent-300" title="Mehr davon">
        <Icon name="thumbs-up" size={13} />
      </button>
    </form>
    <form method="POST" action="?/feedback" use:enhance>
      <input type="hidden" name="link" value={item.link} />
      <input type="hidden" name="signal" value="-1" />
      <button type="submit" class="rounded border border-border px-2 py-1 text-xs text-muted hover:text-warm-500" title="Weniger davon">
        <Icon name="thumbs-down" size={13} />
      </button>
    </form>
    <!-- Cross-App: Artikel als Notiz/Aufgabe in den Kalender übernehmen. -->
    <a
      href={kalenderCaptureUrl(item.title)}
      class="rounded border border-border px-2 py-1 text-xs text-muted hover:text-accent-300"
      title="Im Kalender notieren"
    >
      <Icon name="calendar" size={13} />
    </a>
  </div>
{/snippet}

<section class="space-y-8">
  <header class="space-y-2">
    <div class="flex items-center gap-3">
      <p class="font-mono text-sm uppercase tracking-widest text-muted">Saganta · Mein Briefing</p>
      <span
        class="rounded-full px-2 py-0.5 font-mono text-xs {isPro
          ? 'bg-accent-500/20 text-accent-300'
          : 'border border-border text-muted'}"
      >
        {isPro ? 'Pro' : 'Free'}
      </span>
    </div>
    <h1 class="font-display text-4xl leading-tight">Dein Morgen, auf den Punkt.</h1>
    <p class="text-muted">Wähle deine Themen, der Rest passiert automatisch.</p>
  </header>

  {#if data.configured && !isPro}
    <div class="rounded-xl border border-accent-500/40 bg-accent-500/5 p-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p class="font-display text-lg">Mehr aus deinem Briefing – mit Pro</p>
          <ul class="mt-2 space-y-1 text-sm text-muted">
            {#each proBenefits as b (b)}<li>✓ {b}</li>{/each}
          </ul>
        </div>
        {#if stripeEnabled}
          <form method="POST" action="?/checkout" use:enhance>
            <button
              type="submit"
              class="rounded-lg bg-accent-500 px-5 py-2.5 text-sm font-medium text-black hover:bg-accent-400"
            >
              Pro holen · ~4 €/Mon
            </button>
          </form>
        {:else}
          <a
            href={upgradeMailto}
            class="rounded-lg bg-accent-500 px-5 py-2.5 text-sm font-medium text-black hover:bg-accent-400"
          >
            Pro holen · ~4 €/Mon
          </a>
        {/if}
      </div>
    </div>
  {/if}

  {#if !data.configured}
    <div class="rounded border border-warm-500/40 bg-warm-500/10 p-4 text-sm">
      Briefing-Backend nicht konfiguriert (NEWS_API_BASE_URL fehlt).
    </div>
  {:else}
    {#if form && 'error' in form && form.error}
      <div class="rounded border border-warm-500/40 bg-warm-500/10 p-3 font-mono text-xs">{form.error}</div>
    {/if}

    <!-- ── Höre dein Briefing (für alle, ohne Setup) ─────────────────── -->
    <div class="rounded-lg border border-border bg-surface-2 p-5 space-y-4">
      <h2 class="font-display text-xl">Höre dein Briefing</h2>

      {#if data.today?.has_audio}
        <audio controls preload="none" class="w-full" src="/briefing/audio/today">
          <track kind="captions" />
        </audio>
      {:else}
        <div class="flex flex-wrap items-center gap-3">
          <form method="POST" action="?/generateAudio" use:enhance>
            <button
              type="submit"
              class="inline-flex items-center gap-2 rounded-md bg-accent-500 px-4 py-2 text-sm font-medium text-black hover:bg-accent-400"
            >
              <Icon name="play" size={16} /> Audio erzeugen
            </button>
          </form>
          <span class="text-xs text-muted">
            Wird gesprochen aufbereitet (dauert einen Moment). Danach Seite neu laden.
          </span>
        </div>
      {/if}

      <!-- Auf Handy / Lautsprecher: Podcast-Feed -->
      {#if data.delivery?.feed_url}
        <div class="rounded border border-border bg-surface p-3 space-y-2">
          <div class="flex items-center gap-2 text-sm font-medium">
            <Icon name="rss" size={15} /> Auf Handy oder Lautsprecher hören
          </div>
          <p class="text-xs text-muted">
            Füge diesen Link <strong>einmal</strong> in deiner Podcast-App (oder als Alexa-Flash-Briefing)
            hinzu, dann spielt dein Briefing jeden Morgen automatisch. Der Link ist privat, gib ihn nicht weiter.
          </p>
          <div class="flex items-center gap-2">
            <input
              readonly
              value={data.delivery.feed_url}
              class="flex-1 rounded border border-border bg-surface-2 px-2 py-1 font-mono text-xs"
            />
            <button
              type="button"
              onclick={() => kopieren(data.delivery!.feed_url!, 'feed')}
              class="rounded border border-border px-2 py-1 text-xs hover:text-accent-300"
            >
              {kopiert === 'feed' ? 'Kopiert!' : 'Kopieren'}
            </button>
          </div>
          <form method="POST" action="?/rotateFeed" use:enhance>
            <button type="submit" class="text-xs text-muted underline hover:text-text">
              Neuen Link erzeugen (alten ungültig machen)
            </button>
          </form>
        </div>
      {/if}

      <!-- ★★ In Home Assistant einbinden. Der Abrufweg existierte seit Langem,
           stand aber in keiner Oberflaeche: wer ihn nutzen wollte, haette erst
           den Quelltext lesen, dann den Pfad raten und schliesslich die Form der
           Antwort erraten muessen. Deshalb steht die Konfiguration hier fertig
           zum Kopieren statt als Beschreibung.

           Bewusst der Abruf-Weg und nicht der Webhook daneben: der verlangt, dass
           Home Assistant von aussen erreichbar ist. Beim Abruf geht die
           Verbindung von innen nach aussen, es muss also nichts geoeffnet
           werden. -->
      {#if data.delivery?.json_url}
        <div class="rounded border border-border bg-surface p-3 space-y-2">
          <div class="flex items-center gap-2 text-sm font-medium">
            <Icon name="smartphone" size={15} /> In Home Assistant einbinden
          </div>
          <p class="text-xs text-muted">
            Dein Briefing als Sensor, samt Skript zum Vorlesen. Home Assistant holt es ab, du
            musst dafür nichts nach außen öffnen.
          </p>

          <div class="flex items-center gap-2">
            <input
              readonly
              value={data.delivery.json_url}
              aria-label="Abruf-Adresse"
              class="flex-1 rounded border border-border bg-surface-2 px-2 py-1 font-mono text-xs"
            />
            <button
              type="button"
              onclick={() => kopieren(data.delivery!.json_url!, 'json')}
              class="rounded border border-border px-2 py-1 text-xs hover:text-accent-300"
            >
              {kopiert === 'json' ? 'Kopiert!' : 'Adresse'}
            </button>
          </div>

          <button
            type="button"
            onclick={() => (zeigeHa = !zeigeHa)}
            aria-expanded={zeigeHa}
            class="text-xs text-muted underline hover:text-text"
          >
            {zeigeHa ? '− ' : '+ '}Fertige Konfiguration zum Kopieren
          </button>

          {#if zeigeHa}
            {@const yaml = haKonfiguration(data.delivery.json_url)}
            <div class="space-y-2">
              <div class="flex justify-end">
                <button
                  type="button"
                  onclick={() => kopieren(yaml, 'ha')}
                  class="rounded border border-border px-2 py-1 text-xs hover:text-accent-300"
                >
                  {kopiert === 'ha' ? 'Kopiert!' : 'Konfiguration kopieren'}
                </button>
              </div>
              <pre
                class="max-h-72 overflow-auto rounded border border-border bg-surface-2 p-2 font-mono text-[11px] leading-relaxed">{yaml}</pre>
              <p class="text-xs text-muted">
                In die <code class="font-mono">configuration.yaml</code> einfügen, Home Assistant
                neu starten. Zwei Zeilen im Skript sind anzupassen: deine TTS-Entität und dein
                Lautsprecher.
              </p>
            </div>
          {/if}
        </div>
      {/if}

      <!-- Erweitert: Smart-Home-Webhook (eingeklappt, Power-User) -->
      <div>
        <button
          type="button"
          class="text-xs text-muted underline hover:text-text"
          onclick={() => (showAdvanced = !showAdvanced)}
        >
          {showAdvanced ? '− ' : '+ '}Erweitert: an mein Smart Home senden
        </button>
        {#if showAdvanced && !isPro}
          <div class="mt-3 rounded border border-accent-500/40 bg-accent-500/5 p-3 text-xs">
            <span class="font-medium">Webhook-Zustellung ist ein Pro-Feature.</span>
            <a href={upgradeMailto} class="ml-1 text-accent-300 underline">Pro holen</a>
          </div>
        {:else if showAdvanced}
          <form method="POST" action="?/setWebhook" use:enhance class="mt-3 space-y-2">
            <p class="text-xs text-muted">
              Für Home Assistant / ntfy: Wir schicken „Briefing fertig" + Audio-Link an deine URL.
              Kein Zugang zu deinem Gerät nötig.
            </p>
            <input
              name="webhook_url"
              placeholder="https://dein-ha/api/webhook/…"
              value={data.delivery?.webhook_url ?? ''}
              class="w-full rounded border border-border bg-surface-2 px-2 py-1 font-mono text-xs"
            />
            <input
              name="webhook_secret"
              placeholder="Optionaler Bearer-Token"
              class="w-full rounded border border-border bg-surface-2 px-2 py-1 font-mono text-xs"
            />
            <button type="submit" class="rounded border border-border px-3 py-1 text-xs hover:text-accent-300">
              Webhook speichern
            </button>
          </form>
        {/if}
      </div>
    </div>

    <!-- ── Interessen / Einstellungen ────────────────────────────────── -->
    <form method="POST" action="?/saveProfile" use:enhance class="rounded-lg border border-border bg-surface-2 p-5 space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="font-display text-xl">Deine Themen</h2>
        <label class="flex items-center gap-2 text-sm">
          <input type="checkbox" name="enabled" checked={data.profile?.enabled ?? true} /> Briefing aktiv
        </label>
      </div>

      <div class="flex flex-wrap gap-2">
        {#each data.interests as opt (opt.tag)}
          {@const active = currentInterests.has(opt.tag)}
          <label
            class="flex items-center gap-2 rounded-full border px-3 py-1 text-sm {active
              ? 'border-accent-500 text-accent-300'
              : 'border-border text-muted'}"
          >
            <input type="checkbox" name="interest" value={opt.tag} checked={active} class="hidden" />
            <span>{opt.label}</span>
            <select
              name={`weight_${opt.tag}`}
              class="rounded bg-surface px-1 text-xs"
              value={String(currentInterests.get(opt.tag) ?? 1)}
            >
              <option value="0.5">·</option>
              <option value="1">1×</option>
              <option value="2">2×</option>
              <option value="3">3×</option>
            </select>
          </label>
        {/each}
      </div>
      <p class="text-xs text-muted">Häkchen = Thema aufnehmen, Zahl = Gewichtung.</p>

      <div class="grid gap-4 sm:grid-cols-2">
        <label class="space-y-1 text-sm">
          <span class="text-muted">Eigene Stichwörter{isPro ? '' : ' (Pro)'}</span>
          <input
            name="free_topics"
            value={(data.profile?.free_topics ?? []).join(', ')}
            placeholder={isPro ? 'z. B. solaranlage, heimserver' : 'Pro-Feature'}
            disabled={!isPro}
            class="w-full rounded border border-border bg-surface px-2 py-1 disabled:opacity-50"
          />
        </label>
        <label class="space-y-1 text-sm">
          <span class="text-muted">Länge</span>
          <select name="length" value={data.profile?.length ?? 'mittel'} class="w-full rounded border border-border bg-surface px-2 py-1">
            <option value="kurz">Kurz</option>
            <option value="mittel">Mittel</option>
            <option value="lang" disabled={!isPro}>Lang{isPro ? '' : ' (Pro)'}</option>
          </select>
        </label>
        <label class="flex items-center gap-2 text-sm">
          <input type="checkbox" name="audio_enabled" checked={data.profile?.audio_enabled ?? true} /> Audio jeden Morgen erzeugen
        </label>
        <label class="space-y-1 text-sm">
          <span class="text-muted">Weckzeit (Hinweis)</span>
          <input name="delivery_time" value={data.profile?.delivery_time ?? '05:00'} class="w-full rounded border border-border bg-surface px-2 py-1" />
        </label>
        <label class="space-y-1 text-sm">
          <span class="text-muted">Wetter-Ort (Name)</span>
          <input
            name="weather_place"
            value={data.profile?.weather_place ?? ''}
            placeholder="z. B. Duisburg, nur für den Sprechtext"
            class="w-full rounded border border-border bg-surface px-2 py-1"
          />
        </label>
        <label class="space-y-1 text-sm">
          <span class="text-muted">Breitengrad</span>
          <input
            name="weather_lat"
            value={data.profile?.weather_lat ?? ''}
            placeholder="51.33"
            inputmode="decimal"
            class="w-full rounded border border-border bg-surface px-2 py-1"
          />
        </label>
        <label class="space-y-1 text-sm">
          <span class="text-muted">Längengrad</span>
          <input
            name="weather_lon"
            value={data.profile?.weather_lon ?? ''}
            placeholder="6.98"
            inputmode="decimal"
            class="w-full rounded border border-border bg-surface px-2 py-1"
          />
        </label>
      </div>
      <p class="text-xs text-muted">
        Ohne Koordinaten bleibt das Wetter beim neutralen Standard. Koordinaten findest du in
        jeder Kartenanwendung; sie werden nur für die Vorhersage genutzt.
      </p>

      <button type="submit" class="rounded-md bg-accent-500 px-4 py-2 text-sm font-medium text-black hover:bg-accent-400">
        Speichern
      </button>
      {#if form && 'saved' in form && form.saved}
        <span class="ml-3 text-sm text-accent-300">Gespeichert. Neu laden für frisches Briefing.</span>
      {/if}
    </form>

    <!-- ── Das heutige Briefing ──────────────────────────────────────── -->
    {#if data.today?.content}
      {@const c = data.today.content}
      <div class="space-y-6">
        <div class="flex flex-wrap items-baseline justify-between gap-3">
          <h2 class="font-display text-2xl">
            Briefing · {new Date(c.date).toLocaleDateString('de-DE', { timeZone: 'Europe/Berlin' })}
            <span class="ml-2 text-sm text-muted">{c.item_count} Themen</span>
          </h2>
          <!-- Archiv: die Briefings liegen ohnehin in der Aufbewahrung, hier ist der Weg dorthin. -->
          {#if data.history && data.history.length > 1}
            {@const neuestes = data.history[0]?.date}
            <nav class="flex flex-wrap items-center gap-1.5 text-xs">
              {#each data.history as h (h.date)}
                <a
                  href={h.date === neuestes ? '/briefing' : `/briefing?tag=${h.date}`}
                  class="rounded-full border px-2.5 py-1 {h.date === c.date
                    ? 'border-accent-500 text-accent-300'
                    : 'border-border text-muted hover:text-text'}"
                  title={h.top_title ?? ''}
                >
                  {fmtTag(h.date)}
                </a>
              {/each}
            </nav>
          {/if}
        </div>

        <!-- ── Dein Tag (aus dem Saganta-Kalender) ────────────────────── -->
        {#if c.day}
          {@const d = c.day}
          {@const groups = sessionGroups(d.sessions)}
          <div class="rounded-lg border border-border bg-surface-2 p-4 space-y-3">
            <div class="flex items-center justify-between gap-3">
              <div class="flex items-center gap-2">
                <Icon name="calendar" size={15} />
                <span class="font-display text-lg">Dein Tag</span>
                {#if d.day_type}
                  <span class="rounded-full border border-border px-2 py-0.5 font-mono text-xs text-muted">
                    {DAYTYPE_LABEL[d.day_type] ?? d.day_type}
                  </span>
                {/if}
              </div>
              <a href="https://kalender.saganta.de" class="text-xs text-muted underline hover:text-accent-300">
                Kalender öffnen
              </a>
            </div>

            {#if d.events?.length}
              <ul class="space-y-1 text-sm">
                {#each d.events as e, i (`${e.start ?? ''}-${e.title ?? ''}-${i}`)}
                  <li class="flex gap-3">
                    <span class="w-16 shrink-0 font-mono text-xs text-muted">
                      {e.all_day ? 'ganztags' : hhmm(e.start)}
                    </span>
                    <span>{e.title ?? 'Termin'}</span>
                  </li>
                {/each}
              </ul>
            {/if}

            {#if groups.length}
              <div class="space-y-1">
                <p class="font-mono text-xs uppercase tracking-wider text-muted">Geplante Blöcke</p>
                <ul class="space-y-1 text-sm">
                  {#each groups as g (g.title)}
                    <li class="flex gap-3">
                      <span class="w-16 shrink-0 font-mono text-xs text-muted">{hhmm(g.start)}</span>
                      <span>{g.title}{g.count > 1 ? ` · ${g.count} Blöcke` : ''}</span>
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}

            {#if d.goals?.length}
              <div class="space-y-1">
                <p class="font-mono text-xs uppercase tracking-wider text-muted">Tagesziele</p>
                <ul class="space-y-1 text-sm">
                  {#each d.goals as g, i (`${g.title ?? ''}-${i}`)}<li>{g.title}</li>{/each}
                </ul>
              </div>
            {/if}

            {#if !d.events?.length && !groups.length && !d.goals?.length}
              <p class="text-sm text-muted">Nichts eingetragen, der Tag gehört dir.</p>
            {/if}

            {#if d.tomorrow}
              {@const t = d.tomorrow}
              {@const ersterMorgen = t.events?.[0]}
              <div class="border-t border-border pt-3 text-sm">
                <span class="font-mono text-xs uppercase tracking-wider text-muted">Morgen</span>
                <span class="ml-2">
                  {DAYTYPE_LABEL[t.day_type ?? ''] ?? t.day_type ?? ''}{#if ersterMorgen}{t.day_type
                      ? ' · '
                      : ''}{ersterMorgen.all_day ? 'ganztags' : hhmm(ersterMorgen.start)}
                    {ersterMorgen.title ?? 'Termin'}{#if t.events.length > 1}
                      <span class="text-muted"> +{t.events.length - 1}</span>
                    {/if}
                  {/if}
                </span>
              </div>
            {/if}
          </div>
        {/if}

        {#if c.weather}
          {@const w = c.weather}
          <div class="flex flex-wrap items-baseline gap-x-4 gap-y-1 rounded-lg border border-border bg-surface-2 px-4 py-3 text-sm">
            <span class="font-mono text-xs uppercase tracking-wider text-muted">
              Wetter{w.place ? ` · ${w.place}` : ''}
            </span>
            {#if w.text}<span>{w.text}</span>{/if}
            {#if w.temp_min !== null && w.temp_max !== null}
              <span class="font-medium">{Math.round(w.temp_min)}–{Math.round(w.temp_max)} °C</span>
            {/if}
            {#if w.precipitation_probability !== null && w.precipitation_probability >= 30}
              <span class="text-muted">Regen {Math.round(w.precipitation_probability)} %</span>
            {/if}
          </div>
        {/if}

        {#if c.top_story}
          <article class="rounded-lg border border-accent-500/40 bg-accent-500/5 p-4">
            <p class="font-mono text-xs uppercase tracking-wider text-accent-300">Top-Thema</p>
            <a href={c.top_story.link} target="_blank" rel="noopener noreferrer" class="mt-1 block font-display text-xl hover:text-accent-300">
              {c.top_story.title}
            </a>
            {#if c.top_story.summary}<p class="mt-1 text-sm text-muted">{stripHtml(c.top_story.summary)}</p>{/if}
            {@render aktionen(c.top_story)}
          </article>
        {/if}

        {#each c.sections as sec (sec.tag)}
          <div class="space-y-3">
            <h3 class="font-display text-lg text-muted">{sec.label}</h3>
            <ul class="space-y-3">
              {#each sec.items as item (item.link)}
                <li class="rounded-lg border border-border bg-surface-2 p-4 {item.read ? 'opacity-60' : ''}">
                  <div class="flex items-baseline justify-between gap-2">
                    <span class="font-mono text-xs uppercase tracking-wider text-muted">{item.source}</span>
                    <span class="font-mono text-xs text-muted">{fmtDate(item.published_at)}</span>
                  </div>
                  <a href={item.link} target="_blank" rel="noopener noreferrer" class="mt-1 block font-display text-lg hover:text-accent-300">
                    {item.title}
                  </a>
                  {#if item.summary}<p class="mt-1 text-sm text-muted">{stripHtml(item.summary)}</p>{/if}
                  {@render aktionen(item)}
                </li>
              {/each}
            </ul>
          </div>
        {/each}
      </div>
    {:else if data.profile?.enabled}
      <p class="rounded border border-border bg-surface-2 px-4 py-6 text-center text-muted">
        Noch kein Briefing: Themen wählen und speichern, dann lädt es sich.
      </p>
    {/if}
  {/if}
</section>
