import { createHmac, randomBytes } from 'node:crypto';
import type { SagantaUser } from './types.js';

interface JwtHeader {
  alg: 'HS256';
  typ: 'JWT';
  kid?: string;
}

interface BackendClaims {
  iss: 'saganta';
  sub: string;
  email: string;
  name?: string;
  groups: string[];
  /**
   * Tarif des Kontos. Quelle ist `user.plan` in der auth-DB, nicht eine
   * App-Tabelle: nur so kann jedes Backend ihn prüfen, ohne die news-api zu
   * fragen. Auswertung in `saganta_dienst/tarife.py`, dort fail-closed.
   */
  plan: string;
  aud: string;
  iat: number;
  exp: number;
  jti: string;
}

function b64url(buf: Buffer | string): string {
  return Buffer.from(buf).toString('base64url');
}

function b64urlJson(obj: unknown): string {
  return b64url(JSON.stringify(obj));
}

export interface IssueBackendTokenOptions {
  user: SagantaUser;
  secret: string;
  audience: string;
  /** Lebensdauer in Sekunden. Default: 60s. */
  ttlSeconds?: number;
  /** Optional Key-ID für Rotation. */
  kid?: string;
}

/**
 * Stellt ein HS256-signiertes Saganta-JWT für nachgelagerte Backends aus.
 * Aufrufer ist ausschließlich der BFF (Server-Side). Niemals client-seitig.
 *
 * Der gleiche Secret muss in saganta-auth-proxy + Sidecars konfiguriert sein,
 * dort wird das Token validiert und gegen den Backend-spezifischen Bearer
 * (z. B. KG_INTERNAL_TOKEN) getauscht.
 */
export function issueBackendToken(opts: IssueBackendTokenOptions): string {
  const now = Math.floor(Date.now() / 1000);
  const claims: BackendClaims = {
    iss: 'saganta',
    sub: opts.user.sub,
    email: opts.user.email,
    name: opts.user.name,
    groups: opts.user.groups,
    plan: opts.user.plan === 'pro' ? 'pro' : 'free',
    aud: opts.audience,
    iat: now,
    exp: now + (opts.ttlSeconds ?? 60),
    jti: randomBytes(12).toString('hex'),
  };
  const header: JwtHeader = { alg: 'HS256', typ: 'JWT', kid: opts.kid };
  const signing = `${b64urlJson(header)}.${b64urlJson(claims)}`;
  const sig = createHmac('sha256', opts.secret).update(signing).digest('base64url');
  return `${signing}.${sig}`;
}
