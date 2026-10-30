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
# Die Laufzeit-Versionen werden HIER festgeschrieben, wo `pnpm install
# --frozen-lockfile` schon gelaufen ist. Damit steht in der Liste genau das,
# wogegen `tsc` eben uebersetzt hat -- also der Stand aus `pnpm-lock.yaml`, mit
# Patch-Stelle, nicht der Caret-Bereich aus package.json. Der Unterschied ist
# nicht theoretisch: `^1.6.22` holt heute better-auth 1.7.6, das Lockfile und
# der Uebersetzungslauf stehen aber auf 1.6.22. Ein Bild, dessen Code gegen die
# eine Nebenversion uebersetzt und gegen die andere ausgefuehrt wird, ist genau
# die Sorte Unterschied, die erst im Betrieb auffaellt.
RUN node -e 'const fs=require("fs"); \
  const svc="/repo/apps/auth-service"; \
  const deps=Object.keys(JSON.parse(fs.readFileSync(svc+"/package.json")).dependencies||{}); \
  if(!deps.length){console.error("keine dependencies in apps/auth-service/package.json");process.exit(1)} \
  const zeilen=deps.map(n=>{ \
    const p=svc+"/node_modules/"+n+"/package.json"; \
    if(!fs.existsSync(p)){console.error("nicht installiert: "+n);process.exit(1)} \
    return n+"@"+JSON.parse(fs.readFileSync(p)).version; \
  }); \
  fs.writeFileSync("/repo/laufzeit-deps.txt", zeilen.join("\n")+"\n"); \
  console.log(zeilen.join("\n"));'

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
#
# Die Versionen stehen hier NICHT mehr als Zahlen, sondern kommen aus der
# Bau-Stufe (`laufzeit-deps.txt`, dort erzeugt). Bis 2026-09-27 war hier
# `nodemailer@6` eingetragen, waehrend package.json und Lockfile laengst auf
# `^9.1.0` standen: der Abhaengigkeits-Fix vom 27.09. haette die Laufzeit nie
# erreicht. Ein Neubau haette sogar bestaetigt ausgesehen -- Quelle gruen,
# `tsc --noEmit` gruen, Container `healthy` -- und im Bild weiter nodemailer
# 6.10.1 installiert. Eine zweite Versionsliste neben Lockfile und package.json
# ist eine zweite Wahrheit, und die driftet lautlos in genau die Richtung,
# gegen die der Fix gedacht war. `dependencies` ist die einzige Quelle,
# `devDependencies` bleibt bewusst aussen vor (tsx/typescript gehoeren nicht in
# die Laufzeit).
#
# `--legacy-peer-deps` ist seit dem 2026-10-28 Pflicht, sonst ist dieser
# Dienst NICHT MEHR BAUBAR: npm 10.9.9 (im aktuellen node:22-slim) bricht beim
# Aufloesen der Peer-Dependencies von better-auth mit `Cannot read properties of
# null (reading 'edgesOut')` ab. Gemessen am selben Tag: `pg` allein geht durch,
# die drei zusammen nicht, und der Fehler hat mit dem Quelltext nichts zu tun --
# er trat auch auf dem unveraenderten Stand auf. ⚠️ Der laufende Container
# stammte vom 22.10. und war gesund, der Bruch lag also zwischen zwei Baulaeufen
# in einem fremden Bild. Ein Dienst, der laeuft, sagt nichts darueber, ob er sich
# noch bauen laesst -- und gemerkt haette man es erst beim naechsten Fix, der
# dringend ist.
COPY --from=build /repo/laufzeit-deps.txt /tmp/laufzeit-deps.txt
RUN printf '{"name":"saganta-auth","private":true,"type":"module"}\n' > /app/package.json \
 && echo "Laufzeit-Abhaengigkeiten (Stand des Lockfiles):" && cat /tmp/laufzeit-deps.txt \
 && npm install --omit=optional --no-audit --no-fund --legacy-peer-deps $(cat /tmp/laufzeit-deps.txt) \
 && rm -f /tmp/laufzeit-deps.txt \
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
