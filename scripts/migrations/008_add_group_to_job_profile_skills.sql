ALTER TABLE job_profile_skills ADD COLUMN IF NOT EXISTS group_id INTEGER;
ALTER TABLE resume_skills       ADD COLUMN IF NOT EXISTS importance TEXT
    CHECK (importance IN ('must', 'preferred', 'nice'));
