# Runbook – Phase 1: Auth-Angleichung der Haushalt-Backends an Saganta

Stand: 2026-07-01. Macht lager / mealprep / fitness von Authelia-Header-Auth auf das
Saganta-Backend-JWT-Muster umstellbar. **Verändert Live-Dienste → Owner-Freigabe nötig.**
Grundlage: IST_STAND_BACKENDS.md. Referenz-Implementierung: `saganta/services/mail-api/app/auth.py`.

## Ausgangslage (Ist)

lager/mealprep/fitness nutzen `AutheliaHeaderMiddleware` (Soft-Auth):

```python
class AutheliaHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.user = request.headers.get("remote-user") or ""
        groups_header = request.headers.get("remote-groups") or ""
        request.state.groups = [g.strip() for g in groups_header.split(",") if g.strip()]
        return await call_next(request)
```

Keine echte Durchsetzung; Vertrauen liegt am Edge (`*.daheim.home`). Unter Saganta entfällt
dieser Edge-Trust → die Backends müssen das vom BFF gestempelte HS256-JWT selbst prüfen.

## Ziel (Soll) – Backend-JWT-Verifikation

Pro Backend ein `app/auth.py` analog mail-api:

```python
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from .config import settings

EXPECTED_AUDIENCE = "lager"  # bzw. "mealprep" / "fitness"

class Me(BaseModel):
    sub: str
    email: str = ""
    name: str | None = None
    groups: list[str] = Field(default_factory=list)

def verify_jwt(authorization: str = Header(...)) -> Me:
    # Bearer prüfen, jwt.decode(token, settings.jwt_secret,
    #   algorithms=[settings.jwt_algorithm], audience=EXPECTED_AUDIENCE)
    # iss == "saganta" erzwingen; sub vorhanden; optional allowed_subs-Owner-Gate
    ...

CurrentUser = Depends(verify_jwt)
```

Token-Eigenschaften (vom Saganta-BFF via `@saganta/auth issueBackendToken`):
- Alg HS256, `iss: "saganta"`, `aud: <service>`, `sub`, `email`, `name`, kurze TTL.
- Secret beidseitig identisch (`jwt_secret`), pro Service eigene `audience`.

## Schritte je Backend (lager, mealprep, fitness)

1. **`app/auth.py`** neu anlegen (Vorlage oben, `EXPECTED_AUDIENCE` setzen).
2. **`app/config.py`**: `jwt_secret`, `jwt_algorithm` (default HS256), optional `allowed_subs`
   aus Env lesen.
3. **`main.py`**: `AutheliaHeaderMiddleware` entfernen. Routen, die geschützt sein müssen,
   auf `Depends(verify_jwt)` umstellen (bzw. globaler Router-Dependency). `request.state.user`/
   `groups`-Nutzung im Code suchen und auf `Me.sub` umstellen.
4. **Saganta-BFF**: für jede App ein BFF in `saganta/apps/<app>` + `services/<app>-bff` oder
   Direktanbindung über `auth-proxy` (wie briefkasten/lifeops: `*_BASE_URL` + gestempelter Token).
   Audience im BFF-Aufruf muss `EXPECTED_AUDIENCE` des Backends matchen.
5. **Secret-Verteilung**: `jwt_secret` in SOPS-Vault (`infra/secrets/vault/<service>.env.enc`),
   identisch zum BFF-Secret. `--input-type/--output-type dotenv`.
6. **Compose/Netze**: Backend an `cc-core` (für BFF-Erreichbarkeit) belassen; Authelia-bezogene
   Env/Labels entfernen.
7. **Edge**: `*.daheim.home` → `*.saganta.de`/`.home` umrouten (dev-portal nginx; Single-File-
   Bind-Mount → Container-Restart nötig), AdGuard-Rewrite, ggf. cloudflared-Ingress.

## Verifikation (nach Umstellung, vor Retire)

- `curl` ohne Token → 401; mit falschem `aud`/`iss` → 401; mit gültigem BFF-Token → 200.
- BFF-Flow im Browser: Login (better-auth) → App lädt Daten.
- `docker ps` healthy; control-map-Eintrag aktualisiert.

## Reihenfolge & Risiko

- Empfohlene Erst-Migration: **fitness** (wenigste Abhängigkeiten, nur `mealprep_default`),
  dann mealprep, dann lager (hat cc-core + Assets-Kopplung).
- Rollback: alte Compose-/Middleware-Version aus git; daheim-Edge bleibt bis Cutover bestehen.
- Erst nach grüner Verifikation aller drei: daheim-Suite + Authelia-Pfade retiren.
