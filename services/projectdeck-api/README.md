# projectdeck-api

Projekte, Aufgaben, Meilensteine, Reviews, Wochenfokus und das Deadline-Center.
Alle Urteile entstehen aus Regeln (`rules.py`, `deadline_risk.py`); der
LLM-Layer formuliert sie nur und ist abschaltbar.

## Der KI-Layer ist aus, und so wird er richtig eingeschaltet

`LLM_ENABLED=false` ist der Auslieferungszustand. Wer ihn einschaltet, braucht
**drei** Werte, nicht zwei:

| Variable | Wert | Warum |
|---|---|---|
| `LLM_ENABLED` | `true` | Ohne die anderen beiden bleibt der Layer trotzdem aus |
| `LLM_BASE_URL` | `http://192.0.2.10:8128/v1` | der `llm-gateway`, nicht ein llama.cpp direkt |
| `LLM_MODEL` | ein Gateway-Alias, z. B. `homelab-smart` | kein Dateiname eines Modells |
| `LLM_API_KEY` | der Key dieses Dienstes am Gateway | ohne ihn antwortet der Gateway 401 |

⚠️⚠️ **Auf dieser Installation stehen in `.env` zwei überholte Werte**
(gemessen 2026-10-16):

```
LLM_BASE_URL=http://192.0.2.10:8081     # llama.cpp direkt, am Gateway vorbei
LLM_MODEL=gemma-3-4b                      # dort läuft seit dem 2026-08-28 Qwen3.5-4B
```

Beides ist heute folgenlos, weil `LLM_ENABLED=false`. Es ist aber eine Mine für
den Tag des Einschaltens, und zwar eine leise:

- Der **Modellname** wird von llama.cpp **nicht geprüft**. Der Aufruf würde also
  gelingen und das Ergebnis unter einem Modell verbucht, das auf dem Wirt gar
  nicht liegt. Das ist derselbe Etikettenschwindel, der im Haus schon beim Alias
  `node2-gemma` dokumentiert ist.
- Die **Adresse** umgeht den `llm-gateway` und damit Budget, Key-Store und
  Fallback-Kette. Die Hausregel verlangt den Gateway.

Behebung, Handgriff (`.env` fasse ich nicht an):

```bash
cd /home/user/docker/saganta
sed -i 's|^LLM_BASE_URL=.*|LLM_BASE_URL=http://192.0.2.10:8128/v1|' \
       services/projectdeck-api/.env
sed -i 's|^LLM_MODEL=.*|LLM_MODEL=homelab-smart|' services/projectdeck-api/.env
echo 'LLM_API_KEY=<key dieses Dienstes>' >> services/projectdeck-api/.env
```

Der Key muss am Gateway angelegt sein und **jedes Glied der Fallback-Kette
des Alias erlauben**, sonst existiert der Notausgang nur auf dem Papier:
`llm-gateway/provision-keys.sh --abgleich`.

Danach neu erstellen (COPY-Image, ein Neustart genügt nicht):

```bash
cd infra && docker compose -f docker-compose.yml \
  -f docker-compose.override.lan.yml up -d --build --force-recreate projectdeck-api
```

## Tests

```bash
bash ../../scripts/tests-im-image.sh projectdeck-api
```

Es gibt keine CI. Was das Skript tut und warum es nötig ist, steht in seinem
eigenen Kopf.
