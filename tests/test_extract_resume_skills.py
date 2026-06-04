import psycopg2
import psycopg2.extras
import pytest
from unittest.mock import patch, MagicMock

from db import save_resume_skills
from models.skills import ResumeScanResult, SkillEntry


def _conn(db_url):
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def _insert_user_profile(conn):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (email) VALUES ('test@example.com') ON CONFLICT DO NOTHING"
        )
        cur.execute("SELECT id FROM users WHERE email = 'test@example.com'")
        user_id = cur.fetchone()["id"]
        cur.execute(
            """INSERT INTO user_profiles (user_id, content_hash, schema_version, prompt_version,
               model_version, is_active, profile_json, current_level, primary_role_family,
               total_years_experience)
               VALUES (%s, 'hash1', '1.0', '1.0', 'gpt-4.1-nano', 1, '{}', 'mid', 'backend', 3.0)
               RETURNING id""",
            (user_id,),
        )
        return cur.fetchone()["id"]


def _seed_skill(conn, canonical):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO skills_catalog (canonical, category, source)
               VALUES (%s, 'hard', 'curated')
               ON CONFLICT (canonical) DO UPDATE SET canonical = EXCLUDED.canonical
               RETURNING id""",
            (canonical,),
        )
        return cur.fetchone()["id"]


def _count_resume_skills(conn, user_profile_id):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM resume_skills WHERE resume_id = %s",
            (user_profile_id,),
        )
        return cur.fetchone()["cnt"]


def test_save_resume_skills_basic(temp_db):
    conn = _conn(temp_db)
    user_profile_id = _insert_user_profile(conn)
    conn.commit()

    skill_a = _seed_skill(conn, "Python-resume-basic-a")
    skill_b = _seed_skill(conn, "Docker-resume-basic-b")
    skill_c = _seed_skill(conn, "Kubernetes-resume-basic-c")
    conn.commit()

    entries = [
        (skill_a, "must"),
        (skill_b, "preferred"),
        (skill_c, "nice"),
    ]
    save_resume_skills(user_profile_id, entries, conn)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT skill_id, importance FROM resume_skills WHERE resume_id = %s ORDER BY skill_id",
            (user_profile_id,),
        )
        rows = cur.fetchall()

    assert len(rows) == 3
    importances = {row["skill_id"]: row["importance"] for row in rows}
    assert importances[skill_a] == "must"
    assert importances[skill_b] == "preferred"
    assert importances[skill_c] == "nice"

    conn.close()


def test_save_resume_skills_idempotent(temp_db):
    conn = _conn(temp_db)
    user_profile_id = _insert_user_profile(conn)
    conn.commit()

    skill_a = _seed_skill(conn, "Python-resume-idem-a")
    skill_b = _seed_skill(conn, "Go-resume-idem-b")
    skill_c = _seed_skill(conn, "Rust-resume-idem-c")
    conn.commit()

    entries = [
        (skill_a, "must"),
        (skill_b, "preferred"),
        (skill_c, "nice"),
    ]

    save_resume_skills(user_profile_id, entries, conn)
    save_resume_skills(user_profile_id, entries, conn)

    assert _count_resume_skills(conn, user_profile_id) == 3
    conn.close()


def test_populate_resume_skills_calls_scan_and_saves(temp_db):
    conn = _conn(temp_db)
    user_profile_id = _insert_user_profile(conn)
    conn.commit()

    mock_result = ResumeScanResult(skills=[
        SkillEntry(skill="Python", importance="must", group_id=None),
        SkillEntry(skill="Docker", importance="preferred", group_id=None),
    ])
    mock_usage = MagicMock()

    with patch("pipeline.skills_scan.scan_resume_skills", return_value=(mock_result, mock_usage)):
        from pipeline.skills_scan import populate_resume_skills
        populate_resume_skills(user_profile_id, "some resume text", "{}", conn)

    assert _count_resume_skills(conn, user_profile_id) == 2
    conn.close()


def test_populate_resume_skills_nonfatal_on_error(temp_db):
    conn = _conn(temp_db)
    user_profile_id = _insert_user_profile(conn)
    conn.commit()

    with patch("pipeline.skills_scan.scan_resume_skills", side_effect=Exception("api error")):
        from pipeline.skills_scan import populate_resume_skills
        populate_resume_skills(user_profile_id, "some resume text", "{}", conn)

    assert _count_resume_skills(conn, user_profile_id) == 0
    conn.close()
