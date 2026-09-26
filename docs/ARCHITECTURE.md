# Saganta: Architektur

```
                         ┌─────────────────────────────────────────┐
                         │       dev-portal-edge (nginx)           │
                         │   *.home.arpa → TLS-Termination      │
                         └────────┬────────────────────────────────┘
                                  │
        ┌─────────────────────────┼──────────────────────────────────────────┐
        ▼                         ▼                          ▼               ▼
   shell:3000             kalender:8085             briefkasten:8000   nachrichten:8104
   (SvelteKit BFF)        (native, FEED_TOKEN       (postfach, Session  (security:None)
        │                  Auto-Login)               Token-Bridge)
        │  HS256-JWT (60 s, aud=lifeops/kalender/briefkasten/shell-api)
        ▼
  saganta-auth-proxy                                  saganta-shell-api
  /lifeops/*    → life-ops-api      (offen)            /api/me, /api/apps,
  /kalender/*   → kalender:8085     (KG_INTERNAL_TOKEN) /api/settings
  /briefkasten/* → briefkasten:8000 (Bearer postfach)   (validiert JWT direkt,
                                                         aud=shell-api)

       Authelia (host:9091)
       ├─ OIDC Authorization-Code + PKCE
       ├─ Cookie: __Secure-saganta_session (Domain=.home.arpa → SSO)
       └─ ID-/Refresh-Token niemals im Browser
```

## Schichten

1. **Edge (dev-portal nginx)**: TLS, HSTS, Frame-Options. Routet pro Subdomain entweder an die Shell-BFF oder direkt an einen nativen Backend-Container. Für `mail` und `calendar` Token-Bridge-Rewrite vor `proxy_pass`.
2. **Shell-BFF (SvelteKit, Node-Adapter)**: einziger SvelteKit-Container. Hält Session-Cookie, prüft sie in `hooks.server.ts`, lädt Daten serverseitig und rendert SSR. Keine Backend-Token im Browser.
3. **Auth-Proxy**: validiert die Saganta-JWTs der BFFs, stempelt Backend-Tokens (Kalender/Briefkasten/LifeOps) ein. Backends bleiben unverändert. Externe Konsumenten (knowledge-gateway, shell-api/stats) gehen weiter über die Mounts.
4. **Backends**: bestehende Homelab-Container, eingebunden via `cc-core`-Netz.

## Native Apps mit Auto-Login

Subdomains, die direkt auf native Container routen, bekommen im dev-portal eine Bridge:

- **calendar**: nginx setzt `FEED_TOKEN` als Query/Cookie, kalender liest und legt seine Session an.
- **mail**: nginx rewriteet die erste Anfrage auf `/api/auth/token-login?token=$SAGANTA_SESSION_TOKEN&redirect=/`. `routes_auth.py` in postfach validiert das env-Token, legt die Session für `SAGANTA_SESSION_USER` an.
- **nachrichten**: keine Bridge nötig, App ist offen.

Token bleiben server-side im nginx-Block (`set $TOKEN "…"`), der Browser sieht nur Cookies der nativen App. Pattern und Stolperfallen: siehe Memory `project_saganta`.

## Trust-Modell

- Browser ↔ BFF/native: Cookie-basiert (`__Secure-saganta_session` für Shell, App-eigene Cookies für native Apps). Same-Origin Origin-Check zusätzlich zur SvelteKit-CSRF.
- BFF ↔ Auth-Proxy/Backends: kurzlebiges HS256-JWT (TTL 60 s, audience-bound). Shared Secret zwischen Shell und Auth-Proxy/shell-api.
- Auth-Proxy ↔ Backends: bestehende Backend-Tokens.
- Authelia ↔ BFF: Code-Flow + PKCE. Refresh-Token im Server-Session-Store.

## Netzwerke

| Netz       | Mitglieder                                        | Zweck                       |
|------------|---------------------------------------------------|-----------------------------|
| `cc-proxy` | edge, shell, shell-api                            | Ingress-Traffic             |
| `cc-core`  | shell, shell-api, auth-proxy, kalender, briefkasten, life-ops-api | BFF↔Auth-Proxy↔Backend |

`cc-apps` ist für Apps mit eigener DB reserviert, `cc-mgmt` für Observability (siehe Homelab-NETWORK_ZONES).

## Erweiterung um weitere Apps

Zwei Pfade: Wahl hängt davon ab, ob die App schon nativ läuft:

**Neue SvelteKit-App in Saganta**
1. Workspace anlegen: `apps/<name>/` (SvelteKit + adapter-node).
2. SDK in `packages/sdk-<backend>/`.
3. Eintrag in `services/shell-api/app/registry.py` (DEFAULT_APPS).
4. Route im dev-portal-Edge (Subdomain → Container).
5. OIDC-Client + Auth-Proxy-Mount falls neue Audience.

**Edge-Bridge auf nativen Container**
1. Eintrag in `services/shell-api/app/registry.py` + `apps/shell/src/lib/apps.ts` (Fallback).
2. Server-Block im dev-portal-Edge mit `set $TOKEN "…"` + Rewrite auf die App-eigene Token-Login-Route.
3. Kein eigener Authelia-Client nötig, da Native-App eigene Auth nutzt.

Das Pattern bleibt identisch, keine ad-hoc-Auth-Implementierung pro App.
