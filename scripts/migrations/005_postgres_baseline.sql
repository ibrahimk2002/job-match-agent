CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS job_postings (
    id                       SERIAL PRIMARY KEY,
    source_system            TEXT NOT NULL,
    source_posting_id        TEXT NOT NULL,
    source_url               TEXT,
    title_raw                TEXT,
    company_raw              TEXT,
    location_raw             TEXT,
    posted_date_raw          TEXT,
    source_file              TEXT,
    source_batch             TEXT,
    source_metadata_json     TEXT,
    cleaned_description_text TEXT,
    raw_description_text     TEXT,
    content_hash             TEXT,
    first_seen_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    imported_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_content_changed_at  TIMESTAMPTZ,
    profile_status           TEXT NOT NULL DEFAULT 'missing',
    last_profile_attempt_at  TIMESTAMPTZ,
    last_profile_error       TEXT,
    is_deleted_at_source     INTEGER NOT NULL DEFAULT 0,
    UNIQUE (source_system, source_posting_id)
);

CREATE TABLE IF NOT EXISTS job_profiles (
    id                        SERIAL PRIMARY KEY,
    job_posting_id            INTEGER NOT NULL,
    content_hash              TEXT NOT NULL,
    schema_version            TEXT NOT NULL,
    prompt_version            TEXT NOT NULL,
    model_version             TEXT NOT NULL,
    extracted_at              TIMESTAMPTZ NOT NULL,
    extraction_confidence     REAL NOT NULL DEFAULT 0.5,
    is_active                 INTEGER NOT NULL DEFAULT 0,
    invalidated_at            TIMESTAMPTZ,
    invalidated_reason        TEXT,
    profile_json              TEXT NOT NULL,
    normalized_title          TEXT NOT NULL,
    role_family               TEXT NOT NULL,
    seniority                 TEXT NOT NULL,
    employment_type           TEXT NOT NULL,
    work_mode                 TEXT NOT NULL,
    location_scope            TEXT,
    work_auth_required        INTEGER,
    sponsorship_available     INTEGER,
    degree_required           INTEGER,
    years_min_soft            INTEGER,
    years_min_hard            INTEGER,
    salary_min                INTEGER,
    salary_max                INTEGER,
    salary_currency           TEXT,
    salary_period             TEXT,
    salary_tier               INTEGER,
    axis_backend              REAL NOT NULL,
    axis_frontend             REAL NOT NULL,
    axis_platform             REAL NOT NULL,
    axis_ai_data              REAL NOT NULL,
    axis_security_reliability REAL NOT NULL,
    axis_product_ownership    REAL NOT NULL,
    axis_fullstack_span       REAL NOT NULL DEFAULT 0.0,
    FOREIGN KEY (job_posting_id) REFERENCES job_postings(id),
    UNIQUE (job_posting_id, content_hash, schema_version, prompt_version, model_version)
);

CREATE TABLE IF NOT EXISTS match_results (
    id               SERIAL PRIMARY KEY,
    job_posting_id   INTEGER NOT NULL UNIQUE,
    job_profile_id   INTEGER,
    stage1_score     REAL,
    stage1_decision  TEXT,
    stage1_reasoning TEXT,
    stage2_score     REAL,
    stage2_decision  TEXT,
    stage2_reasoning TEXT,
    FOREIGN KEY (job_posting_id) REFERENCES job_postings(id),
    FOREIGN KEY (job_profile_id) REFERENCES job_profiles(id)
);

CREATE TABLE IF NOT EXISTS user_actions (
    id             SERIAL PRIMARY KEY,
    job_posting_id INTEGER NOT NULL,
    status         TEXT,
    notes          TEXT,
    updated_at     TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (job_posting_id) REFERENCES job_postings(id)
);

CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,
    email      TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id                        SERIAL PRIMARY KEY,
    user_id                   INTEGER NOT NULL REFERENCES users(id),
    content_hash              TEXT NOT NULL,
    schema_version            TEXT NOT NULL,
    prompt_version            TEXT NOT NULL,
    model_version             TEXT NOT NULL,
    is_active                 INTEGER NOT NULL DEFAULT 1,
    invalidated_at            TIMESTAMPTZ,
    invalidated_reason        TEXT,
    profile_json              TEXT NOT NULL,
    full_name                 TEXT,
    total_years_experience    REAL,
    current_level             TEXT,
    primary_role_family       TEXT,
    axis_backend              REAL,
    axis_frontend             REAL,
    axis_platform             REAL,
    axis_ai_data              REAL,
    axis_security_reliability REAL,
    axis_product_ownership    REAL,
    axis_fullstack_span       REAL,
    skills_languages          TEXT,
    skills_frameworks         TEXT,
    skills_cloud              TEXT,
    desired_role_families     TEXT,
    desired_seniority         TEXT,
    desired_work_modes        TEXT,
    desired_locations         TEXT,
    desired_salary_min        INTEGER,
    desired_salary_max        INTEGER,
    desired_salary_currency   TEXT,
    work_auth_canada          INTEGER,
    work_auth_us              INTEGER,
    sponsorship_needed        INTEGER,
    degree_level              INTEGER,
    created_at                TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_postings_status ON job_postings(profile_status);
CREATE INDEX IF NOT EXISTS idx_job_postings_content_hash ON job_postings(content_hash);
CREATE INDEX IF NOT EXISTS idx_job_profiles_lookup ON job_profiles(job_posting_id, is_active);
CREATE INDEX IF NOT EXISTS idx_job_profiles_filters ON job_profiles(role_family, seniority, work_mode, employment_type);
CREATE UNIQUE INDEX IF NOT EXISTS ux_job_profiles_active ON job_profiles(job_posting_id) WHERE is_active = 1;
CREATE UNIQUE INDEX IF NOT EXISTS ux_user_profiles_active ON user_profiles(user_id) WHERE is_active = 1;
