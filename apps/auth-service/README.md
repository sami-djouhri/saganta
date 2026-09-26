# @saganta/auth-service

Zentraler Auth-Service der Saganta-Suite auf Basis von [better-auth](https://better-auth.com).
Ersetzt das bisherige Authelia/Zitadel-OIDC. Eigene Login-UI lebt im `shell` (Suite-Optik);
dieser Service ist die API + Session-Authority.

## Architektur

```
Browser ──cookie .saganta.de──► shell/news/kalender/assets (BFFs)
                                   │ validiert Session ──► saganta-auth (/api/auth/*)
                                   │ mintet HS256-Backend-JWT  (better-auth + Postgres)
                                   ▼
                          auth-proxy ──► FastAPI-Backends (UNVERÄNDERT)
```

Die FastAPI-Backends kennen kein OIDC, sie validieren nur das HS256-Backend-Token,
das die BFFs via `@saganta/auth` (`backend-token.ts`) ausstellen. Daher berührt der
Auth-Wechsel nur die BFF-/`packages/auth`-Schicht.

## Phasen

1. **(jetzt)** Email/Passwort + Session, Cross-Subdomain-Cookie.
2. `packages/auth` auf better-auth-Session umstellen + Login-UI im shell.
3. 2FA (TOTP) + Passkeys (WebAuthn): better-auth-Plugins.
4. Self-Service-Signup / Passwort-Reset / E-Mail-Verifikation + SMTP.
5. Organizations / Multi-Tenant.

## Entwicklung

```bash
cp .env.example .env          # Secrets setzen (AUTH_INSECURE_COOKIES=true für http-localhost)
pnpm --filter @saganta/auth-service check     # Typecheck
pnpm --filter @saganta/auth-service db:migrate # Schema in Postgres anlegen
pnpm --filter @saganta/auth-service dev        # lokal starten
```

Health: `GET /healthz` → `{"ok":true,"service":"saganta-auth"}`
Auth-API: `ALL /api/auth/*` (better-auth-Handler).

## Deployment

Container (Dockerfile), Netz `cc-core` (BFF-Zugriff) + `cc-proxy` (Edge für `auth.saganta.de`).
Eigene Postgres `saganta-auth-db`. Secrets via SOPS (`infra/secrets/vault/auth-service.env.enc`).
**Noch nicht deployt**: Phase 1 ist lokales Scaffold.
