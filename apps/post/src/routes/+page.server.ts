import { fail, redirect } from '@sveltejs/kit';
import {
  archiveLetter,
  getLetterDetail,
  getMailBody,
  loadFeed,
  sendMail,
  setMailState,
  snoozeLetter,
  DEFAULT_LIMIT,
  MAX_LIMIT,
  type FeedOptions,
  type FeedResult,
  type LetterDetail,
  type MailBody,
} from '$lib/post-api';
import { canAccessLetters } from '$lib/server/gate';
import type { Actions, PageServerLoad } from './$types';

const EMPTY_OPTIONS: FeedOptions = {
  source: 'all',
  unreadOnly: false,
  starredOnly: false,
  limit: DEFAULT_LIMIT,
  offset: 0,
};
const EMPTY: FeedResult = {
  items: [],
  contracts: [],
  accounts: [],
  categories: [],
  failures: {},
  counts: { mail: 0, letters: 0, mailUnread: 0 },
  hasMore: false,
  options: EMPTY_OPTIONS,
  canSeeLetters: false,
};

function readOptions(url: URL): FeedOptions {
  const source = url.searchParams.get('source');
  const account = Number(url.searchParams.get('account'));
  const limit = Number(url.searchParams.get('limit'));
  const offset = Number(url.searchParams.get('offset'));
  const category = url.searchParams.get('category');
  const suche = (url.searchParams.get('q') ?? '').trim();
  return {
    source: source === 'mail' || source === 'letter' ? source : 'all',
    unreadOnly: url.searchParams.get('unread') === '1',
    starredOnly: url.searchParams.get('markiert') === '1',
    accountId: Number.isInteger(account) && account > 0 ? account : undefined,
    category: category || undefined,
    suche: suche || undefined,
    limit: Number.isInteger(limit) && limit > 0 ? Math.min(limit, MAX_LIMIT) : DEFAULT_LIMIT,
    offset: Number.isInteger(offset) && offset > 0 ? offset : 0,
  };
}

/** `mail-42` / `letter-7` aus dem `offen`-Parameter. */
function readOffen(url: URL): { source: 'mail' | 'letter'; id: number } | null {
  const raw = url.searchParams.get('offen');
  if (!raw) return null;
  const [source, rest] = raw.split('-');
  const id = Number(rest);
  if ((source !== 'mail' && source !== 'letter') || !Number.isInteger(id) || id <= 0) return null;
  return { source, id };
}

export type EntwurfModus = 'neu' | 'antwort' | 'alle' | 'weiter';

export interface Entwurf {
  modus: EntwurfModus;
  accountId: number | null;
  to: string;
  cc: string;
  subject: string;
  body: string;
  /** Message-ID des Originals. Leer heisst: neuer Faden. */
  inReplyTo: string | null;
  /**
   * Gesetzt, wenn die Nachricht nur als HTML vorlag und deshalb nicht zitiert
   * werden konnte. Die Oberflaeche sagt das, statt ein leeres Zitat zu zeigen.
   */
  ohneZitat: boolean;
}

function istModus(v: string | null): v is EntwurfModus {
  return v === 'neu' || v === 'antwort' || v === 'alle' || v === 'weiter';
}

/** `Re: ` / `Fwd: ` nur voranstellen, wenn es noch nicht dasteht. */
function betreffMit(praefix: string, betreff: string): string {
  const b = betreff.trim();
  if (b.toLowerCase().startsWith(praefix.toLowerCase())) return b;
  return `${praefix}${b}`;
}

function zitat(mail: MailBody): string {
  if (!mail.text) return '';
  const wann = mail.date
    ? new Date(mail.date).toLocaleString('de-DE', { timeZone: 'Europe/Berlin' })
    : 'unbekanntem Datum';
  const zeilen = mail.text.replace(/\r\n/g, '\n').split('\n');
  return `\n\nAm ${wann} schrieb ${mail.from_addr}:\n${zeilen.map((z) => `> ${z}`).join('\n')}\n`;
}

/**
 * Entwurf aus der geoeffneten Nachricht vorbelegen.
 *
 * ★ `Reply-To` schlaegt `From`. Newsletter und Ticketsysteme setzen genau dafuer
 * diesen Kopf, und eine Antwort an `From` landet dann bei `noreply@`.
 *
 * ★ Bei "Allen antworten" fallen die EIGENEN Adressen aus dem Verteiler. Ohne
 * das schriebe man sich bei jeder Antwort selbst mit an, und zwar dauerhaft,
 * weil der eigene Name im `To` des Originals steht.
 */
function baueEntwurf(
  modus: EntwurfModus,
  mail: MailBody | null,
  eigeneAdressen: string[],
  accountId: number | null,
): Entwurf {
  const leer: Entwurf = {
    modus,
    accountId,
    to: '',
    cc: '',
    subject: '',
    body: '',
    inReplyTo: null,
    ohneZitat: false,
  };
  if (modus === 'neu' || !mail) return { ...leer, modus: 'neu' };

  const eigene = new Set(eigeneAdressen.map((a) => a.toLowerCase()));
  const fremd = (adressen: string[]) =>
    adressen.map((a) => a.trim()).filter((a) => a && !eigene.has(a.toLowerCase()));

  const antwortAn = fremd(mail.reply_to?.length ? mail.reply_to : [mail.from_addr]);
  const ohneZitat = !mail.text && !!mail.html;

  if (modus === 'weiter') {
    return {
      ...leer,
      subject: betreffMit('Fwd: ', mail.subject || ''),
      body: zitat(mail),
      ohneZitat,
    };
  }

  // "Allen antworten": alle uebrigen Empfaenger des Originals nach Cc, ohne die
  // Adresse, an die die Antwort ohnehin geht.
  const cc =
    modus === 'alle'
      ? fremd([...(mail.to ?? []), ...(mail.cc ?? [])]).filter(
          (a) => !antwortAn.some((z) => z.toLowerCase() === a.toLowerCase()),
        )
      : [];

  return {
    ...leer,
    to: antwortAn.join(', '),
    cc: cc.join(', '),
    subject: betreffMit('Re: ', mail.subject || ''),
    body: zitat(mail),
    inReplyTo: mail.message_id ?? null,
    ohneZitat,
  };
}

/**
 * Aus welchem Konto geantwortet wird: aus dem, an das die Nachricht ging.
 *
 * ★ Bewusst aus `to_addr` der Nachricht und nicht aus der geladenen Liste.
 * Ueber die Liste ginge es nur, solange die Nachricht auf der gerade sichtbaren
 * Seite steht; bei einem Link auf eine aeltere Nachricht waere dann still das
 * erste Konto voreingestellt, und man antwortete unter falschem Namen.
 */
function absenderFuer(
  mail: MailBody | null,
  konten: { id: number; email: string }[],
): number | null {
  const erstes = konten[0];
  if (!erstes) return null;
  const empfaenger = (mail?.to_addr ?? '').toLowerCase();
  const treffer = konten.find((k) => empfaenger.includes(k.email.toLowerCase()));
  return (treffer ?? erstes).id;
}

export const load: PageServerLoad = async ({ locals, fetch, url }) => {
  if (!locals.user) return { feed: EMPTY, offenerBrief: null, offeneMail: null, entwurf: null };

  const darfBriefe = canAccessLetters(locals.user);
  const feed = await loadFeed(locals.user, fetch, readOptions(url), darfBriefe);

  // Das geoeffnete Element haengt jetzt an der Adresse statt an einem
  // Formular-Ergebnis. Zwei Dinge gehen damit, die vorher nicht gingen: der
  // Zustand ueberlebt jede andere Aktion (markieren, archivieren) statt sie
  // stillschweigend zu schliessen, und ein geoeffneter Brief laesst sich
  // verlinken.
  const offen = readOffen(url);
  let offeneMail: MailBody | null = null;
  let offenerBrief: LetterDetail | null = null;
  let fehler: string | null = null;

  if (offen?.source === 'mail') {
    try {
      offeneMail = await getMailBody(locals.user, fetch, offen.id);
      // Eine geoeffnete Nachricht ist gelesen. Vorher musste man das zusaetzlich
      // von Hand klicken, und der ungelesen-Zaehler blieb stehen, obwohl man
      // gerade alles gelesen hatte.
      //
      // Der Schreibzugriff sitzt bewusst hier und nicht in einer Aktion: das
      // Oeffnen IST das Ereignis. Er ist idempotent, ein erneutes Laden derselben
      // Adresse aendert nichts mehr.
      const eintrag = feed.items.find((i) => i.source === 'mail' && i.rawId === offen.id);
      if (eintrag?.unread) {
        await setMailState(locals.user, fetch, offen.id, { is_read: true }).catch(() => null);
        eintrag.unread = false;
        feed.counts.mailUnread = Math.max(0, feed.counts.mailUnread - 1);
      }
    } catch (err) {
      fehler = `Nachricht konnte nicht geladen werden: ${String(err)}`;
    }
  } else if (offen?.source === 'letter') {
    if (!darfBriefe) {
      fehler = 'Kein Zugriff auf Briefe.';
    } else {
      try {
        offenerBrief = await getLetterDetail(fetch, offen.id);
      } catch (err) {
        fehler = `Brief konnte nicht geladen werden: ${String(err)}`;
      }
    }
  }

  const modusRoh = url.searchParams.get('verfassen');
  const entwurf = istModus(modusRoh)
    ? baueEntwurf(
        modusRoh,
        offeneMail,
        feed.accounts.map((a) => a.email),
        absenderFuer(offeneMail, feed.accounts),
      )
    : null;

  return { feed, offeneMail, offenerBrief, entwurf, ladeFehler: fehler };
};

function itemRef(fd: FormData): { source: 'mail' | 'letter'; id: number } | null {
  const source = String(fd.get('source') ?? '');
  const id = Number(fd.get('item_id'));
  if ((source !== 'mail' && source !== 'letter') || !Number.isInteger(id)) return null;
  return { source, id };
}

export const actions: Actions = {
  // read/star gibt es nur für Mails (Briefe kennen kein read/star).
  setState: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { error: 'not authenticated' });
    const fd = await request.formData();
    const ref = itemRef(fd);
    if (!ref || ref.source !== 'mail') return fail(400, { error: 'bad item ref' });
    const state: { is_read?: boolean; is_starred?: boolean } = {};
    if (fd.has('is_read')) state.is_read = fd.get('is_read') === 'true';
    if (fd.has('is_starred')) state.is_starred = fd.get('is_starred') === 'true';
    try {
      const message = await setMailState(locals.user, fetch, ref.id, state);
      return { message };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  archive: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { error: 'not authenticated' });
    if (!canAccessLetters(locals.user)) return fail(403, { error: 'Kein Zugriff auf Briefe.' });
    const ref = itemRef(await request.formData());
    if (!ref || ref.source !== 'letter') return fail(400, { error: 'bad item ref' });
    try {
      const letter = await archiveLetter(fetch, ref.id, true);
      return { archived: letter.id };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // Wiedervorlage: der Brief verschwindet bis zum gewaehlten Tag aus der Liste.
  // Gegenstueck zum Archivieren, das "erledigt" meint.
  snooze: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { error: 'not authenticated' });
    if (!canAccessLetters(locals.user)) return fail(403, { error: 'Kein Zugriff auf Briefe.' });
    const fd = await request.formData();
    const ref = itemRef(fd);
    if (!ref || ref.source !== 'letter') return fail(400, { error: 'bad item ref' });
    const tage = Number(fd.get('tage'));
    if (!Number.isInteger(tage) || tage < 1 || tage > 365) {
      return fail(400, { error: 'Zeitraum muss zwischen 1 und 365 Tagen liegen.' });
    }
    const bis = new Date(Date.now() + tage * 24 * 60 * 60 * 1000).toISOString();
    try {
      const letter = await snoozeLetter(fetch, ref.id, bis);
      return { snoozed: letter.id, snoozedTage: tage };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // Mail verfassen und via mail-api (SMTP des jeweiligen Kontos) versenden.
  // Briefe sind read-only (briefkasten kennt keinen Versand).
  send: async ({ locals, fetch, request, url }) => {
    if (!locals.user) return fail(401, { error: 'not authenticated' });
    const fd = await request.formData();
    const accountId = Number(fd.get('account_id'));
    const to = splitAddresses(String(fd.get('to') ?? ''));
    const cc = splitAddresses(String(fd.get('cc') ?? ''));
    const subject = String(fd.get('subject') ?? '');
    const body = String(fd.get('body') ?? '');
    const inReplyTo = String(fd.get('in_reply_to') ?? '').trim() || null;
    const values = {
      account_id: Number.isInteger(accountId) && accountId > 0 ? String(accountId) : '',
      to: to.join(', '),
      cc: cc.join(', '),
      subject,
      body,
      in_reply_to: inReplyTo ?? '',
    };
    if (!Number.isInteger(accountId) || accountId <= 0) {
      return fail(400, { sendError: 'Bitte ein Absender-Konto wählen.', values });
    }
    if (to.length === 0) {
      return fail(400, { sendError: 'Mindestens eine Empfängeradresse angeben.', values });
    }
    const invalid = [...to, ...cc].filter((addr) => !isEmail(addr));
    if (invalid.length > 0) {
      return fail(400, { sendError: `Ungültige Adresse: ${invalid.join(', ')}`, values });
    }
    try {
      await sendMail(locals.user, fetch, {
        account_id: accountId,
        to,
        subject,
        body,
        cc,
        in_reply_to: inReplyTo,
      });
    } catch (err) {
      return fail(502, { sendError: String(err), values });
    }
    // Umleiten statt einen Erfolg zurueckzugeben: damit verschwindet `verfassen`
    // aus der Adresse, das Formular schliesst sich, und ein Neuladen der Seite
    // schickt nicht nochmal dieselbe Nachricht.
    const ziel = new URL(url);
    ziel.searchParams.delete('verfassen');
    ziel.searchParams.set('gesendet', '1');
    redirect(303, `${ziel.pathname}${ziel.search}`);
  },
};

// Empfänger aus Freitext (Komma/Semikolon/Whitespace-getrennt) normalisieren.
function splitAddresses(raw: string): string[] {
  return raw
    .split(/[,;\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

// Einfache, pragmatische E-Mail-Prüfung (kein RFC-5322-Vollparser).
function isEmail(addr: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(addr);
}
