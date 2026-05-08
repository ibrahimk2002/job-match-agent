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
        "model_version", "is_active", "invalidated_reason", "profile_json",
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
