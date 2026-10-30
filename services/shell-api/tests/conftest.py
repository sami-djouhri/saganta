"""Test-Setup: sichere JWT-Secrets setzen, BEVOR app.config die Settings baut.

app.config instanziiert `settings = Settings()` beim Import und bricht bei
unsicheren Default-Secrets ab (Fail-Fast). Die Env-Variablen müssen daher vor
dem ersten Import eines app-Moduls stehen: conftest wird vor den Testmodulen
geladen, deshalb passt das hier.
"""

import os

os.environ.setdefault("JWT_SECRET", "test-secret-not-a-default")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
# Owner-Gate im Test offen lassen, außer ein Test setzt allowed_subs explizit.
os.environ.setdefault("ALLOWED_SUBS", "")
