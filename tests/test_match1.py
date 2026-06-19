import pytest
from pipeline.match1 import _l2_similarity, run_stage1_naive, timed


def test_l2_similarity_identical_vectors():
    v = [0.9, 0.1, 0.5, 0.2, 0.6, 0.4]
    assert _l2_similarity(v, v) == pytest.approx(1.0, abs=1e-6)


def test_l2_similarity_zero_distance_means_perfect_match():
    a = [0.5, 0.3, 0.1, 0.0, 0.2, 0.4]
    assert _l2_similarity(a, a) == pytest.approx(1.0, abs=1e-6)


def test_l2_similarity_different_magnitude_same_direction_not_equal():
    # Unlike cosine, L2 distinguishes [0.9,...] from [0.3,...] even if proportional
    a = [0.9, 0.0, 0.0, 0.0, 0.0, 0.0]
    b = [0.3, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert _l2_similarity(a, b) < 1.0


def test_l2_similarity_decreases_as_vectors_diverge():
    base = [0.8, 0.1, 0.3, 0.2, 0.4, 0.1]
    close = [0.7, 0.1, 0.3, 0.2, 0.4, 0.1]
    far   = [0.1, 0.9, 0.0, 0.0, 0.0, 0.0]
    assert _l2_similarity(base, close) > _l2_similarity(base, far)


def test_l2_similarity_always_positive():
    a = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    b = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    assert _l2_similarity(a, b) > 0.0


def test_timed_returns_correct_result():
    result, _ = timed(lambda x: x * 2, 21)
    assert result == 42


def test_timed_elapsed_is_non_negative():
    _, elapsed = timed(lambda: None)
    assert elapsed >= 0.0


def _insert_job(cur, jp_id: int, content_hash: str, title: str, role: str, seniority: str, axes: tuple):
    cur.execute(
        """
        INSERT INTO job_profiles
            (job_posting_id, content_hash, schema_version, prompt_version, model_version,
             extracted_at, profile_json, normalized_title, role_family, seniority,
             employment_type, work_mode, is_active,
             axis_backend, axis_frontend, axis_platform, axis_ai_data,
             axis_security_reliability, axis_product_ownership, axis_fullstack_span)
        VALUES (%s, %s, '2.0', '2.0', 'test', NOW(), '{}', %s, %s, %s,
                'full_time', 'remote', 1, %s, %s, %s, %s, %s, %s, 0.10)
        """,
        (jp_id, content_hash, title, role, seniority) + axes,
    )


def test_naive_ranks_closer_vector_first(temp_db):
    import os
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO job_postings (source_system, source_posting_id, content_hash, profile_status) "
        "VALUES ('t','j1','h1','current'),('t','j2','h2','current') RETURNING id"
    )
    rows = cur.fetchall()
    jp1_id, jp2_id = rows[0]["id"], rows[1]["id"]

    # Job 1: backend-heavy — close to user axes
    _insert_job(cur, jp1_id, "h1", "Backend SWE", "backend", "senior",
                (0.90, 0.05, 0.30, 0.10, 0.40, 0.20))
    # Job 2: frontend-heavy — far from user axes
    _insert_job(cur, jp2_id, "h2", "Frontend SWE", "frontend", "junior",
                (0.05, 0.90, 0.10, 0.05, 0.10, 0.30))
    conn.commit()
    cur.close()
    conn.close()

    user_axes = [0.85, 0.05, 0.25, 0.10, 0.40, 0.20]
    results = run_stage1_naive(user_axes, preferred_role=None, preferred_seniority=None, limit=5)

    assert len(results) == 2
    assert results[0]["normalized_title"] == "Backend SWE"
    assert results[0]["match_score"] > results[1]["match_score"]


def test_naive_applies_role_bonus(temp_db):
    import os
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO job_postings (source_system, source_posting_id, content_hash, profile_status) "
        "VALUES ('t','x1','hx1','current'),('t','x2','hx2','current') RETURNING id"
    )
    rows = cur.fetchall()
    jp1_id, jp2_id = rows[0]["id"], rows[1]["id"]

    # Both jobs have identical axes — role bonus is the only differentiator
    axes = (0.60, 0.20, 0.30, 0.15, 0.35, 0.25)
    _insert_job(cur, jp1_id, "hx1", "Job Backend", "backend", "mid", axes)
    _insert_job(cur, jp2_id, "hx2", "Job Frontend", "frontend", "mid", axes)
    conn.commit()
    cur.close()
    conn.close()

    user_axes = list(axes)
    results = run_stage1_naive(user_axes, preferred_role="backend", preferred_seniority=None, limit=5)

    assert results[0]["role_family"] == "backend"
    assert results[0]["match_score"] - results[1]["match_score"] == pytest.approx(0.10, abs=1e-4)
