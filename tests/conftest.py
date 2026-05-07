import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# Order matters: ROOT comes first (for `from config.job_profile import ...`),
# then src/ (for `import db`). No name collisions between the two.
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


@pytest.fixture
def temp_db(monkeypatch):
    """Yields a path to a fresh SQLite DB with all migrations applied."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    import db as db_module
    monkeypatch.setattr(db_module, "_DB_PATH", path)
    db_module.init_db()

    yield path

    try:
        os.remove(path)
    except OSError:
        pass
