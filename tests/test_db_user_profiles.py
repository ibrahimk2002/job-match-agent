def _column_names(db_path, table):
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [r[1] for r in rows]
    finally:
        conn.close()


def test_users_table_exists(temp_db):
    cols = _column_names(temp_db, "users")
    assert "id" in cols
    assert "email" in cols
    assert "created_at" in cols


def test_user_profiles_table_exists(temp_db):
    cols = _column_names(temp_db, "user_profiles")
    expected = [
        "id", "user_id", "content_hash", "schema_version", "prompt_version",
        "model_version", "is_active", "invalidated_at", "invalidated_reason", "profile_json",
        "full_name", "total_years_experience", "current_level", "primary_role_family",
        "axis_backend", "axis_frontend", "axis_platform", "axis_ai_data",
        "axis_security_reliability", "axis_product_ownership", "axis_fullstack_span",
        "skills_languages", "skills_frameworks", "skills_cloud",
        "desired_role_families", "desired_seniority", "desired_work_modes",
        "desired_locations", "desired_salary_min", "desired_salary_max",
        "desired_salary_currency", "work_auth_canada", "work_auth_us",
        "sponsorship_needed", "degree_level", "created_at",
    ]
    for col in expected:
        assert col in cols, f"missing column: {col}"


def _make_user_profile():
    """Reusable minimal UserProfile for DB tests."""
    from config.user_profile import (
        UserProfile, ResumeSkills,
        ResumeEducation, CareerPreferences, ResumeWorkAuth,
    )
    from config.job_profile import ProfileMeta, Axes
    return UserProfile(
        meta=ProfileMeta(
            schema_version="1.0", prompt_version="1.0",
            model="gpt-4.1-nano", generated_at="2026-05-07T00:00:00+00:00",
        ),
        full_name="Test User",
        total_years_experience=2.0,
        current_level="junior",
        primary_role_family="backend",
        axes=Axes(
            axis_backend=0.5, axis_frontend=0.1, axis_platform=0.2,
            axis_ai_data=0.1, axis_security_reliability=0.2, axis_product_ownership=0.1,
        ),
        skills=ResumeSkills(
            languages=["Python"], frameworks=[], cloud=[], databases=[],
            devops=[], ai_ml=[], other_tools=[], concepts=[],
        ),
        work_experience=[],
        education=ResumeEducation(degree_level=1, fields=["CS"]),
        preferences=CareerPreferences(
            desired_roles=[], desired_role_families=["backend"],
            desired_seniority="mid", desired_work_modes=["remote"],
            desired_locations=[], desired_salary_min=None,
            desired_salary_max=None, desired_salary_currency="CAD",
        ),
        work_auth=ResumeWorkAuth(canada=True, us=False, sponsorship_needed=None),
        extraction_confidence=0.8,
        evidence_snippets=[],
    )


def test_get_or_create_user_idempotent(temp_db):
    import db
    user_id_1 = db.get_or_create_user("alice@example.com")
    user_id_2 = db.get_or_create_user("alice@example.com")
    assert isinstance(user_id_1, int)
    assert user_id_1 == user_id_2


def test_get_or_create_user_different_emails(temp_db):
    import db
    id_a = db.get_or_create_user("alice@example.com")
    id_b = db.get_or_create_user("bob@example.com")
    assert id_a != id_b


def test_get_active_user_profile_returns_none_when_empty(temp_db):
    import db
    user_id = db.get_or_create_user("alice@example.com")
    result = db.get_active_user_profile(user_id)
    assert result is None


def test_save_resume_extraction_stores_row(temp_db):
    import db
    import sqlite3
    from user_profile_columns import build_profile_columns

    user_id = db.get_or_create_user("alice@example.com")
    profile = _make_user_profile()
    db.save_resume_extraction(user_id, profile, build_profile_columns(profile), content_hash="abc123")

    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ? AND is_active = 1", (user_id,)
        ).fetchone()
        assert row is not None
        assert row["current_level"] == "junior"
        assert row["content_hash"] == "abc123"
        assert row["is_active"] == 1
    finally:
        conn.close()


def test_get_active_user_profile_returns_row_after_save(temp_db):
    import db
    from user_profile_columns import build_profile_columns

    user_id = db.get_or_create_user("alice@example.com")
    profile = _make_user_profile()
    db.save_resume_extraction(user_id, profile, build_profile_columns(profile), content_hash="abc123")

    result = db.get_active_user_profile(user_id)
    assert result is not None
    assert result["content_hash"] == "abc123"


def test_versioning_supersedes_old_row(temp_db):
    import db
    import sqlite3
    from user_profile_columns import build_profile_columns

    user_id = db.get_or_create_user("alice@example.com")
    profile = _make_user_profile()

    db.save_resume_extraction(user_id, profile, build_profile_columns(profile), content_hash="hash_v1")
    db.save_resume_extraction(user_id, profile, build_profile_columns(profile), content_hash="hash_v2")

    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)).fetchall()
        assert len(rows) == 2
        active = [r for r in rows if r["is_active"] == 1]
        inactive = [r for r in rows if r["is_active"] == 0]
        assert len(active) == 1
        assert len(inactive) == 1
        assert inactive[0]["invalidated_reason"] == "superseded"
        assert active[0]["content_hash"] == "hash_v2"
    finally:
        conn.close()


def test_unique_index_prevents_two_active_profiles(temp_db):
    import sqlite3
    import pytest

    conn = sqlite3.connect(temp_db)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("INSERT INTO users (email) VALUES ('test@example.com')")
        user_id = conn.execute(
            "SELECT id FROM users WHERE email = 'test@example.com'"
        ).fetchone()[0]

        conn.execute(
            """INSERT INTO user_profiles
               (user_id, content_hash, schema_version, prompt_version, model_version, is_active, profile_json)
               VALUES (?, 'h1', '1.0', '1.0', 'model', 1, '{}')""",
            (user_id,),
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO user_profiles
                   (user_id, content_hash, schema_version, prompt_version, model_version, is_active, profile_json)
                   VALUES (?, 'h2', '1.0', '1.0', 'model', 1, '{}')""",
                (user_id,),
            )
            conn.commit()
    finally:
        conn.close()
