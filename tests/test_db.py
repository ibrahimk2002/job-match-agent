import pytest
import os
import sys
import json
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
        assert "jobs" in tables
        assert "job_content" in tables
        assert "match_results" in tables
        assert "user_actions" in tables

    def test_import_jobs_from_jsonl_inserts_rows(self, temp_db, tmp_path):
        """import_jobs_from_jsonl must insert job and job_content rows for each JSONL object."""
        jsonl_file = tmp_path / "jobs.jsonl"
        rows = [
            {
                "job_id": "li-001",
                "url": "https://example.com/1",
                "title": "Engineer",
                "company": "Acme",
                "location": "Remote",
                "posted_date": "2026-01-01",
                "description": "Do stuff",
            },
            {
                "job_id": "li-002",
                "url": "https://example.com/2",
                "title": "SWE",
                "company": "FAANG",
                "location": "NYC",
                "posted_date": "2026-01-02",
                "description": "Build things",
            },
        ]
        jsonl_file.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        inserted = temp_db.import_jobs_from_jsonl(str(jsonl_file))
        assert inserted == 2

        conn = temp_db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jobs")
        assert cursor.fetchone()[0] == 2
        cursor.execute("SELECT COUNT(*) FROM job_content")
        assert cursor.fetchone()[0] == 2
        conn.close()

    def test_import_jobs_from_jsonl_is_idempotent(self, temp_db, tmp_path):
        """Re-importing the same JSONL must not create duplicate rows."""
        jsonl_file = tmp_path / "jobs.jsonl"
        row = {
            "job_id": "li-003",
            "url": "https://example.com/3",
            "title": "Dev",
            "company": "Corp",
            "location": "London",
            "posted_date": None,
            "description": "Some desc",
        }
        jsonl_file.write_text(json.dumps(row) + "\n", encoding="utf-8")
        temp_db.import_jobs_from_jsonl(str(jsonl_file))
        temp_db.import_jobs_from_jsonl(str(jsonl_file))

        conn = temp_db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jobs")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_get_pending_extraction_returns_pending_rows(self, temp_db, tmp_path):
        """get_pending_extraction must return only rows with extraction_status='pending'."""
        jsonl_file = tmp_path / "jobs.jsonl"
        rows = [
            {
                "job_id": "li-010",
                "url": "https://example.com/10",
                "title": "Dev",
                "company": "Corp",
                "location": "Remote",
                "posted_date": None,
                "description": "Has description",
            },
            {
                "job_id": "li-011",
                "url": "https://example.com/11",
                "title": "PM",
                "company": "Corp",
                "location": "Remote",
                "posted_date": None,
                "description": "Has description",
            },
        ]
        jsonl_file.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        temp_db.import_jobs_from_jsonl(str(jsonl_file))

        # Manually mark one as done
        conn = temp_db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE job_content SET extraction_status = 'done' "
            "WHERE job_id = (SELECT id FROM jobs WHERE source_id = 'li-011')"
        )
        conn.commit()
        conn.close()

        pending = temp_db.get_pending_extraction()
        source_ids_in_pending = {row["source_id"] for row in pending}

        assert "li-010" in source_ids_in_pending
        assert "li-011" not in source_ids_in_pending

    def test_save_stage1_result_inserts_row(self, temp_db, tmp_path):
        """save_stage1_result must create a match_results row."""
        jsonl_file = tmp_path / "jobs.jsonl"
        row = {
            "job_id": "li-020",
            "url": "https://example.com/20",
            "title": "Dev",
            "company": "Corp",
            "location": "Remote",
            "posted_date": None,
            "description": "Desc",
        }
        jsonl_file.write_text(json.dumps(row) + "\n", encoding="utf-8")
        temp_db.import_jobs_from_jsonl(str(jsonl_file))

        conn = temp_db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM jobs WHERE source_id = 'li-020'")
        job_id = cursor.fetchone()["id"]
        conn.close()

        temp_db.save_stage1_result(job_id, score=0.85, decision="advance", reasoning="Looks good")

        conn = temp_db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM match_results WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row["stage1_score"] == pytest.approx(0.85)
        assert row["stage1_decision"] == "advance"
        assert row["stage1_reasoning"] == "Looks good"
        assert row["stage2_score"] is None

    def test_save_stage2_result_updates_existing_row(self, temp_db, tmp_path):
        """save_stage2_result must update the existing match_results row."""
        jsonl_file = tmp_path / "jobs.jsonl"
        row = {
            "job_id": "li-021",
            "url": "https://example.com/21",
            "title": "Dev",
            "company": "Corp",
            "location": "Remote",
            "posted_date": None,
            "description": "Desc",
        }
        jsonl_file.write_text(json.dumps(row) + "\n", encoding="utf-8")
        temp_db.import_jobs_from_jsonl(str(jsonl_file))

        conn = temp_db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM jobs WHERE source_id = 'li-021'")
        job_id = cursor.fetchone()["id"]
        conn.close()

        temp_db.save_stage1_result(job_id, score=0.9, decision="advance", reasoning="Stage1 ok")
        temp_db.save_stage2_result(job_id, score=0.75, decision="apply", reasoning="Strong fit")

        conn = temp_db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM match_results WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()

        assert row["stage2_score"] == pytest.approx(0.75)
        assert row["stage2_decision"] == "apply"
        assert row["stage2_reasoning"] == "Strong fit"

