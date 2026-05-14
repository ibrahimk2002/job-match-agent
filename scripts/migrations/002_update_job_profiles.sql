-- 1. Remove role_subtype
ALTER TABLE job_profiles DROP COLUMN role_subtype;

-- 2. work_auth_required: backfill NULLs to 0 (No)
--    SQLite cannot ALTER a column's DEFAULT/NOT NULL; enforcement is handled in profile_columns.py.
UPDATE job_profiles SET work_auth_required = 0 WHERE work_auth_required IS NULL;

-- 3. Rename axis columns
ALTER TABLE job_profiles RENAME COLUMN axis_platform      TO axis_platform_cloud;
ALTER TABLE job_profiles RENAME COLUMN axis_ownership     TO axis_security_reliability;
ALTER TABLE job_profiles RENAME COLUMN axis_collaboration TO axis_product_sense;

-- 4. Add new axis column (DEFAULT 0.0 satisfies NOT NULL for existing rows)
ALTER TABLE job_profiles ADD COLUMN axis_fullstack_span REAL NOT NULL DEFAULT 0.0;
