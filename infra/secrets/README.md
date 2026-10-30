# Secrets

Klartext-`.env` gehört **nie** ins Repo. Stattdessen:

1. Klartext-Datei lokal anlegen (z. B. `./.env.dev`).
2. Mit SOPS verschlüsseln: `sops -e --age <recipient> .env.dev > vault/.env.dev.enc`.
3. Nur `vault/*.enc` einchecken.

Der age-Empfänger-Key liegt auf host unter `~/.config/sops/age/keys.txt`.
`scripts/deploy.sh` entschlüsselt automatisch beim Deploy.

Beispiel-Schlüssel-Set: siehe `.env.example`.
