import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';
import { MAX_LIMIT } from './constants';
export { DEFAULT_LIMIT, MAX_LIMIT } from './constants';

// Post = Aggregation zweier komplementaerer Quellen:
//  - mail-api (IMAP/SMTP, better-auth Backend-JWT, audience mail-api)
//  - briefkasten (physische Post + Vertraege, eigene Auth, interne API mit
//    statischem Bearer KG_INTERNAL_TOKEN). KEIN Schema-Merge, nur Zusammenfuehrung.

// ---------------------------------------------------------------------------
// mail-api
// ---------------------------------------------------------------------------
export interface MailMessage {
  id: number;
  account_email: string;
  subject: string;
  from_addr: string;
  from_name: string | null;
  snippet: string | null;
  date: string | null;
  is_read: boolean;
  is_starred: boolean;
}

export interface MailBody {
  id: number;
  subject: string;
  from_addr: string;
  to_addr: string | null;
  date: string | null;
  text: string | null;
  html: string | null;
  /** RFC-5322-Message-ID des Originals. Ohne sie wird aus der Antwort ein neuer Faden. */
  message_id?: string | null;
  /** Antwortadresse des Absenders. Hat Vorrang vor `from_addr`. */
  reply_to?: string[];
  /** Empfaenger und Mitempfaenger des Originals, fuer "Allen antworten". */
  to?: string[];
  cc?: string[];
}

interface MailPage {
  items: MailMessage[];
  total: number;
}

export interface MailAccountInfo {
  id: number;
  email: string;
  display_name: string | null;
  enabled: boolean;
}

const MAIL_AUDIENCE = 'mail-api';

function backendSecret(): string {
  const secret = env.SAGANTA_BACKEND_SECRET;
  if (!secret) throw new Error('SAGANTA_BACKEND_SECRET ist nicht gesetzt: Backend-Token kann nicht signiert werden.');
  return secret;
}

function mailToken(user: SagantaUser): string {
  return issueBackendToken({
    user,
    secret: backendSecret(),
    audience: MAIL_AUDIENCE,
    ttlSeconds: 60,
  });
}

interface MailQuery {
  limit: number;
  offset?: number;
  unread?: boolean;
  starred?: boolean;
  accountId?: number;
  suche?: string;
}

async function fetchMail(
  user: SagantaUser,
  fetcher: typeof fetch,
  query: MailQuery,
): Promise<MailPage> {
  const base = env.MAIL_API_BASE_URL;
  if (!base) return { items: [], total: 0 };
  const params = new URLSearchParams({ limit: String(query.limit) });
  if (query.offset) params.set('offset', String(query.offset));
  if (query.unread) params.set('unread', 'true');
  if (query.starred) params.set('starred', 'true');
  if (query.accountId != null) params.set('account_id', String(query.accountId));
  if (query.suche) params.set('suche', query.suche);
  const res = await fetcher(`${base.replace(/\/$/, '')}/api/mail/messages?${params}`, {
    headers: { Authorization: `Bearer ${mailToken(user)}`, Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`mail-api ${res.status}`);
  const page = (await res.json()) as MailPage;
  return { items: page.items ?? [], total: page.total ?? (page.items?.length ?? 0) };
}

/**
 * Wie viele Nachrichten es insgesamt gibt, ohne sie zu holen (`limit=1`).
 *
 * ★ Braucht es, weil die Kopfzeile vorher `mail.length` anzeigte, also die Zahl
 * der geladenen Eintraege. Bei 50 geladenen von 2000 stand dort "50 Mails", und
 * das las sich wie ein Bestand, war aber eine Seitengroesse.
 */
async function zaehleMail(
  user: SagantaUser,
  fetcher: typeof fetch,
  query: Omit<MailQuery, 'limit' | 'offset'>,
): Promise<number> {
  const page = await fetchMail(user, fetcher, { ...query, limit: 1 });
  return page.total;
}

async function mailApiFetch<T>(
  user: SagantaUser,
  fetcher: typeof fetch,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const base = env.MAIL_API_BASE_URL;
  if (!base) throw new Error('MAIL_API_BASE_URL fehlt');
  const res = await fetcher(`${base.replace(/\/$/, '')}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${mailToken(user)}`,
      Accept: 'application/json',
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`mail-api ${res.status}: ${body.slice(0, 200)}`);
  }
  return (await res.json()) as T;
}

export function getMailBody(user: SagantaUser, fetcher: typeof fetch, id: number): Promise<MailBody> {
  return mailApiFetch<MailBody>(user, fetcher, `/api/mail/messages/${id}/body`);
}

export function setMailState(
  user: SagantaUser,
  fetcher: typeof fetch,
  id: number,
  state: { is_read?: boolean; is_starred?: boolean },
): Promise<MailMessage> {
  return mailApiFetch<MailMessage>(user, fetcher, `/api/mail/messages/${id}/state`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(state),
  });
}

export function fetchMailAccounts(
  user: SagantaUser,
  fetcher: typeof fetch,
): Promise<MailAccountInfo[]> {
  return mailApiFetch<MailAccountInfo[]>(user, fetcher, '/api/mail/accounts');
}

export interface SendMailInput {
  account_id: number;
  to: string[];
  subject: string;
  body: string;
  cc?: string[];
  /** Message-ID des Originals. Macht aus der Nachricht eine Antwort im selben Faden. */
  in_reply_to?: string | null;
}

export function sendMail(
  user: SagantaUser,
  fetcher: typeof fetch,
  input: SendMailInput,
): Promise<{ sent: boolean }> {
  return mailApiFetch<{ sent: boolean }>(user, fetcher, '/api/mail/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}

// Konto-Verwaltung (mail-api, pro sub isoliert), seit dem Post←Mail-Merge direkt
// aus Post nutzbar (die alte, unrouted apps/mail-App ist damit ersetzt).
export interface MailAccount {
  id: number;
  email: string;
  provider: string;
  display_name: string | null;
  /** `passwort` oder `oauth2`. Bei OAuth2 liegt hier kein Passwort. */
  auth_typ?: string;
  imap_host: string;
  imap_port: number;
  smtp_host: string;
  smtp_port: number;
  enabled: boolean;
  last_sync_at: string | null;
  last_error: string | null;
  created_at: string;
}

export interface MailProviderPreset {
  key: string;
  imap_host: string;
  imap_port: number;
  smtp_host: string;
  smtp_port: number;
  note: string | null;
}

export function listMailAccounts(user: SagantaUser, fetcher: typeof fetch): Promise<MailAccount[]> {
  return mailApiFetch<MailAccount[]>(user, fetcher, '/api/mail/accounts');
}

export function listMailProviders(
  user: SagantaUser,
  fetcher: typeof fetch,
): Promise<MailProviderPreset[]> {
  return mailApiFetch<MailProviderPreset[]>(user, fetcher, '/api/mail/providers');
}

/** OAuth2-Anbieter, fuer die eine Konfiguration hinterlegt ist. Ohne Eintrag leer. */
export interface OAuthAnbieter {
  schluessel: string;
  name: string;
}

export function listOAuthAnbieter(
  user: SagantaUser,
  fetcher: typeof fetch,
): Promise<OAuthAnbieter[]> {
  return mailApiFetch<OAuthAnbieter[]>(user, fetcher, '/api/mail/oauth/anbieter');
}

/** Schritt 1: die Adresse, auf die der Nutzer zum Anbieter geschickt wird. */
export function startOAuth(
  user: SagantaUser,
  fetcher: typeof fetch,
  anbieter: string,
  email = '',
): Promise<{ url: string; zustand: string }> {
  return mailApiFetch<{ url: string; zustand: string }>(user, fetcher, '/api/mail/oauth/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ anbieter, email }),
  });
}

/** Schritt 3: den zurueckgereichten Code einloesen und das Konto anlegen. */
export function abschlussOAuth(
  user: SagantaUser,
  fetcher: typeof fetch,
  zustand: string,
  code: string,
): Promise<MailAccount> {
  return mailApiFetch<MailAccount>(user, fetcher, '/api/mail/oauth/abschluss', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ zustand, code }),
  });
}

export function addMailAccount(
  user: SagantaUser,
  fetcher: typeof fetch,
  payload: Record<string, unknown>,
): Promise<MailAccount> {
  return mailApiFetch<MailAccount>(user, fetcher, '/api/mail/accounts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deleteMailAccount(
  user: SagantaUser,
  fetcher: typeof fetch,
  id: number,
): Promise<void> {
  // mail-api antwortet auf DELETE mit 204 (kein Body) → nicht als JSON parsen.
  const base = env.MAIL_API_BASE_URL;
  if (!base) throw new Error('MAIL_API_BASE_URL fehlt');
  const res = await fetcher(`${base.replace(/\/$/, '')}/api/mail/accounts/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${mailToken(user)}`, Accept: 'application/json' },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`mail-api ${res.status}: ${body.slice(0, 200)}`);
  }
}

export function syncMailAccount(
  user: SagantaUser,
  fetcher: typeof fetch,
  id: number,
): Promise<MailAccount> {
  return mailApiFetch<MailAccount>(user, fetcher, `/api/mail/accounts/${id}/sync`, {
    method: 'POST',
  });
}

export function setMailAccountEnabled(
  user: SagantaUser,
  fetcher: typeof fetch,
  id: number,
  enabled: boolean,
): Promise<MailAccount> {
  return mailApiFetch<MailAccount>(user, fetcher, `/api/mail/accounts/${id}/enabled`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
}

// ---------------------------------------------------------------------------
// briefkasten (interne API)
// ---------------------------------------------------------------------------
export interface LetterTag {
  id: number;
  name: string;
  color: string | null;
}

export interface Letter {
  id: number;
  title: string | null;
  sender: string | null;
  category: string | null;
  received_date: string | null;
  created_at: string | null;
  summary: string | null;
  is_archived: boolean;
  /** Anzahl angehaengter Scans. Die Liste zeigt damit, ob es etwas zu oeffnen gibt. */
  file_count?: number;
  tags?: LetterTag[];
  /** Wiedervorlage: bis dahin aus der Liste genommen. */
  snoozed_until?: string | null;
}

interface LetterQuery {
  limit: number;
  offset?: number;
  category?: string;
  /** Volltext ueber Titel, Absender, OCR-Text, Notizen und Zusammenfassung. */
  suche?: string;
}

async function fetchLetters(fetcher: typeof fetch, query: LetterQuery): Promise<Letter[]> {
  const base = env.BRIEFKASTEN_BASE_URL;
  const token = env.BRIEFKASTEN_INTERNAL_TOKEN;
  if (!base || !token) return [];
  // briefkasten lehnt limit>200 mit 422 ab → defensiv clampen.
  const limit = Math.min(query.limit, MAX_LIMIT);
  const params = new URLSearchParams({ limit: String(limit), is_archived: 'false' });
  if (query.offset) params.set('skip', String(query.offset));
  if (query.category) params.set('category', query.category);
  // ★ `search` geht an den Briefkasten und damit ueber den OCR-Volltext. Das ist
  // der Unterschied zwischen "findet den Brief, in dem die Vertragsnummer steht"
  // und "findet nur, was gerade auf dem Bildschirm liegt".
  if (query.suche) params.set('search', query.suche);
  const res = await fetcher(`${base.replace(/\/$/, '')}/api/internal/letters?${params}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`briefkasten ${res.status}`);
  return (await res.json()) as Letter[];
}

export interface LetterStats {
  total: number;
  active: number;
  archived: number;
  pending_ocr: number;
}

/** Gesamtzahlen des Briefkastens, unabhaengig von der gerade geladenen Seite. */
async function fetchLetterStats(fetcher: typeof fetch): Promise<LetterStats | null> {
  const base = env.BRIEFKASTEN_BASE_URL;
  const token = env.BRIEFKASTEN_INTERNAL_TOKEN;
  if (!base || !token) return null;
  const res = await fetcher(`${base.replace(/\/$/, '')}/api/internal/stats`, {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`briefkasten stats ${res.status}`);
  return (await res.json()) as LetterStats;
}

export interface LetterFile {
  id: number;
  filename: string;
  original_filename: string | null;
  content_type: string | null;
  file_size: number | null;
  page_number: number | null;
}

export interface LetterDetail extends Letter {
  letter_date: string | null;
  ocr_text: string | null;
  notes: string | null;
  tags: { id: number; name: string; color: string | null }[];
  files: LetterFile[];
}

async function briefkastenFetch(path: string, fetcher: typeof fetch, init: RequestInit = {}): Promise<Response> {
  const base = env.BRIEFKASTEN_BASE_URL;
  const token = env.BRIEFKASTEN_INTERNAL_TOKEN;
  if (!base || !token) throw new Error('briefkasten nicht konfiguriert');
  const res = await fetcher(`${base.replace(/\/$/, '')}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`briefkasten ${res.status}: ${body.slice(0, 200)}`);
  }
  return res;
}

export async function getLetterDetail(fetcher: typeof fetch, id: number): Promise<LetterDetail> {
  const res = await briefkastenFetch(`/api/internal/letters/${id}`, fetcher);
  return (await res.json()) as LetterDetail;
}

export async function archiveLetter(fetcher: typeof fetch, id: number, archived = true): Promise<LetterDetail> {
  const res = await briefkastenFetch(`/api/internal/letters/${id}`, fetcher, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_archived: archived }),
  });
  return (await res.json()) as LetterDetail;
}

/**
 * Wiedervorlage: den Brief bis zu einem Zeitpunkt aus der Liste nehmen.
 *
 * Der Briefkasten kann das seit jeher (`snoozed_until`), Post bot es nicht an.
 * Fuer einen Brief, der erst naechsten Monat dran ist, gab es damit nur zwei
 * Antworten: stehen lassen oder archivieren. Archivieren heisst hier "erledigt",
 * und was archiviert ist, faellt aus der Ansicht, auch wenn es noch zu tun ist.
 */
export async function snoozeLetter(
  fetcher: typeof fetch,
  id: number,
  bis: string | null,
): Promise<LetterDetail> {
  const res = await briefkastenFetch(`/api/internal/letters/${id}`, fetcher, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ snoozed_until: bis }),
  });
  return (await res.json()) as LetterDetail;
}

// Datei-Streams laufen als Proxy über den BFF (briefkasten ist nur intern erreichbar).
// range wird durchgereicht: briefkasten (Starlette FileResponse) beantwortet Range
// nativ mit 206 → Inline-PDF-Viewer/Seek funktionieren im Browser.
export function fetchLetterFile(
  fetcher: typeof fetch,
  letterId: number,
  fileId: number,
  range?: string,
): Promise<Response> {
  return briefkastenFetch(
    `/api/internal/letters/${letterId}/files/${fileId}`,
    fetcher,
    range ? { headers: { Range: range } } : {},
  );
}

// ---------------------------------------------------------------------------
// briefkasten Vertraege/Abos (interne API)
// ---------------------------------------------------------------------------
export interface Contract {
  id: number;
  name: string;
  kind: string | null;
  monthly_amount: number | null;
  end_date: string | null;
  notice_deadline: string | null;
  days_until_notice: number | null;
}

async function fetchContracts(fetcher: typeof fetch): Promise<Contract[]> {
  const base = env.BRIEFKASTEN_BASE_URL;
  const token = env.BRIEFKASTEN_INTERNAL_TOKEN;
  if (!base || !token) return [];
  const res = await fetcher(`${base.replace(/\/$/, '')}/api/internal/accounts?only_active=true`, {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`briefkasten accounts ${res.status}`);
  return (await res.json()) as Contract[];
}

// ---------------------------------------------------------------------------
// Zusammengefuehrter Feed
// ---------------------------------------------------------------------------
export type Source = 'mail' | 'letter';

export interface FeedItem {
  source: Source;
  id: string;
  rawId: number;
  title: string;
  from: string;
  /**
   * Kurzvorschau. Bei Briefen die LLM-Zusammenfassung.
   *
   * ⚠️ Bei Mails immer leer, und zwar strukturell: `mail-api` legt bewusst keinen
   * Nachrichtentext ab (`sync.py` setzt `snippet=None`). Die Oberflaeche darf
   * hier also keine Zeile freihalten, die nie gefuellt wird.
   */
  preview: string;
  date: string | null;
  unread: boolean;
  starred: boolean;
  category: string | null;
  /** Nur Briefe: Anzahl angehaengter Scans. */
  fileCount?: number;
  /** Nur Briefe: vergebene Schlagworte. */
  tags?: LetterTag[];
}

function ts(d: string | null): number {
  if (!d) return 0;
  const t = Date.parse(d);
  return Number.isNaN(t) ? 0 : t;
}

export interface FeedOptions {
  source: 'all' | 'mail' | 'letter';
  unreadOnly: boolean;
  /** Nur markierte Nachrichten. Kennt wie `unreadOnly` nur die Mail-Seite. */
  starredOnly: boolean;
  accountId?: number;
  category?: string;
  /** Suchbegriff. Geht an BEIDE Quellen, nicht an den geladenen Ausschnitt. */
  suche?: string;
  limit: number;
  /** Beginn der Seite. Wird an beide Quellen gereicht. */
  offset: number;
}

export interface FeedResult {
  items: FeedItem[];
  contracts: Contract[];
  accounts: MailAccountInfo[];
  categories: string[];
  failures: { mail?: string; letters?: string; contracts?: string; accounts?: string };
  /**
   * Bestandszahlen, nicht Seitengroessen und nicht Trefferzahlen.
   *
   * Alle drei meinen den **ganzen Bestand** und ignorieren Suche, Ungelesen-,
   * Markiert- und Kategorie-Filter; nur ein gewaehltes Konto engt sie ein. Die
   * Kopfzeile beschreibt damit das Postfach ("47 Briefe · 1203 Mails"), nicht
   * das gerade sichtbare Ergebnis, das ohnehin in der Liste darunter steht.
   *
   * ★ Sie muessen **dieselbe** Frage beantworten, sonst wird das Nebeneinander
   * zur Falle: zwei Zahlen in einer Zeile liest man als Paar. Bis 2026-09-14 war
   * es die Laenge der geladenen Seite, danach eine gefilterte Mail-Zahl neben
   * einer ungefilterten Brief-Zahl.
   */
  counts: { mail: number; letters: number; mailUnread: number };
  hasMore: boolean;
  options: FeedOptions;
  /** Darf dieser Nutzer die single-tenant Briefkasten-Daten sehen? Steuert Feed + UI. */
  canSeeLetters: boolean;
}

export async function loadFeed(
  user: SagantaUser,
  fetcher: typeof fetch,
  options: FeedOptions,
  canSeeLetters: boolean,
): Promise<FeedResult> {
  const failures: FeedResult['failures'] = {};
  // "Nur ungelesen" und "nur markiert" kennen nur die Mail-Seite (Briefe haben
  // weder read- noch star-Konzept) → Quelle in dem Fall effektiv auf Mail einengen.
  const nurMailFilter = options.unreadOnly || options.starredOnly;
  const wantMail = options.source !== 'letter';
  // Briefe/Verträge (briefkasten, single-tenant) nur für Berechtigte laden.
  // Fail-safe: für Nicht-Owner werden sie serverseitig gar nicht erst geholt.
  const wantLetters =
    canSeeLetters &&
    (options.source === 'letter' || (options.source === 'all' && !nurMailFilter));

  const mailFilter = {
    unread: options.unreadOnly,
    starred: options.starredOnly,
    accountId: options.accountId,
    suche: options.suche,
  };

  const [mailRes, letterRes, contractRes, accountRes, unreadRes, statsRes, gesamtRes] =
    await Promise.allSettled([
      wantMail
        ? fetchMail(user, fetcher, { ...mailFilter, limit: options.limit, offset: options.offset })
        : Promise.resolve<MailPage>({ items: [], total: 0 }),
      wantLetters
        ? fetchLetters(fetcher, {
            limit: options.limit,
            offset: options.offset,
            category: options.category,
            suche: options.suche,
          })
        : Promise.resolve<Letter[]>([]),
      canSeeLetters ? fetchContracts(fetcher) : Promise.resolve<Contract[]>([]),
      fetchMailAccounts(user, fetcher),
      // Der Ungelesen-Zaehler am Reiter meint immer den ganzen Bestand, auch wenn
      // gerade nach etwas anderem gefiltert wird. Sonst zeigte er "0", sobald
      // eine Suche offen war.
      zaehleMail(user, fetcher, { accountId: options.accountId, unread: true }),
      canSeeLetters ? fetchLetterStats(fetcher) : Promise.resolve<LetterStats | null>(null),
      // Dasselbe fuer die Gesamtzahl. Sie stand vorher auf `mailPage.total`, also
      // auf der Trefferzahl der aktiven Filter, waehrend die Brief-Zahl daneben
      // den ganzen Bestand meinte. In der Kopfzeile las sich das als ein Paar
      // vergleichbarer Zahlen, war aber keins: eine Suche machte aus
      // "47 Briefe · 1203 Mails" ein "47 Briefe · 3 Mails", und auf dem
      // Brief-Reiter stand "0 Mails", weil dort gar keine geladen werden.
      zaehleMail(user, fetcher, { accountId: options.accountId }),
    ]);

  const mailPage = mailRes.status === 'fulfilled' ? mailRes.value : { items: [], total: 0 };
  if (mailRes.status === 'rejected') failures.mail = String(mailRes.reason);
  const mail = mailPage.items;
  const letters = letterRes.status === 'fulfilled' ? letterRes.value : [];
  if (letterRes.status === 'rejected') failures.letters = String(letterRes.reason);
  const contracts = contractRes.status === 'fulfilled' ? contractRes.value : [];
  if (contractRes.status === 'rejected') failures.contracts = String(contractRes.reason);
  const accounts = accountRes.status === 'fulfilled' ? accountRes.value : [];
  if (accountRes.status === 'rejected') failures.accounts = String(accountRes.reason);
  const mailUnread = unreadRes.status === 'fulfilled' ? unreadRes.value : 0;
  const stats = statsRes.status === 'fulfilled' ? statsRes.value : null;
  const mailGesamt = gesamtRes.status === 'fulfilled' ? gesamtRes.value : mailPage.total;

  const items: FeedItem[] = [
    ...mail.map((m): FeedItem => ({
      source: 'mail',
      id: `mail-${m.id}`,
      rawId: m.id,
      title: m.subject || '(ohne Betreff)',
      from: m.from_name || m.from_addr,
      preview: m.snippet ?? '',
      date: m.date,
      unread: !m.is_read,
      starred: m.is_starred === true,
      category: m.account_email,
    })),
    ...letters.map((l): FeedItem => ({
      source: 'letter',
      id: `letter-${l.id}`,
      rawId: l.id,
      title: l.title || '(ohne Titel)',
      from: l.sender || 'Unbekannt',
      preview: l.summary ?? '',
      date: l.received_date || l.created_at,
      unread: false,
      starred: false,
      category: l.category,
      fileCount: l.file_count,
      tags: l.tags,
    })),
  ].sort((a, b) => ts(b.date) - ts(a.date));

  // Brief-Kategorien für die Filter-Chips.
  //
  // ★ Der aktive Filter ist IMMER dabei, auch wenn die geladene Seite ihn nicht
  // belegt. Vorher verschwand die Schaltflaeche, sobald die Seite leer war, und
  // der Filter blieb trotzdem gesetzt: eine Liste ohne Treffer und nichts, woran
  // man sah, warum. Dasselbe beim Blaettern in eine Seite ohne diese Kategorie.
  const categories = [
    ...new Set(
      [...letters.map((l) => l.category), options.category].filter((c): c is string => !!c),
    ),
  ].sort((a, b) => a.localeCompare(b, 'de'));

  // Eine weitere Seite gibt es, wenn eine der beiden Quellen ueber das Ende der
  // aktuellen hinausreicht. Bei Mail ist das exakt (`total`), beim Briefkasten
  // ueber die Fuellung der Seite geschaetzt: er liefert keine Gesamtzahl je Filter.
  //
  // ⚠️ In der gemischten Ansicht blaettert jede Quelle fuer sich. Eine Seite
  // enthaelt also die n-ten Mails UND die n-ten Briefe, nach Datum gemischt.
  // Kein Eintrag faellt dabei aus oder doppelt sich; nur die Datumsfolge gilt
  // innerhalb einer Seite, nicht ueber Seitengrenzen hinweg.
  const hasMore =
    (wantMail && mailPage.total > options.offset + mail.length) ||
    (wantLetters && letters.length >= options.limit);

  return {
    items,
    contracts,
    accounts,
    categories,
    failures,
    counts: {
      mail: mailGesamt,
      letters: stats ? stats.active : letters.length,
      mailUnread,
    },
    hasMore,
    options,
    canSeeLetters,
  };
}
