<script lang="ts">
  import { enhance } from '$app/forms';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Icon, kalenderCaptureUrl, raumVon, STANDARD_RAUM } from '@saganta/ui';
  import { DEFAULT_LIMIT } from '$lib/constants';
  import type { ActionData, PageData } from './$types';

  interface Props {
    data: PageData;
    form: ActionData;
  }
  let { data, form }: Props = $props();
  const feed = $derived(data.feed);
  const opts = $derived(feed.options);
  const offeneMail = $derived(data.offeneMail);
  const offenerBrief = $derived(data.offenerBrief);
  const entwurf = $derived(data.entwurf);

  const actionError = $derived(
    (form && 'error' in form ? form.error : null) ?? data.ladeFehler ?? null,
  );
  const archivedId = $derived(form && 'archived' in form ? form.archived : null);
  const snoozedTage = $derived(form && 'snoozedTage' in form ? form.snoozedTage : null);
  const sendError = $derived(form && 'sendError' in form ? form.sendError : null);
  const sendValues = $derived(
    form && 'values' in form ? (form.values as Record<string, string>) : null,
  );
  // Nach dem Senden leitet die Aktion mit `gesendet=1` um. Der Hinweis haengt
  // damit an der Adresse und nicht am Formular-Ergebnis, das ein Neuladen
  // verliert.
  const sendOk = $derived($page.url.searchParams.get('gesendet') === '1');

  /**
   * Der Briefkasten liegt im Raum des Aufrufers.
   *
   * ★ Hier stand bis 2026-09-14 fest `https://mail.saganta.de`. Wer die App
   * unter `post.home.arpa` benutzte, wurde damit aus dem Heimnetz durch den
   * Tunnel geschickt, in einen anderen Cookie-Raum und im Zweifel in eine neue
   * Anmeldung. Dieselbe Begruendung wie in `packages/ui/src/apps.ts`; der
   * Briefkasten ist dort nur nicht gelistet, weil er kein Saganta-Frontend ist.
   */
  const briefkastenUrl = $derived(`https://mail.${raumVon($page.url.host) ?? STANDARD_RAUM}`);
  const host = $derived($page.url.host);

  // ── Adressen ──────────────────────────────────────────────────────────────
  //
  // Der Zustand der Seite steht vollstaendig in der Adresse: welcher Filter,
  // welche Seite, was geoeffnet ist, ob verfasst wird. Das ist der Grund, warum
  // eine geoeffnete Nachricht das Markieren eines anderen Eintrags jetzt
  // ueberlebt, und warum sich ein Brief verlinken laesst.

  interface Patch {
    source?: 'all' | 'mail' | 'letter';
    unread?: boolean;
    markiert?: boolean;
    account?: number | null;
    category?: string | null;
    q?: string | null;
    offen?: string | null;
    verfassen?: string | null;
    offset?: number;
  }

  function hrefWith(patch: Patch): string {
    const source = patch.source ?? opts.source;
    const quellenwechsel = patch.source !== undefined && patch.source !== opts.source;
    const unread = patch.unread ?? opts.unreadOnly;
    const markiert = patch.markiert ?? opts.starredOnly;
    const account = patch.account === undefined ? opts.accountId : (patch.account ?? undefined);
    // Der Kategorie-Filter betrifft nur Briefe. Beim Wechsel in die reine
    // Mail-Ansicht faellt er weg, statt unsichtbar weiterzuwirken.
    const category =
      source === 'mail'
        ? undefined
        : patch.category === undefined
          ? opts.category
          : (patch.category ?? undefined);
    const q = patch.q === undefined ? opts.suche : (patch.q ?? undefined);
    // Ein geoeffnetes Element aus einer anderen Quelle passt nicht zur neuen
    // Ansicht und wird beim Wechsel geschlossen.
    const offen =
      patch.offen === undefined
        ? quellenwechsel
          ? undefined
          : ($page.url.searchParams.get('offen') ?? undefined)
        : (patch.offen ?? undefined);
    const verfassen = patch.verfassen === undefined ? undefined : (patch.verfassen ?? undefined);

    const p = new URLSearchParams();
    if (source !== 'all') p.set('source', source);
    if (unread) p.set('unread', '1');
    if (markiert) p.set('markiert', '1');
    if (account) p.set('account', String(account));
    if (category) p.set('category', category);
    if (q) p.set('q', q);
    if (offen) p.set('offen', offen);
    if (verfassen) p.set('verfassen', verfassen);
    // Jeder Filterwechsel beginnt wieder vorn. Ohne das landet man nach einer
    // Einengung auf Seite 4 eines Ergebnisses, das nur eine Seite hat, und sieht
    // eine leere Liste.
    //
    // ★ Ein Filterwechsel, nicht jeder Klick: Oeffnen und Verfassen lassen die
    // Seite stehen. Vorher fiel die Liste auf Seite 1 zurueck, sobald man auf
    // Seite 3 eine Nachricht anklickte: die Nachricht ging auf, die Liste
    // darunter zeigte etwas anderes, und Schliessen kam woanders heraus.
    const filterwechsel = (
      ['source', 'unread', 'markiert', 'account', 'category', 'q'] as const
    ).some((k) => patch[k] !== undefined);
    const offset = patch.offset ?? (filterwechsel ? 0 : opts.offset);
    if (offset) p.set('offset', String(offset));
    const qs = p.toString();
    return qs ? `?${qs}` : '?';
  }

  const seite = $derived(Math.floor(opts.offset / opts.limit) + 1);

  // Briefe (single-tenant Briefkasten) nur für Berechtigte; Nicht-Owner sehen nur Mail.
  const canSeeLetters = $derived(feed.canSeeLetters);
  const tabs = $derived(
    [
      { key: 'all', label: 'Alle' },
      { key: 'mail', label: 'E-Mail' },
      ...(canSeeLetters ? [{ key: 'letter', label: 'Briefe' }] : []),
    ] as { key: 'all' | 'mail' | 'letter'; label: string }[],
  );

  /**
   * Datum wie in einer Inbox: heute die Uhrzeit, im laufenden Jahr Tag und
   * Monat, davor mit Jahreszahl.
   *
   * ★ Vorher stand ueberall das volle Datum ohne Uhrzeit. Bei mehreren
   * Nachrichten desselben Tages, also dem Normalfall oben in der Liste, sagte
   * die Spalte damit nichts mehr aus.
   */
  function fmtDatum(d: string | null): string {
    if (!d) return '';
    const t = Date.parse(d);
    if (Number.isNaN(t)) return '';
    const wann = new Date(t);
    const jetzt = new Date();
    const zone = 'Europe/Berlin';
    const tag = (x: Date) => x.toLocaleDateString('de-DE', { timeZone: zone });
    if (tag(wann) === tag(jetzt)) {
      return wann.toLocaleTimeString('de-DE', { timeZone: zone, hour: '2-digit', minute: '2-digit' });
    }
    if (wann.getFullYear() === jetzt.getFullYear()) {
      return wann.toLocaleDateString('de-DE', { timeZone: zone, day: '2-digit', month: 'short' });
    }
    return wann.toLocaleDateString('de-DE', {
      timeZone: zone,
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  }

  /** Volles Datum mit Uhrzeit, fuer die Kopfzeile eines geoeffneten Elements. */
  function fmtVoll(d: string | null): string {
    if (!d) return '';
    const t = Date.parse(d);
    if (Number.isNaN(t)) return '';
    return new Date(t).toLocaleString('de-DE', {
      timeZone: 'Europe/Berlin',
      day: '2-digit',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function fmtSize(bytes: number | null): string {
    if (bytes == null) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  // Vertraege mit baldiger Kuendigungsfrist zuerst; nur die relevantesten zeigen.
  const contracts = $derived(
    [...feed.contracts].sort((a, b) => {
      const av = a.days_until_notice ?? Infinity;
      const bv = b.days_until_notice ?? Infinity;
      return av - bv;
    }),
  );

  function fmtEur(v: number | null): string {
    if (v == null) return '';
    return v.toLocaleString('de-DE', { style: 'currency', currency: 'EUR' });
  }

  // HTML-Mails sicher rendern: sandboxed iframe + strenge CSP → keine Scripts,
  // keine Remote-Fetches (also keine Tracking-Pixel), nur inline-Styles + data:-Bilder.
  function mailSrcdoc(html: string): string {
    const csp =
      "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:;\">";
    const style =
      '<style>body{font-family:system-ui,sans-serif;font-size:14px;line-height:1.5;color:#1a1a1a;margin:0;padding:8px;word-break:break-word}img{max-width:100%;height:auto}a{color:#2563eb}</style>';
    return `<!doctype html><html><head><meta charset="utf-8">${csp}${style}</head><body>${html}</body></html>`;
  }

  // Formularwerte: ein fehlgeschlagener Versand gewinnt gegen die Vorbelegung,
  // sonst verliert man beim Tippfehler in einer Adresse den ganzen Text.
  const feldWert = $derived((name: keyof typeof leereWerte) =>
    sendValues ? (sendValues[name] ?? '') : (entwurfWert(name) ?? ''),
  );
  const leereWerte = { account_id: '', to: '', cc: '', subject: '', body: '', in_reply_to: '' };
  function entwurfWert(name: keyof typeof leereWerte): string {
    if (!entwurf) return '';
    switch (name) {
      case 'account_id':
        return entwurf.accountId ? String(entwurf.accountId) : String(feed.accounts[0]?.id ?? '');
      case 'to':
        return entwurf.to;
      case 'cc':
        return entwurf.cc;
      case 'subject':
        return entwurf.subject;
      case 'body':
        return entwurf.body;
      case 'in_reply_to':
        return entwurf.inReplyTo ?? '';
    }
  }

  const entwurfTitel = $derived(
    entwurf?.modus === 'antwort'
      ? 'Antworten'
      : entwurf?.modus === 'alle'
        ? 'Allen antworten'
        : entwurf?.modus === 'weiter'
          ? 'Weiterleiten'
          : 'Neue Nachricht',
  );
  // Cc nur ausklappen, wenn etwas drinsteht. Der Normalfall braucht das Feld nicht.
  let ccOffen = $state(false);
  $effect(() => {
    if (feldWert('cc')) ccOffen = true;
  });
</script>

<svelte:head>
  <title>Post · Saganta</title>
</svelte:head>

<header class="mb-8 flex items-start justify-between gap-4">
  <div>
    <h1 class="font-display text-4xl tracking-tight">Post</h1>
    <p class="mt-2 text-sm text-muted">
      {canSeeLetters ? 'Briefe und alle E-Mail-Konten in einer Inbox.' : 'Alle E-Mail-Konten in einer Inbox.'}
      <span class="ml-1">
        {#if canSeeLetters}{feed.counts.letters}
          {feed.counts.letters === 1 ? 'Brief' : 'Briefe'} ·
        {/if}{feed.counts.mail}
        {feed.counts.mail === 1 ? 'Mail' : 'Mails'}
      </span>
    </p>
  </div>
  <div class="mt-1 flex shrink-0 items-center gap-2">
    {#if canSeeLetters}
      <a
        href={briefkastenUrl}
        class="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-muted transition-colors duration-fast ease-saganta hover:text-text"
        title="Briefe scannen, per OCR archivieren, Verträge und Fristen verwalten"
      >
        <Icon name="inbox" size={15} /> Briefkasten
      </a>
    {/if}
    <a
      href="/accounts"
      class="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-muted transition-colors duration-fast ease-saganta hover:text-text"
    >
      <Icon name="settings" size={15} /> Konten
    </a>
  </div>
</header>

{#if feed.failures.mail || feed.failures.letters}
  <div class="mb-6 rounded-lg border border-warm-500/40 bg-warm-500/10 px-4 py-3 text-sm text-muted">
    {#if feed.failures.letters}<p>Briefkasten nicht erreichbar.</p>{/if}
    {#if feed.failures.mail}<p>Mailkonten nicht erreichbar.</p>{/if}
  </div>
{/if}

{#if actionError}
  <p class="mb-6 rounded-md border border-warm-700 bg-warm-700/10 px-3 py-2 text-sm text-warm-500">
    {actionError}
  </p>
{/if}
{#if archivedId != null}
  <p class="mb-6 rounded-md border border-accent-700 bg-accent-700/10 px-3 py-2 text-sm text-accent-300">
    Brief archiviert.
  </p>
{/if}
{#if snoozedTage != null}
  <p class="mb-6 rounded-md border border-accent-700 bg-accent-700/10 px-3 py-2 text-sm text-accent-300">
    Brief ist für {snoozedTage} {snoozedTage === 1 ? 'Tag' : 'Tage'} aus der Liste genommen.
  </p>
{/if}
{#if sendOk}
  <p class="mb-6 rounded-md border border-accent-700 bg-accent-700/10 px-3 py-2 text-sm text-accent-300">
    Nachricht gesendet.
  </p>
{/if}

<!-- Werkzeugleiste: Quelle, Filter, Suche, Verfassen -->
<section class="mb-6 space-y-3">
  <div class="flex flex-wrap items-center gap-2">
    <div class="inline-flex rounded-lg border border-border bg-surface-2/30 p-0.5">
      {#each tabs as t (t.key)}
        <a
          href={hrefWith(
            t.key === 'letter' ? { source: 'letter', unread: false, markiert: false } : { source: t.key },
          )}
          class="rounded-md px-3 py-1.5 text-sm transition-colors duration-fast ease-saganta {opts.source ===
          t.key
            ? 'bg-accent-500/15 text-accent-300'
            : 'text-muted hover:text-text'}"
        >
          {t.label}
          {#if t.key !== 'letter' && feed.counts.mailUnread > 0}
            <span class="ml-1 text-xs text-muted/70">{feed.counts.mailUnread}</span>
          {/if}
        </a>
      {/each}
    </div>

    {#if opts.source !== 'letter'}
      <a
        href={hrefWith({ unread: !opts.unreadOnly })}
        class="rounded-md border px-3 py-1.5 text-sm transition-colors duration-fast ease-saganta {opts.unreadOnly
          ? 'border-accent-700 bg-accent-700/10 text-accent-300'
          : 'border-border text-muted hover:text-text'}"
      >
        Nur ungelesen
      </a>
      <!-- Markierte gab es nur zum Setzen, nicht zum Wiederfinden: der Filter
           steckte seit jeher in mail-api und hatte keine Schaltflaeche. -->
      <a
        href={hrefWith({ markiert: !opts.starredOnly })}
        class="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm transition-colors duration-fast ease-saganta {opts.starredOnly
          ? 'border-warm-500/50 bg-warm-500/10 text-warm-500'
          : 'border-border text-muted hover:text-text'}"
      >
        <Icon name="star" size={14} filled={opts.starredOnly} /> Markiert
      </a>
    {/if}

    {#if feed.accounts.length > 1 && opts.source !== 'letter'}
      <select
        class="rounded-md border border-border bg-surface-2/30 px-2 py-1.5 text-sm text-muted"
        value={opts.accountId ? String(opts.accountId) : ''}
        onchange={(e) => {
          const v = Number((e.currentTarget as HTMLSelectElement).value);
          goto(hrefWith({ account: v > 0 ? v : null }));
        }}
      >
        <option value="">Alle Konten</option>
        {#each feed.accounts as a (a.id)}
          <option value={String(a.id)}>{a.display_name || a.email}</option>
        {/each}
      </select>
    {/if}

    <div class="ml-auto flex items-center gap-2">
      <!-- Die Suche laeuft ueber den ganzen Bestand, nicht ueber den geladenen
           Ausschnitt: bei Mails ueber Betreff und Adressen, bei Briefen
           zusaetzlich ueber den OCR-Volltext. Deshalb ein GET-Formular und kein
           Filtern im Browser. -->
      <form method="GET" class="flex items-center gap-2">
        {#if opts.source !== 'all'}<input type="hidden" name="source" value={opts.source} />{/if}
        {#if opts.unreadOnly}<input type="hidden" name="unread" value="1" />{/if}
        {#if opts.starredOnly}<input type="hidden" name="markiert" value="1" />{/if}
        {#if opts.accountId}<input type="hidden" name="account" value={String(opts.accountId)} />{/if}
        {#if opts.category}<input type="hidden" name="category" value={opts.category} />{/if}
        <label class="flex items-center gap-1.5 rounded-md border border-border bg-surface-2/30 px-2.5 py-1.5">
          <Icon name="search" size={15} />
          <input
            type="search"
            name="q"
            value={opts.suche ?? ''}
            placeholder="Durchsuchen"
            class="w-32 bg-transparent text-sm text-text placeholder:text-muted/60 focus:outline-none sm:w-44"
          />
        </label>
      </form>
      <a
        href={hrefWith({ verfassen: 'neu', offen: null })}
        class="inline-flex items-center gap-1.5 rounded-md border border-accent-700 bg-accent-700/10 px-3 py-1.5 text-sm text-accent-300 transition-colors duration-fast ease-saganta hover:bg-accent-700/20"
      >
        <Icon name="mail" size={15} />
        Verfassen
      </a>
    </div>
  </div>

  {#if feed.categories.length > 0 && opts.source !== 'mail'}
    <div class="flex flex-wrap items-center gap-1.5">
      <a
        href={hrefWith({ category: null })}
        class="rounded-full border px-2.5 py-0.5 text-xs transition-colors {opts.category
          ? 'border-border text-muted hover:text-text'
          : 'border-warm-500/50 bg-warm-500/10 text-warm-500'}"
      >
        Alle Kategorien
      </a>
      {#each feed.categories as cat (cat)}
        <a
          href={hrefWith({ category: cat })}
          class="rounded-full border px-2.5 py-0.5 text-xs transition-colors {opts.category === cat
            ? 'border-warm-500/50 bg-warm-500/10 text-warm-500'
            : 'border-border text-muted hover:text-text'}"
        >
          {cat}
        </a>
      {/each}
    </div>
  {/if}

  {#if opts.suche}
    <p class="text-xs text-muted/70">
      Suche nach „{opts.suche}".
      <a href={hrefWith({ q: null })} class="text-accent-400 hover:text-accent-300">zurücksetzen</a>
    </p>
  {/if}
  {#if opts.source === 'all' && (opts.unreadOnly || opts.starredOnly)}
    <p class="text-xs text-muted/70">
      Briefe sind hier ausgeblendet: sie kennen weder gelesen noch markiert.
    </p>
  {/if}
</section>

{#if entwurf}
  <form
    method="POST"
    action="?/send"
    use:enhance
    class="mb-8 space-y-3 rounded-xl border border-accent-700 bg-surface-2 p-4"
  >
    <div class="flex items-center justify-between">
      <h2 class="font-display text-lg text-text">{entwurfTitel}</h2>
      <a
        href={hrefWith({ verfassen: null })}
        class="text-muted transition-colors hover:text-text"
        aria-label="Schließen"
      >
        <Icon name="x" size={18} />
      </a>
    </div>
    {#if sendError}
      <p class="rounded-md border border-warm-700 bg-warm-700/10 px-3 py-2 text-sm text-warm-500">
        {sendError}
      </p>
    {/if}
    {#if feed.accounts.length === 0}
      <p class="text-sm text-muted">
        Kein Mailkonto verbunden.
        <a href="/accounts" class="text-accent-400 hover:text-accent-300">Jetzt eines verbinden.</a>
      </p>
    {:else}
      {#if entwurf.modus !== 'neu' && !entwurf.inReplyTo && entwurf.modus !== 'weiter'}
        <p class="rounded-md border border-border bg-surface/60 px-3 py-2 text-xs text-muted">
          Diese Nachricht trägt keine Kennung, an die sich anknüpfen lässt. Sie geht als
          neue Nachricht an denselben Empfänger, nicht als Antwort im selben Gesprächsfaden.
        </p>
      {/if}
      {#if entwurf.ohneZitat}
        <p class="rounded-md border border-border bg-surface/60 px-3 py-2 text-xs text-muted">
          Das Original lag nur als HTML vor und wurde deshalb nicht zitiert.
        </p>
      {/if}
      <input type="hidden" name="in_reply_to" value={feldWert('in_reply_to')} />
      <label class="block text-sm">
        <span class="mb-1 block text-muted">Von</span>
        <select
          name="account_id"
          value={feldWert('account_id') || String(feed.accounts[0]?.id ?? '')}
          class="w-full rounded-md border border-border bg-surface px-3 py-2 text-text"
        >
          {#each feed.accounts as a (a.id)}
            <option value={String(a.id)}>{a.display_name ? `${a.display_name} · ` : ''}{a.email}</option>
          {/each}
        </select>
      </label>
      <label class="block text-sm">
        <span class="mb-1 flex items-center justify-between text-muted">
          <span>An (mehrere per Komma)</span>
          {#if !ccOffen}
            <button
              type="button"
              class="text-xs text-accent-400 transition-colors hover:text-accent-300"
              onclick={() => (ccOffen = true)}
            >
              Cc hinzufügen
            </button>
          {/if}
        </span>
        <input
          name="to"
          type="text"
          required
          value={feldWert('to')}
          class="w-full rounded-md border border-border bg-surface px-3 py-2 text-text"
        />
      </label>
      <!-- Cc wurde serverseitig seit jeher verarbeitet und im Formular nie
           angeboten: der Wert konnte nur leer ankommen. -->
      {#if ccOffen}
        <label class="block text-sm">
          <span class="mb-1 block text-muted">Cc</span>
          <input
            name="cc"
            type="text"
            value={feldWert('cc')}
            class="w-full rounded-md border border-border bg-surface px-3 py-2 text-text"
          />
        </label>
      {/if}
      <label class="block text-sm">
        <span class="mb-1 block text-muted">Betreff</span>
        <input
          name="subject"
          type="text"
          value={feldWert('subject')}
          class="w-full rounded-md border border-border bg-surface px-3 py-2 text-text"
        />
      </label>
      <label class="block text-sm">
        <span class="mb-1 block text-muted">Text</span>
        <textarea
          name="body"
          rows="10"
          value={feldWert('body')}
          class="w-full rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text"
        ></textarea>
      </label>
      <div class="flex justify-end">
        <button
          class="rounded-md border border-accent-700 bg-accent-700/10 px-4 py-2 text-sm text-accent-300 transition-colors hover:bg-accent-700/20"
        >
          Senden
        </button>
      </div>
    {/if}
  </form>
{/if}

{#if contracts.length > 0}
  <section class="mb-8">
    <h2 class="mb-3 flex items-center gap-2 font-display text-xl text-text">
      <Icon name="box" size={18} />
      Verträge und Fristen
    </h2>
    <ul class="grid gap-2 sm:grid-cols-2">
      {#each contracts as c (c.id)}
        {@const urgent = c.days_until_notice != null && c.days_until_notice <= 30}
        <li class="rounded-xl border {urgent ? 'border-warm-500/50 bg-warm-500/10' : 'border-border bg-surface-2/20'} px-4 py-3">
          <div class="flex items-baseline justify-between gap-2">
            <span class="truncate font-medium text-text">{c.name}</span>
            {#if c.monthly_amount != null}
              <span class="shrink-0 text-xs text-muted">{fmtEur(c.monthly_amount)}/Mon</span>
            {/if}
          </div>
          <div class="mt-1 flex items-center gap-2 text-sm text-muted">
            {#if c.kind}<span class="rounded-full border border-border px-2 py-0.5 text-xs">{c.kind}</span>{/if}
            {#if c.notice_deadline}
              <span class={urgent ? 'text-warm-500' : 'text-muted'}>
                Frist {fmtDatum(c.notice_deadline)}{#if c.days_until_notice != null} · {c.days_until_notice} Tage{/if}
              </span>
            {/if}
          </div>
          {#if c.notice_deadline}
            <!-- Cross-App: Kündigungsfrist per Deep-Link in den Kalender übernehmen.
                 `host` ist Pflicht, sonst zeigt der Link aus dem Heimnetz durch
                 den Tunnel auf die oeffentliche Domaene (siehe packages/ui/links.ts). -->
            <a
              href={kalenderCaptureUrl(`${c.name} kündigen`, c.notice_deadline, host)}
              class="mt-2 inline-flex items-center gap-1 text-xs text-accent-400 hover:text-accent-300"
              title="Frist als Termin im Kalender anlegen"
            >
              <Icon name="calendar" size={13} /> Frist in den Kalender
            </a>
          {/if}
        </li>
      {/each}
    </ul>
  </section>
{/if}

<!-- Geöffnetes Element -->
{#if offeneMail}
  <article class="mb-8 space-y-3 rounded-lg border border-accent-700 bg-surface-2 p-4">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="font-display text-2xl">{offeneMail.subject || '(kein Betreff)'}</h2>
        <p class="mt-1 text-sm text-muted">
          {offeneMail.from_addr} · {fmtVoll(offeneMail.date)}
        </p>
        {#if offeneMail.to_addr}
          <p class="text-xs text-muted/70">An: {offeneMail.to_addr}</p>
        {/if}
      </div>
      <a
        href={hrefWith({ offen: null, verfassen: null })}
        class="shrink-0 text-muted transition-colors hover:text-text"
        aria-label="Schließen"
      >
        <Icon name="x" size={18} />
      </a>
    </div>

    <!-- Antworten war bis 2026-09-14 gar nicht moeglich: die App konnte Post nur
         lesen. Der Versand samt `In-Reply-To` lag im Backend bereit. -->
    <div class="flex flex-wrap gap-2">
      <a
        href={hrefWith({ verfassen: 'antwort' })}
        class="inline-flex items-center gap-1.5 rounded-md border border-accent-700 bg-accent-700/10 px-3 py-1.5 text-sm text-accent-300 transition-colors hover:bg-accent-700/20"
      >
        <Icon name="arrow-left" size={14} /> Antworten
      </a>
      <a
        href={hrefWith({ verfassen: 'alle' })}
        class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-muted transition-colors hover:text-text"
      >
        Allen antworten
      </a>
      <a
        href={hrefWith({ verfassen: 'weiter' })}
        class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-muted transition-colors hover:text-text"
      >
        Weiterleiten
      </a>
      <form method="POST" action="?/setState" use:enhance class="ml-auto">
        <input type="hidden" name="source" value="mail" />
        <input type="hidden" name="item_id" value={offeneMail.id} />
        <input type="hidden" name="is_read" value="false" />
        <button class="rounded-md border border-border px-3 py-1.5 text-sm text-muted transition-colors hover:text-text">
          Als ungelesen
        </button>
      </form>
    </div>

    {#if offeneMail.text}
      <pre class="whitespace-pre-wrap font-sans text-sm">{offeneMail.text}</pre>
    {:else if offeneMail.html}
      <iframe
        title="E-Mail-Inhalt"
        sandbox=""
        referrerpolicy="no-referrer"
        srcdoc={mailSrcdoc(offeneMail.html)}
        class="h-96 w-full rounded-md border border-border bg-white"
      ></iframe>
      <p class="text-xs text-muted/70">
        Externe Bilder werden aus Datenschutzgründen nicht geladen.
      </p>
    {:else}
      <p class="text-sm text-muted">(leerer Inhalt)</p>
    {/if}
  </article>
{/if}

{#if offenerBrief}
  <article class="mb-8 space-y-3 rounded-lg border border-warm-500/50 bg-surface-2 p-4">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="font-display text-2xl">{offenerBrief.title || '(ohne Titel)'}</h2>
        <p class="text-sm text-muted">
          {offenerBrief.sender || 'Unbekannt'} · {fmtDatum(offenerBrief.received_date || offenerBrief.created_at)}
        </p>
      </div>
      <a
        href={hrefWith({ offen: null })}
        class="shrink-0 text-muted transition-colors hover:text-text"
        aria-label="Schließen"
      >
        <Icon name="x" size={18} />
      </a>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      {#if !offenerBrief.is_archived}
        <form method="POST" action="?/archive" use:enhance>
          <input type="hidden" name="source" value="letter" />
          <input type="hidden" name="item_id" value={offenerBrief.id} />
          <button class="rounded-md border border-border px-3 py-1.5 text-sm text-muted transition-colors duration-fast ease-saganta hover:text-text">
            Archivieren
          </button>
        </form>
        <!-- Wiedervorlage statt Archivieren: fuer alles, was noch zu tun ist,
             aber nicht heute. Archivieren heisst hier erledigt. -->
        <form method="POST" action="?/snooze" use:enhance class="flex items-center gap-1.5">
          <input type="hidden" name="source" value="letter" />
          <input type="hidden" name="item_id" value={offenerBrief.id} />
          <label class="flex items-center gap-1.5 text-sm text-muted">
            Später erinnern in
            <select
              name="tage"
              class="rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
            >
              <option value="7">7 Tagen</option>
              <option value="14">14 Tagen</option>
              <option value="30">30 Tagen</option>
              <option value="90">90 Tagen</option>
            </select>
          </label>
          <button class="rounded-md border border-border px-3 py-1.5 text-sm text-muted transition-colors hover:text-text">
            Übernehmen
          </button>
        </form>
      {/if}
    </div>

    {#if offenerBrief.tags.length > 0}
      <div class="flex flex-wrap gap-1.5">
        {#each offenerBrief.tags as t (t.id)}
          <span class="rounded-full border border-border px-2 py-0.5 text-xs text-muted">{t.name}</span>
        {/each}
      </div>
    {/if}
    {#if offenerBrief.summary}
      <p class="text-sm">{offenerBrief.summary}</p>
    {/if}
    {#if offenerBrief.ocr_text}
      <details class="text-sm text-muted">
        <summary class="cursor-pointer select-none">Volltext (OCR)</summary>
        <pre class="mt-2 whitespace-pre-wrap font-sans">{offenerBrief.ocr_text}</pre>
      </details>
    {/if}
    {#if offenerBrief.notes}
      <p class="text-sm text-muted">Notiz: {offenerBrief.notes}</p>
    {/if}
    {#if offenerBrief.files.length > 0}
      <ul class="space-y-1 text-sm">
        {#each offenerBrief.files as f (f.id)}
          <li>
            <a
              class="inline-flex items-center gap-1.5 text-accent-300 hover:underline"
              href={`/files/${offenerBrief.id}/${f.id}`}
              target="_blank"
              rel="noopener"
            >
              <Icon name="box" size={14} />
              {f.original_filename || f.filename}
              {#if f.file_size != null}<span class="text-xs text-muted">({fmtSize(f.file_size)})</span>{/if}
            </a>
          </li>
        {/each}
      </ul>
    {/if}
  </article>
{/if}

{#if feed.items.length === 0}
  <div class="rounded-2xl border border-dashed border-border bg-surface-2/30 p-10 text-center">
    {#if opts.suche}
      <p class="text-text">Keine Treffer für „{opts.suche}".</p>
      <p class="mt-1 text-sm text-muted">
        Gesucht wird über Betreff und Absender, bei Briefen zusätzlich im erkannten Text.
      </p>
      <a
        href={hrefWith({ q: null })}
        class="mt-3 inline-flex items-center gap-1.5 rounded-md border border-border px-4 py-2 text-sm text-muted transition-colors duration-fast ease-saganta hover:text-text"
      >
        Suche zurücksetzen
      </a>
    {:else if opts.unreadOnly || opts.starredOnly || opts.category || opts.offset > 0}
      <p class="text-text">Hier ist nichts.</p>
      <a
        href="?"
        class="mt-3 inline-flex items-center gap-1.5 rounded-md border border-border px-4 py-2 text-sm text-muted transition-colors duration-fast ease-saganta hover:text-text"
      >
        Alle Filter zurücksetzen
      </a>
    {:else}
      <div class="mx-auto mb-3 grid size-12 place-items-center rounded-xl bg-accent-500/12 text-accent-400">
        <Icon name="mail" size={24} />
      </div>
      <p class="text-text">Noch nichts in deiner Post.</p>
      <p class="mt-1 text-sm text-muted">
        <a href="/accounts" class="text-accent-400 hover:text-accent-300">Verbinde ein Mailkonto</a>
        {#if canSeeLetters}
          oder <a href={briefkastenUrl} class="text-accent-400 hover:text-accent-300">scanne einen Brief</a>
        {/if}.
      </p>
    {/if}
  </div>
{:else}
  <ul class="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-surface-2/20">
    {#each feed.items as item (item.id)}
      {@const istOffen = $page.url.searchParams.get('offen') === item.id}
      <li
        class="flex items-start gap-4 px-5 py-4 transition-colors {istOffen
          ? 'bg-accent-500/[0.07]'
          : 'hover:bg-surface-2/50'}"
      >
        <div
          class="mt-0.5 grid size-9 shrink-0 place-items-center rounded-lg {item.source === 'letter'
            ? 'bg-warm-500/15 text-warm-500'
            : 'bg-accent-500/12 text-accent-400'}"
          title={item.source === 'letter' ? 'Brief' : 'E-Mail'}
        >
          <Icon name={item.source === 'letter' ? 'box' : 'mail'} size={18} />
        </div>
        <div class="min-w-0 flex-1">
          <!-- Ein Link, kein Formular: damit laesst sich der Eintrag in einem
               neuen Tab oeffnen, verlinken und mit Zurueck wieder schliessen. -->
          <a href={hrefWith({ offen: istOffen ? null : item.id, verfassen: null })} class="block">
            <div class="flex items-baseline justify-between gap-3">
              <span class="truncate {item.unread ? 'font-semibold text-text' : 'text-muted'}">
                {item.title}
              </span>
              <span class="shrink-0 text-xs text-muted/70">{fmtDatum(item.date)}</span>
            </div>
            <div class="mt-0.5 flex items-center gap-2 text-sm text-muted">
              <span class="truncate">{item.from}</span>
              {#if item.category}
                <span class="shrink-0 rounded-full border border-border px-2 py-0.5 text-xs text-muted/70">
                  {item.category}
                </span>
              {/if}
              {#if item.fileCount}
                <span
                  class="inline-flex shrink-0 items-center gap-0.5 text-xs text-muted/70"
                  title="{item.fileCount} {item.fileCount === 1 ? 'Anhang' : 'Anhänge'}"
                >
                  <Icon name="box" size={12} />{item.fileCount}
                </span>
              {/if}
            </div>
            {#if item.preview}
              <p class="mt-1 line-clamp-2 text-sm text-muted/80">{item.preview}</p>
            {/if}
            {#if item.tags?.length}
              <div class="mt-1 flex flex-wrap gap-1">
                {#each item.tags as t (t.id)}
                  <span class="rounded-full border border-border px-1.5 py-0.5 text-[11px] text-muted/70">
                    {t.name}
                  </span>
                {/each}
              </div>
            {/if}
          </a>
        </div>
        {#if item.source === 'mail'}
          <div class="flex shrink-0 items-center gap-2 pt-0.5">
            <form method="POST" action="?/setState" use:enhance>
              <input type="hidden" name="source" value="mail" />
              <input type="hidden" name="item_id" value={item.rawId} />
              <input type="hidden" name="is_starred" value={(!item.starred).toString()} />
              <button
                class="transition-colors duration-fast ease-saganta {item.starred ? 'text-warm-500' : 'text-muted hover:text-text'}"
                title={item.starred ? 'Markierung entfernen' : 'Markieren'}
                aria-label={item.starred ? 'Markierung entfernen' : 'Markieren'}
              >
                <Icon name="star" size={17} filled={item.starred} />
              </button>
            </form>
            <form method="POST" action="?/setState" use:enhance>
              <input type="hidden" name="source" value="mail" />
              <input type="hidden" name="item_id" value={item.rawId} />
              <input type="hidden" name="is_read" value={item.unread.toString()} />
              <button class="text-xs text-muted hover:text-text" title={item.unread ? 'Als gelesen' : 'Als ungelesen'} aria-label={item.unread ? 'Als gelesen markieren' : 'Als ungelesen markieren'}>
                {item.unread ? '●' : '○'}
              </button>
            </form>
          </div>
        {/if}
      </li>
    {/each}
  </ul>

  <!-- Blaettern statt das Limit aufzublaehen. Vorher lud "Mehr laden" alles neu
       mit groesserem Limit und endete hart bei 200; beide Quellen koennen
       `offset` seit jeher. -->
  {#if opts.offset > 0 || feed.hasMore}
    <div class="mt-4 flex items-center justify-between gap-3">
      {#if opts.offset > 0}
        <a
          href={hrefWith({ offset: Math.max(0, opts.offset - opts.limit) })}
          class="inline-flex items-center gap-1.5 rounded-md border border-border px-4 py-2 text-sm text-muted transition-colors duration-fast ease-saganta hover:text-text"
        >
          <Icon name="arrow-left" size={14} /> Neuere
        </a>
      {:else}
        <span></span>
      {/if}
      <span class="text-xs text-muted/70">Seite {seite}</span>
      {#if feed.hasMore}
        <a
          href={hrefWith({ offset: opts.offset + opts.limit })}
          class="inline-flex items-center gap-1.5 rounded-md border border-border px-4 py-2 text-sm text-muted transition-colors duration-fast ease-saganta hover:text-text"
        >
          Ältere <Icon name="arrow-right" size={14} />
        </a>
      {:else}
        <span></span>
      {/if}
    </div>
  {/if}
{/if}
