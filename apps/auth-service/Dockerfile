FROM node:22-slim AS base
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH
RUN corepack enable && corepack prepare pnpm@10.33.2 --activate

FROM base AS deps
WORKDIR /repo
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml* ./
COPY apps/auth-service/package.json apps/auth-service/package.json
COPY packages packages
RUN pnpm install --frozen-lockfile || pnpm install

FROM deps AS build
WORKDIR /repo
COPY apps/auth-service apps/auth-service
RUN pnpm --filter @saganta/auth-service build

FROM node:22-slim AS runner
# Sicherheitsstand des Basis-Image nachziehen. Ein Upstream-Image friert die Paketstaende
# vom Tag seines Baus ein, Debian-security ist regelmaessig weiter, und ein `--pull` holt
# nur ein neueres Bild derselben Verspaetung: gemessen am 2026-09-13 trug das aktuelle
# python:3.13-slim aus der Registry dieselben drei perl-CVEs wie das monatealte lokale.
# `upgrade`, nicht `dist-upgrade`: letzteres darf Pakete entfernen, um Konflikte zu loesen.
RUN apt-get update \
 && apt-get -y upgrade \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -u 10001 -m -d /home/appuser appuser
WORKDIR /app
COPY --from=build /repo/apps/auth-service/dist /app/dist
# Lesbarkeit für den non-root appuser erzwingen: tsc kann Output-Dateien mit
# restriktivem Mode (660) erzeugen (Quelle-ACL/umask) → sonst EACCES beim Import
# einzelner Module (z. B. email.js). a+rX macht dist deterministisch lesbar.
RUN chmod -R a+rX /app/dist
# Self-contained Runtime-Deps: pnpm-Workspaces legen die Service-Deps in
# apps/auth-service/node_modules (nicht Root) → /repo/node_modules zu kopieren greift
# nicht. Die Workspace-package.json (workspace:* in devDeps) bringt npm zum Stolpern,
# darum eine minimale package.json (nur type:module für ESM) + flacher Prod-Install.
RUN printf '{"name":"saganta-auth","private":true,"type":"module"}\n' > /app/package.json \
 && npm install --omit=optional --no-audit --no-fund better-auth@1.6.22 pg@8 nodemailer@6 \
 && npm cache clean --force \
 && rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx
# Das npm-Entfernen haengt bewusst an DIESEM RUN und steht nicht davor: der
# Prod-Install oben braucht npm noch. Danach nicht mehr -- gestartet wird mit
# `node dist/server.js`. Das mitgelieferte npm schleppt CVE-2026-59873 (node-tar)
# mit, und KEIN node-Basisimage liefert die Fix-Version 7.5.19 (gemessen
# 2026-08-22: 22-slim 7.5.11, 24-slim 7.5.16) -- ein Basis-Bump behebt das nicht.
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
USER appuser
EXPOSE 3000
CMD ["node", "dist/server.js"]
