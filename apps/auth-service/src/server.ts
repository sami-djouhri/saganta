import { createHmac, randomBytes } from 'node:crypto';
import { createServer, type IncomingMessage } from 'node:http';
import { toNodeHandler } from 'better-auth/node';
import { auth, pool } from './auth.js';

// Audiences, für die native Apps ein Backend-JWT anfordern dürfen.
// lager/mealprep/fitness akzeptieren das gleiche HS256-Backend-JWT (aud=<app>-api,
// gleiches SAGANTA_BACKEND_SECRET) im dualen db.py-Pfad (Bearer neben X-Saganta-Sub).
const MOBILE_AUDIENCES = new Set([
  'news-api',
  'projectdeck-api',
  'assets-api',
  'kalender-bff',
  'lager-api',
  'mealprep-api',
  'fitness-api',
  // notizen-api: gleiche Kette wie projectdeck-api (HS256, iss=saganta, eigene
  // EXPECTED_AUDIENCE, allowed_subs-Gate im Backend). Ergaenzt 2026-08-28 fuer
  // die Linux-Programme (host/saganta-desktop). Ohne Eintrag antwortet der
  // Tausch mit 400 invalid_audience, und zwar BEVOR die Sitzung geprueft wird,
  // was wie ein Anmeldeproblem aussieht und keines ist.
  'notizen-api',
]);
// Fail-Fast: ohne echtes Shared-Secret kann der Mobile-Token-Stempel gefälscht
// werden → Boot abbrechen statt still unsicher laufen. (2026-06-28)
const BACKEND_SECRET = process.env.SAGANTA_BACKEND_SECRET ?? '';
if (!BACKEND_SECRET || BACKEND_SECRET === 'change-me') {
  throw new Error(
    '[saganta-auth] FATAL: SAGANTA_BACKEND_SECRET fehlt oder ist unsicherer Default.',
  );
}
const MOBILE_TOKEN_TTL = 3600; // 1h

// Zielgruppe der dienstinternen Aufrufe (Tarif setzen). Bewusst eine eigene:
// so kann ein erbeutetes Nutzer-Token diese Route nicht bedienen.
const INTERN_AUDIENCE = 'auth-service-intern';
const ERLAUBTE_TARIFE = new Set(['free', 'pro']);

function b64url(input: string): string {
  return Buffer.from(input).toString('base64url');
}

/**
 * Inline-Spiegel von packages/auth/src/backend-token.ts (issueBackendToken).
 * Bewusst dupliziert: der Auth-Service hängt nicht am @saganta/auth-Workspace-
 * Paket, und ein Dep-Graph-/Dockerfile-Umbau am zentralen IdP wäre teurer als
 * diese paar Zeilen reine node:crypto-HMAC-Logik. Secret + Format sind identisch.
 */
function issueBackendToken(
  user: { sub: string; email: string; name?: string; plan?: string },
  aud: string,
): string {
  const now = Math.floor(Date.now() / 1000);
  const header = b64url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const claims = b64url(
    JSON.stringify({
      iss: 'saganta',
      sub: user.sub,
      email: user.email,
      name: user.name,
      groups: [],
      // ★ Muss hier genauso stehen wie im BFF-Pfad. Dies ist der Weg der
      // NATIVEN Apps; fehlte der Claim nur hier, saehen genau sie ueberall
      // 'free', waehrend im Browser alles stimmt, und niemand suchte den
      // Fehler in der Auth-Kette.
      plan: user.plan === 'pro' ? 'pro' : 'free',
      aud,
      iat: now,
      exp: now + MOBILE_TOKEN_TTL,
      jti: randomBytes(12).toString('hex'),
    }),
  );
  const signing = `${header}.${claims}`;
  const sig = createHmac('sha256', BACKEND_SECRET).update(signing).digest('base64url');
  return `${signing}.${sig}`;
}

/**
 * Prüft ein dienstinternes HS256-Token (Gegenrichtung zu issueBackendToken).
 *
 * Der Tarif gehört zum Konto, also gehört er in diese Datenbank. Geschrieben
 * wird er aber woanders ausgelöst: der Stripe-Webhook landet bei der news-api,
 * weil dort das Briefing-Produkt und der Stripe-Schlüssel liegen. Statt der
 * news-api einen zweiten Datenbankzugang zu geben, ruft sie hier an.
 *
 * Kein neues Geheimnis: news-api und dieser Dienst teilen bereits
 * SAGANTA_BACKEND_SECRET (dasselbe, mit dem hier Backend-Tokens gestempelt und
 * dort geprüft werden). Die eigene `aud` trennt die Richtungen sauber: ein
 * Nutzer-Token für 'news-api' taugt hier nicht, und dieses taugt bei keinem
 * Backend.
 */
function pruefeInternesToken(authorization: string | undefined): Record<string, unknown> | null {
  if (!authorization?.startsWith('Bearer ')) return null;
  const teile = authorization.slice(7).trim().split('.');
  if (teile.length !== 3) return null;
  const [kopf, last, sig] = teile as [string, string, string];
  const erwartet = createHmac('sha256', BACKEND_SECRET)
    .update(`${kopf}.${last}`)
    .digest('base64url');
  // Längengleicher Vergleich vor timingSafeEqual: unterschiedliche Längen
  // würden dort werfen statt abzulehnen.
  if (sig.length !== erwartet.length) return null;
  let gleich = 0;
  for (let i = 0; i < sig.length; i++) gleich |= sig.charCodeAt(i) ^ erwartet.charCodeAt(i);
  if (gleich !== 0) return null;
  try {
    const c = JSON.parse(Buffer.from(last, 'base64url').toString()) as Record<string, unknown>;
    if (c.iss !== 'saganta') return null;
    if (c.aud !== INTERN_AUDIENCE) return null;
    if (typeof c.exp !== 'number' || c.exp < Math.floor(Date.now() / 1000)) return null;
    return c;
  } catch {
    return null;
  }
}

function leseRumpf(req: IncomingMessage): Promise<string> {
  return new Promise((fertig, fehler) => {
    let daten = '';
    req.on('data', (stueck) => {
      daten += stueck;
      // Ein interner Aufruf mit drei Feldern braucht keine 8 KB.
      if (daten.length > 8192) fehler(new Error('Rumpf zu gross'));
    });
    req.on('end', () => fertig(daten));
    req.on('error', fehler);
  });
}

// node http req.headers (Record) → Web Headers für auth.api.getSession.
function toWebHeaders(req: IncomingMessage): Headers {
  const h = new Headers();
  for (const [k, v] of Object.entries(req.headers)) {
    if (Array.isArray(v)) v.forEach((x) => h.append(k, x));
    else if (typeof v === 'string') h.set(k, v);
  }
  return h;
}

// Letzte Verteidigungslinie: unerwartete Rejections loggen statt den Prozess
// stillschweigend zu beenden (idle-DB-Fehler werden bereits am Pool abgefangen).
process.on('unhandledRejection', (reason) => {
  console.error('[saganta-auth] unhandledRejection', reason);
});

const port = Number(process.env.PORT ?? 3000);
const host = process.env.HOST ?? '0.0.0.0';

const authHandler = toNodeHandler(auth);

const server = createServer((req, res) => {
  const url = req.url ?? '/';

  if (url === '/healthz' || url === '/health') {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ ok: true, service: 'saganta-auth' }));
    return;
  }

  // Mobiler Token-Tausch: gültige better-auth-Session (Cookie ODER Bearer via
  // bearer-Plugin) → kurzlebiges Saganta-Backend-JWT für eine erlaubte audience.
  // Spiegelt den BFF-internen issueBackendToken-Pfad für native Clients.
  if (url.startsWith('/api/mobile/token')) {
    const u = new URL(url, `http://${req.headers.host ?? 'localhost'}`);
    const aud = u.searchParams.get('aud') ?? '';
    if (!MOBILE_AUDIENCES.has(aud)) {
      res.writeHead(400, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ error: 'invalid_audience' }));
      return;
    }
    Promise.resolve(auth.api.getSession({ headers: toWebHeaders(req) }))
      .then((session) => {
        if (!session?.user) {
          res.writeHead(401, { 'content-type': 'application/json' });
          res.end(JSON.stringify({ error: 'unauthorized' }));
          return;
        }
        const token = issueBackendToken(
          {
            sub: session.user.id,
            email: session.user.email,
            name: session.user.name ?? undefined,
            // Fail-closed schon hier: fehlt das Feld (alte Zeile in der DB),
            // ist der Tarif 'free' und nicht 'undefined'.
            plan: (session.user as { plan?: string | null }).plan ?? 'free',
          },
          aud,
        );
        res.writeHead(200, { 'content-type': 'application/json' });
        res.end(JSON.stringify({ token, aud, expires_in: MOBILE_TOKEN_TTL }));
      })
      .catch((err: unknown) => {
        console.error('[saganta-auth] mobile token error', err);
        if (!res.headersSent) {
          res.writeHead(500, { 'content-type': 'application/json' });
          res.end(JSON.stringify({ error: 'internal' }));
        } else {
          res.end();
        }
      });
    return;
  }

  // Dienstinterner Schreibweg für den Tarif. Aufrufer ist heute der
  // Stripe-Webhook der news-api; die Wahrheit liegt aber hier, weil der Tarif
  // zum Konto gehört und nicht zum Briefing-Produkt.
  if (url === '/api/intern/tarif' && req.method === 'POST') {
    const claims = pruefeInternesToken(req.headers.authorization);
    if (!claims) {
      res.writeHead(401, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ error: 'unauthorized' }));
      return;
    }
    leseRumpf(req)
      .then(async (roh) => {
        const körper = JSON.parse(roh || '{}') as {
          sub?: string;
          plan?: string;
          status?: string | null;
        };
        const sub = körper.sub;
        const plan = körper.plan;
        if (!sub || !plan || !ERLAUBTE_TARIFE.has(plan)) {
          res.writeHead(400, { 'content-type': 'application/json' });
          res.end(JSON.stringify({ error: 'invalid_request' }));
          return;
        }
        // Direkt auf die Tabelle: better-auth bietet für ein Zusatzfeld ohne
        // Nutzersitzung keinen Weg an, und ein Admin-Plugin nur für zwei
        // Spalten wäre mehr Fläche als Nutzen.
        const ergebnis = await pool.query(
          'UPDATE "user" SET "plan" = $1, "planStatus" = $2, "updatedAt" = now() WHERE id = $3',
          [plan, körper.status ?? null, sub],
        );
        if (ergebnis.rowCount === 0) {
          res.writeHead(404, { 'content-type': 'application/json' });
          res.end(JSON.stringify({ error: 'unknown_user' }));
          return;
        }
        console.log(
          '[saganta-auth] Tarif gesetzt',
          JSON.stringify({ sub, plan, status: körper.status ?? null }),
        );
        res.writeHead(200, { 'content-type': 'application/json' });
        res.end(JSON.stringify({ ok: true, sub, plan }));
      })
      .catch((err: unknown) => {
        console.error('[saganta-auth] Tarif setzen fehlgeschlagen', err);
        if (!res.headersSent) {
          res.writeHead(500, { 'content-type': 'application/json' });
          res.end(JSON.stringify({ error: 'internal' }));
        } else {
          res.end();
        }
      });
    return;
  }

  if (url.startsWith('/api/auth')) {
    // Handler-Fehler abfangen, damit eine einzelne fehlerhafte Anfrage nicht den
    // gesamten Prozess via unhandledRejection mitreißt.
    Promise.resolve(authHandler(req, res)).catch((err: unknown) => {
      console.error('[saganta-auth] handler error', err);
      if (!res.headersSent) {
        res.writeHead(500, { 'content-type': 'application/json' });
        res.end(JSON.stringify({ error: 'internal' }));
      } else {
        res.end();
      }
    });
    return;
  }

  res.writeHead(404, { 'content-type': 'application/json' });
  res.end(JSON.stringify({ error: 'not_found' }));
});

server.listen(port, host, () => {
  // eslint-disable-next-line no-console
  console.log(`[saganta-auth] listening on http://${host}:${port}`);
});
