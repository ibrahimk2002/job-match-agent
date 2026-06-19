-- Switch axes_vec HNSW indexes from cosine ops to L2 ops.
-- L2 distance captures both direction and magnitude, unlike cosine which
-- measures direction only.
DROP INDEX IF EXISTS idx_job_profiles_axes_vec_hnsw;
DROP INDEX IF EXISTS idx_user_profiles_axes_vec_hnsw;

CREATE INDEX IF NOT EXISTS idx_job_profiles_axes_vec_l2
    ON job_profiles USING hnsw (axes_vec vector_l2_ops)
    WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS idx_user_profiles_axes_vec_l2
    ON user_profiles USING hnsw (axes_vec vector_l2_ops)
    WHERE is_active = 1;
