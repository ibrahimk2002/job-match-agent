import pytest
import os
import sys
import sqlite3

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))
sys.path.insert(0, project_root)


class TestDatabase:
    """Validates that the SQLite database initialises and supports CRUD operations."""

    def test_init_db_creates_all_tables(self, temp_db):
        """init_db must create jobs, job_content, match_results, and user_actions tables."""
        conn = temp_db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "jobs" in tables, "Table 'jobs' was not created"
        assert "job_content" in tables, "Table 'job_content' was not created"
        assert "match_results" in tables, "Table 'match_results' was not created"
        assert "user_actions" in tables, "Table 'user_actions' was not created"

    def test_insert_job_returns_integer_id(self, temp_db):
        """insert_job must return an integer primary key."""
        job_id = temp_db.insert_job(
            url="https://example.com/job/1",
            url_hash="abc123",
            company="Acme",
            title="Engineer",
            location="Remote",
        )
        assert isinstance(job_id, int), "insert_job should return an int"
        assert job_id > 0, "Returned job_id must be positive"

    def test_insert_job_row_is_persisted(self, temp_db):
        """A job inserted via insert_job must be queryable from the jobs table."""
        url = "https://example.com/job/2"
        url_hash = "def456"
        temp_db.insert_job(url=url, url_hash=url_hash, company="FAANG", title="SWE", location="NYC")
        conn = temp_db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE url_hash = ?", (url_hash,))
        row = cursor.fetchone()
        conn.close()
        assert row is not None, "Inserted job row not found in database"
        assert row["url"] == url
        assert row["company"] == "FAANG"

    def test_update_job_content_upserts_row(self, temp_db):
        """update_job_content must insert a row that can be read back."""
        job_id = temp_db.insert_job(url="https://example.com/job/3", url_hash="ghi789")
        temp_db.update_job_content(
            job_id=job_id,
            raw_text="Job description text",
            extraction_json='{"title": "Dev"}',
            status="done",
        )
        conn = temp_db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM job_content WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        assert row is not None, "job_content row not found after update_job_content"
        assert row["raw_text"] == "Job description text"
        assert row["scrape_status"] == "done"

    def test_get_pending_jobs_returns_only_pending(self, temp_db):
        """get_pending_jobs must return only rows with scrape_status='pending'."""
        job_id_a = temp_db.insert_job(url="https://example.com/job/4", url_hash="hash-a")
        job_id_b = temp_db.insert_job(url="https://example.com/job/5", url_hash="hash-b")
        temp_db.update_job_content(job_id=job_id_a, raw_text="a", extraction_json="{}", status="pending")
        temp_db.update_job_content(job_id=job_id_b, raw_text="b", extraction_json="{}", status="done")
        pending = temp_db.get_pending_jobs()
        pending_ids = [row["job_id"] for row in pending]
        assert job_id_a in pending_ids, "Pending job should be in get_pending_jobs result"
        assert job_id_b not in pending_ids, "Completed job must not appear in get_pending_jobs"
