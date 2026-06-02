import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

os.environ.setdefault("OPENAI_API_KEY", "test-sk-dummy")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

_TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://localhost/jobmatch_test"
)


def _drop_all_tables(url: str) -> None:
    import psycopg2

    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DROP TABLE IF EXISTS
                    resume_skills, job_profile_skills, skill_aliases, skills_catalog,
                    match_results, user_actions, user_profiles, users,
                    job_profiles, job_postings, schema_migrations
                CASCADE
                """
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def temp_db(monkeypatch):
    """Yields a Postgres DATABASE_URL with a fresh schema and all migrations applied."""
    import db as db_module

    monkeypatch.setenv("DATABASE_URL", _TEST_DB_URL)
    _drop_all_tables(_TEST_DB_URL)
    db_module.init_db()

    yield _TEST_DB_URL

    _drop_all_tables(_TEST_DB_URL)
