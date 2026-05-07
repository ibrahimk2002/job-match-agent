CREATE TABLE IF NOT EXISTS job_postings (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
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
    first_seen_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    imported_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_content_changed_at  DATETIME,
    profile_status           TEXT NOT NULL DEFAULT 'missing',
    last_profile_attempt_at  DATETIME,
    last_profile_error       TEXT,
    is_deleted_at_source     INTEGER NOT NULL DEFAULT 0,
    UNIQUE (source_system, source_posting_id)
);

CREATE TABLE IF NOT EXISTS job_profiles (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    job_posting_id          INTEGER NOT NULL,
    content_hash            TEXT NOT NULL,
    schema_version          TEXT NOT NULL,
    prompt_version          TEXT NOT NULL,
    model_version           TEXT NOT NULL,
    extracted_at            DATETIME NOT NULL,
    extraction_confidence   REAL NOT NULL DEFAULT 0.5,
    is_active               INTEGER NOT NULL DEFAULT 0,
    invalidated_at          DATETIME,
    invalidated_reason      TEXT,
    profile_json            TEXT NOT NULL,
    normalized_title        TEXT NOT NULL,
    role_family             TEXT NOT NULL,
    role_subtype            TEXT,
    seniority               TEXT NOT NULL,
    employment_type         TEXT NOT NULL,
    work_mode               TEXT NOT NULL,
    location_scope          TEXT,
    work_auth_required      INTEGER,
    sponsorship_available   INTEGER,
    degree_required         INTEGER,
    years_min_soft          INTEGER,
    years_min_hard          INTEGER,
    salary_min              INTEGER,
    salary_max              INTEGER,
    salary_currency         TEXT,
    salary_period           TEXT,
    salary_tier             INTEGER,
    axis_backend            REAL NOT NULL,
    axis_frontend           REAL NOT NULL,
    axis_platform           REAL NOT NULL,
    axis_ai_data            REAL NOT NULL,
    axis_ownership          REAL NOT NULL,
    axis_collaboration      REAL NOT NULL,
    eligible_countries_json TEXT,
    eligible_regions_json   TEXT,
    FOREIGN KEY (job_posting_id) REFERENCES job_postings(id),
    UNIQUE (job_posting_id, content_hash, schema_version, prompt_version, model_version)
);

CREATE TABLE IF NOT EXISTS match_results (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    job_posting_id INTEGER NOT NULL,
    status         TEXT,
    notes          TEXT,
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_posting_id) REFERENCES job_postings(id)
);

CREATE INDEX IF NOT EXISTS idx_job_postings_status ON job_postings(profile_status);
CREATE INDEX IF NOT EXISTS idx_job_postings_content_hash ON job_postings(content_hash);
CREATE INDEX IF NOT EXISTS idx_job_profiles_lookup ON job_profiles(job_posting_id, is_active);
CREATE INDEX IF NOT EXISTS idx_job_profiles_filters ON job_profiles(role_family, seniority, work_mode, employment_type);
CREATE UNIQUE INDEX IF NOT EXISTS ux_job_profiles_active ON job_profiles(job_posting_id) WHERE is_active = 1;
