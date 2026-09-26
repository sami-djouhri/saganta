# Saganta: Auth

## Identity

Authelia (host:9091) ist der einzige Identity-Provider. Saganta hat **keinen eigenen User-Speicher**, alles über Authelia-Users/-Gruppen.

## Flow (Authorization Code + PKCE)

1. Browser → `https://shell.home.arpa/`
2. `hooks.server.ts` (`createAuthHandle` aus `@saganta/auth`) prüft Cookie `__Host-saganta_session`.
3. Cookie fehlt → 303 zu `/auth/login?next=/`. Dort wird ein PKCE-Code-Verifier erzeugt, State & Nonce in den `PendingStore` (in-memory Phase 1, später Redis), Redirect zu Authelia `/api/oidc/authorization`.
4. Authelia callback → `/auth/callback?code=…&state=…`. BFF tauscht Code gegen Tokens (PKCE), validiert `state`/`nonce`, holt ID-Token-Claims.
5. BFF erzeugt eine Session-ID, legt den `SessionRecord` (ID-/Access-/Refresh-Token + User) im `SessionStore` ab und setzt das Cookie.

Cookie-Attribute:

```
__Host-saganta_session=<sid>; Max-Age=28800; Path=/; HttpOnly; Secure; SameSite=Lax; Domain=.home.arpa
```

`Domain=.home.arpa` ermöglicht SSO zwischen den App-Subdomains. (Der `__Host-` Präfix ist hier nur Marker, die `Domain`-Attribute-Setzung macht ihn formal RFC-incompatible, ist aber bewusst gewählt, weil der Cookie Subdomain-fähig sein muss. Wer strikt RFC will, nimmt `__Secure-` Prefix.)

## Token-Propagation zu Backends

Das OIDC-Access-Token taugt nicht für die Backends, die kennen keinen Authelia-Audience. Stattdessen:

- BFF nutzt `issueBackendToken({user, secret, audience, ttlSeconds})` aus `@saganta/auth/backend-token`.
- Output: kurzlebiges HS256-JWT (60s) mit `iss=saganta`, `sub`, `email`, `groups`, `aud`.
- BFF sendet das JWT als `Authorization: Bearer …` an `saganta-auth-proxy`.
- Auth-Proxy validiert (Signatur, Issuer, Audience, exp) und proxied an das Backend mit dem **Backend-eigenen** Bearer-Token (`KG_INTERNAL_TOKEN`, `LIFEOPS_INTERNAL_TOKEN`, …).
- Auth-Proxy hängt `X-Saganta-Sub`, `X-Saganta-Email`, `X-Saganta-Groups` als Header an (für Audit/Logging im Backend).

Der Shared-Secret zwischen BFFs und Auth-Proxy liegt im SOPS-Vault als `SAGANTA_BACKEND_SECRET`. Rotation: neuen Secret in Vault einspielen, Auth-Proxy + alle BFFs gleichzeitig neu starten.

## Cross-App-SSO

Innerhalb der SvelteKit-Shell greift das Saganta-Session-Cookie für alle Routen.

Native Apps hinter Edge-Bridge (`calendar.home.arpa`, `mail.home.arpa`) bekommen vom dev-portal-nginx im Server-Block ein server-seitiges Token mit (`FEED_TOKEN` bzw. `SAGANTA_SESSION_TOKEN`), das die App in eine eigene Session umwandelt. Das Saganta-Cookie wird dabei nicht weiterverwendet, die native App vertraut der Edge.

Logout in der Shell ruft `/auth/logout` auf, das:

1. Authelia `end_session_endpoint` triggert (falls verfügbar)
2. das Cookie domain-weit invalidiert (`Max-Age=0`)
3. zurück zur Shell-URL redirected

## Stores

Phase 1: `createMemorySessionStore` / `createMemoryPendingStore` (in-memory pro Container).

Phase 2 (sobald Multi-Replica oder Restart-Persistenz nötig wird): `createRedisSessionStore(ioredis)`; das Interface ist drop-in kompatibel.

## CSRF

SvelteKit aktiviert per Default `csrf.checkOrigin=true` (in SvelteKit 2 als `csrf.trustedOrigins`). Wir ergänzen in `hooks.server.ts` einen expliziten Origin-Check für alle non-GET/HEAD-Requests.

## Lessons Learned (2026-06-10 First Deploy)

Fünf Stolpersteine zwischen `openid-client` v6 und Authelia, die alle harte Login-Fails sind und nichts in der Standard-OIDC-Doku erwähnen. Wer Saganta erweitert oder einen weiteren Authelia-Client hinzufügt, sollte alle fünf direkt von Anfang an setzen.

1. **Authelia `session.cookies[]` braucht einen Eintrag mit `domain: home.arpa`** und `authelia_url: https://auth.home.arpa/authelia/`. Sonst setzt Authelia auf der Login-Seite keinen Session-Cookie auf der `home.arpa`-Domain → der OIDC-Authorization-Endpoint sieht den User als anonym → `server_error: Could not obtain the user session`.
2. **`client_secret_basic` ist Pflicht in der Client-Definition** (`token_endpoint_auth_method: client_secret_basic`). `openid-client` v6 Default wäre `client_secret_post`, das Authelia mit `invalid_client` ablehnt. Symmetrisch im Client: `client.discovery(..., client.ClientSecretBasic(secret))` in `packages/auth/src/oidc.ts`.
3. **`consent_mode: implicit`** für eigene, vertraute Apps. Default `explicit` zeigt nach Login eine Zustimmungs-Seite, die in unserem PKCE-Setup zu Redirect-Loops geführt hat (Authelia speichert die Zustimmung nicht idempotent über mehrere Browser-Sessions).
4. **Cookie-Name-Prefix `__Secure-`, nicht `__Host-`**: Wir setzen `AUTH_COOKIE_DOMAIN=.home.arpa` für Cross-App-SSO. Das `__Host-` Prefix verbietet aber per Spec ein `Domain=`-Attribut, also dropt der Browser den Cookie still → Endlos-Redirect-Loop. `__Secure-` erlaubt Domain und erzwingt trotzdem HTTPS.
5. **Username-Matching ist case-sensitive**: User in `users_database.yml` ist `sami` (klein). Login-Formular `Sami` führt zu `user not found` ohne weiteren Hinweis im UI.

Erkennungsmuster im Code:
- `OAUTH_RESPONSE_BODY_ERROR` mit `invalid_client` → Punkt 2.
- `AuthorizationResponseError` mit `error=server_error, description=...user session` → Punkt 1.
- „Umleitungsfehler" / `ERR_TOO_MANY_REDIRECTS` im Browser → Punkt 3 oder 4 (Browser-DevTools `Set-Cookie` prüfen: fehlend = Punkt 4, vorhanden mit Consent-Loop = Punkt 3).
- `user not found` in Authelia-Log → Punkt 5.
