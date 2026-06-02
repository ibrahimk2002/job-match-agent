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
