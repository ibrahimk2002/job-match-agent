def _column_names(temp_db_path, table):
    import sqlite3
    conn = sqlite3.connect(temp_db_path)
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [r[1] for r in rows]
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
