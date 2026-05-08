CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT NOT NULL UNIQUE,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                   INTEGER NOT NULL REFERENCES users(id),
    content_hash              TEXT NOT NULL,
    schema_version            TEXT NOT NULL,
    prompt_version            TEXT NOT NULL,
    model_version             TEXT NOT NULL,
    is_active                 INTEGER NOT NULL DEFAULT 1,
    invalidated_reason        TEXT,
    profile_json              TEXT NOT NULL,

    -- identity
    full_name                 TEXT,
    total_years_experience    REAL,
    current_level             TEXT,
    primary_role_family       TEXT,

    -- capability axes
    axis_backend              REAL,
    axis_frontend             REAL,
    axis_platform             REAL,
    axis_ai_data              REAL,
    axis_security_reliability REAL,
    axis_product_ownership    REAL,
    axis_fullstack_span       REAL,

    -- top skills (JSON arrays as TEXT)
    skills_languages          TEXT,
    skills_frameworks         TEXT,
    skills_cloud              TEXT,

    -- preferences
    desired_role_families     TEXT,
    desired_seniority         TEXT,
    desired_work_modes        TEXT,
    desired_locations         TEXT,
    desired_salary_min        INTEGER,
    desired_salary_max        INTEGER,
    desired_salary_currency   TEXT,

    -- work eligibility
    work_auth_canada          INTEGER,
    work_auth_us              INTEGER,
    sponsorship_needed        INTEGER,

    -- education
    degree_level              INTEGER,

    created_at                TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_profiles_active
    ON user_profiles(user_id) WHERE is_active = 1;
