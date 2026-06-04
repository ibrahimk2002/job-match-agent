import psycopg2
import psycopg2.extras
import pytest
from unittest.mock import patch, MagicMock

from db import save_job_profile_skills
from skills import canonicalize
from models.skills import JobSkillScanResult, SkillEntry


def _conn(db_url):
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def _insert_job_profile(conn):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO job_postings (source_system, source_posting_id, content_hash, profile_status)
               VALUES ('linkedin', 'test-job-1', 'hash1', 'current') RETURNING id"""
        )
        posting_id = cur.fetchone()["id"]
        cur.execute(
            """INSERT INTO job_profiles (job_posting_id, content_hash, schema_version, prompt_version,
               model_version, extracted_at, is_active, profile_json, normalized_title, role_family, seniority,
               employment_type, work_mode, extraction_confidence,
               axis_backend, axis_frontend, axis_platform, axis_ai_data,
               axis_security_reliability, axis_product_ownership)
               VALUES (%s, 'hash1', '2.0', '2.6', 'gpt-4.1-nano', NOW(), 1, '{}',
                       'Engineer', 'backend', 'mid', 'full_time', 'remote', 0.9,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
               RETURNING id""",
            (posting_id,),
        )
        return cur.fetchone()["id"]


def _seed_skill(conn, canonical):
    """Insert a skill into skills_catalog and return its id."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO skills_catalog (canonical, category, source)
               VALUES (%s, 'hard', 'curated')
               ON CONFLICT (canonical) DO UPDATE SET canonical = EXCLUDED.canonical
               RETURNING id""",
            (canonical,),
        )
        return cur.fetchone()["id"]


def _count_job_skills(conn, job_profile_id):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM job_profile_skills WHERE job_profile_id = %s",
            (job_profile_id,),
        )
        return cur.fetchone()["cnt"]


def test_save_job_profile_skills_basic(temp_db):
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn)
    conn.commit()

    skill_a = _seed_skill(conn, "Python-test-basic-a")
    skill_b = _seed_skill(conn, "Docker-test-basic-b")
    skill_c = _seed_skill(conn, "Kubernetes-test-basic-c")
    conn.commit()

    entries = [
        (skill_a, "must", None),
        (skill_b, "preferred", None),
        (skill_c, "nice", 1),
    ]
    save_job_profile_skills(job_profile_id, entries, conn)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT skill_id, importance, group_id FROM job_profile_skills WHERE job_profile_id = %s ORDER BY skill_id",
            (job_profile_id,),
        )
        rows = cur.fetchall()

    assert len(rows) == 3
    importances = {row["skill_id"]: row["importance"] for row in rows}
    group_ids = {row["skill_id"]: row["group_id"] for row in rows}
    assert importances[skill_a] == "must"
    assert importances[skill_b] == "preferred"
    assert importances[skill_c] == "nice"
    assert group_ids[skill_c] == 1

    conn.close()


def test_save_job_profile_skills_idempotent(temp_db):
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn)
    conn.commit()

    skill_a = _seed_skill(conn, "Python-test-idem-a")
    skill_b = _seed_skill(conn, "Docker-test-idem-b")
    skill_c = _seed_skill(conn, "Go-test-idem-c")
    conn.commit()

    entries = [
        (skill_a, "must", None),
        (skill_b, "preferred", None),
        (skill_c, "nice", None),
    ]

    save_job_profile_skills(job_profile_id, entries, conn)
    save_job_profile_skills(job_profile_id, entries, conn)

    assert _count_job_skills(conn, job_profile_id) == 3
    conn.close()


def test_save_job_profile_skills_or_group(temp_db):
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn)
    conn.commit()

    skill_a = _seed_skill(conn, "Python-test-orgroup-a")
    skill_b = _seed_skill(conn, "Java-test-orgroup-b")
    skill_c = _seed_skill(conn, "Go-test-orgroup-c")
    conn.commit()

    entries = [
        (skill_a, "must", 1),
        (skill_b, "must", 1),
        (skill_c, "preferred", None),
    ]
    save_job_profile_skills(job_profile_id, entries, conn)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT skill_id, group_id FROM job_profile_skills WHERE job_profile_id = %s ORDER BY skill_id",
            (job_profile_id,),
        )
        rows = cur.fetchall()

    assert len(rows) == 3
    group_map = {row["skill_id"]: row["group_id"] for row in rows}
    assert group_map[skill_a] == 1
    assert group_map[skill_b] == 1
    assert group_map[skill_c] is None

    conn.close()


def test_populate_job_skills_calls_scan_and_saves(temp_db):
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn)
    conn.commit()

    mock_result = JobSkillScanResult(skills=[
        SkillEntry(skill="Python", importance="must", group_id=None),
        SkillEntry(skill="Docker", importance="preferred", group_id=None),
    ])
    mock_usage = MagicMock()

    with patch("pipeline.skills_scan.scan_job_skills", return_value=(mock_result, mock_usage)):
        from pipeline.skills_scan import populate_job_skills
        populate_job_skills(job_profile_id, "some job text", "{}", conn)

    assert _count_job_skills(conn, job_profile_id) == 2
    conn.close()


def test_populate_job_skills_nonfatal_on_error(temp_db):
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn)
    conn.commit()

    with patch("pipeline.skills_scan.scan_job_skills", side_effect=Exception("api error")):
        from pipeline.skills_scan import populate_job_skills
        populate_job_skills(job_profile_id, "some job text", "{}", conn)

    assert _count_job_skills(conn, job_profile_id) == 0
    conn.close()


def test_auto_insert_unknown_skill(temp_db):
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn)
    conn.commit()

    skill_id = canonicalize("some-brand-new-skill-xyz", conn)
    conn.commit()

    entries = [(skill_id, "must", None)]
    save_job_profile_skills(job_profile_id, entries, conn)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT canonical, source FROM skills_catalog WHERE id = %s",
            (skill_id,),
        )
        row = cur.fetchone()

    assert row["canonical"] == "some-brand-new-skill-xyz"
    assert row["source"] == "auto"

    assert _count_job_skills(conn, job_profile_id) == 1
    conn.close()
