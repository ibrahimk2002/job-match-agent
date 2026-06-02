def _column_names(db_url, table):
    import psycopg2
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                (table,),
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def test_axis_columns_use_canonical_names(temp_db):
    cols = _column_names(temp_db, "job_profiles")
    assert "axis_platform" in cols
    assert "axis_product_ownership" in cols
    assert "axis_platform_cloud" not in cols
    assert "axis_product_sense" not in cols


def test_axis_fullstack_span_column_still_exists(temp_db):
    cols = _column_names(temp_db, "job_profiles")
    assert "axis_fullstack_span" in cols


def test_skills_catalog_tables_exist(temp_db):
    tables = ['skills_catalog', 'skill_aliases', 'job_profile_skills', 'resume_skills']
    for table in tables:
        cols = _column_names(temp_db, table)
        assert len(cols) > 0, f"Table {table!r} not found or has no columns"

def test_skills_catalog_columns(temp_db):
    cols = _column_names(temp_db, 'skills_catalog')
    assert 'id' in cols
    assert 'canonical' in cols
    assert 'category' in cols
    assert 'source' in cols

def test_job_profile_skills_columns(temp_db):
    cols = _column_names(temp_db, 'job_profile_skills')
    assert 'job_profile_id' in cols
    assert 'skill_id' in cols
    assert 'importance' in cols

def test_resume_skills_columns(temp_db):
    cols = _column_names(temp_db, 'resume_skills')
    assert 'resume_id' in cols
    assert 'skill_id' in cols
