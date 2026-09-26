export interface AuthConfig {
  /** Authelia OIDC issuer, z. B. https://auth.home */
  issuer: string;
  clientId: string;
  clientSecret: string;
  /** Vollständige Redirect-URI für diese App, z. B. https://shell.home.arpa/auth/callback */
  redirectUri: string;
  /** Wohin nach Logout. Default: post-logout an Shell-URL. */
  postLogoutRedirectUri?: string;
  /** Scopes. Default: openid profile email groups */
  scopes?: string[];
  /** Cookie-Name. Default: __Host-saganta_session */
  cookieName?: string;
  /** Cookie-Domain für Cross-App-SSO. Default: undefined (Host-only). */
  cookieDomain?: string;
  /** Session-TTL in Sekunden. Default: 8h */
  sessionTtl?: number;
  /** Pending-State-TTL in Sekunden. Default: 10min */
  pendingTtl?: number;
}

export function loadAuthConfig(env: Record<string, string | undefined>): AuthConfig {
  const required = (key: string): string => {
    const value = env[key];
    if (!value) throw new Error(`Missing env var: ${key}`);
    return value;
  };

  return {
    issuer: required('AUTH_ISSUER'),
    clientId: required('AUTH_CLIENT_ID'),
    clientSecret: required('AUTH_CLIENT_SECRET'),
    redirectUri: required('AUTH_REDIRECT_URI'),
    postLogoutRedirectUri: env.AUTH_POST_LOGOUT_URI,
    scopes: env.AUTH_SCOPES?.split(/\s+/).filter(Boolean) ?? [
      'openid',
      'profile',
      'email',
      'groups',
    ],
    cookieName: env.AUTH_COOKIE_NAME ?? '__Host-saganta_session',
    cookieDomain: env.AUTH_COOKIE_DOMAIN,
    sessionTtl: env.AUTH_SESSION_TTL ? Number(env.AUTH_SESSION_TTL) : 8 * 60 * 60,
    pendingTtl: env.AUTH_PENDING_TTL ? Number(env.AUTH_PENDING_TTL) : 10 * 60,
  };
}
