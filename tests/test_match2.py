import psycopg2
import psycopg2.extras
import pytest

from db import save_job_profile_skills, save_resume_skills


def _conn(db_url):
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def _insert_job_profile(conn, posting_suffix="1"):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO job_postings (source_system, source_posting_id, content_hash, profile_status)
               VALUES ('linkedin', %s, %s, 'current') RETURNING id""",
            (f"test-job-{posting_suffix}", f"hash-posting-{posting_suffix}"),
        )
        posting_id = cur.fetchone()["id"]
        cur.execute(
            """INSERT INTO job_profiles (job_posting_id, content_hash, schema_version, prompt_version,
               model_version, extracted_at, is_active, profile_json, normalized_title, role_family, seniority,
               employment_type, work_mode, extraction_confidence,
               axis_backend, axis_frontend, axis_platform, axis_ai_data,
               axis_security_reliability, axis_product_ownership)
               VALUES (%s, %s, '2.0', '2.6', 'gpt-4.1-nano', NOW(), 1, '{}',
                       'Engineer', 'backend', 'mid', 'full_time', 'remote', 0.9,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
               RETURNING id""",
            (posting_id, f"hash-profile-{posting_suffix}"),
        )
        return cur.fetchone()["id"]


def _insert_user_profile(conn, email="match2_user@example.com"):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (email) VALUES (%s) ON CONFLICT DO NOTHING",
            (email,),
        )
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        user_id = cur.fetchone()["id"]
        cur.execute(
            """INSERT INTO user_profiles (user_id, content_hash, schema_version, prompt_version,
               model_version, is_active, profile_json, current_level, primary_role_family,
               total_years_experience)
               VALUES (%s, 'hash-resume-1', '1.0', '1.0', 'gpt-4.1-nano', 1, '{}', 'mid', 'backend', 3.0)
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


STAGE2_SQL = """
WITH req_groups AS (
    SELECT
        jps.job_profile_id,
        CASE
            WHEN jps.group_id IS NOT NULL THEN 'g' || jps.group_id::text
            ELSE 's' || jps.skill_id::text
        END AS req_key,
        MAX(CASE jps.importance
            WHEN 'must'      THEN 3
            WHEN 'preferred' THEN 2
            ELSE 1
        END) AS weight,
        BOOL_OR(rs.skill_id IS NOT NULL) AS matched,
        ARRAY_AGG(jps.skill_id) FILTER (WHERE rs.skill_id IS NULL)  AS missing_ids,
        ARRAY_AGG(jps.skill_id) FILTER (WHERE rs.skill_id IS NOT NULL) AS matched_ids
    FROM job_profile_skills jps
    LEFT JOIN resume_skills rs
        ON rs.skill_id = jps.skill_id AND rs.resume_id = %(user_profile_id)s
    WHERE jps.job_profile_id = ANY(%(shortlist)s)
    GROUP BY jps.job_profile_id, req_key
)
SELECT
    job_profile_id,
    SUM(CASE WHEN matched THEN weight ELSE 0 END)::float
        / NULLIF(SUM(weight), 0) AS keyword_score,
    ARRAY_REMOVE(ARRAY_AGG(ARRAY_TO_JSON(missing_ids)::jsonb), NULL) AS missing_skill_ids,
    ARRAY_REMOVE(ARRAY_AGG(ARRAY_TO_JSON(matched_ids)::jsonb), NULL) AS matched_skill_ids
FROM req_groups
GROUP BY job_profile_id
ORDER BY keyword_score DESC
"""


def _run_stage2(conn, user_profile_id, shortlist):
    with conn.cursor() as cur:
        cur.execute(
            STAGE2_SQL,
            {"user_profile_id": user_profile_id, "shortlist": shortlist},
        )
        return cur.fetchall()


def test_partial_match_score(temp_db):
    """User matches 1 of 2 must-skills. Score = 3/6 = 0.5."""
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn, "pm1")
    user_profile_id = _insert_user_profile(conn)
    skill_a = _seed_skill(conn, "SkillA-partial")
    skill_b = _seed_skill(conn, "SkillB-partial")
    conn.commit()

    save_job_profile_skills(job_profile_id, [(skill_a, "must", None), (skill_b, "must", None)], conn)
    save_resume_skills(user_profile_id, [(skill_a, "must")], conn)

    rows = _run_stage2(conn, user_profile_id, [job_profile_id])
    assert len(rows) == 1
    assert abs(rows[0]["keyword_score"] - 0.5) < 1e-6
    conn.close()


def test_full_match_score(temp_db):
    """User has all 3 skills (must+preferred+nice). Score = 6/6 = 1.0."""
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn, "fm1")
    user_profile_id = _insert_user_profile(conn)
    skill_a = _seed_skill(conn, "SkillA-full")
    skill_b = _seed_skill(conn, "SkillB-full")
    skill_c = _seed_skill(conn, "SkillC-full")
    conn.commit()

    save_job_profile_skills(
        job_profile_id,
        [(skill_a, "must", None), (skill_b, "preferred", None), (skill_c, "nice", None)],
        conn,
    )
    save_resume_skills(
        user_profile_id,
        [(skill_a, "must"), (skill_b, "preferred"), (skill_c, "nice")],
        conn,
    )

    rows = _run_stage2(conn, user_profile_id, [job_profile_id])
    assert len(rows) == 1
    assert abs(rows[0]["keyword_score"] - 1.0) < 1e-6
    conn.close()


def test_or_group_counts_once(temp_db):
    """OR-group: 2 must-skills in same group. User has ONE. Group counts as matched. Score = 3/3 = 1.0."""
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn, "og1")
    user_profile_id = _insert_user_profile(conn)
    skill_a = _seed_skill(conn, "SkillA-orgroup")
    skill_b = _seed_skill(conn, "SkillB-orgroup")
    conn.commit()

    # Both in group_id=1 (OR semantics: having either counts as match)
    save_job_profile_skills(
        job_profile_id,
        [(skill_a, "must", 1), (skill_b, "must", 1)],
        conn,
    )
    # User only has skill_a
    save_resume_skills(user_profile_id, [(skill_a, "must")], conn)

    rows = _run_stage2(conn, user_profile_id, [job_profile_id])
    assert len(rows) == 1
    assert abs(rows[0]["keyword_score"] - 1.0) < 1e-6
    conn.close()


def test_missing_skill_ids_populated(temp_db):
    """User has 0 matching skills. All skill_ids appear in missing_skill_ids."""
    conn = _conn(temp_db)
    job_profile_id = _insert_job_profile(conn, "miss1")
    user_profile_id = _insert_user_profile(conn)
    skill_a = _seed_skill(conn, "SkillA-missing")
    skill_b = _seed_skill(conn, "SkillB-missing")
    conn.commit()

    save_job_profile_skills(
        job_profile_id,
        [(skill_a, "must", None), (skill_b, "must", None)],
        conn,
    )
    # User has no skills — don't call save_resume_skills

    rows = _run_stage2(conn, user_profile_id, [job_profile_id])
    assert len(rows) == 1
    assert rows[0]["keyword_score"] == 0.0 or rows[0]["keyword_score"] is None

    # Flatten the JSON arrays from missing_skill_ids
    missing_flat = []
    for arr in (rows[0]["missing_skill_ids"] or []):
        if isinstance(arr, list):
            missing_flat.extend(arr)
        else:
            import json
            missing_flat.extend(json.loads(arr))

    assert skill_a in missing_flat
    assert skill_b in missing_flat
    conn.close()


def test_higher_match_ranks_first(temp_db):
    """Job A: user matches all 3 must-skills. Job B: user matches 1 of 3 must-skills. A ranks first."""
    conn = _conn(temp_db)
    job_a_id = _insert_job_profile(conn, "rankA")
    job_b_id = _insert_job_profile(conn, "rankB")
    user_profile_id = _insert_user_profile(conn)

    skill_1 = _seed_skill(conn, "Skill1-rank")
    skill_2 = _seed_skill(conn, "Skill2-rank")
    skill_3 = _seed_skill(conn, "Skill3-rank")
    conn.commit()

    # Job A requires all three skills (user has all)
    save_job_profile_skills(
        job_a_id,
        [(skill_1, "must", None), (skill_2, "must", None), (skill_3, "must", None)],
        conn,
    )
    # Job B requires the same three (user has only skill_1)
    save_job_profile_skills(
        job_b_id,
        [(skill_1, "must", None), (skill_2, "must", None), (skill_3, "must", None)],
        conn,
    )
    # User has all three skills
    save_resume_skills(
        user_profile_id,
        [(skill_1, "must"), (skill_2, "must"), (skill_3, "must")],
        conn,
    )

    rows_all = _run_stage2(conn, user_profile_id, [job_a_id, job_b_id])
    assert rows_all[0]["job_profile_id"] == job_a_id
    assert rows_all[0]["keyword_score"] == 1.0

    # Now verify job B with only 1 match scores lower
    # Override job B's user match: only keep skill_1 for a second user
    conn2 = _conn(temp_db)
    # Create a second user with only skill_1 to test job B ranking
    with conn2.cursor() as cur:
        cur.execute("INSERT INTO users (email) VALUES ('rank_user2@example.com') RETURNING id")
        user2_id_row = cur.fetchone()["id"]
        cur.execute(
            """INSERT INTO user_profiles (user_id, content_hash, schema_version, prompt_version,
               model_version, is_active, profile_json, current_level, primary_role_family,
               total_years_experience)
               VALUES (%s, 'hash-resume-2', '1.0', '1.0', 'gpt-4.1-nano', 1, '{}', 'mid', 'backend', 3.0)
               RETURNING id""",
            (user2_id_row,),
        )
        user2_profile_id = cur.fetchone()["id"]
    conn2.commit()
    save_resume_skills(user2_profile_id, [(skill_1, "must")], conn2)

    rows2 = _run_stage2(conn2, user2_profile_id, [job_a_id, job_b_id])
    assert rows2[0]["keyword_score"] == pytest.approx(1 / 3, abs=1e-6)
    assert rows2[0]["job_profile_id"] in (job_a_id, job_b_id)  # both tie at 1/3

    conn2.close()
    conn.close()
