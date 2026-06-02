-- 006_skills_catalog.sql
-- Skills controlled vocabulary and junction tables.
-- Seed data is added later in this file (see below).

CREATE TABLE IF NOT EXISTS skills_catalog (
    id        SERIAL PRIMARY KEY,
    canonical TEXT NOT NULL UNIQUE,
    category  TEXT NOT NULL CHECK (category IN ('hard', 'soft', 'other')),
    source    TEXT NOT NULL DEFAULT 'curated' CHECK (source IN ('auto', 'curated'))
);

CREATE TABLE IF NOT EXISTS skill_aliases (
    alias    TEXT PRIMARY KEY,
    skill_id INTEGER NOT NULL REFERENCES skills_catalog(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS job_profile_skills (
    job_profile_id INTEGER NOT NULL REFERENCES job_profiles(id) ON DELETE CASCADE,
    skill_id       INTEGER NOT NULL REFERENCES skills_catalog(id) ON DELETE CASCADE,
    importance     TEXT NOT NULL CHECK (importance IN ('must', 'preferred', 'nice')),
    PRIMARY KEY (job_profile_id, skill_id)
);

CREATE TABLE IF NOT EXISTS resume_skills (
    resume_id INTEGER NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    skill_id  INTEGER NOT NULL REFERENCES skills_catalog(id) ON DELETE CASCADE,
    PRIMARY KEY (resume_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_job_profile_skills_skill ON job_profile_skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_resume_skills_skill ON resume_skills(skill_id);
