import * as client from 'openid-client';
import type { AuthConfig } from './config.js';
import type { SagantaUser, SessionRecord } from './types.js';

let cachedConfig: client.Configuration | null = null;
let cachedIssuerUrl: string | null = null;

export async function getOidcConfig(cfg: AuthConfig): Promise<client.Configuration> {
  if (cachedConfig && cachedIssuerUrl === cfg.issuer) return cachedConfig;
  // Authelia-Clients sind als `client_secret_basic` registriert (HTTP Basic Auth
  // am Token-Endpoint). openid-client v6 Default wäre `client_secret_post`, das
  // Authelia mit `invalid_client` ablehnt.
  cachedConfig = await client.discovery(
    new URL(cfg.issuer),
    cfg.clientId,
    cfg.clientSecret,
    client.ClientSecretBasic(cfg.clientSecret),
  );
  cachedIssuerUrl = cfg.issuer;
  return cachedConfig;
}

export interface AuthRequest {
  url: URL;
  state: string;
  nonce: string;
  codeVerifier: string;
}

export async function buildAuthRequest(cfg: AuthConfig): Promise<AuthRequest> {
  const oidc = await getOidcConfig(cfg);
  const codeVerifier = client.randomPKCECodeVerifier();
  const codeChallenge = await client.calculatePKCECodeChallenge(codeVerifier);
  const state = client.randomState();
  const nonce = client.randomNonce();

  const url = client.buildAuthorizationUrl(oidc, {
    redirect_uri: cfg.redirectUri,
    scope: (cfg.scopes ?? ['openid', 'profile', 'email', 'groups']).join(' '),
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
    state,
    nonce,
  });

  return { url, state, nonce, codeVerifier };
}

export async function completeAuth(
  cfg: AuthConfig,
  currentUrl: URL,
  expectedState: string,
  expectedNonce: string,
  codeVerifier: string,
): Promise<SessionRecord> {
  const oidc = await getOidcConfig(cfg);
  const tokens = await client.authorizationCodeGrant(oidc, currentUrl, {
    pkceCodeVerifier: codeVerifier,
    expectedState,
    expectedNonce,
  });

  const claims = tokens.claims();
  if (!claims) throw new Error('OIDC response had no ID-Token claims.');
  if (!tokens.access_token || !tokens.id_token) {
    throw new Error('OIDC response missing access or id token.');
  }

  const user: SagantaUser = {
    sub: String(claims.sub),
    email: String(claims.email ?? ''),
    name: typeof claims.name === 'string' ? claims.name : undefined,
    groups: Array.isArray(claims.groups) ? claims.groups.map(String) : [],
  };

  const now = Math.floor(Date.now() / 1000);
  const expiresIn = typeof tokens.expires_in === 'number' ? tokens.expires_in : 3600;
  const record: SessionRecord = {
    user,
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    idToken: tokens.id_token,
    expiresAt: now + expiresIn,
    createdAt: now,
  };
  return record;
}

export async function refreshSession(
  cfg: AuthConfig,
  refreshToken: string,
): Promise<SessionRecord> {
  const oidc = await getOidcConfig(cfg);
  const tokens = await client.refreshTokenGrant(oidc, refreshToken);
  const claims = tokens.claims();
  if (!claims || !tokens.access_token || !tokens.id_token) {
    throw new Error('Refresh failed: incomplete token response.');
  }
  const user: SagantaUser = {
    sub: String(claims.sub),
    email: String(claims.email ?? ''),
    name: typeof claims.name === 'string' ? claims.name : undefined,
    groups: Array.isArray(claims.groups) ? claims.groups.map(String) : [],
  };
  const now = Math.floor(Date.now() / 1000);
  const expiresIn = typeof tokens.expires_in === 'number' ? tokens.expires_in : 3600;
  return {
    user,
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token ?? refreshToken,
    idToken: tokens.id_token,
    expiresAt: now + expiresIn,
    createdAt: now,
  };
}

export async function endSessionUrl(cfg: AuthConfig, idToken: string): Promise<URL | null> {
  const oidc = await getOidcConfig(cfg);
  try {
    return client.buildEndSessionUrl(oidc, {
      id_token_hint: idToken,
      post_logout_redirect_uri: cfg.postLogoutRedirectUri ?? cfg.redirectUri,
    });
  } catch {
    return null;
  }
}

export function randomSessionId(): string {
  return client.randomState();
}
