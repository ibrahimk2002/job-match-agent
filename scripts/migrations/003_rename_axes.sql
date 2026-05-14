-- Issue #13: align axis column names with docs/AXIS_MEASURE_SKILL.md
ALTER TABLE job_profiles RENAME COLUMN axis_platform_cloud TO axis_platform;
ALTER TABLE job_profiles RENAME COLUMN axis_product_sense  TO axis_product_ownership;
