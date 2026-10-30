# saganta-mail-api

Aggregator-Inbox: bündelt **externe** IMAP-Konten der Mitglieder, Versand über den
**Origin-SMTP** des jeweiligen Kontos. **Kein eigener Mailserver** (der liegt separat als
Mailcow auf dem netcup). Frontend: `apps/mail`.

## Architektur-Prinzip
- IMAP-**Pull**: pollt aktive Konten (`SYNC_INTERVAL_SECONDS`), cacht nur Header/Metadaten.
  Voller Body wird **live** geholt (`/messages/{id}/body`), nicht at-rest gespeichert (DSGVO).
- Versand **nur** über das Anbieter-SMTP des Nutzers → Saganta/netcup-IP versendet nie im
  Namen Fremder, kein Reputationsrisiko.
- Passwörter werden mit **Fernet** verschlüsselt abgelegt (`secret_cipher`), Key aus `FERNET_KEY`.

## Endpoints (alle `sub`-gescoped, JWT-Audience `mail-api`)
`GET /api/mail/providers` · `GET/POST/DELETE /api/mail/accounts` ·
`POST /api/mail/accounts/{id}/sync` · `GET /api/mail/messages` ·
`GET /api/mail/messages/{id}/body` · `POST /api/mail/messages/{id}/state` · `POST /api/mail/send`

## Secrets (SOPS-Vault, kanonisch auf host)
`infra/secrets/vault/mail-api.env.enc` muss auf host erzeugt werden (Laptop-Vault ist leer):

```bash
# auf host, im saganta-Repo:
cat > infra/secrets/vault/mail-api.env <<EOF
DATABASE_URL=sqlite:////data/mail.db
SYNC_INTERVAL_SECONDS=300
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
JWT_SECRET=<<identisch zum shared SAGANTA_BACKEND_SECRET / shell-api HS256-Secret>>
JWT_ALGORITHM=HS256
CORS_ORIGINS=https://shell.home.arpa,https://post.home.arpa
EOF
sops --input-type dotenv --output-type dotenv -e infra/secrets/vault/mail-api.env \
  > infra/secrets/vault/mail-api.env.enc
shred -u infra/secrets/vault/mail-api.env
```

**FERNET_KEY ist stabil zu halten**: Rotation = alle Konten neu verbinden.
**JWT_SECRET** muss exakt dem shared HS256-Secret entsprechen, mit dem `apps/mail`
(`SAGANTA_BACKEND_SECRET`) Tokens stempelt, sonst 401.

Für `apps/mail/.env` analog (`MAIL_API_BASE_URL`, `SAGANTA_BACKEND_SECRET`, Auth-Vars),
Vorlage `apps/mail/.env.example`.

## Deploy
```bash
# 1) Quelle syncen (kein --delete; Protect-Filter). Siehe die Projektregeln.
rsync -a --filter='P .env' --exclude='.git' --exclude='node_modules' \
  --exclude='.svelte-kit' --exclude='build' ~/saganta/ host:/home/user/docker/saganta/
# 2) Secrets entschlüsseln (deploy.sh): mail-api.env + apps/mail/.env entstehen.
# 3) NUR mail-Services bauen:
ssh host "cd /home/user/docker/saganta/infra && \
  docker compose -f docker-compose.yml -f docker-compose.override.lan.yml up -d --build mail mail-api"
# 4) ⚠️ Dieser Abschnitt beschreibt einen Plan, der nicht umgesetzt wurde:
#    `apps/mail` ist nicht deployt (kein Compose-Dienst `mail`, kein Vhost
#    postfach.*), und die Oberflaeche, die dieses Backend benutzt, ist
#    `apps/post` unter post.<domaene>. Wer hier weiterbaut, klaert zuerst, ob
#    apps/mail wiederbelebt oder entfernt wird (siehe die Projektregeln).
# 5) Auf host committen + nach gitea pushen.
```

## Egress-Pflicht
`mail-api` hängt an `cc-core` und braucht **ausgehend** 993 (IMAP), 465/587 (SMTP).
Fehlt der Egress, füllt sich `MailAccount.last_error` (analog news-api RSS-Egress).
