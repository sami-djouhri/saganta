#!/usr/bin/env bash
# Startet alle drei SvelteKit-Apps lokal über Turborepo.
# Hinweis: Auth läuft nur lokal, wenn AUTH_ISSUER auf eine erreichbare
# Authelia-Instanz zeigt. Andernfalls /auth/login → 502.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d node_modules ]; then
  pnpm install
fi

exec pnpm dev
