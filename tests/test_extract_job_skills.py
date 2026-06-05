import psycopg2
import psycopg2.extras
import pytest
from unittest.mock import patch, MagicMock

from db import save_job_profile_skills, save_resume_skills
from skills import canonicalize
from models.skills import JobSkillScanResult, ResumeScanResult, SkillEntry
from pipeline.skills_scan import _dedup_job_entries, _dedup_resume_entries


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


# --- Dedup unit tests (no DB needed) ---

def test_dedup_job_keeps_highest_importance():
    """Same skill_id twice: must wins over nice."""
    entries = [(1, "nice", None), (1, "must", None), (2, "preferred", None)]
    result = _dedup_job_entries(entries)
    by_id = {sid: (imp, gid) for sid, imp, gid in result}
    assert by_id[1] == ("must", None)
    assert by_id[2] == ("preferred", None)
    assert len(result) == 2


def test_dedup_job_preserves_group_id_from_winner():
    """group_id comes from whichever entry had the higher importance."""
    entries = [(5, "preferred", 3), (5, "must", None)]
    result = _dedup_job_entries(entries)
    assert len(result) == 1
    sid, imp, gid = result[0]
    assert imp == "must"
    assert gid is None


def test_dedup_resume_keeps_highest_importance():
    """Resume dedup: must beats preferred beats nice."""
    entries = [(10, "nice"), (10, "preferred"), (10, "must")]
    result = _dedup_resume_entries(entries)
    assert len(result) == 1
    assert result[0] == (10, "must")


# --- Integration: alias collision (JavaScript / Node.js → same skill_id) ---

def test_populate_deduplicates_aliased_skills(temp_db):
    """LLM returns 'PostgreSQL' (must) and 'postgres' (nice). Both canonicalize to
    the same skill_id via the 'postgres' alias. Only one row must be saved, with
    importance=must."""
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn)
    conn.commit()

    mock_result = JobSkillScanResult(skills=[
        SkillEntry(skill="PostgreSQL", importance="must", group_id=None),
        SkillEntry(skill="postgres", importance="nice", group_id=None),
    ])
    mock_usage = MagicMock()

    with patch("pipeline.skills_scan.scan_job_skills", return_value=(mock_result, mock_usage)):
        from pipeline.skills_scan import populate_job_skills
        populate_job_skills(job_profile_id, "some job text", "{}", conn)

    assert _count_job_skills(conn, job_profile_id) == 1

    with conn.cursor() as cur:
        cur.execute(
            "SELECT importance FROM job_profile_skills WHERE job_profile_id = %s",
            (job_profile_id,),
        )
        row = cur.fetchone()
    assert row["importance"] == "must"
    conn.close()


def test_nodejs_is_distinct_from_javascript(temp_db):
    """After migration 009, Node.js is its own canonical skill.
    A JD requiring both JavaScript and Node.js stores two separate rows."""
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn)
    conn.commit()

    mock_result = JobSkillScanResult(skills=[
        SkillEntry(skill="JavaScript", importance="must", group_id=None),
        SkillEntry(skill="Node.js", importance="preferred", group_id=None),
    ])
    mock_usage = MagicMock()

    with patch("pipeline.skills_scan.scan_job_skills", return_value=(mock_result, mock_usage)):
        from pipeline.skills_scan import populate_job_skills
        populate_job_skills(job_profile_id, "some job text", "{}", conn)

    assert _count_job_skills(conn, job_profile_id) == 2

    with conn.cursor() as cur:
        cur.execute(
            """SELECT sc.canonical, jps.importance
               FROM job_profile_skills jps
               JOIN skills_catalog sc ON sc.id = jps.skill_id
               WHERE jps.job_profile_id = %s
               ORDER BY sc.canonical""",
            (job_profile_id,),
        )
        rows = {r["canonical"]: r["importance"] for r in cur.fetchall()}

    assert rows.get("JavaScript") == "must"
    assert rows.get("Node.js") == "preferred"
    conn.close()


def test_populate_filters_empty_skill_strings(temp_db):
    """LLM returns an entry with an empty/whitespace skill string; it must be dropped."""
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn)
    conn.commit()

    mock_result = JobSkillScanResult(skills=[
        SkillEntry(skill="Python", importance="must", group_id=None),
        SkillEntry(skill="   ", importance="nice", group_id=None),
    ])
    mock_usage = MagicMock()

    with patch("pipeline.skills_scan.scan_job_skills", return_value=(mock_result, mock_usage)):
        from pipeline.skills_scan import populate_job_skills
        populate_job_skills(job_profile_id, "some job text", "{}", conn)

    assert _count_job_skills(conn, job_profile_id) == 1
    conn.close()


def test_populate_handles_empty_skills_list_nonfatal(temp_db):
    """LLM returns an empty skills array; function logs and returns without error."""
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn)
    conn.commit()

    mock_result = JobSkillScanResult(skills=[])
    mock_usage = MagicMock()

    with patch("pipeline.skills_scan.scan_job_skills", return_value=(mock_result, mock_usage)):
        from pipeline.skills_scan import populate_job_skills
        populate_job_skills(job_profile_id, "some job text", "{}", conn)

    assert _count_job_skills(conn, job_profile_id) == 0
    conn.close()


def test_save_job_profile_skills_on_conflict_upserts(temp_db):
    """Calling save_job_profile_skills twice with different importance on same
    (job_profile_id, skill_id) must not raise; second call wins via ON CONFLICT."""
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn)
    skill_a = _seed_skill(conn, "ConflictSkill-upsert")
    conn.commit()

    save_job_profile_skills(job_profile_id, [(skill_a, "nice", None)], conn)
    conn.commit()
    save_job_profile_skills(job_profile_id, [(skill_a, "must", None)], conn)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT importance FROM job_profile_skills WHERE job_profile_id=%s AND skill_id=%s",
            (job_profile_id, skill_a),
        )
        row = cur.fetchone()
    assert row["importance"] == "must"
    conn.close()
