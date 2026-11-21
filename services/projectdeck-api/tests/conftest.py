"""Testumgebung, bevor irgendein Testmodul `app` importiert.

test_akte.py importiert `app.nachbarn` vor `tests.test_api`, und damit liest die
Konfiguration den Vorgabepfad `/data/projectdeck.db`, bevor test_api.py seine
Wegwerf-Datenbank setzt. Im Image gibt es `/data`, im Quellbaum (CI) nicht.
"""

import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp(prefix='projectdeck-test-')}/test.db")
os.environ.setdefault("JWT_SECRET", "test-secret")
