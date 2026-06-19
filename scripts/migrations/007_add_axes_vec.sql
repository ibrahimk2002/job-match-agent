ALTER TABLE job_profiles ADD COLUMN IF NOT EXISTS axes_vec vector(6);
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS axes_vec vector(6);

UPDATE job_profiles
SET axes_vec = ARRAY[
    COALESCE(axis_backend, 0.0),
    COALESCE(axis_frontend, 0.0),
    COALESCE(axis_platform, 0.0),
    COALESCE(axis_ai_data, 0.0),
    COALESCE(axis_security_reliability, 0.0),
    COALESCE(axis_product_ownership, 0.0)
]::vector
WHERE axes_vec IS NULL;

UPDATE user_profiles
SET axes_vec = ARRAY[
    COALESCE(axis_backend, 0.0),
    COALESCE(axis_frontend, 0.0),
    COALESCE(axis_platform, 0.0),
    COALESCE(axis_ai_data, 0.0),
    COALESCE(axis_security_reliability, 0.0),
    COALESCE(axis_product_ownership, 0.0)
]::vector
WHERE axes_vec IS NULL;

CREATE INDEX IF NOT EXISTS idx_job_profiles_axes_vec_hnsw
    ON job_profiles USING hnsw (axes_vec vector_cosine_ops)
    WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS idx_user_profiles_axes_vec_hnsw
    ON user_profiles USING hnsw (axes_vec vector_cosine_ops)
    WHERE is_active = 1;
