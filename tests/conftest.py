import os
import sys
import sqlite3
import pytest

# src/ and config/ both need to be on the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))
sys.path.insert(0, os.path.join(project_root, "config"))

# Load .env so that os.getenv() calls inside utils/config.py succeed at import time.
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))


@pytest.fixture()
def temp_logs_dir(tmp_path, monkeypatch):
    """Redirect logging.basicConfig so no real log file is created."""
    monkeypatch.setattr("logging.basicConfig", lambda **kwargs: None)
    return tmp_path


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """
    Provide an isolated, file-backed SQLite database in a temp directory.

    Monkeypatches db.get_db_connection so all db functions use the temp file
    instead of 'job_matcher.db' in the working directory.  Returns the db
    module so tests can call its public functions directly.
    """
    import db as db_module

    db_file = str(tmp_path / "test_job_matcher.db")

    def _get_conn():
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    monkeypatch.setattr(db_module, "get_db_connection", _get_conn)
    db_module.init_db()
    return db_module
